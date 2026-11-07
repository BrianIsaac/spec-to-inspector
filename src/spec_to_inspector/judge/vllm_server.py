"""Which server answered: a vLLM server in its container, read from where each fact lives.

vLLM's endpoints say what they can: `GET /version` its version, `GET /v1/models` the model it
serves, the weights' path and its context, and `GET /metrics` its prefix-cache counters. They do not
say which image it runs in, or its precision. The container says the first, through `docker
inspect`. Its labels are Intel's, naming the base image's date and revision and not the tag or the
digest, so those come from the fields Docker keeps beside the labels. The precision comes from the
engine's own line in the server's log, which is what it runs at; the command line is only what it
was asked for.

The log is also the void rule's: `Prefix cache hit rate` is printed there every ten seconds while
the server is busy. With the cache off from the server's start the counters stay at 0 of 0, so the
rate can only be read as those lines give it, and `hits` alone is the exact count.
"""

import json
import re
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Final, NamedTuple, cast
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict

OWN_MINIMUM: Final = "the model's own minimum"
UNKNOWN: Final = "unknown"
LOG_INTERVAL_SECONDS: Final = 10.0
"""How often vLLM prints its figures; a run's last line comes up to this long after its answer."""
_TIMEOUT_SECONDS: Final = 5.0
_LOG_TIMEOUT_SECONDS: Final = 60.0
_PIXELS_PER_TOKEN: Final = 32 * 32
_COLD_FLAGS: Final = ("--no-enable-prefix-caching", "--mm-processor-cache-gb 0")
_VERSION_LABEL: Final = "org.opencontainers.image.version"
_REVISION_LABEL: Final = "org.opencontainers.image.revision"
_HIT_RATE: Final = re.compile(r"Prefix cache hit rate: ([0-9.]+)%")
_ENGINE_LINE: Final = re.compile(r"Initializing a V1 LLM engine .*")
_ENGINE_DTYPE: Final = re.compile(r"\bdtype=torch\.(\w+)")
_ENGINE_PREFIX_CACHING: Final = re.compile(r"\benable_prefix_caching=(True|False)")
_FLAG_DTYPE: Final = re.compile(r"--dtype[= ](\w+)")
_FLAG_PORT: Final = re.compile(r"--port[= ](\d+)")
_SHORTEST_EDGE: Final = re.compile(r'"shortest_edge":\s*(\d+)')
_SNAPSHOT: Final = re.compile(r"/snapshots/([0-9a-f]{40})")
_DEFAULT_PORTS: Final = {"http": 80, "https": 443}


class PrefixCacheCounters(NamedTuple):
    """vLLM's two prefix-cache counters, in tokens, since the server started.

    Attributes:
        hits: Tokens found in the cache.
        queries: Tokens looked for in it; none while the cache is off.
    """

    hits: int
    queries: int


class ServerReading(BaseModel):
    """What was read of the server that is answering.

    Attributes:
        facts: Each fact found, as text. It holds nothing that a restart changes, so two runs of
            one setting on either side of a restart have the same facts.
        sources: Where each of the facts was read from.
        image_min_tokens: The fewest tokens the server gives an image, from its command line.
        cold_flags: Those of the switches that keep the prefix cache off which its command line has.
        engine_prefix_caching: Whether the engine says its prefix cache is on; None if the line is
            not in the log.
        started_at: When the container started, as Docker gives it.
    """

    model_config = ConfigDict(frozen=True)

    facts: dict[str, str]
    sources: dict[str, str]
    image_min_tokens: str
    cold_flags: tuple[str, ...]
    engine_prefix_caching: bool | None
    started_at: str | None


def _docker(
    program: str | None, arguments: Sequence[str], *, with_stderr: bool, timeout_seconds: float
) -> str | None:
    """Run a Docker command and give what it printed.

    Args:
        program: The path of `docker`; None where there is none.
        arguments: Its arguments.
        with_stderr: Whether to take standard error with the output, as a container's log needs.
        timeout_seconds: How long it may take.

    Returns:
        What it printed, or None if it could not be run or failed.
    """
    if program is None:
        return None
    try:
        done = subprocess.run(
            [program, *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if with_stderr else subprocess.DEVNULL,
            text=True,
            errors="replace",
            timeout=timeout_seconds,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout


def _inspected(program: str | None, *arguments: str) -> Mapping[str, object] | None:
    """Read the first object `docker inspect` or `docker image inspect` prints.

    Args:
        program: The path of `docker`.
        *arguments: The command, without the program.

    Returns:
        The object, or None if there is none.
    """
    printed = _docker(program, arguments, with_stderr=False, timeout_seconds=_TIMEOUT_SECONDS)
    if printed is None:
        return None
    try:
        listing: object = json.loads(printed)
    except ValueError:
        return None
    if isinstance(listing, list) and listing and isinstance(listing[0], dict):
        return cast("Mapping[str, object]", listing[0])
    return None


def _section(parent: Mapping[str, object], name: str) -> Mapping[str, object]:
    """Take a nested object out of what Docker printed.

    Args:
        parent: The object holding it.
        name: Its name.

    Returns:
        The nested object, empty if it is not one.
    """
    value = parent.get(name)
    return cast("Mapping[str, object]", value) if isinstance(value, dict) else {}


def _get_json(url: str) -> Mapping[str, object]:
    """Read a JSON object from an endpoint.

    Args:
        url: The endpoint.

    Returns:
        The object; empty if the server does not answer with one.
    """
    try:
        response = httpx.get(url, timeout=_TIMEOUT_SECONDS)
        payload: object = response.json() if response.is_success else {}
    except (httpx.HTTPError, ValueError):
        return {}
    return cast("Mapping[str, object]", payload) if isinstance(payload, dict) else {}


def _from_endpoints(url: str) -> tuple[dict[str, str], dict[str, str]]:
    """Read what vLLM says of itself.

    Args:
        url: The server's base URL, up to and including `/v1`.

    Returns:
        The facts found, and where each was read from.
    """
    facts: dict[str, str] = {}
    sources: dict[str, str] = {}
    version = _get_json(f"{url.removesuffix('/v1')}/version").get("version")
    if isinstance(version, str):
        facts["vllm_version"] = version
        sources["vllm_version"] = "GET /version"
    data = _get_json(f"{url}/models").get("data")
    first = cast("list[object]", data)[0] if isinstance(data, list) and data else None
    if isinstance(first, dict):
        model = cast("Mapping[str, object]", first)
        root = model.get("root")
        revision = _SNAPSHOT.search(root) if isinstance(root, str) else None
        found = {
            "served_model": model.get("id"),
            "weights_revision": revision.group(1) if revision else None,
            "max_model_len": model.get("max_model_len"),
        }
        for key, value in found.items():
            if value is not None:
                facts[key] = str(value)
                sources[key] = "GET /v1/models"
    return facts, sources


def _serves_this_port(command: str, url: str) -> bool:
    """Tell whether a container's command serves the port a URL names.

    Args:
        command: The container's command line.
        url: The server's URL.

    Returns:
        True if the command asks for that port: a container that does not cannot be what answers.
    """
    parts = urlsplit(url)
    port = _FLAG_PORT.search(command)
    wanted = parts.port or _DEFAULT_PORTS.get(parts.scheme)
    return port is not None and int(port.group(1)) == wanted


def _image_min_tokens(command: str) -> str:
    """Find the fewest tokens the server gives an image, from its command line.

    Args:
        command: The container's command line.

    Returns:
        The tokens that the smallest edge setting comes to, or the model's own minimum without it.
    """
    edge = _SHORTEST_EDGE.search(command)
    return str(int(edge.group(1)) // _PIXELS_PER_TOKEN) if edge else OWN_MINIMUM


def _engine_says(log: str) -> tuple[str | None, bool | None]:
    """Read the engine's line in the server's log.

    Args:
        log: The log from the server's start.

    Returns:
        The engine's precision and whether its prefix cache is on; None for what is not there.
    """
    line = _ENGINE_LINE.search(log)
    if line is None:
        return None, None
    dtype = _ENGINE_DTYPE.search(line.group(0))
    caching = _ENGINE_PREFIX_CACHING.search(line.group(0))
    return (
        dtype.group(1) if dtype else None,
        caching.group(1) == "True" if caching else None,
    )


def read_server(
    url: str, container: str, *, docker: str | None = shutil.which("docker")
) -> ServerReading:
    """Read which server is answering at a URL.

    Args:
        url: The server's base URL, up to and including `/v1`.
        container: The name of the container it is expected to run in.
        docker: The path of `docker`; None where there is none.

    Returns:
        What could be read. What could not is left out, for the record to say so; the container's
        facts are left out if it is not running or does not serve the URL's port.
    """
    facts, sources = _from_endpoints(url)
    inspected = _inspected(docker, "inspect", "--type", "container", container)
    state: Mapping[str, object] = {} if inspected is None else _section(inspected, "State")
    arguments = None if inspected is None else inspected.get("Args")
    command = (
        " ".join(" ".join(str(a) for a in cast("list[object]", arguments)).split())
        if isinstance(arguments, list)
        else ""
    )
    if inspected is None or state.get("Running") is not True or not _serves_this_port(command, url):
        return ServerReading(
            facts=facts,
            sources=sources,
            image_min_tokens=UNKNOWN,
            cold_flags=(),
            engine_prefix_caching=None,
            started_at=None,
        )

    config = _section(inspected, "Config")
    labels = _section(config, "Labels")
    image_id = inspected.get("Image")
    image = _inspected(docker, "image", "inspect", str(image_id))
    digests = None if image is None else image.get("RepoDigests")
    digest = (
        str(cast("list[object]", digests)[0]).rpartition("@")[2]
        if isinstance(digests, list) and digests
        else None
    )
    found: dict[str, tuple[object, str]] = {
        "image": (config.get("Image"), "docker inspect, Config.Image"),
        "image_digest": (
            digest or image_id,
            "docker image inspect, RepoDigests" if digest else "docker inspect, Image",
        ),
        "image_label_version": (labels.get(_VERSION_LABEL), f"container label {_VERSION_LABEL}"),
        "image_label_revision": (
            labels.get(_REVISION_LABEL),
            f"container label {_REVISION_LABEL}",
        ),
        "command": (command, "docker inspect, Args"),
    }
    log = _docker(
        docker, ("logs", container), with_stderr=True, timeout_seconds=_LOG_TIMEOUT_SECONDS
    )
    dtype, caching = _engine_says(log or "")
    if dtype is not None:
        found["dtype"] = (dtype, "the server's log, the engine's line, dtype=torch.*")
    else:
        asked = _FLAG_DTYPE.search(command)
        found["dtype"] = (asked.group(1) if asked else None, "docker inspect, Args, --dtype")
    for key, (value, source) in found.items():
        if value is not None:
            facts[key] = str(value)
            sources[key] = source
    started = state.get("StartedAt")
    return ServerReading(
        facts=facts,
        sources=sources,
        image_min_tokens=_image_min_tokens(command),
        cold_flags=tuple(flag for flag in _COLD_FLAGS if flag in command),
        engine_prefix_caching=caching,
        started_at=started if isinstance(started, str) else None,
    )


def parse_counters(text: str) -> PrefixCacheCounters | None:
    """Read the prefix-cache counters from what `GET /metrics` prints.

    Args:
        text: The metrics, in Prometheus's text format.

    Returns:
        Each counter summed over the engines, or None if either is not there.
    """
    totals: dict[str, float] = {}
    for line in text.splitlines():
        name, _, rest = line.partition("{")
        if name in {"vllm:prefix_cache_hits_total", "vllm:prefix_cache_queries_total"}:
            try:
                totals[name] = totals.get(name, 0.0) + float(rest.rpartition(" ")[2])
            except ValueError:
                return None
    if len(totals) < 2:
        return None
    return PrefixCacheCounters(
        hits=round(totals["vllm:prefix_cache_hits_total"]),
        queries=round(totals["vllm:prefix_cache_queries_total"]),
    )


def read_counters(url: str) -> PrefixCacheCounters | None:
    """Read a server's prefix-cache counters.

    Args:
        url: The server's base URL, up to and including `/v1`.

    Returns:
        The counters, or None if they cannot be read.
    """
    try:
        response = httpx.get(f"{url.removesuffix('/v1')}/metrics", timeout=_TIMEOUT_SECONDS)
    except httpx.HTTPError:
        return None
    return parse_counters(response.text) if response.is_success else None


def read_log(
    container: str, since: datetime, *, docker: str | None = shutil.which("docker")
) -> str | None:
    """Read a container's log from a moment on.

    Args:
        container: The container's name.
        since: The moment; Docker reads it to the second, so a line of that second is included.
        docker: The path of `docker`; None where there is none.

    Returns:
        The log, or None if it cannot be read.
    """
    moment = since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _docker(
        docker,
        ("logs", "--since", moment, container),
        with_stderr=True,
        timeout_seconds=_LOG_TIMEOUT_SECONDS,
    )


def log_hit_rates(log: str) -> list[float]:
    """Find every prefix-cache hit rate a server's log prints.

    Args:
        log: The log.

    Returns:
        The rates, as percentages, in the order printed.
    """
    return [float(rate) for rate in _HIT_RATE.findall(log)]
