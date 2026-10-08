"""The VisA PCB categories: streamed from Amazon's tarball, kept in part, verified.

The tarball (1.9 GB) is never stored. It is streamed over HTTP into GNU tar,
which keeps only the four PCB categories and `split_csv/`; a dropped
connection resumes with a Range request into the same tar process. The kept
tree is extracted into a partial directory, counted against Amazon's
published table, given a manifest, and only then moved into place, so the
dataset directory either holds a verified tree or does not exist. A second
fetch reads the manifest, recounts and rehashes the tree, and touches no
network.

The layout kept is the one Anomalib's `Visa` datamodule expects as its root:
`<category>/Data/Images/{Normal,Anomaly}`, `<category>/Data/Masks/Anomaly`,
`<category>/image_anno.csv` and `split_csv/1cls.csv`.
"""

import csv
import hashlib
import shutil
import tempfile
import time
from collections import Counter
from collections.abc import Callable, Generator, Iterable, Mapping, Sequence
from contextlib import closing, contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from subprocess import DEVNULL, PIPE, Popen
from typing import IO, Final, Literal

import httpx
from pydantic import BaseModel, ConfigDict

VISA_URL: Final = "https://amazon-visual-anomaly.s3.us-west-2.amazonaws.com/VisA_20220922.tar"
VISA_TAR_BYTES: Final = 1_929_840_640
VISA_LICENCE: Final = "CC BY 4.0"
SPLIT_DIR: Final = "split_csv"
SPLIT_CSV: Final = "1cls.csv"
MANIFEST_NAME: Final = "manifest.json"
NORMAL_LABEL: Final = "normal"
REQUIRED_FREE_BYTES: Final = 3 * 1024**3
RETRY_DELAYS: Final = (2.0, 10.0, 30.0)


ProgressCallback = Callable[[int, int | None], None]


class CategoryCounts(BaseModel):
    """What one VisA category holds, from its folders and its two CSVs.

    Attributes:
        normal: Images in `Data/Images/Normal`.
        anomalous: Images in `Data/Images/Anomaly`.
        masks: Masks in `Data/Masks/Anomaly`.
        train_normal: Normal images in the training split of `1cls.csv`.
        test_normal: Normal images in the test split of `1cls.csv`.
        test_anomalous: Anomalous images in the test split of `1cls.csv`.
        multi_defect: Anomalous images whose label names more than one defect type.
        defect_types: Images per defect type in `image_anno.csv`; an image counts once
            for each type it carries.
    """

    model_config = ConfigDict(frozen=True)

    normal: int
    anomalous: int
    masks: int
    train_normal: int
    test_normal: int
    test_anomalous: int
    multi_defect: int
    defect_types: dict[str, int]


PUBLISHED_COUNTS: Final[Mapping[str, CategoryCounts]] = {
    "pcb1": CategoryCounts(
        normal=1004,
        anomalous=100,
        masks=100,
        train_normal=904,
        test_normal=100,
        test_anomalous=100,
        multi_defect=9,
        defect_types={"melt": 54, "scratch": 21, "missing": 20, "bent": 15},
    ),
    "pcb2": CategoryCounts(
        normal=1001,
        anomalous=100,
        masks=100,
        train_normal=901,
        test_normal=100,
        test_anomalous=100,
        multi_defect=9,
        defect_types={"melt": 55, "scratch": 20, "missing": 19, "bent": 15},
    ),
    "pcb3": CategoryCounts(
        normal=1006,
        anomalous=100,
        masks=100,
        train_normal=905,
        test_normal=101,
        test_anomalous=100,
        multi_defect=7,
        defect_types={"melt": 43, "scratch": 25, "bent": 20, "missing": 20},
    ),
    "pcb4": CategoryCounts(
        normal=1005,
        anomalous=100,
        masks=100,
        train_normal=904,
        test_normal=101,
        test_anomalous=100,
        multi_defect=56,
        defect_types={
            "dirt": 42,
            "missing": 33,
            "extra": 30,
            "damage": 21,
            "scratch": 17,
            "wrong place": 13,
            "burnt": 8,
        },
    ),
}
"""Amazon's published image counts, and the defect types read from each `image_anno.csv`."""


class SourceRecord(BaseModel):
    """The tarball as it was streamed.

    Attributes:
        url: Where it was streamed from.
        bytes: Its size as received.
        sha256: The SHA-256 of the bytes received, computed in flight.
        etag: The server's ETag, if it sent one.
        licence: The dataset's licence, as Amazon's README states it.
    """

    model_config = ConfigDict(frozen=True)

    url: str
    bytes: int
    sha256: str
    etag: str | None
    licence: str = VISA_LICENCE


class TreeDigest(BaseModel):
    """A digest of a kept tree: every file's relative path and contents, in path order.

    Attributes:
        sha256: The digest.
        files: The number of files covered.
        bytes: Their total size.
    """

    model_config = ConfigDict(frozen=True)

    sha256: str
    files: int
    bytes: int


class Manifest(BaseModel):
    """The record a fetch leaves in `data/visa/manifest.json`.

    Attributes:
        manifest_version: The manifest's own format version.
        dataset: Always "VisA".
        source: The tarball as streamed.
        fetched_at: When the fetch finished, in UTC.
        kept: The archive members kept, in order.
        split: The split file Anomalib's VisA datamodule applies.
        categories: The verified counts per category.
        tree: The digest of the kept members, for re-verification.
    """

    model_config = ConfigDict(frozen=True)

    manifest_version: Literal[1] = 1
    dataset: Literal["VisA"] = "VisA"
    source: SourceRecord
    fetched_at: datetime
    kept: tuple[str, ...]
    split: str = f"{SPLIT_DIR}/{SPLIT_CSV}"
    categories: dict[str, CategoryCounts]
    tree: TreeDigest


class FetchResult(BaseModel):
    """What a fetch did.

    Attributes:
        manifest: The manifest of the verified tree.
        downloaded: True if this run streamed the tarball, False if it re-verified.
        path: The dataset directory.
    """

    model_config = ConfigDict(frozen=True)

    manifest: Manifest
    downloaded: bool
    path: Path


class VisaFetchError(RuntimeError):
    """The tarball could not be streamed and extracted."""


class VisaVerificationError(RuntimeError):
    """The tree on disk differs from what is expected.

    Attributes:
        differences: One line per difference found.
    """

    def __init__(self, differences: Sequence[str], hint: str = "") -> None:
        """Collect the differences into one message.

        Args:
            differences: One line per difference found.
            hint: What to do about it, appended to the message.
        """
        self.differences = tuple(differences)
        lines = ["VisA verification failed:", *(f"  {d}" for d in self.differences)]
        if hint:
            lines.append(hint)
        super().__init__("\n".join(lines))


def _count_files(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.iterdir() if path.is_file())


def _read_csv(path: Path, columns: Iterable[str]) -> list[dict[str, str]]:
    if not path.is_file():
        raise VisaVerificationError([f"{path.name} is missing: {path}"])
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(columns) - set(reader.fieldnames or ())
        if missing:
            raise VisaVerificationError([f"{path} lacks the columns {sorted(missing)}"])
        return list(reader)


def _defect_types(label: str) -> set[str]:
    return {part.strip() for part in label.split(",") if part.strip()}


def count_category(root: Path, category: str) -> CategoryCounts:
    """Count one category's images, masks, split and defect types.

    Args:
        root: The dataset directory, holding `<category>/` and `split_csv/`.
        category: The category's folder name, such as "pcb1".

    Returns:
        The category's counts.

    Raises:
        VisaVerificationError: If `image_anno.csv` or `split_csv/1cls.csv` is
            missing or lacks its columns.
    """
    base = root / category
    annotations = _read_csv(base / "image_anno.csv", ("image", "label", "mask"))
    split_rows = _read_csv(
        root / SPLIT_DIR / SPLIT_CSV, ("object", "split", "label", "image", "mask")
    )

    types: Counter[str] = Counter()
    multi_defect = 0
    for row in annotations:
        if row["label"].strip() == NORMAL_LABEL:
            continue
        found = _defect_types(row["label"])
        types.update(found)
        multi_defect += len(found) > 1

    split = Counter((row["split"], row["label"]) for row in split_rows if row["object"] == category)
    return CategoryCounts(
        normal=_count_files(base / "Data" / "Images" / "Normal"),
        anomalous=_count_files(base / "Data" / "Images" / "Anomaly"),
        masks=_count_files(base / "Data" / "Masks" / "Anomaly"),
        train_normal=split["train", "normal"],
        test_normal=split["test", "normal"],
        test_anomalous=split["test", "anomaly"],
        multi_defect=multi_defect,
        defect_types=dict(types.most_common()),
    )


def _compare(category: str, observed: CategoryCounts, expected: CategoryCounts) -> list[str]:
    differences: list[str] = []
    for field in CategoryCounts.model_fields:
        seen, wanted = getattr(observed, field), getattr(expected, field)
        if seen != wanted:
            differences.append(f"{category}: {field} is {seen}, expected {wanted}")
    return differences


def _missing_references(root: Path, category: str) -> list[str]:
    """List files named by the category's CSVs that are not on disk."""
    named: set[str] = set()
    for row in _read_csv(root / category / "image_anno.csv", ("image", "mask")):
        named.update(value for value in (row["image"], row["mask"]) if value)
    for row in _read_csv(root / SPLIT_DIR / SPLIT_CSV, ("object", "image", "mask")):
        if row["object"] == category:
            named.update(value for value in (row["image"], row["mask"]) if value)
    return [
        f"{category}: {name} is named but missing"
        for name in sorted(named)
        if not (root / name).is_file()
    ]


def _irregular_entries(root: Path, members: Iterable[str]) -> list[str]:
    """List anything under the kept members that is neither a regular file nor a directory."""
    found: list[str] = []
    for member in members:
        for path in sorted((root / member).rglob("*")):
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                found.append(f"{path.relative_to(root)} is not a regular file or directory")
    return found


def verify(
    root: Path, expected: Mapping[str, CategoryCounts] = PUBLISHED_COUNTS
) -> dict[str, CategoryCounts]:
    """Check a kept tree against the expected counts.

    Every count of every category must match; every image and mask that a CSV
    names must be on disk; nothing under the kept members may be a link or a
    special file.

    Args:
        root: The dataset directory.
        expected: The expected counts per category.

    Returns:
        The observed counts per category, equal to `expected`.

    Raises:
        VisaVerificationError: With every difference found.
    """
    differences: list[str] = []
    observed: dict[str, CategoryCounts] = {}
    for category, wanted in expected.items():
        if not (root / category).is_dir():
            differences.append(f"{category}: the folder is missing")
            continue
        try:
            observed[category] = count_category(root, category)
            differences.extend(_missing_references(root, category))
        except VisaVerificationError as error:
            differences.extend(f"{category}: {d}" for d in error.differences)
            continue
        differences.extend(_compare(category, observed[category], wanted))
    differences.extend(_irregular_entries(root, _kept_members(expected)))
    if differences:
        raise VisaVerificationError(differences)
    return observed


def tree_digest(root: Path, members: Iterable[str]) -> TreeDigest:
    """Digest the files under the kept members, names and contents, in path order.

    Anything beside the kept members (the manifest, Anomalib's split copy) is
    not covered, so derived data may live under the same root.

    Args:
        root: The dataset directory.
        members: The kept top-level folders.

    Returns:
        The digest, the file count and the total size.
    """
    digest = hashlib.sha256()
    files = 0
    size = 0
    paths = sorted(
        path for member in members for path in (root / member).rglob("*") if path.is_file()
    )
    for path in paths:
        with path.open("rb") as handle:
            content = hashlib.file_digest(handle, "sha256").digest()
        digest.update(path.relative_to(root).as_posix().encode() + b"\0" + content)
        files += 1
        size += path.stat().st_size
    return TreeDigest(sha256=digest.hexdigest(), files=files, bytes=size)


class _RetryableError(Exception):
    """A failure worth retrying: a dropped connection, a short body, a 5xx."""


class _ResumableDownload:
    """A URL's bytes, resumed with a Range request after a drop, hashed as they pass.

    Attributes:
        received: Bytes yielded so far.
        total: The size the server declared, once known.
        etag: The server's ETag, once known.
    """

    def __init__(
        self,
        client: httpx.Client,
        url: str,
        *,
        expected_bytes: int | None,
        retry_delays: Sequence[float],
    ) -> None:
        """Prepare the download; nothing is requested until `chunks` is iterated.

        Args:
            client: The HTTP client.
            url: The URL.
            expected_bytes: The size the server must declare, if known.
            retry_delays: Seconds to wait before each retry; its length is the budget.
        """
        self._client = client
        self._url = url
        self._expected_bytes = expected_bytes
        self._retry_delays = retry_delays
        self._digest = hashlib.sha256()
        self.received = 0
        self.total: int | None = None
        self.etag: str | None = None

    def chunks(self) -> Generator[bytes]:
        """Yield the body, resuming after each retryable failure until the budget runs out.

        Yields:
            The body's bytes, in order, each byte once.

        Raises:
            VisaFetchError: If the server refuses or the retries run out.
        """
        attempt = 0
        while True:
            try:
                yield from self._attempt()
                return
            except (httpx.TransportError, _RetryableError) as error:
                if attempt >= len(self._retry_delays):
                    msg = (
                        f"streaming {self._url} failed after {attempt + 1} attempts "
                        f"at byte {self.received}: {error}"
                    )
                    raise VisaFetchError(msg) from error
                time.sleep(self._retry_delays[attempt])
                attempt += 1

    def record(self) -> SourceRecord:
        """Describe the stream once it is complete.

        Returns:
            The URL, size, SHA-256 and ETag of what was received.
        """
        return SourceRecord(
            url=self._url, bytes=self.received, sha256=self._digest.hexdigest(), etag=self.etag
        )

    def _attempt(self) -> Generator[bytes]:
        headers: dict[str, str] = {}
        if self.received:
            headers["Range"] = f"bytes={self.received}-"
            if self.etag:
                headers["If-Range"] = self.etag
        with self._client.stream("GET", self._url, headers=headers) as response:
            self._accept(response)
            for chunk in response.iter_bytes():
                self._digest.update(chunk)
                self.received += len(chunk)
                yield chunk
        if self.total is not None and self.received != self.total:
            raise _RetryableError(f"the body ended at byte {self.received} of {self.total}")

    def _accept(self, response: httpx.Response) -> None:
        """Check a response continues the stream at `received`, and note its size and ETag.

        Raises:
            _RetryableError: On a server error.
            VisaFetchError: On any other status, a resume the server will not honour,
                or a size other than the expected one.
        """
        status = response.status_code
        if status >= 500:
            raise _RetryableError(f"HTTP {status} from {response.url}")
        if self.received == 0:
            if status != 200:
                raise VisaFetchError(f"HTTP {status} from {response.url}")
            length = response.headers.get("Content-Length")
            self.total = int(length) if length is not None else None
            self.etag = response.headers.get("ETag")
            if self._expected_bytes is not None and self.total != self._expected_bytes:
                msg = f"{self._url} is {self.total} bytes, expected {self._expected_bytes} bytes"
                raise VisaFetchError(msg)
            return
        if status != 206:
            msg = f"resuming at byte {self.received} needs HTTP 206, got {status}"
            raise VisaFetchError(msg)
        content_range = response.headers.get("Content-Range", "")
        if not content_range.startswith(f"bytes {self.received}-"):
            msg = f"asked to resume at byte {self.received}, got range {content_range!r}"
            raise VisaFetchError(msg)


@contextmanager
def _tar_extracting(
    dest: Path, members: Sequence[str], stderr: IO[bytes]
) -> Generator[Popen[bytes]]:
    """Run GNU tar reading an archive from its standard input, killed if left running.

    Args:
        dest: The directory to extract into.
        members: The top-level archive members to keep.
        stderr: Where tar's messages go.

    Yields:
        The tar process.
    """
    command = [
        "tar",
        "--extract",
        "--file=-",
        f"--directory={dest}",
        "--no-same-owner",
        "--no-same-permissions",
        "--",
        *members,
    ]
    tar = Popen(command, stdin=PIPE, stdout=DEVNULL, stderr=stderr)
    try:
        yield tar
    finally:
        if tar.poll() is None:
            tar.kill()
            tar.wait()
        if tar.stdin is not None and not tar.stdin.closed:
            with suppress(BrokenPipeError):
                tar.stdin.close()


def _tar_error(code: int, stderr: IO[bytes]) -> VisaFetchError:
    stderr.seek(0)
    words = stderr.read().decode(errors="replace").strip()
    return VisaFetchError(f"tar exited with {code}: {words}")


def stream_through_tar(
    url: str,
    dest: Path,
    members: Sequence[str],
    *,
    client: httpx.Client,
    expected_bytes: int | None = None,
    retry_delays: Sequence[float] = RETRY_DELAYS,
    on_progress: ProgressCallback | None = None,
) -> SourceRecord:
    """Stream a tarball into GNU tar, keeping only the named members.

    The bytes go from the HTTP response to tar's standard input and are hashed
    on the way; nothing is written but what tar extracts. A dropped connection
    or a server error resumes from the last byte written with a Range request
    (guarded by If-Range on the ETag), after each delay in `retry_delays`.
    GNU tar refuses absolute member names and `..` components by default.

    Args:
        url: The tarball's URL.
        dest: An existing, empty directory to extract into.
        members: The top-level archive members to keep.
        client: The HTTP client.
        expected_bytes: The tarball's size, if known; another size is refused.
        retry_delays: Seconds to wait before each retry; its length is the retry budget.
        on_progress: Called with the bytes received and the total, after each chunk.

    Returns:
        The size, SHA-256 and ETag of the stream.

    Raises:
        VisaFetchError: If the server refuses, the retries run out, the size is
            wrong, or tar fails.
    """
    download = _ResumableDownload(
        client, url, expected_bytes=expected_bytes, retry_delays=retry_delays
    )
    with tempfile.TemporaryFile() as stderr, _tar_extracting(dest, members, stderr) as tar:
        stdin = tar.stdin
        if stdin is None:  # pragma: no cover - Popen with PIPE always sets it
            raise VisaFetchError("tar's standard input is not a pipe")
        try:
            with closing(download.chunks()) as chunks:
                for chunk in chunks:
                    stdin.write(chunk)
                    if on_progress is not None:
                        on_progress(download.received, download.total)
            stdin.close()
        except BrokenPipeError as error:
            raise _tar_error(tar.wait(), stderr) from error
        if (code := tar.wait()) != 0:
            raise _tar_error(code, stderr)
    return download.record()


def _kept_members(expected: Mapping[str, CategoryCounts]) -> tuple[str, ...]:
    return (*expected, SPLIT_DIR)


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _reverify(dest: Path, expected: Mapping[str, CategoryCounts]) -> Manifest:
    """Recount and rehash a fetched tree against its manifest and the expected table."""
    hint = f"Run `spec-to-inspector data fetch --force` to fetch {dest} afresh."
    try:
        manifest = Manifest.model_validate_json((dest / MANIFEST_NAME).read_text())
    except ValueError as error:
        raise VisaVerificationError(
            [f"{dest / MANIFEST_NAME} is unreadable: {error}"], hint
        ) from error
    try:
        verify(dest, expected)
    except VisaVerificationError as error:
        raise VisaVerificationError(error.differences, hint) from error
    differences = [
        line
        for category, wanted in expected.items()
        if category in manifest.categories
        for line in _compare(f"manifest {category}", manifest.categories[category], wanted)
    ]
    differences.extend(
        f"manifest: {category} is not recorded"
        for category in expected
        if category not in manifest.categories
    )
    if tree_digest(dest, manifest.kept) != manifest.tree:
        differences.append("the kept files changed since they were fetched (tree digest differs)")
    if differences:
        raise VisaVerificationError(differences, hint)
    return manifest


def fetch_visa(
    dest: Path,
    *,
    url: str = VISA_URL,
    force: bool = False,
    expected: Mapping[str, CategoryCounts] = PUBLISHED_COUNTS,
    expected_bytes: int | None = VISA_TAR_BYTES,
    transport: httpx.BaseTransport | None = None,
    retry_delays: Sequence[float] = RETRY_DELAYS,
    required_free_bytes: int = REQUIRED_FREE_BYTES,
    on_progress: ProgressCallback | None = None,
) -> FetchResult:
    """Fetch the PCB categories of VisA into `dest`, or re-verify them if already there.

    With a manifest in `dest` and no `force`, nothing is downloaded: the tree is
    recounted and rehashed against the manifest and `expected`. Otherwise the
    tarball is streamed through tar into a partial directory beside `dest`,
    verified, given its manifest, and swapped into place; on any failure or
    interruption the partial directory is removed and `dest` is left as it was.

    Args:
        dest: The dataset directory, `data/visa` by default settings.
        url: The tarball's URL.
        force: Fetch afresh even if a manifest is present. Anything else under
            `dest`, such as Anomalib's split copy, is removed with the old tree.
        expected: The expected counts per category; its keys are the categories kept.
        expected_bytes: The tarball's size, if known.
        transport: An httpx transport to use instead of the network, for tests.
        retry_delays: Seconds to wait before each retry of a dropped stream.
        required_free_bytes: Free space needed beside `dest` before streaming.
        on_progress: Called with the bytes received and the total, after each chunk.

    Returns:
        The manifest and whether this run downloaded.

    Raises:
        VisaFetchError: If there is too little free space or the stream fails.
        VisaVerificationError: If the counts or the tree differ from what is expected.
    """
    if (dest / MANIFEST_NAME).is_file() and not force:
        return FetchResult(manifest=_reverify(dest, expected), downloaded=False, path=dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(dest.parent).free
    if free < required_free_bytes:
        raise VisaFetchError(
            f"{free / 1024**3:.1f} GB free beside {dest}; the kept data needs "
            f"{required_free_bytes / 1024**3:.1f} GB free"
        )

    members = _kept_members(expected)
    staging = dest.with_name(f".{dest.name}.partial")
    retired = dest.with_name(f".{dest.name}.old")
    _remove(staging)
    _remove(retired)
    staging.mkdir()
    try:
        with httpx.Client(
            transport=transport,
            timeout=httpx.Timeout(30.0, read=120.0),
            follow_redirects=True,
        ) as client:
            source = stream_through_tar(
                url,
                staging,
                members,
                client=client,
                expected_bytes=expected_bytes,
                retry_delays=retry_delays,
                on_progress=on_progress,
            )
        categories = verify(staging, expected)
        manifest = Manifest(
            source=source,
            fetched_at=datetime.now(UTC),
            kept=members,
            categories=categories,
            tree=tree_digest(staging, members),
        )
        (staging / MANIFEST_NAME).write_text(manifest.model_dump_json(indent=2) + "\n")
        if dest.exists():
            dest.rename(retired)
        staging.rename(dest)
    except BaseException:
        _remove(staging)
        if retired.exists() and not dest.exists():
            retired.rename(dest)
        raise
    _remove(retired)
    return FetchResult(manifest=manifest, downloaded=True, path=dest)
