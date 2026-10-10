"""Tests for the token count in the judge's tokenizer."""

import pytest
from tokenizers import Tokenizer
from tokenizers.models import WordLevel
from tokenizers.pre_tokenizers import Whitespace

from spec_to_inspector.spec import tokens
from spec_to_inspector.spec.tokens import VLM_TOKENIZER, TokenizerError, count_tokens


def test_tokens_are_counted_by_the_tokenizer_given() -> None:
    """A tokenizer passed in is used as it is, with no special tokens added."""
    words = Tokenizer(WordLevel({"a": 0, "scratch": 1, "[UNK]": 2}, unk_token="[UNK]"))  # noqa: S106
    words.pre_tokenizer = Whitespace()  # pyright: ignore[reportAttributeAccessIssue]

    assert count_tokens("a scratch a dent", tokenizer=words) == 4
    assert count_tokens("", tokenizer=words) == 0


def test_the_default_is_the_judges_own_tokenizer() -> None:
    """The count is in Qwen3-VL's tokens (7 MB, fetched once into the Hugging Face cache)."""
    assert VLM_TOKENIZER == "Qwen/Qwen3-VL-8B-Instruct"
    assert count_tokens("A scratch is rejected when its size exceeds 0.5 mm.") == 14


def test_a_tokenizer_that_cannot_be_loaded_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    """Offline with an empty cache, or with a wrong name, the error says which tokenizer."""
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    tokens.load_tokenizer.cache_clear()

    with pytest.raises(TokenizerError, match="no-such-org/no-such-tokenizer"):
        count_tokens("text", tokenizer="no-such-org/no-such-tokenizer")
