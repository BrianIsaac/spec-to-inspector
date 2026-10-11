"""Tests for the specification the console holds: uploaded, parsed, kept and reloaded."""

import threading
from pathlib import Path

import pytest

from spec_to_inspector.app.specs import SpecError, SpecStore
from spec_to_inspector.spec.extract import SpecificationError
from spec_to_inspector.spec.pdf import PdfError
from spec_to_inspector.spec.schema import Specification, write_clause_table
from tests.spec.spec_fakes import specification

PDF = b"%PDF-1.7\nfake body\n%%EOF\n"


class Recording:
    """A parser that answers with a fixed specification or error and records what it was given."""

    def __init__(self, result: Specification | Exception) -> None:
        """Set the answer.

        Args:
            result: The specification to return, or the error to raise.
        """
        self.result = result
        self.seen: list[bytes] = []

    def __call__(self, path: Path) -> Specification:
        """Read the file as the real parser would, then answer.

        Args:
            path: The uploaded PDF, where the store put it.

        Returns:
            The fixed specification.
        """
        self.seen.append(path.read_bytes())
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def test_a_new_console_holds_no_specification(tmp_path: Path) -> None:
    """Before anything is uploaded there is nothing in force."""
    store = SpecStore(tmp_path / "state", parser=Recording(specification()))

    assert store.current() is None


def test_an_uploaded_pdf_is_parsed_and_becomes_the_specification_in_force(tmp_path: Path) -> None:
    """The upload is given to the parser as a file, and its clauses are then in force."""
    parser = Recording(specification())
    store = SpecStore(tmp_path / "state", parser=parser)

    loaded = store.install("customer spec.pdf", PDF)

    assert parser.seen == [PDF]
    assert loaded.specification == specification()
    assert loaded.source == "customer spec.pdf"
    assert loaded.parse_seconds is not None
    assert loaded.pdf is not None
    assert loaded.pdf.read_bytes() == PDF
    assert store.current() == loaded


def test_an_uploaded_specification_is_still_in_force_after_a_restart(tmp_path: Path) -> None:
    """The PDF, its clause table and where it came from are kept in the state directory."""
    first = SpecStore(tmp_path / "state", parser=Recording(specification()))
    loaded = first.install("customer.pdf", PDF)

    again = SpecStore(tmp_path / "state", parser=Recording(RuntimeError("not called")))

    assert again.current() == loaded


@pytest.mark.parametrize(
    ("filename", "data", "words"),
    [
        ("", b"", "no file was chosen"),
        ("empty.pdf", b"", "is empty"),
        ("notes.txt", b"plain text, not a document", "is not a PDF"),
    ],
)
def test_an_upload_that_is_not_a_pdf_is_refused_before_parsing(
    tmp_path: Path, filename: str, data: bytes, words: str
) -> None:
    """Nothing, an empty file and a file of another kind never reach the parser."""
    parser = Recording(specification())
    store = SpecStore(tmp_path / "state", parser=parser)

    with pytest.raises(SpecError, match=words):
        store.install(filename, data)

    assert parser.seen == []
    assert store.current() is None


@pytest.mark.parametrize(
    "error",
    [
        PdfError("docling could not convert the file: no pages"),
        SpecificationError("the document has no numbered clause"),
    ],
)
def test_a_pdf_that_does_not_parse_leaves_the_earlier_specification_in_force(
    tmp_path: Path, error: Exception
) -> None:
    """The parser's own message is passed on, and what was in force stays in force."""
    store = SpecStore(tmp_path / "state", parser=Recording(specification()))
    kept = store.install("good.pdf", PDF)
    store.parser = Recording(error)

    with pytest.raises(SpecError, match=str(error)):
        store.install("bad.pdf", PDF + b"more")

    assert store.current() == kept
    assert kept.pdf is not None
    assert kept.pdf.read_bytes() == PDF
    assert sorted(path.name for path in (tmp_path / "state").iterdir()) == [
        "specification.clauses.json",
        "specification.json",
        "specification.pdf",
    ]


def test_a_clause_table_given_at_start_is_in_force_with_the_pdf_beside_it(tmp_path: Path) -> None:
    """`--spec` names a table `parse` wrote; the PDF of the same name is shown with it."""
    table = tmp_path / "pcb.clauses.json"
    write_clause_table(specification(), table)
    (tmp_path / "pcb.pdf").write_bytes(PDF)

    store = SpecStore(tmp_path / "state", parser=Recording(specification()), initial=table)
    loaded = store.current()

    assert loaded is not None
    assert loaded.specification == specification()
    assert loaded.pdf == tmp_path / "pcb.pdf"
    assert loaded.source == str(table)
    assert loaded.parse_seconds is None


def test_a_clause_table_given_at_start_wins_over_an_earlier_upload(tmp_path: Path) -> None:
    """What the operator names on the command line is what the console starts with."""
    SpecStore(tmp_path / "state", parser=Recording(specification())).install("old.pdf", PDF)
    other = specification(title="Another specification")
    table = tmp_path / "other.clauses.json"
    write_clause_table(other, table)

    store = SpecStore(tmp_path / "state", parser=Recording(specification()), initial=table)
    loaded = store.current()

    assert loaded is not None
    assert loaded.specification.title == "Another specification"
    assert loaded.pdf is None


def test_a_clause_table_that_cannot_be_read_stops_the_console_in_words(tmp_path: Path) -> None:
    """A mistyped `--spec` is an error at start, not an empty page later."""
    with pytest.raises(SpecError, match=r"absent\.clauses\.json"):
        SpecStore(
            tmp_path / "state",
            parser=Recording(specification()),
            initial=tmp_path / "absent.clauses.json",
        )


def test_a_page_is_not_held_up_by_a_parse_in_progress(tmp_path: Path) -> None:
    """While an upload is being parsed, the specification in force can still be read."""
    started = threading.Event()
    release = threading.Event()

    def slow(path: Path) -> Specification:
        started.set()
        assert release.wait(timeout=10)
        return specification(title="The new one")

    store = SpecStore(tmp_path / "state", parser=Recording(specification()))
    kept = store.install("first.pdf", PDF)
    store.parser = slow
    upload = threading.Thread(target=store.install, args=("second.pdf", PDF))
    upload.start()
    try:
        assert started.wait(timeout=10)
        seen: list[object] = []
        reader = threading.Thread(target=lambda: seen.append(store.current()))
        reader.start()
        reader.join(timeout=2)
        assert seen == [kept], "reading the specification waited for the parse"
    finally:
        release.set()
        upload.join(timeout=10)
    loaded = store.current()
    assert loaded is not None
    assert loaded.specification.title == "The new one"


def test_an_upload_that_cannot_be_kept_leaves_the_earlier_one_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the disk fails while the new files are written, the old ones are still the old ones."""
    store = SpecStore(tmp_path / "state", parser=Recording(specification()))
    kept = store.install("first.pdf", PDF)
    store.parser = Recording(specification(title="The new one"))

    def fail(*_: object, **__: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr("spec_to_inspector.app.specs.write_clause_table", fail)
    with pytest.raises(SpecError, match="No space left on device"):
        store.install("second.pdf", PDF + b"more")
    monkeypatch.undo()

    assert store.current() == kept
    again = SpecStore(tmp_path / "state", parser=Recording(specification()))
    assert again.current() == kept
    assert sorted(path.name for path in (tmp_path / "state").iterdir()) == [
        "specification.clauses.json",
        "specification.json",
        "specification.pdf",
    ]
