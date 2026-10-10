"""What `scripts/serve_vlm.sh` needs from the settings, one value per line.

The script starts llama.cpp's server on the laptop; where the weights and
the build live, and the address it listens on, are settings like every other
path, so the script asks for them here instead of reading `.env` itself.
"""

from urllib.parse import urlsplit

from spec_to_inspector.settings import Settings

DEFAULT_PORTS = {"http": 80, "https": 443}


def serving_lines(settings: Settings) -> list[str]:
    """List the values the serving script reads, in the order it reads them.

    Args:
        settings: The settings.

    Returns:
        The models directory and the llama.cpp directory as absolute paths,
        then the host, the port and the model name of the VLM server.
    """
    url = urlsplit(settings.vlm_url)
    return [
        str(settings.models_dir.resolve()),
        str(settings.llama_cpp_dir.resolve()),
        url.hostname or "",
        str(url.port or DEFAULT_PORTS[url.scheme]),
        settings.vlm_model,
    ]


if __name__ == "__main__":
    print("\n".join(serving_lines(Settings())))
