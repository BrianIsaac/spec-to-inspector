"""Tests for the page of figures written from a bench record."""

from pathlib import Path

from spec_to_inspector.bench.observe import DigitReason, DigitReasons
from spec_to_inspector.bench.readme import render_readme, summary_lines
from spec_to_inspector.bench.record import (
    BenchRecord,
    BoardOnThreshold,
    OnThreshold,
    compare,
    read_record,
)
from tests.bench.bench_fakes import IMAGE_DIGEST


def test_the_page_gives_each_figure_with_its_count_its_n_and_its_interval(
    record: BenchRecord,
) -> None:
    """The deck's table: strict, per part, lenient, per region, referred, false rejects."""
    page = render_readme(record)

    assert page.startswith("# Stage I: what the laptop prototype measured\n")
    assert (
        "| Clause-citation accuracy, strict, single-defect images | 66.7% (2 of 3) | 3 "
        "| 20.8% to 93.9% |" in page
    )
    assert (
        "| Clause-citation accuracy, strict, single-defect images, pcb4 only | 50.0% (1 of 2) | 2 |"
        in page
    )
    assert "| Clause-citation accuracy, lenient, multi-defect images | 0.0% (0 of 1) | 1 |" in page
    assert "| Good boards rejected (false rejects) | 0.0% (0 of 3) | 3 | 0.0% to 56.1% |" in page
    assert "| Good boards flagged by the anomaly model | 33.3% (1 of 3) | 3 |" in page
    assert record.measured_on in page
    assert "`spec-to-inspector bench`" in page


def test_the_page_says_how_the_run_was_made_and_that_nothing_leaked(record: BenchRecord) -> None:
    """The protocol by digest, the server's setting, cold asking, the empty store."""
    page = render_readme(record)

    assert f"(SHA-256 `{record.protocol[0].sha256[:16]}`)" in page
    assert "image minimum 1024 tokens; GPU Fake GPU; up to 3 areas an image" in page
    assert "Every question asked cold (`cache_prompt` false)" in page
    assert "0 of 7 decisions had a correction in a prompt" in page
    assert "4 anomalous test images: 3 single-defect, 1 multi-defect" in page
    assert "**This is a partial run**" not in page


def test_the_confusion_table_has_a_row_for_each_expected_type(record: BenchRecord) -> None:
    """Columns in the mapping table's order, then why there is no citation."""
    page = render_readme(record)

    assert "pcb4, single-defect images:" in page
    assert "| Expected \\ cited | scratch | not flagged | Images |" in page
    assert "| **missing** | 0 | 1 | 1 |" in page
    assert "| **scratch** | 1 | 0 | 1 |" in page
    assert "| **dirt** | 0 | 1 | 1 |" in page


def test_causes_times_minutes_and_memory_are_on_the_page(record: BenchRecord) -> None:
    """Each of the protocol's remaining figures has its lines."""
    page = render_readme(record)

    assert "By cause: no clause applies 1." in page
    assert "By cause: outside every zone 1." in page
    assert "- Row of the clause table applied: 4.1 1, 5.6.1 1." in page
    assert (
        "| all | 3 | 33.3% (1 of 3) | 0.0% (0 of 3), 0.0% to 56.1% | 33.3% (1 of 3) "
        "| 0.0% (0 of 3) |" in page
    )
    assert "4 flagged images, 5 areas asked (1.25 an image)" in page
    assert "| pcb4 |" in page
    assert "| 720 s |" in page
    assert "| Judging | 8,700 MiB (the VLM server) | 10,000 MiB | 10,000 MiB |" in page
    assert "| Anomaly model scoring, pcb1 | 1,300 MiB (the bench's process) |" in page
    assert "Training pcb1 peaked at 8,192 MiB allocated" in page


def test_a_single_run_says_so_and_a_repeat_says_what_differed(record: BenchRecord) -> None:
    """Without an earlier run there is nothing to compare; with one, the counts are given."""
    assert "This file holds one run." in render_readme(record)

    repeated = record.model_copy(update={"repeat": compare(record, record)})
    page = render_readme(repeated)
    assert "4 images answered on region 1 in both runs: 0 with another heading cited" in page
    assert "Every counted figure of the protocol is equal in the two runs." in page
    assert summary_lines(repeated)[-1].endswith("the figures are equal")


def test_a_partial_run_is_marked_as_not_for_the_deck(record: BenchRecord) -> None:
    """A trial run's page cannot be mistaken for the protocol's figures."""
    page = render_readme(record.model_copy(update={"partial": True, "limit": 5}))
    assert "**This is a partial run** (4 labelled images, the first 5 of each kind per part" in page
    assert summary_lines(record.model_copy(update={"partial": True}))[0].startswith("Partial run")


def test_the_other_image_setting_stands_beside_the_shipped_one(record: BenchRecord) -> None:
    """The comparison declared in the protocol is a table of the two settings."""
    judge = record.judge.model_copy(update={"image_min_tokens": "the model's own minimum"})
    page = render_readme(record, beside=record.model_copy(update={"judge": judge}))

    assert "## The other image setting" in page
    assert (
        "| Figure | Image tokens: 1024 (this page) | Image tokens: the model's own minimum |"
        in page
    )
    assert "| Strict, single-defect images | 66.7% (2 of 3) | 66.7% (2 of 3) |" in page
    assert "## The other image setting" not in render_readme(record)


def test_the_terminal_summary_is_the_three_accuracies_and_the_false_rejects(
    record: BenchRecord,
) -> None:
    """A few lines, each with its N and interval."""
    lines = summary_lines(record)
    assert lines[0] == (
        "Clause-citation accuracy, strict, 3 single-defect images: 66.7% (2 of 3), "
        "95% interval 20.8% to 93.9%"
    )
    assert lines[1].startswith("Lenient, 1 multi-defect images: 0.0% (0 of 1)")
    assert lines[3].startswith("Good boards rejected: 0.0% (0 of 3)")
    assert lines[4] == "Corrections in a prompt: 0 of 7 decisions"


REPOSITORY = Path(__file__).parents[2]


def test_stage_ones_page_is_the_page_it_has_always_been() -> None:
    """Every word of the tracked page comes back from the tracked record."""
    stage1 = REPOSITORY / "results" / "stage1"
    page = render_readme(
        read_record(stage1 / "bench.json"),
        beside=read_record(stage1 / "bench-own-image-tokens.json"),
    )
    assert page == (stage1 / "README.md").read_text(encoding="utf-8")


def test_a_stage_two_run_has_a_page_of_its_own(stage2_record: BenchRecord) -> None:
    """It is the machine's: nothing on it calls it the laptop prototype or sets the two together."""
    page = render_readme(stage2_record)

    assert page.startswith("# Stage II: what the machine measured\n")
    lowered = page.lower()
    for word in ("laptop", "prototype", "nvidia", "cuda", "the deck", "llama", "uv run"):
        assert word not in lowered, word
    assert "Stage I:" not in page
    assert "| Clause-citation accuracy, strict, single-defect images | 66.7% (2 of 3) | 3 " in page
    assert "`cache_prompt` false" not in page


def test_the_stage_two_page_shows_each_of_the_six_things(stage2_record: BenchRecord) -> None:
    """What the protocol asks a final run's record to hold, each where a reader can see it."""
    page = render_readme(stage2_record)

    assert "| Judging | not read (the VLM server) | 29,456 MiB | 29,456 MiB |" in page
    assert "\n\n\nRead from" not in page
    assert "Read from `xpu-smi`" in page
    assert "card 0000:ba:00.0" in page
    assert "xpu-smi ps does not list its process" in page
    for file in stage2_record.protocol:
        assert f"| `{file.path}` | `{file.sha256}` |" in page
    assert "| image | `intel/llm-scaler-vllm:0.26.0-b1` | docker inspect, Config.Image |" in page
    assert f"| image_digest | `{IMAGE_DIGEST}` | docker image inspect, RepoDigests |" in page
    assert "| dtype | `float16` |" in page
    assert "Intel(R) Arc(TM) Pro B70 Graphics" in page
    assert "Its image minimum: 1024 tokens" in page
    assert "`--no-enable-prefix-caching`, `--mm-processor-cache-gb 0`" in page
    assert "the highest of 2 rates in its log is 0.0%" in page
    assert "one question before the judge's clock, on pcb1 bad-000" in page
    checkpoint = stage2_record.runs["pcb4"].checkpoint
    assert checkpoint is not None
    assert checkpoint.sha256 in page
    assert "This run's record holds what the protocol asks of a final run." in page


def test_the_boards_on_the_threshold_have_a_heading_of_their_own(
    stage2_record: BenchRecord,
) -> None:
    """Each with its score and threshold, and the rule said; and a run with none says none."""
    assert "## The boards on the threshold" in render_readme(stage2_record)
    assert "None of this run's boards (pcb1, pcb4) sits on its threshold." in render_readme(
        stage2_record
    )
    board = BoardOnThreshold(
        part="pcb1",
        image_id="bad-029",
        label="bad",
        score=31.319490432739258,
        threshold=31.319488525390625,
        above=True,
    )
    found = OnThreshold(tolerance=1e-3, parts=("pcb1", "pcb4"), boards=(board,))
    page = render_readme(stage2_record.model_copy(update={"on_threshold": found}))

    assert "The rule is a strict `>`." in page
    assert "| pcb1 | `bad-029` | bad | 31.319490 | 31.319489 | yes | yes |" in page


def test_the_boards_the_bench_does_not_score_are_on_the_page_and_say_so(
    stage2_record: BenchRecord,
) -> None:
    """The ruling's other two: never read as this run's own scores, and shown when it has none."""
    page = render_readme(stage2_record)

    assert "None of this run's boards (pcb1, pcb4) sits on its threshold." in page
    assert "| pcb2 | `bad-060` | bad | 29.304890 | 29.304890 | no | no: week 2's record |" in page
    assert "| pcb3 | `bad-097` | bad | 31.543020 | 31.543051 | no | no: week 2's record |" in page
    assert "the bench does not score them" in page


def test_a_stage_two_run_that_lacks_something_says_it_is_not_final(
    stage2_record: BenchRecord,
) -> None:
    """On the page and in the terminal, each thing by name."""
    lacking = stage2_record.model_copy(
        update={"partial": True, "limit": 3, "not_final": ["the warm-up having been asked"]}
    )
    page = render_readme(lacking)

    assert "**This run is not final.**" in page
    assert "- the warm-up having been asked." in page
    assert "**This is a partial run**" in page
    assert "Not yet final: the warm-up having been asked" in summary_lines(lacking)


def test_only_the_designators_comparison_lists_reasons(stage2_record: BenchRecord) -> None:
    """Listed for both runs, with the count, and a size marked where one passed."""
    assert "## The reasons with a digit in them" not in render_readme(stage2_record)
    size = DigitReason(
        part="pcb4",
        image_id="bad-080",
        area=1,
        reason="a mark of R5 mm",
        valid=True,
        followed_by_a_unit=True,
    )
    reasons = DigitReasons(reasons=(size,), followed_by_a_unit=1)
    earlier = stage2_record.model_copy(update={"digit_reasons": reasons})
    second = earlier.model_copy(update={"repeat": compare(earlier, earlier)})
    page = render_readme(second)

    assert "## The reasons with a digit in them" in page
    assert page.count("1 reasons with a digit, of which 1 have a digit followed by a unit") == 2
    assert "| pcb4 | `bad-080` | 1 | yes | **yes** | a mark of R5 mm |" in page
