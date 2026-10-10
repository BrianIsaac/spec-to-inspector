"""The specification's size in the judge's tokens.

The judge is Qwen3-VL-8B-Instruct, so text is counted with that model's own
tokenizer (`tokenizer.json`, 7 MB, fetched once into the Hugging Face
cache): the count is exact for text, not an approximation. Images are not
text and are not counted here.
"""

from functools import lru_cache
from typing import Final

from tokenizers import Tokenizer

VLM_TOKENIZER: Final = "Qwen/Qwen3-VL-8B-Instruct"


class TokenizerError(RuntimeError):
    """A tokenizer could not be loaded."""


@lru_cache(maxsize=4)
def load_tokenizer(name: str) -> Tokenizer:
    """Load a tokenizer from the Hugging Face hub or its cache.

    Args:
        name: The model repository that holds a `tokenizer.json`.

    Returns:
        The tokenizer.

    Raises:
        TokenizerError: If it is neither cached nor reachable.
    """
    try:
        return Tokenizer.from_pretrained(name)
    except Exception as error:
        raise TokenizerError(f"cannot load the tokenizer {name}: {error}") from error


def count_tokens(text: str, *, tokenizer: str | Tokenizer = VLM_TOKENIZER) -> int:
    """Count a text's tokens, with no special tokens added.

    Args:
        text: The text.
        tokenizer: A tokenizer, or the model repository to load one from.

    Returns:
        The number of tokens.

    Raises:
        TokenizerError: If the named tokenizer cannot be loaded.
    """
    loaded = load_tokenizer(tokenizer) if isinstance(tokenizer, str) else tokenizer
    return len(loaded.encode(text, add_special_tokens=False).ids)
