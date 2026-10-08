"""A synthetic VisA, packed as Amazon's tarball is, and an S3-like server for it."""

import csv
import io
import tarfile
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from spec_to_inspector.datasets.visa import SPLIT_DIR, CategoryCounts

URL = "https://visa.example/VisA_20220922.tar"
ETAG = '"fake-etag-1"'
NO_WAIT = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class FakeCategory:
    """A category of the synthetic VisA: normal images by split, anomalous images by label."""

    train_normal: int
    test_normal: int
    anomaly_labels: tuple[str, ...]


FAKE = {
    "pcb1": FakeCategory(3, 2, ("bent", "melt,scratch", "missing")),
    "pcb4": FakeCategory(2, 1, ("wrong place,dirt", "dirt", "burnt")),
    "candle": FakeCategory(1, 1, ("wax",)),
}
KEPT = {"pcb1", "pcb4"}

EXPECTED: Mapping[str, CategoryCounts] = {
    "pcb1": CategoryCounts(
        normal=5,
        anomalous=3,
        masks=3,
        train_normal=3,
        test_normal=2,
        test_anomalous=3,
        multi_defect=1,
        defect_types={"bent": 1, "melt": 1, "missing": 1, "scratch": 1},
    ),
    "pcb4": CategoryCounts(
        normal=3,
        anomalous=3,
        masks=3,
        train_normal=2,
        test_normal=1,
        test_anomalous=3,
        multi_defect=1,
        defect_types={"burnt": 1, "dirt": 2, "wrong place": 1},
    ),
}


def fake_files(categories: Mapping[str, FakeCategory] = FAKE) -> dict[str, bytes]:
    """Lay out a synthetic VisA as VisA's own tarball does.

    Args:
        categories: The categories to lay out.

    Returns:
        Archive member paths mapped to their contents.
    """
    files: dict[str, bytes] = {}
    split_rows: list[list[str]] = [["object", "split", "label", "image", "mask"]]
    for name, category in categories.items():
        anno_rows: list[list[str]] = [["image", "label", "mask"]]
        normal_count = category.train_normal + category.test_normal
        for i in range(normal_count):
            image = f"{name}/Data/Images/Normal/{i:04d}.JPG"
            files[image] = f"normal {image}".encode()
            anno_rows.append([image, "normal", ""])
            split = "train" if i < category.train_normal else "test"
            split_rows.append([name, split, "normal", image, ""])
        for i, label in enumerate(category.anomaly_labels):
            image = f"{name}/Data/Images/Anomaly/{i:03d}.JPG"
            mask = f"{name}/Data/Masks/Anomaly/{i:03d}.png"
            files[image] = f"anomalous {image}".encode()
            files[mask] = f"mask {mask}".encode()
            anno_rows.append([image, label, mask])
            split_rows.append([name, "test", "anomaly", image, mask])
        files[f"{name}/image_anno.csv"] = _csv_bytes(anno_rows)
    files[f"{SPLIT_DIR}/1cls.csv"] = _csv_bytes(split_rows)
    files[f"{SPLIT_DIR}/2cls_fewshot.csv"] = b"object,split,label,image,mask\n"
    return files


def _csv_bytes(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerows(rows)
    return buffer.getvalue().encode()


def write_tree(root: Path, files: Mapping[str, bytes]) -> None:
    """Write members to disk as tar would extract them.

    Args:
        root: The directory to write under.
        files: Member paths mapped to contents.
    """
    for member, content in files.items():
        path = root / member
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def make_tar(files: Mapping[str, bytes]) -> bytes:
    """Pack members into an uncompressed tarball, directories first as VisA's is.

    Args:
        files: Member paths mapped to contents.

    Returns:
        The tarball's bytes.
    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        directories = sorted({str(Path(m).parent) for m in files} - {"."})
        for directory in directories:
            info = tarfile.TarInfo(directory)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            archive.addfile(info)
        for member, content in files.items():
            info = tarfile.TarInfo(member)
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


class _DroppingStream(httpx.SyncByteStream):
    """A body that yields its bytes in small chunks, then drops the connection at a byte."""

    def __init__(self, body: bytes, drop_at: int | None) -> None:
        self._body = body
        self._drop_at = drop_at

    def __iter__(self) -> Iterator[bytes]:
        end = len(self._body) if self._drop_at is None else self._drop_at
        for start in range(0, end, 4096):
            yield self._body[start : min(start + 4096, end)]
        if self._drop_at is not None:
            raise httpx.ReadError("connection reset by peer")


@dataclass
class FakeServer:
    """An S3-like server for one tarball: honours Range and If-Range, can drop or misbehave."""

    body: bytes
    drops: list[int]
    ignore_range: bool = False
    requests: list[httpx.Request] = field(default_factory=lambda: [])

    def handler(self, request: httpx.Request) -> httpx.Response:
        """Answer one request.

        Args:
            request: The incoming request.

        Returns:
            The full body, or the requested range, possibly cut short.
        """
        self.requests.append(request)
        start = 0
        status = 200
        headers = {"ETag": ETAG}
        range_header = request.headers.get("Range")
        if range_header and not self.ignore_range:
            start = int(range_header.removeprefix("bytes=").removesuffix("-"))
            status = 206
            headers["Content-Range"] = f"bytes {start}-{len(self.body) - 1}/{len(self.body)}"
        payload = self.body[start:]
        headers["Content-Length"] = str(len(payload))
        drop_at = self.drops.pop(0) if self.drops else None
        return httpx.Response(status, headers=headers, stream=_DroppingStream(payload, drop_at))

    def transport(self) -> httpx.MockTransport:
        """Wrap the handler as an httpx transport.

        Returns:
            The transport.
        """
        return httpx.MockTransport(self.handler)
