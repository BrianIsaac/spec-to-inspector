"""Tests for the page of figures written from a bench record."""

from spec_to_inspector.bench.readme import render_readme, summary_lines
from spec_to_inspector.bench.record import BenchRecord, compare


def test_the_page_gives_each_figure_with_its_count_its_n_and_its_interval(
    record: BenchRecord,
) -> None:
    """The deck's table: strict, per part, lenient, per region, referred, false rejects."""
    page = render_readme(record)

    assert page.startswith("# Stage I: what the laptop prototype measured\n")
    assert (
        "| Clause-citation accuracy, strict, single-defect images | 66.7% (2 of 3) | 3 "
        "| 20.8% to 93.9% |" in page
    )
    assert (
        "| Clause-citation accuracy, strict, single-defect images, pcb4 only | 50.0% (1 of 2) | 2 |"
        in page
    )
    assert "| Clause-citation accuracy, lenient, multi-defect images | 0.0% (0 of 1) | 1 |" in page
    assert "| Good boards rejected (false rejects) | 0.0% (0 of 3) | 3 | 0.0% to 56.1% |" in page
    assert "| Good boards flagged by the anomaly model | 33.3% (1 of 3) | 3 |" in page
    assert record.measured_on in page
    assert "`spec-to-inspector bench`" in page


def test_the_page_says_how_the_run_was_made_and_that_nothing_leaked(record: BenchRecord) -> None:
    """The protocol by digest, the server's setting, cold asking, the empty store."""
    page = render_readme(record)

    assert f"(SHA-256 `{record.protocol.sha256[:16]}`)" in page
    assert "image minimum 1024 tokens; GPU Fake GPU; up to 3 areas an image" in page
    assert "Every question asked cold (`cache_prompt` false)" in page
    assert "0 of 7 decisions had a correction in a prompt" in page
    assert "4 anomalous test images: 3 single-defect, 1 multi-defect" in page
    assert "**This is a partial run**" not in page


def test_the_confusion_table_has_a_row_for_each_expected_type(record: BenchRecord) -> None:
    """Columns in the mapping table's order, then why there is no citation."""
    page = render_readme(record)

    assert "pcb4, single-defect images:" in page
    assert "| Expected \\ cited | scratch | not flagged | Images |" in page
    assert "| **missing** | 0 | 1 | 1 |" in page
    assert "| **scratch** | 1 | 0 | 1 |" in page
    assert "| **dirt** | 0 | 1 | 1 |" in page


def test_causes_times_minutes_and_memory_are_on_the_page(record: BenchRecord) -> None:
    """Each of the protocol's remaining figures has its lines."""
    page = render_readme(record)

    assert "By cause: no clause applies 1." in page
    assert "By cause: outside every zone 1." in page
    assert "- Row of the clause table applied: 4.1 1, 5.6.1 1." in page
    assert (
        "| all | 3 | 33.3% (1 of 3) | 0.0% (0 of 3), 0.0% to 56.1% | 33.3% (1 of 3) "
        "| 0.0% (0 of 3) |" in page
    )
    assert "4 flagged images, 5 areas asked (1.25 an image)" in page
    assert "| pcb4 |" in page
    assert "| 720 s |" in page
    assert "| Judging | 8,700 MiB (the VLM server) | 10,000 MiB | 10,000 MiB |" in page
    assert "| Anomaly model scoring, pcb1 | 1,300 MiB (the bench's process) |" in page
    assert "Training pcb1 peaked at 8,192 MiB allocated" in page


def test_a_single_run_says_so_and_a_repeat_says_what_differed(record: BenchRecord) -> None:
    """Without an earlier run there is nothing to compare; with one, the counts are given."""
    assert "This file holds one run." in render_readme(record)

    repeated = record.model_copy(update={"repeat": compare(record, record)})
    page = render_readme(repeated)
    assert "4 images answered on region 1 in both runs: 0 with another heading cited" in page
    assert "Every counted figure of the protocol is equal in the two runs." in page
    assert summary_lines(repeated)[-1].endswith("the figures are equal")


def test_a_partial_run_is_marked_as_not_for_the_deck(record: BenchRecord) -> None:
    """A trial run's page cannot be mistaken for the protocol's figures."""
    page = render_readme(record.model_copy(update={"partial": True, "limit": 5}))
    assert "**This is a partial run** (4 labelled images, the first 5 of each kind per part" in page
    assert summary_lines(record.model_copy(update={"partial": True}))[0].startswith("Partial run")


def test_the_other_image_setting_stands_beside_the_shipped_one(record: BenchRecord) -> None:
    """The comparison declared in the protocol is a table of the two settings."""
    judge = record.judge.model_copy(update={"image_min_tokens": "the model's own minimum"})
    page = render_readme(record, beside=record.model_copy(update={"judge": judge}))

    assert "## The other image setting" in page
    assert (
        "| Figure | Image minimum 1024 (this page) | Image minimum the model's own minimum |"
        in page
    )
    assert "| Strict, single-defect images | 66.7% (2 of 3) | 66.7% (2 of 3) |" in page
    assert "## The other image setting" not in render_readme(record)


def test_the_terminal_summary_is_the_three_accuracies_and_the_false_rejects(
    record: BenchRecord,
) -> None:
    """A few lines, each with its N and interval."""
    lines = summary_lines(record)
    assert lines[0] == (
        "Clause-citation accuracy, strict, 3 single-defect images: 66.7% (2 of 3), "
        "95% interval 20.8% to 93.9%"
    )
    assert lines[1].startswith("Lenient, 1 multi-defect images: 0.0% (0 of 1)")
    assert lines[3].startswith("Good boards rejected: 0.0% (0 of 3)")
    assert lines[4] == "Corrections in a prompt: 0 of 7 decisions"
