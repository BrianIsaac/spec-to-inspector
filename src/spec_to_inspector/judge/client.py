"""The judge's client: one chat completion from an OpenAI-compatible server.

The backend is a URL and a model name. llama.cpp's server on the laptop and
vLLM or llm-scaler on the B70 take the same request; what only llama.cpp
understands (the per-request prompt-cache switch, its `timings`) is sent or
read only when asked for or present.
"""

import contextlib
import time
from collections.abc import Mapping, Sequence
from types import TracebackType
from typing import Final, Self, cast

import httpx
from pydantic import BaseModel, ConfigDict

Message = Mapping[str, object]
"""One chat message in the OpenAI shape: a role and its content."""

SCHEMA_NAME: Final = "judge_answer"
DEFAULT_MAX_TOKENS: Final = 256
_ERROR_BODY_CHARACTERS: Final = 300


class VlmError(RuntimeError):
    """The server gave no completion; the message says why, in words."""


class Completion(BaseModel):
    """One completion, with what the server and the client measured of it.

    Attributes:
        text: The assistant's text.
        finish_reason: Why generation stopped, as the server names it.
        prompt_tokens: Tokens in the prompt, images included, by the server's count.
        completion_tokens: Tokens generated.
        cached_tokens: Prompt tokens the server took from its cache instead of
            evaluating; None if the server does not say.
        seconds: Wall time of the request, as the client saw it.
        prompt_seconds: The server's time evaluating the prompt (llama.cpp only).
        generation_seconds: The server's time generating (llama.cpp only).
        tokens_per_second: The server's generation rate (llama.cpp only).
    """

    model_config = ConfigDict(frozen=True)

    text: str
    finish_reason: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    cached_tokens: int | None = None
    seconds: float
    prompt_seconds: float | None = None
    generation_seconds: float | None = None
    tokens_per_second: float | None = None


def _mapping(value: object) -> Mapping[str, object]:
    """Read a JSON value as an object, or as an empty one if it is not.

    Args:
        value: A decoded JSON value.

    Returns:
        The object, or an empty mapping.
    """
    return cast("Mapping[str, object]", value) if isinstance(value, dict) else {}


def _count(value: object) -> int | None:
    """Read a JSON value as a count.

    Args:
        value: A decoded JSON value.

    Returns:
        The integer, or None if the value is not one.
    """
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _number(value: object) -> float | None:
    """Read a JSON value as a number.

    Args:
        value: A decoded JSON value.

    Returns:
        The number as a float, or None if the value is not one.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _milliseconds(value: object) -> float | None:
    """Read a JSON value in milliseconds as seconds.

    Args:
        value: A decoded JSON value.

    Returns:
        The duration in seconds, or None if the value is not a number.
    """
    number = _number(value)
    return None if number is None else number / 1000.0


class ChatClient:
    """A connection to one OpenAI-compatible chat server."""

    def __init__(self, url: str, model: str, *, timeout_seconds: float = 120.0) -> None:
        """Open the client; nothing is sent until a completion is asked for.

        Args:
            url: The server's base URL, up to and including `/v1`.
            model: The model's name as the server knows it.
            timeout_seconds: How long one request may take.
        """
        self._url = url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._http = httpx.Client(timeout=httpx.Timeout(timeout_seconds))

    @property
    def url(self) -> str:
        """The server's base URL."""
        return self._url

    @property
    def model(self) -> str:
        """The model's name as the server knows it."""
        return self._model

    def __enter__(self) -> Self:
        """Give the client as a context manager.

        Returns:
            The client.
        """
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        """Close the connection."""
        self.close()

    def close(self) -> None:
        """Close the connection."""
        self._http.close()

    def complete(
        self,
        messages: Sequence[Message],
        *,
        schema: Mapping[str, object] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        cache_prompt: bool | None = None,
    ) -> Completion:
        """Ask for one completion, at temperature zero.

        Args:
            messages: The conversation, in the OpenAI shape.
            schema: A JSON schema to constrain the output to, where the server
                supports constrained decoding.
            max_tokens: The most tokens to generate.
            cache_prompt: llama.cpp's per-request prompt-cache switch; None
                leaves the server's default and sends nothing a server might
                not know.

        Returns:
            The completion.

        Raises:
            VlmError: If the server cannot be reached, does not answer in
                time, answers with an error, or its reply holds no text.
        """
        body: dict[str, object] = {
            "model": self._model,
            "messages": list(messages),
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        if schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": SCHEMA_NAME, "strict": True, "schema": dict(schema)},
            }
        if cache_prompt is not None:
            body["cache_prompt"] = cache_prompt

        started = time.perf_counter()
        try:
            response = self._http.post(f"{self._url}/chat/completions", json=body)
        except httpx.ConnectError as error:
            raise VlmError(f"cannot reach the VLM server at {self._url}: {error}") from error
        except httpx.TimeoutException as error:
            raise VlmError(
                f"the VLM server at {self._url} did not answer within {self._timeout_seconds:g} s"
            ) from error
        except httpx.HTTPError as error:
            raise VlmError(f"the request to the VLM server at {self._url} failed: {error}") from (
                error
            )
        seconds = time.perf_counter() - started

        if response.status_code >= httpx.codes.BAD_REQUEST:
            said = " ".join(response.text.split())[:_ERROR_BODY_CHARACTERS]
            raise VlmError(
                f"the VLM server at {self._url} answered HTTP {response.status_code}: {said}"
            )
        return self._read(response, seconds)

    def _read(self, response: httpx.Response, seconds: float) -> Completion:
        """Read a successful response as a completion.

        Args:
            response: The server's response.
            seconds: The request's wall time.

        Returns:
            The completion.

        Raises:
            VlmError: If the body holds no assistant text.
        """
        payload: Mapping[str, object] = {}
        with contextlib.suppress(ValueError):
            payload = _mapping(response.json())
        choices = payload.get("choices")
        listed = cast("list[object]", choices) if isinstance(choices, list) else []
        first: Mapping[str, object] = _mapping(listed[0]) if listed else {}
        text = _mapping(first.get("message")).get("content")
        if not isinstance(text, str):
            raise VlmError(f"the reply of the VLM server at {self._url} holds no completion")

        usage = _mapping(payload.get("usage"))
        timings = _mapping(payload.get("timings"))
        cached = _count(_mapping(usage.get("prompt_tokens_details")).get("cached_tokens"))
        finish = first.get("finish_reason")
        return Completion(
            text=text,
            finish_reason=finish if isinstance(finish, str) else None,
            prompt_tokens=_count(usage.get("prompt_tokens")),
            completion_tokens=_count(usage.get("completion_tokens")),
            cached_tokens=cached if cached is not None else _count(timings.get("cache_n")),
            seconds=seconds,
            prompt_seconds=_milliseconds(timings.get("prompt_ms")),
            generation_seconds=_milliseconds(timings.get("predicted_ms")),
            tokens_per_second=_number(timings.get("predicted_per_second")),
        )
