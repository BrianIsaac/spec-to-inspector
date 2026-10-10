"""A fake OpenAI-compatible chat server on a local port, for the judge's contract tests.

It is a real HTTP server on the loopback interface, so the client under test
is exercised through its whole network path: the request it records is the
request a real server would have received.
"""

import json
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Self, cast


@dataclass(frozen=True)
class Reply:
    """One scripted reply.

    Attributes:
        content: The assistant's text, when the reply is a completion.
        status: The HTTP status.
        body: The raw body to send instead of a completion.
        delay_seconds: How long to wait before answering.
        usage: The `usage` object of the completion.
        timings: llama.cpp's `timings` object, if the fake plays that server.
    """

    content: str = ""
    status: int = 200
    body: str | None = None
    delay_seconds: float = 0.0
    usage: dict[str, Any] = field(
        default_factory=lambda: {"prompt_tokens": 2100, "completion_tokens": 30}
    )
    timings: dict[str, Any] | None = None


class FakeVlm:
    """A chat-completions server that answers from a script and records what it was asked.

    Attributes:
        requests: The JSON body of every request received, in order.
        paths: The path of every request received, in order.
    """

    def __init__(self, replies: Iterable[str | Reply] = (), *, default: str | None = None) -> None:
        """Set the script.

        Args:
            replies: The replies to give, in order; a string is a completion's text.
            default: The completion's text once the script runs out; without
                one the server then answers HTTP 500.
        """
        self._replies = [Reply(reply) if isinstance(reply, str) else reply for reply in replies]
        self._default = default
        self._lock = threading.Lock()
        self.requests: list[dict[str, Any]] = []
        self.paths: list[str] = []
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length", "0"))
                body = cast("dict[str, Any]", json.loads(self.rfile.read(length)))
                reply = fake.next_reply(self.path, body)
                time.sleep(reply.delay_seconds)
                payload = fake.payload(reply, body).encode()
                try:
                    self.send_response(reply.status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, format: str, *args: object) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    def next_reply(self, path: str, body: dict[str, Any]) -> Reply:
        """Record a request and take the next reply of the script.

        Args:
            path: The request's path.
            body: The request's JSON body.

        Returns:
            The reply to give.
        """
        with self._lock:
            self.paths.append(path)
            self.requests.append(body)
            if self._replies:
                return self._replies.pop(0)
        if self._default is not None:
            return Reply(self._default)
        return Reply(status=500, body='{"error": {"message": "no reply scripted"}}')

    @staticmethod
    def payload(reply: Reply, body: dict[str, Any]) -> str:
        """Lay a reply out as the server's response body.

        Args:
            reply: The scripted reply.
            body: The request it answers.

        Returns:
            The raw body if one was scripted, else an OpenAI chat completion.
        """
        if reply.body is not None:
            return reply.body
        completion: dict[str, Any] = {
            "id": "chatcmpl-fake",
            "object": "chat.completion",
            "model": body.get("model"),
            "choices": [
                {
                    "index": 0,
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": reply.content},
                }
            ],
            "usage": reply.usage,
        }
        if reply.timings is not None:
            completion["timings"] = reply.timings
        return json.dumps(completion)

    @property
    def url(self) -> str:
        """The server's base URL, up to and including `/v1`."""
        return f"http://127.0.0.1:{self._server.server_address[1]}/v1"

    def __enter__(self) -> Self:
        """Start serving.

        Returns:
            The running fake.
        """
        self._thread.start()
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        """Stop serving and free the port."""
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()
