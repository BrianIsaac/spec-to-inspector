"""The marked bench test: the real command on five labelled images of pcb4.

It needs what the default gate does not have: the fetched VisA data, the
trained pcb4 model under the settings' models directory, the CUDA GPU and the
VLM server up (`scripts/serve_vlm.sh start`). It runs the verb as a user
would, cut down to the first five anomalous and the first five good test
images, into a run directory and files of its own, and checks what it writes;
what the figures are is the whole run's to measure, not this test's to assert.

    uv run pytest -m bench
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from spec_to_inspector.bench.record import read_record
from spec_to_inspector.cli import app
from spec_to_inspector.judge.inspect import load_decision
from spec_to_inspector.settings import Settings

ROOT = Path(__file__).parents[2]
BATCH = "bench-trial"
IMAGES = 5


# docling 2.135.0 warns about fields of its own that it still reads.
@pytest.mark.filterwarnings("ignore::DeprecationWarning")
@pytest.mark.bench
def test_the_command_runs_on_five_images_and_writes_its_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A partial record and its page, a decision per image, and no correction in any prompt."""
    monkeypatch.chdir(ROOT)
    results, page = tmp_path / "bench.json", tmp_path / "README.md"
    arguments = ["bench", "--part", "pcb4", "--limit", str(IMAGES), "--batch", BATCH]
    result = CliRunner().invoke(app, [*arguments, "--results", str(results), "--readme", str(page)])

    assert result.exit_code == 0, result.output
    record = read_record(results)
    assert record.partial
    assert (record.limit, record.parts) == (IMAGES, ["pcb4"])
    assert (record.labels.images, len(record.observations)) == (IMAGES, 2 * IMAGES)
    assert record.specification.equals_tracked_clause_table
    assert record.specification.parse_seconds > 0
    assert record.leak.model_dump() == {"decisions": 2 * IMAGES, "with_corrections_in_prompt": 0}
    assert record.scores.headline.strict.all.n == record.labels.single_defect
    assert record.scores.stale_region_truth == []
    assert record.judge.cache_prompt is False
    assert record.times.areas_asked >= record.times.flagged_images > 0
    assert record.judge_memory.samples > 0

    run = Settings().runs_dir / "pcb4" / BATCH
    for observation in record.observations:
        decision = load_decision(run / observation.image_id)
        assert decision.corrected.in_prompt is False
        assert all(region.corrections == () for region in decision.regions)
        assert all(
            region.call is None or region.call.cached_tokens in (None, 0)
            for region in decision.regions
        )

    text = page.read_text(encoding="utf-8")
    assert "**This is a partial run**" in text
    assert "| Clause-citation accuracy, strict, single-defect images |" in text
    assert f"Figures: {results}" in result.stdout
