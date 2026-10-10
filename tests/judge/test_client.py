"""Tests for the OpenAI-compatible client, against a fake server on a local port."""

import pytest

from spec_to_inspector.judge.client import ChatClient, Completion, VlmError
from tests.judge.fake_vlm import FakeVlm, Reply

MESSAGES = [
    {"role": "system", "content": "You are an inspector."},
    {"role": "user", "content": [{"type": "text", "text": "What is this?"}]},
]
SCHEMA = {"type": "object", "properties": {"reason": {"type": "string"}}}


def test_a_completion_comes_back_with_its_text_and_its_counts() -> None:
    """The assistant's text, the token counts and the client's own clock are returned."""
    with FakeVlm(['{"reason": "a lump of solder"}']) as server, ChatClient(server.url, "m") as vlm:
        completion = vlm.complete(MESSAGES)

    assert isinstance(completion, Completion)
    assert completion.text == '{"reason": "a lump of solder"}'
    assert completion.finish_reason == "stop"
    assert completion.prompt_tokens == 2100
    assert completion.completion_tokens == 30
    assert completion.cached_tokens is None
    assert completion.seconds > 0
    assert completion.tokens_per_second is None


def test_the_request_is_an_openai_chat_completion() -> None:
    """Any OpenAI-compatible server understands the request: nothing in it is one vendor's."""
    with FakeVlm(["{}"]) as server, ChatClient(server.url, "qwen3-vl") as vlm:
        vlm.complete(MESSAGES, schema=SCHEMA, max_tokens=99)

    assert server.paths == ["/v1/chat/completions"]
    (request,) = server.requests
    assert request == {
        "model": "qwen3-vl",
        "messages": MESSAGES,
        "temperature": 0,
        "max_tokens": 99,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "judge_answer", "strict": True, "schema": SCHEMA},
        },
    }


def test_without_a_schema_the_output_is_not_constrained() -> None:
    """A request with no schema carries no response format."""
    with FakeVlm(["free text"]) as server, ChatClient(server.url, "m") as vlm:
        vlm.complete(MESSAGES)

    assert "response_format" not in server.requests[0]
    assert "cache_prompt" not in server.requests[0]


@pytest.mark.parametrize("cache", [True, False])
def test_the_prompt_cache_can_be_set_for_one_request(cache: bool) -> None:
    """llama.cpp's per-request switch is sent only when asked for."""
    with FakeVlm(["{}"]) as server, ChatClient(server.url, "m") as vlm:
        vlm.complete(MESSAGES, cache_prompt=cache)

    assert server.requests[0]["cache_prompt"] is cache


def test_llama_cpp_timings_are_read_when_the_server_gives_them() -> None:
    """The server's own clock and its cache count come back beside the client's."""
    reply = Reply(
        "{}",
        usage={
            "prompt_tokens": 2100,
            "completion_tokens": 30,
            "prompt_tokens_details": {"cached_tokens": 1900},
        },
        timings={
            "cache_n": 1900,
            "prompt_n": 200,
            "prompt_ms": 250.0,
            "predicted_n": 30,
            "predicted_ms": 600.0,
            "predicted_per_second": 50.0,
        },
    )
    with FakeVlm([reply]) as server, ChatClient(server.url, "m") as vlm:
        completion = vlm.complete(MESSAGES)

    assert completion.cached_tokens == 1900
    assert completion.prompt_seconds == 0.25
    assert completion.generation_seconds == 0.6
    assert completion.tokens_per_second == 50.0


def test_a_server_that_is_down_is_an_error_with_the_cause() -> None:
    """A closed port is reported in words, with the address that was dialled."""
    with FakeVlm() as server:
        url = server.url

    with ChatClient(url, "m") as vlm, pytest.raises(VlmError, match="cannot reach") as caught:
        vlm.complete(MESSAGES)

    assert url in str(caught.value)


def test_a_server_that_does_not_answer_in_time_is_an_error() -> None:
    """The timeout is the settings', and the message states it."""
    with (
        FakeVlm([Reply("{}", delay_seconds=0.5)]) as server,
        ChatClient(server.url, "m", timeout_seconds=0.1) as vlm,
        pytest.raises(VlmError, match=r"did not answer within 0\.1 s"),
    ):
        vlm.complete(MESSAGES)


def test_an_http_error_is_an_error_with_the_status_and_the_servers_words() -> None:
    """The server's own message is kept, cut short."""
    reply = Reply(status=500, body='{"error": {"message": "the context is full"}}')
    with (
        FakeVlm([reply]) as server,
        ChatClient(server.url, "m") as vlm,
        pytest.raises(VlmError, match="HTTP 500") as caught,
    ):
        vlm.complete(MESSAGES)

    assert "the context is full" in str(caught.value)


@pytest.mark.parametrize(
    "body",
    [
        "not json",
        "[]",
        "{}",
        '{"choices": []}',
        '{"choices": [{"message": {"content": null}}]}',
        '{"choices": [{"message": {"content": 7}}]}',
        '{"choices": [{"message": "text"}]}',
    ],
)
def test_a_reply_without_a_completion_is_an_error(body: str) -> None:
    """A 200 that carries no assistant text is not passed on as an empty answer."""
    with (
        FakeVlm([Reply(body=body)]) as server,
        ChatClient(server.url, "m") as vlm,
        pytest.raises(VlmError, match="no completion"),
    ):
        vlm.complete(MESSAGES)


def test_counts_of_the_wrong_type_are_left_out_not_guessed() -> None:
    """A usage block the client cannot read gives no counts, and the text still comes back."""
    reply = Reply("{}", usage={"prompt_tokens": "many"}, timings={"predicted_per_second": "fast"})
    with FakeVlm([reply]) as server, ChatClient(server.url, "m") as vlm:
        completion = vlm.complete(MESSAGES)

    assert completion.text == "{}"
    assert completion.prompt_tokens is None
    assert completion.completion_tokens is None
    assert completion.tokens_per_second is None
