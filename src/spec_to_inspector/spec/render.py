"""The specification's Markdown, printed to PDF by headless Chrome.

The Markdown is rendered to one HTML page (headings keep their levels, each
clause is a section that is never split across pages, a lone image is a
captioned figure, a rule is a page break) and printed with the installed
`google-chrome --headless`, in a throwaway profile, with a PDF outline so
the parser can read heading levels from the bookmarks. One command rebuilds
the PDF:

    uv run python -m spec_to_inspector.spec.render [--figures] [specs/pcb-spec.md]

`--figures` first rebuilds the figures from `data/visa`.
"""

import argparse
import html
import shutil
import subprocess
import tempfile
from collections.abc import Sequence
from importlib import resources
from pathlib import Path
from typing import Final

from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict

from spec_to_inspector.settings import Settings
from spec_to_inspector.spec.extract import SpecificationError
from spec_to_inspector.spec.figures import FigureError, build_figures
from spec_to_inspector.spec.markdown import is_figure, markdown_parser, plain_text

CHROME: Final = "google-chrome"
DEFAULT_SOURCE: Final = Path("specs/pcb-spec.md")
FOOTER_NOTE: Final = "demonstration document written for the Spec to Inspector entry"
PRINT_TIMEOUT_SECONDS: Final = 120

_CRITERIA_PREFIX: Final = "acceptance criteria"


class RenderError(RuntimeError):
    """The specification could not be printed to PDF."""


def _image(
    renderer: RendererHTML, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
) -> str:
    """Render an image with its caption; the title, which names its source, is not printed.

    Args:
        renderer: The HTML renderer.
        tokens: The inline tokens.
        idx: The image's position among them.
        options: The parser's options.
        env: The parse environment.

    Returns:
        The image element followed by its caption.
    """
    token = tokens[idx]
    source, caption = html.escape(str(token.attrGet("src") or "")), html.escape(token.content)
    return f'<img src="{source}" alt="{caption}"><span class="caption">{caption}</span>'


def _render_body(text: str) -> tuple[str, str]:
    """Render a Markdown source to the HTML of the page's body.

    Args:
        text: The Markdown source.

    Returns:
        The body's HTML and the document's title, as plain text.
    """
    parser = markdown_parser()
    parser.add_render_rule("image", _image)
    tokens = parser.parse(text)
    parts: list[str] = []
    title, start, in_section, in_criteria = "", 0, False, False
    for index, token in enumerate(tokens):
        if token.type in ("heading_open", "hr"):
            parts.append(parser.renderer.render(tokens[start:index], parser.options, {}))
            start = index
            if in_section:
                parts.append("</section>\n")
                in_section = False
        if token.type == "heading_open":
            heading = plain_text(tokens[index + 1])
            if token.tag == "h1" and not title:
                title = heading
            elif token.tag == "h2":
                in_criteria = _CRITERIA_PREFIX in heading.casefold()
            elif token.tag == "h3":
                parts.append(f'<section class="{"clause" if in_criteria else "block"}">\n')
                in_section = True
        elif token.type == "paragraph_open" and is_figure(tokens[index + 1]):
            token.attrSet("class", "figure")
        elif token.type == "hr":
            token.attrSet("class", "page-break")
    parts.append(parser.renderer.render(tokens[start:], parser.options, {}))
    if in_section:
        parts.append("</section>\n")
    return "".join(parts), title


def render_html(text: str, *, base: Path) -> str:
    """Render a specification's Markdown source to a whole HTML page for print.

    Args:
        text: The Markdown source.
        base: The directory the source's figure paths are relative to.

    Returns:
        The HTML document, with the print stylesheet inline and the title
        and page number in every page's footer.
    """
    body, title = _render_body(text)
    stylesheet = resources.files("spec_to_inspector.spec").joinpath("pdf.css").read_text("utf-8")
    footer = f"{title}: {FOOTER_NOTE}".replace("\\", "\\\\").replace('"', '\\"')
    return (
        "<!doctype html>\n"
        '<html lang="en-GB">\n<head>\n<meta charset="utf-8">\n'
        f"<title>{html.escape(title)}</title>\n"
        f'<base href="{base.resolve().as_uri()}/">\n'
        f"<style>\n{stylesheet}\n"
        "@page {\n"
        f'  @bottom-left {{ content: "{footer}"; font-size: 7.5pt; color: #555; }}\n'
        '  @bottom-right { content: "Page " counter(page) " of " counter(pages); '
        "font-size: 7.5pt; color: #555; }\n"
        "}\n</style>\n</head>\n"
        f"<body>\n{body}</body>\n</html>\n"
    )


def print_pdf(html_path: Path, pdf_path: Path, *, chrome: str = CHROME) -> None:
    """Print an HTML file to PDF with headless Chrome, in a profile of its own.

    Args:
        html_path: The HTML file.
        pdf_path: Where the PDF goes; replaced only when the print succeeds.
        chrome: The browser's executable.

    Raises:
        RenderError: If the browser is missing, fails, runs out of time, or
            writes no PDF.
    """
    with tempfile.TemporaryDirectory(prefix="spec-render-") as scratch:
        printed = Path(scratch) / "printed.pdf"
        command = [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-first-run",
            "--no-pdf-header-footer",
            "--generate-pdf-document-outline",
            f"--user-data-dir={Path(scratch) / 'profile'}",
            f"--print-to-pdf={printed}",
            html_path.resolve().as_uri(),
        ]
        try:
            done = subprocess.run(
                command, capture_output=True, text=True, timeout=PRINT_TIMEOUT_SECONDS, check=False
            )
        except FileNotFoundError as error:
            raise RenderError(f"the browser {chrome!r} is not installed") from error
        except subprocess.TimeoutExpired as error:
            raise RenderError(
                f"{chrome} did not finish printing in {PRINT_TIMEOUT_SECONDS} s"
            ) from error
        if done.returncode != 0:
            raise RenderError(f"{chrome} exited {done.returncode}: {done.stderr.strip()[-500:]}")
        if not printed.is_file() or not printed.read_bytes().startswith(b"%PDF"):
            raise RenderError(f"{chrome} wrote no PDF: {done.stderr.strip()[-500:]}")
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(printed, pdf_path)


def render_specification(
    markdown_path: Path, pdf_path: Path | None = None, *, chrome: str = CHROME
) -> Path:
    """Print a specification's Markdown source to PDF.

    Args:
        markdown_path: The Markdown source; its figures are read relative to it.
        pdf_path: Where the PDF goes; beside the source, with its name, by default.
        chrome: The browser's executable.

    Returns:
        The PDF's path.

    Raises:
        RenderError: If the print fails.
    """
    target = pdf_path if pdf_path is not None else markdown_path.with_suffix(".pdf")
    page = render_html(markdown_path.read_text(encoding="utf-8"), base=markdown_path.parent)
    with tempfile.TemporaryDirectory(prefix="spec-html-") as scratch:
        html_path = Path(scratch) / f"{markdown_path.stem}.html"
        html_path.write_text(page, encoding="utf-8")
        print_pdf(html_path, target, chrome=chrome)
    return target


def main(argv: Sequence[str] | None = None) -> int:
    """Rebuild a specification's PDF, and its figures if asked.

    Args:
        argv: The command line, without the program name.

    Returns:
        The exit code: 0 when the PDF was written, 1 otherwise.
    """
    parser = argparse.ArgumentParser(
        prog="python -m spec_to_inspector.spec.render",
        description="Print a specification's Markdown source to PDF with headless Chrome.",
    )
    parser.add_argument("source", nargs="?", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument(
        "--figures", action="store_true", help="first rebuild the figures from data/visa"
    )
    args = parser.parse_args(argv)
    try:
        if args.figures:
            for figure in build_figures(args.source, visa_dir=Settings().visa_dir):
                print(f"figure {figure}")
        print(f"pdf {render_specification(args.source)}")
    except (RenderError, FigureError, SpecificationError, OSError) as error:
        print(f"render failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
