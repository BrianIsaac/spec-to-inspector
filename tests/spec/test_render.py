"""Tests for the rendering of a specification's Markdown to HTML and PDF."""

import shutil
import stat
from pathlib import Path

import pytest

from spec_to_inspector.spec.render import (
    CHROME,
    RenderError,
    print_pdf,
    render_html,
    render_specification,
)

SOURCE = """\
# A "small" specification

Written for a test.

## 1 Calibration and zones

### 1.1 Zones

Zones are rectangles.

![The zones.](figures/zones.jpg "visa:pcb9/Data/Images/Normal/0001.JPG#zones")

---

## 2 Acceptance criteria for part PCB9

### 2.1 Scratch

A scratch is rejected when 1 < 2.

| Clause | Limit |
| --- | --- |
| 2.1 | > 1.0 mm |

![A scratch.](figures/scratch.jpg "visa:pcb9/Data/Images/Anomaly/007.JPG#mask=2")
"""


def test_the_html_is_a_whole_document_titled_and_based_where_its_figures_are() -> None:
    """The page carries the title, British English, the base for figures and the footer."""
    html = render_html(SOURCE, base=Path("/somewhere/specs"))

    assert html.startswith("<!doctype html>")
    assert '<html lang="en-GB">' in html
    assert "<title>A &quot;small&quot; specification</title>" in html
    assert '<base href="file:///somewhere/specs/">' in html
    assert 'content: "A \\"small\\" specification' in html
    assert "counter(page)" in html


def test_headings_keep_their_levels_and_clauses_are_kept_whole() -> None:
    """Each level-3 heading opens a section; those under acceptance criteria are clauses."""
    html = render_html(SOURCE, base=Path("/x"))

    assert "<h1>A &quot;small&quot; specification</h1>" in html
    assert "<h2>1 Calibration and zones</h2>" in html
    assert '<section class="block">\n<h3>1.1 Zones</h3>' in html
    assert '<section class="clause">\n<h3>2.1 Scratch</h3>' in html
    assert html.count("<section") == html.count("</section>") == 2
    assert html.index("</section>") < html.index("<hr") < html.index("<h2>2 Acceptance criteria")


def test_figures_rules_and_tables_are_rendered_for_print() -> None:
    """A lone image is a captioned figure, a rule is a page break, a table keeps its cells."""
    html = render_html(SOURCE, base=Path("/x"))

    assert (
        '<p class="figure"><img src="figures/scratch.jpg" alt="A scratch.">'
        '<span class="caption">A scratch.</span></p>'
    ) in html
    assert "visa:" not in html
    assert '<hr class="page-break"' in html
    assert "<td>&gt; 1.0 mm</td>" in html
    assert "1 &lt; 2" in html


def fake_chrome(directory: Path, body: str) -> str:
    """Write an executable shell script standing in for Chrome.

    Args:
        directory: Where to write it.
        body: The script's commands; `$out` is the PDF path asked for.

    Returns:
        The script's path.
    """
    script = directory / "fake-chrome"
    script.write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do case "$arg" in --print-to-pdf=*) out="${arg#--print-to-pdf=}";; '
        "esac; done\n"
        f'printf "%s\\n" "$@" > "{directory}/args.txt"\n{body}\n',
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return str(script)


def test_printing_runs_chrome_headless_with_an_outline_and_its_own_profile(
    tmp_path: Path,
) -> None:
    """Chrome is asked for a headless print with a PDF outline, never the user's profile."""
    html, pdf = tmp_path / "page.html", tmp_path / "out" / "page.pdf"
    html.write_text("<p>x</p>", encoding="utf-8")
    chrome = fake_chrome(tmp_path, 'printf "%%PDF-1.4 fake" > "$out"')

    print_pdf(html, pdf, chrome=chrome)

    args = (tmp_path / "args.txt").read_text(encoding="utf-8").splitlines()
    assert pdf.read_bytes().startswith(b"%PDF")
    assert "--headless" in args
    assert "--generate-pdf-document-outline" in args
    assert "--no-pdf-header-footer" in args
    assert args[-1] == html.as_uri()
    (profile,) = [arg for arg in args if arg.startswith("--user-data-dir=")]
    assert not Path(profile.removeprefix("--user-data-dir=")).exists()


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        ('echo "boom" >&2; exit 3', "boom"),
        ("exit 0", "wrote no PDF"),
        ('printf "not a pdf" > "$out"', "wrote no PDF"),
    ],
)
def test_a_failed_print_raises_with_the_cause(tmp_path: Path, body: str, reason: str) -> None:
    """A non-zero exit, a missing file or a file that is not a PDF is an error."""
    html = tmp_path / "page.html"
    html.write_text("<p>x</p>", encoding="utf-8")

    with pytest.raises(RenderError, match=reason):
        print_pdf(html, tmp_path / "page.pdf", chrome=fake_chrome(tmp_path, body))


def test_a_missing_chrome_is_named(tmp_path: Path) -> None:
    """Without the browser the error says which executable was wanted."""
    html = tmp_path / "page.html"
    html.write_text("<p>x</p>", encoding="utf-8")

    with pytest.raises(RenderError, match="no-such-chrome"):
        print_pdf(html, tmp_path / "page.pdf", chrome="no-such-chrome")


@pytest.mark.skipif(shutil.which(CHROME) is None, reason=f"{CHROME} is not installed")
def test_the_real_browser_prints_a_specification_to_pdf(tmp_path: Path) -> None:
    """Headless Chrome prints the Markdown to a PDF beside it, leaving no HTML behind."""
    source = tmp_path / "small.md"
    source.write_text(SOURCE.replace("![", "[").replace("](figures", "](#"), encoding="utf-8")

    pdf = render_specification(source)

    assert pdf == tmp_path / "small.pdf"
    assert pdf.read_bytes().startswith(b"%PDF")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["small.md", "small.pdf"]
