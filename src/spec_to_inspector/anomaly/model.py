"""PatchCore as Anomalib ships it, holding its training embeddings once instead of twice.

Anomalib 2.7 keeps every training batch's patch embeddings in a list on the
GPU and then stacks the list there, so for a moment the card holds the whole
embedding set twice. For a VisA PCB category at 256 px that is 904 images x
1,024 patches x 1,536 floats, 5.30 GiB, twice: more than a 12 GB card has
free.

The variant here is told how many training images to expect, allocates one
tensor for all their embeddings on the model's device when the first batch
arrives, and writes each batch straight into it. Anomalib's own k-centre
greedy coreset selection then runs on that tensor. The embeddings, their
order, the sampler and its random draws are the same, so the memory bank is
the one stock Anomalib would select on a card large enough to hold two
copies; a test compares the two on the CPU. Nothing waits in host memory.
"""

import time
from collections.abc import Callable
from typing import Any, cast

import torch
from anomalib.data import Batch
from anomalib.models import Patchcore
from anomalib.models.components import KCenterGreedy


class SingleCopyPatchcore(Patchcore):
    """PatchCore that collects its training embeddings into one preallocated tensor.

    Attributes:
        expected_images: How many training images the epoch will embed; set it
            before training. While it is None the variant behaves as stock
            Anomalib does, list and stack included.
        embedding_rows: Patch embeddings collected before coreset selection; 0 until fitted.
        coreset_seconds: Wall time of coreset selection; 0.0 until fitted.
    """

    expected_images: int | None = None
    embedding_rows: int = 0
    coreset_seconds: float = 0.0
    _buffer: torch.Tensor | None = None
    _filled: int = 0

    @property
    def buffer_capacity(self) -> int:
        """Rows the embedding buffer was allocated for; 0 when there is no buffer."""
        return 0 if self._buffer is None else self._buffer.shape[0]

    @property
    def buffered_rows(self) -> int:
        """Rows of the embedding buffer written so far."""
        return self._filled

    def _store(self) -> list[torch.Tensor]:
        """Anomalib's list of per-batch embeddings, which it leaves untyped."""
        return cast(
            "list[torch.Tensor]",
            self.model.embedding_store,  # pyright: ignore[reportUnknownMemberType]
        )

    def training_step(self, batch: Batch[Any], *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Embed a batch and write its embeddings into the one buffer.

        Args:
            batch: The training batch.
            *args: Passed on to Anomalib's step, which ignores them.
            **kwargs: Passed on to Anomalib's step, which ignores them.

        Returns:
            Anomalib's dummy loss.

        Raises:
            ValueError: If the epoch holds more images than `expected_images`.
        """
        step = cast(
            "Callable[..., None]",
            super().training_step,  # pyright: ignore[reportUnknownMemberType]
        )
        loss = step(batch, *args, **kwargs)
        if self.expected_images is None:
            return loss

        chunk = self._store().pop()
        if self._buffer is None:
            rows_per_image = chunk.shape[0] // cast("torch.Tensor", batch.image).shape[0]
            self._buffer = torch.empty(
                (self.expected_images * rows_per_image, chunk.shape[1]),
                dtype=chunk.dtype,
                device=chunk.device,
            )
            self._filled = 0
        end = self._filled + chunk.shape[0]
        if end > self._buffer.shape[0]:
            msg = (
                f"the epoch holds more than expected_images={self.expected_images} images: "
                f"{end} embedding rows for a buffer of {self._buffer.shape[0]}"
            )
            raise ValueError(msg)
        self._buffer[self._filled : end] = chunk
        self._filled = end
        return loss

    def fit(self) -> None:
        """Select the coreset from the embeddings collected, and release them.

        Raises:
            ValueError: If no training batch has been embedded.
        """
        started = time.perf_counter()
        if self._buffer is None:
            store = self._store()
            if not store:
                msg = "Embedding store is empty. Cannot perform coreset selection."
                raise ValueError(msg)
            rows = sum(chunk.shape[0] for chunk in store)
            super().fit()
        else:
            rows = self._filled
            embeddings = self._buffer[:rows]
            self._buffer = None
            self._filled = 0
            sampler = KCenterGreedy(
                embedding=embeddings, sampling_ratio=self.coreset_sampling_ratio
            )
            self.model.memory_bank = sampler.sample_coreset()
        self.embedding_rows = rows
        self.coreset_seconds = time.perf_counter() - started
