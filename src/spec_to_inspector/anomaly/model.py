"""PatchCore as Anomalib ships it, with training embeddings held in host memory.

Anomalib 2.7 keeps every training batch's patch embeddings on the GPU and
then stacks them there, so for a moment the card holds the whole embedding
set twice. For a VisA PCB category at 256 px that is 904 images x 1,024
patches x 1,536 floats, 5.30 GiB, twice: more than a 12 GB card has free.

The variant here moves each batch's embeddings to host memory as they are
made, stacks them there, and puts one copy on the GPU for Anomalib's own
k-centre greedy coreset selection. The embeddings, their order, the sampler
and its random draws are the same, so the memory bank is the one stock
Anomalib would select on a card large enough to hold it; a test compares the
two on the CPU.
"""

import time
from collections.abc import Callable
from typing import Any, cast

import torch
from anomalib.data import Batch
from anomalib.models import Patchcore
from anomalib.models.components import KCenterGreedy


class HostBufferedPatchcore(Patchcore):
    """PatchCore whose training embeddings wait in host memory until the coreset is selected.

    Attributes:
        embedding_rows: Patch embeddings collected before coreset selection; 0 until fitted.
        coreset_seconds: Wall time of stacking and coreset selection; 0.0 until fitted.
    """

    embedding_rows: int = 0
    coreset_seconds: float = 0.0

    def _store(self) -> list[torch.Tensor]:
        """Anomalib's list of per-batch embeddings, which it leaves untyped."""
        return cast(
            "list[torch.Tensor]",
            self.model.embedding_store,  # pyright: ignore[reportUnknownMemberType]
        )

    def training_step(self, batch: Batch[Any], *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """Embed a batch and move its embeddings off the GPU.

        Args:
            batch: The training batch.
            *args: Passed on to Anomalib's step, which ignores them.
            **kwargs: Passed on to Anomalib's step, which ignores them.

        Returns:
            Anomalib's dummy loss.
        """
        step = cast(
            "Callable[..., None]",
            super().training_step,  # pyright: ignore[reportUnknownMemberType]
        )
        loss = step(batch, *args, **kwargs)
        store = self._store()
        store[-1] = store[-1].cpu()
        return loss

    def fit(self) -> None:
        """Stack the embeddings on the host, then select the coreset on the model's device.

        Raises:
            ValueError: If no training batch has been embedded.
        """
        started = time.perf_counter()
        store = self._store()
        if not store:
            msg = "Embedding store is empty. Cannot perform coreset selection."
            raise ValueError(msg)

        rows = sum(chunk.shape[0] for chunk in store)
        embeddings = torch.empty((rows, store[0].shape[1]), dtype=store[0].dtype)
        offset = 0
        while store:
            chunk = store.pop(0)
            embeddings[offset : offset + chunk.shape[0]] = chunk
            offset += chunk.shape[0]

        if self.device.type == "cuda":
            torch.cuda.empty_cache()
        embeddings = embeddings.to(self.device)
        sampler = KCenterGreedy(embedding=embeddings, sampling_ratio=self.coreset_sampling_ratio)
        self.model.memory_bank = sampler.sample_coreset()
        self.embedding_rows = rows
        self.coreset_seconds = time.perf_counter() - started
