"""Tests for streaming, keeping and verifying the VisA PCB categories."""

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from spec_to_inspector.datasets.visa import (
    MANIFEST_NAME,
    PUBLISHED_COUNTS,
    SPLIT_DIR,
    VISA_TAR_BYTES,
    FetchResult,
    Manifest,
    VisaFetchError,
    VisaVerificationError,
    count_category,
    fetch_visa,
    stream_through_tar,
    tree_digest,
    verify,
)
from tests.datasets.visa_fakes import (
    ETAG,
    EXPECTED,
    NO_WAIT,
    URL,
    FakeServer,
    fake_files,
    make_tar,
    write_tree,
)


def _refuse(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"no request expected, got {request.method} {request.url}")


def _fetch(dest: Path, server: FakeServer | None, **kwargs: object) -> FetchResult:
    transport = server.transport() if server else httpx.MockTransport(_refuse)
    body_bytes = len(server.body) if server else None
    options: dict[str, object] = {
        "url": URL,
        "expected": EXPECTED,
        "expected_bytes": body_bytes,
        "transport": transport,
        "retry_delays": NO_WAIT,
        **kwargs,
    }
    return fetch_visa(dest, **options)  # pyright: ignore[reportArgumentType]


# The published table


def test_the_published_counts_are_the_plans_section_3_5() -> None:
    """The constants carry Amazon's published counts and the plan's defect-type table."""
    rows = {
        name: (c.normal, c.anomalous, c.train_normal, c.test_normal, c.test_anomalous)
        for name, c in PUBLISHED_COUNTS.items()
    }
    assert rows == {
        "pcb1": (1004, 100, 904, 100, 100),
        "pcb2": (1001, 100, 901, 100, 100),
        "pcb3": (1006, 100, 905, 101, 100),
        "pcb4": (1005, 100, 904, 101, 100),
    }
    assert {n: c.multi_defect for n, c in PUBLISHED_COUNTS.items()} == {
        "pcb1": 9,
        "pcb2": 9,
        "pcb3": 7,
        "pcb4": 56,
    }
    assert PUBLISHED_COUNTS["pcb4"].defect_types == {
        "dirt": 42,
        "missing": 33,
        "extra": 30,
        "damage": 21,
        "scratch": 17,
        "wrong place": 13,
        "burnt": 8,
    }
    assert PUBLISHED_COUNTS["pcb1"].defect_types == {
        "melt": 54,
        "scratch": 21,
        "missing": 20,
        "bent": 15,
    }
    assert VISA_TAR_BYTES == 1_929_840_640


# Counting and verifying a tree on disk


def test_count_category_reads_files_annotations_and_split(tmp_path: Path) -> None:
    """Counts come from the image folders, image_anno.csv and split_csv/1cls.csv."""
    write_tree(tmp_path, fake_files())

    assert count_category(tmp_path, "pcb1") == EXPECTED["pcb1"]
    assert count_category(tmp_path, "pcb4") == EXPECTED["pcb4"]


def test_verify_returns_the_counts_when_they_match(tmp_path: Path) -> None:
    """A tree that matches the expected table verifies."""
    write_tree(tmp_path, {k: v for k, v in fake_files().items() if not k.startswith("candle/")})

    assert verify(tmp_path, EXPECTED) == dict(EXPECTED)


def test_verify_names_every_difference(tmp_path: Path) -> None:
    """A missing image and a relabelled defect are both reported, by category and field."""
    files = fake_files()
    del files["pcb1/Data/Images/Normal/0000.JPG"]
    write_tree(tmp_path, files)
    anno = tmp_path / "pcb4/image_anno.csv"
    anno.write_text(anno.read_text().replace(",burnt,", ",scorch,"))

    with pytest.raises(VisaVerificationError) as caught:
        verify(tmp_path, EXPECTED)

    message = "\n".join(caught.value.differences)
    assert "pcb1: normal is 4, expected 5" in message
    assert "pcb1/Data/Images/Normal/0000.JPG" in message
    assert "pcb4: defect_types" in message
    assert "scorch" in message


def test_verify_refuses_a_missing_category(tmp_path: Path) -> None:
    """A category that is not on disk is a difference, not a crash."""
    files = {k: v for k, v in fake_files().items() if not k.startswith("pcb4/")}
    write_tree(tmp_path, files)

    with pytest.raises(VisaVerificationError, match="pcb4"):
        verify(tmp_path, EXPECTED)


def test_verify_refuses_links_in_the_tree(tmp_path: Path) -> None:
    """Only regular files and directories are expected; a symbolic link is refused."""
    write_tree(tmp_path, fake_files())
    (tmp_path / "pcb1/Data/Images/Normal/link.JPG").symlink_to("/etc/hostname")

    with pytest.raises(VisaVerificationError, match="not a regular file"):
        verify(tmp_path, EXPECTED)


def test_tree_digest_covers_names_and_contents_of_kept_members_only(tmp_path: Path) -> None:
    """The digest changes with any kept byte or name, and ignores what lives beside them."""
    write_tree(tmp_path, fake_files())
    members = ("pcb1", "pcb4", SPLIT_DIR)
    first = tree_digest(tmp_path, members)

    (tmp_path / "visa_pytorch").mkdir()
    (tmp_path / "visa_pytorch/derived.png").write_bytes(b"x")
    (tmp_path / "candle/image_anno.csv").write_text("changed")
    assert tree_digest(tmp_path, members) == first

    (tmp_path / "pcb4/Data/Masks/Anomaly/000.png").write_bytes(b"changed")
    assert tree_digest(tmp_path, members).sha256 != first.sha256
    assert first.files == sum(1 for k in fake_files() if not k.startswith("candle/"))


# Streaming through tar


def test_stream_keeps_only_the_named_members_and_hashes_the_stream(tmp_path: Path) -> None:
    """Tar keeps the named members; the tarball's hash and size are those of the bytes served."""
    body = make_tar(fake_files())
    server = FakeServer(body, drops=[])
    seen: list[tuple[int, int | None]] = []

    with httpx.Client(transport=server.transport()) as client:
        record = stream_through_tar(
            URL,
            tmp_path,
            ("pcb1", "pcb4", SPLIT_DIR),
            client=client,
            expected_bytes=len(body),
            on_progress=lambda received, total: seen.append((received, total)),
        )

    assert record.bytes == len(body)
    assert record.sha256 == hashlib.sha256(body).hexdigest()
    assert record.etag == ETAG
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pcb1", "pcb4", SPLIT_DIR]
    assert (tmp_path / "pcb4/image_anno.csv").read_bytes() == fake_files()["pcb4/image_anno.csv"]
    assert seen[-1] == (len(body), len(body))
    assert not list(tmp_path.rglob("*.tar"))


def test_stream_resumes_after_a_dropped_connection(tmp_path: Path) -> None:
    """A drop mid-stream resumes with a Range request into the same tar process."""
    body = make_tar(fake_files())
    server = FakeServer(body, drops=[10_240, 4_096])
    requests = server.requests

    with httpx.Client(transport=server.transport()) as client:
        record = stream_through_tar(URL, tmp_path, ("pcb1",), client=client, retry_delays=NO_WAIT)

    assert record.sha256 == hashlib.sha256(body).hexdigest()
    assert [r.headers.get("Range") for r in requests] == [None, "bytes=10240-", "bytes=14336-"]
    assert all(r.headers.get("If-Range") == ETAG for r in requests[1:])
    assert (tmp_path / "pcb1/image_anno.csv").read_bytes() == fake_files()["pcb1/image_anno.csv"]


def test_stream_gives_up_after_its_retries(tmp_path: Path) -> None:
    """Drops beyond the retry budget fail with the cause, not a hang."""
    body = make_tar(fake_files())
    server = FakeServer(body, drops=[4_096] * 4)

    with (
        httpx.Client(transport=server.transport()) as client,
        pytest.raises(VisaFetchError, match="after 4 attempts"),
    ):
        stream_through_tar(URL, tmp_path, ("pcb1",), client=client, retry_delays=NO_WAIT)


def test_stream_refuses_a_server_that_ignores_range(tmp_path: Path) -> None:
    """A 200 to a resume would restart the tarball inside tar's stream: refused."""
    body = make_tar(fake_files())
    server = FakeServer(body, drops=[8_192], ignore_range=True)

    with (
        httpx.Client(transport=server.transport()) as client,
        pytest.raises(VisaFetchError, match="206"),
    ):
        stream_through_tar(URL, tmp_path, ("pcb1",), client=client, retry_delays=NO_WAIT)


def test_stream_refuses_a_tarball_of_the_wrong_size(tmp_path: Path) -> None:
    """A Content-Length other than the published size fails before anything is extracted."""
    body = make_tar(fake_files())
    server = FakeServer(body, drops=[])

    with (
        httpx.Client(transport=server.transport()) as client,
        pytest.raises(VisaFetchError, match="expected 7 bytes"),
    ):
        stream_through_tar(URL, tmp_path, ("pcb1",), client=client, expected_bytes=7)


def test_stream_reports_an_http_error(tmp_path: Path) -> None:
    """A 403 from the bucket is reported with its status."""

    def forbidden(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="AccessDenied")

    with (
        httpx.Client(transport=httpx.MockTransport(forbidden)) as client,
        pytest.raises(VisaFetchError, match="403"),
    ):
        stream_through_tar(URL, tmp_path, ("pcb1",), client=client, retry_delays=NO_WAIT)


def test_stream_reports_tar_failing(tmp_path: Path) -> None:
    """A member absent from the archive makes tar fail, and its own words are reported."""
    body = make_tar(fake_files())
    server = FakeServer(body, drops=[])

    with (
        httpx.Client(transport=server.transport()) as client,
        pytest.raises(VisaFetchError, match="pcb9: Not found in archive"),
    ):
        stream_through_tar(URL, tmp_path, ("pcb1", "pcb9"), client=client)


def test_stream_reports_garbage_that_is_not_a_tarball(tmp_path: Path) -> None:
    """Bytes that are not a tarball make tar fail, reported as such."""
    server = FakeServer(b"<Error>not a tarball</Error>" * 100, drops=[])

    with (
        httpx.Client(transport=server.transport()) as client,
        pytest.raises(VisaFetchError, match="tar exited"),
    ):
        stream_through_tar(URL, tmp_path, ("pcb1",), client=client)


# Fetching: download, verify, manifest, re-verify


def test_fetch_keeps_the_pcb_categories_and_writes_the_manifest(tmp_path: Path) -> None:
    """A first fetch keeps the PCB categories and split_csv, verifies, and writes the manifest."""
    body = make_tar(fake_files())
    dest = tmp_path / "data" / "visa"

    result = _fetch(dest, FakeServer(body, drops=[]))

    assert result.downloaded is True
    assert sorted(p.name for p in dest.iterdir()) == [MANIFEST_NAME, "pcb1", "pcb4", SPLIT_DIR]
    assert sorted(p.name for p in dest.parent.iterdir()) == ["visa"]
    manifest = Manifest.model_validate_json((dest / MANIFEST_NAME).read_text())
    assert manifest.categories == dict(EXPECTED)
    assert manifest.source.sha256 == hashlib.sha256(body).hexdigest()
    assert manifest.source.bytes == len(body)
    assert manifest.source.url == URL
    assert manifest.source.licence == "CC BY 4.0"
    assert manifest.kept == ("pcb1", "pcb4", SPLIT_DIR)
    assert manifest.tree == tree_digest(dest, manifest.kept)
    raw = json.loads((dest / MANIFEST_NAME).read_text())
    assert raw["categories"]["pcb4"]["defect_types"]["wrong place"] == 1


def test_a_second_fetch_re_verifies_without_the_network(tmp_path: Path) -> None:
    """With a manifest present the fetch touches no network and rewrites nothing."""
    dest = tmp_path / "visa"
    _fetch(dest, FakeServer(make_tar(fake_files()), drops=[]))
    written = (dest / MANIFEST_NAME).stat().st_mtime_ns

    result = _fetch(dest, None)

    assert result.downloaded is False
    assert (dest / MANIFEST_NAME).stat().st_mtime_ns == written


def test_a_second_fetch_tolerates_derived_folders_beside_the_kept_ones(tmp_path: Path) -> None:
    """Anomalib's split copy under the dataset root does not fail re-verification."""
    dest = tmp_path / "visa"
    _fetch(dest, FakeServer(make_tar(fake_files()), drops=[]))
    (dest / "visa_pytorch/pcb1/train/good").mkdir(parents=True)

    assert _fetch(dest, None).downloaded is False


def test_a_second_fetch_catches_a_changed_file(tmp_path: Path) -> None:
    """A file changed since the fetch fails re-verification, pointing at --force."""
    dest = tmp_path / "visa"
    _fetch(dest, FakeServer(make_tar(fake_files()), drops=[]))
    (dest / "pcb1/Data/Images/Normal/0001.JPG").write_bytes(b"tampered")

    with pytest.raises(VisaVerificationError, match="--force"):
        _fetch(dest, None)


def test_force_fetches_again_and_replaces(tmp_path: Path) -> None:
    """--force downloads afresh and swaps the new tree in whole."""
    dest = tmp_path / "visa"
    _fetch(dest, FakeServer(make_tar(fake_files()), drops=[]))
    (dest / "pcb1/Data/Images/Normal/0001.JPG").write_bytes(b"tampered")

    result = _fetch(dest, FakeServer(make_tar(fake_files()), drops=[]), force=True)

    assert result.downloaded is True
    assert (dest / "pcb1/Data/Images/Normal/0001.JPG").read_bytes().startswith(b"normal")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["visa"]


def test_a_failed_verification_leaves_nothing_behind(tmp_path: Path) -> None:
    """Counts that differ from the table leave neither the tree nor a partial directory."""
    files = fake_files()
    del files["pcb4/Data/Masks/Anomaly/002.png"]
    dest = tmp_path / "visa"

    with pytest.raises(VisaVerificationError, match="pcb4: masks is 2, expected 3"):
        _fetch(dest, FakeServer(make_tar(files), drops=[]))

    assert list(tmp_path.iterdir()) == []


def test_an_interrupted_fetch_leaves_nothing_behind(tmp_path: Path) -> None:
    """Ctrl-C halfway through the stream stops tar and removes the partial directory."""
    dest = tmp_path / "visa"

    def interrupt(received: int, total: int | None) -> None:
        if received > 8_192:
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        _fetch(dest, FakeServer(make_tar(fake_files()), drops=[]), on_progress=interrupt)

    assert list(tmp_path.iterdir()) == []


def test_a_stale_partial_directory_is_cleared_first(tmp_path: Path) -> None:
    """A partial directory left by a killed run is removed before the next stream."""
    stale = tmp_path / ".visa.partial"
    (stale / "pcb1").mkdir(parents=True)
    (stale / "pcb1/leftover").write_bytes(b"x")

    _fetch(tmp_path / "visa", FakeServer(make_tar(fake_files()), drops=[]))

    assert sorted(p.name for p in tmp_path.iterdir()) == ["visa"]
    assert not (tmp_path / "visa/pcb1/leftover").exists()


def test_fetch_refuses_to_start_without_disk_space(tmp_path: Path) -> None:
    """Too little free space fails before a byte is requested."""
    with pytest.raises(VisaFetchError, match="free"):
        _fetch(tmp_path / "visa", None, required_free_bytes=2**62)


# The real data, when fetched


@pytest.mark.data
def test_the_fetched_data_matches_the_published_counts() -> None:
    """The fetched data/visa re-verifies against Amazon's table and its own manifest."""
    dest = Path("data/visa")
    assert (dest / MANIFEST_NAME).is_file(), "run `spec-to-inspector data fetch` first"

    result = fetch_visa(dest, transport=httpx.MockTransport(_refuse))

    assert result.downloaded is False
    manifest = Manifest.model_validate_json((dest / MANIFEST_NAME).read_text())
    assert manifest.categories == dict(PUBLISHED_COUNTS)
    assert manifest.source.bytes == VISA_TAR_BYTES
