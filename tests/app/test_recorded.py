"""Route tests over the recorded runs: the console on what `train` and `inspect` really left.

These need the trained models and the scored runs in the settings'
directories (`.env` points them at the copies kept outside the worktree), so
they are marked `recorded` and left out of the default gate:
`uv run pytest -m recorded`. Nothing here writes to those directories.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from spec_to_inspector.app.runs import Board, Status, count_statuses, list_runs, open_run
from spec_to_inspector.app.server import build_console
from spec_to_inspector.app.sink import InMemorySink
from spec_to_inspector.app.training import read_train_record
from spec_to_inspector.corrections.store import CorrectionStore
from spec_to_inspector.judge.inspect import DECISION_NAME
from spec_to_inspector.settings import Settings

pytestmark = pytest.mark.recorded

CLAUSE_TABLE = Path("specs/pcb-spec.clauses.json")
PARTS = ("pcb1", "pcb4")


@pytest.fixture(scope="module")
def settings() -> Settings:
    """The settings, as `.env` gives them.

    Returns:
        The settings.
    """
    return Settings()


@pytest.fixture(scope="module")
def client(settings: Settings, tmp_path_factory: pytest.TempPathFactory) -> TestClient:
    """The console as `serve` builds it over the recorded runs, with the tracked clause table.

    Its overrides are kept in memory. The recorded runs and the settings'
    corrections store are shared with every other piece of work on this
    machine, and `serve`'s own sink writes a row the judge would then recall
    and flags the board's decision: these tests must leave both as they
    found them. The store's join is proven on copies in `test_store_sink.py`
    and `test_web.py`.

    Returns:
        Its client.
    """
    console = build_console(
        settings,
        state_dir=tmp_path_factory.mktemp("recorded"),
        spec=CLAUSE_TABLE,
        sink=InMemorySink(),
    )
    return TestClient(console, follow_redirects=False)


def _boards(settings: Settings, part: str) -> list[Board]:
    return open_run(settings.runs_dir, part, "test").boards()


def test_the_recorded_runs_are_listed(settings: Settings) -> None:
    """Both parts' test runs are there to be shown."""
    listed = {(run.category, run.name) for run in list_runs(settings.runs_dir)}

    assert {(part, "test") for part in PARTS} <= listed


def test_the_specification_page_shows_the_demo_document(client: TestClient) -> None:
    """Sixteen clauses, and the page of the clause chosen."""
    page = client.get("/specification", params={"clause": "5.1.1"})

    assert page.status_code == 200
    assert page.text.count('class="clause-row') == 16
    assert 'src="/specification/pages/4.png"' in page.text
    assert client.get("/specification/pages/4.png").status_code == 200


@pytest.mark.parametrize("part", PARTS)
def test_the_train_page_shows_each_recorded_threshold(
    client: TestClient, settings: Settings, part: str
) -> None:
    """The threshold on the page is the one in the part's training record."""
    record = read_train_record(settings.models_dir, part)
    assert record is not None

    page = client.get("/train").text

    assert f'id="part-{part}"' in page
    assert f"{record.thresholds.image:.3f}" in page
    assert f"{record.metrics.image_auroc:.3f}" in page


@pytest.mark.parametrize("part", PARTS)
def test_the_grid_and_every_filter_agree_with_the_decisions_on_disk(
    client: TestClient, settings: Settings, part: str
) -> None:
    """The grid shows every board, and each filter exactly the boards of its disposition."""
    boards = _boards(settings, part)
    counts = count_statuses(boards)

    page = client.get(f"/batch/{part}/test")

    assert page.status_code == 200
    assert page.text.count('class="tile ') == len(boards)
    for status in Status:
        filtered = client.get(f"/batch/{part}/test", params={"disposition": status.value})
        assert filtered.status_code == 200
        assert filtered.text.count('class="tile ') == counts[status]
        assert f"{status.label} {counts[status]}" in " ".join(filtered.text.split())


@pytest.mark.parametrize("part", PARTS)
def test_every_judged_board_has_a_card_with_its_clause_and_its_pictures(
    client: TestClient, settings: Settings, part: str
) -> None:
    """Each decision on disk renders, cites its clause with its page, and serves its pictures."""
    judged = [board for board in _boards(settings, part) if board.decision is not None]
    assert judged, f"no decision is recorded for {part}"

    for board in judged:
        decision = board.decision
        assert decision is not None
        base = f"/batch/{part}/test/{board.image_id}"
        card = client.get(base)
        assert card.status_code == 200, board.image_id
        assert f"badge-{board.status.value}" in card.text
        if decision.review_cause is not None:
            assert decision.review_cause.value in card.text
        elif decision.clause is not None:
            assert f"Clause {decision.clause.id} {decision.clause.title}" in card.text
            assert f"page {decision.clause.page} of the specification" in card.text
        assert client.get(f"{base}/thumbnail.jpg").status_code == 200
        for region in decision.regions:
            for picture in ("crop", "heatmap", "overlay"):
                response = client.get(f"{base}/regions/{region.index}/{picture}.png")
                assert response.status_code == 200, (board.image_id, region.index, picture)
            if region.measurement is not None and not region.from_peak:
                assert "<polygon" in client.get(base, params={"region": region.index}).text


def test_a_flagged_board_not_yet_judged_has_a_card(client: TestClient, settings: Settings) -> None:
    """A board the judge has not seen still opens, with its crop and heatmap."""
    waiting = next(
        board
        for board in _boards(settings, "pcb4")
        if board.decision is None and board.entry.regions > 0
    )
    base = f"/batch/pcb4/test/{waiting.image_id}"

    card = client.get(base)

    assert card.status_code == 200
    assert "has not been judged" in card.text
    assert client.get(f"{base}/regions/1/crop.png").status_code == 200
    assert client.get(f"{base}/regions/1/heatmap.png").status_code == 200


def test_a_run_of_another_part_is_corrected_with_its_own_clauses(
    client: TestClient, settings: Settings
) -> None:
    """A pcb1 board's override offers pcb1's clauses and none of pcb4's, and is recorded."""
    reject = next(board for board in _boards(settings, "pcb1") if board.status is Status.REJECT)
    base = f"/batch/pcb1/test/{reject.image_id}"
    store = CorrectionStore(settings.corrections_path)
    decision_file = settings.runs_dir / "pcb1" / "test" / reject.image_id / DECISION_NAME
    stored, decision = store.count(), decision_file.read_bytes()

    card = client.get(base).text
    refused = client.post(
        f"{base}/override",
        data={"region": "1", "defect_class": "dirt", "clause": "5.1", "note": "Not this part's."},
    )
    recorded = client.post(
        f"{base}/override",
        data={"region": "1", "defect_class": "bent", "clause": "4.4", "note": "A pin is bent."},
    )

    assert 'value="4.4"' in card
    assert 'value="5.1"' not in card
    assert refused.status_code == 422
    assert "has no defect class" in refused.text
    assert recorded.status_code == 303
    assert "4.4 Bent header pin" in client.get(base).text
    # Nothing shared was written: no row for the judge to recall, the decision byte for byte.
    assert store.count() == stored
    assert decision_file.read_bytes() == decision


def test_a_part_filed_under_the_wrong_name_is_not_found(client: TestClient) -> None:
    """There is no pcb2 run, and asking for one says so."""
    response = client.get("/batch/pcb2/test")

    assert response.status_code == 404
    assert "no batch test of part pcb2" in response.text
