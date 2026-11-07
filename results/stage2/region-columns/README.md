# The region columns, regenerated from the machine's checkpoints

Done on 7 November 2026, 04:11 to 04:12 UTC, on the machine, under the first ruling of
`eval/PROTOCOL-stage2-addition-region-columns-2026-11-07.md`, by the code that derived them from the
laptop's: `spec_to_inspector.bench.labels`. Its record, as written by the command, is `changes.json`.
This is not a final run, and no figure here is one.

## The checkpoints

The ones the protocol names, the first training on the machine. The whole record, with the size, the
training and its date, and the laptop's two marked as the laptop's, is
`results/stage2/checkpoints.json`.

| Part | SHA-256 | Path on the machine |
| --- | --- | --- |
| pcb1 | `b71ff0c3db7e780c6198db5686569fa59de4a56b5663557b56d90e237b37a855` | `~/week2/run-1/models/patchcore/pcb1/model.ckpt` |
| pcb4 | `cc571d9a4c56ee791888a2f6ce73e7db2f7f46b57c7aeb683ce7ba447f03ccb4` | `~/week2/run-1/models/patchcore/pcb4/model.ckpt` |

## The command

From `~/spec-to-inspector`, whose `.env` holds `SPEC_TO_INSPECTOR_DEVICE=xpu`,
`SPEC_TO_INSPECTOR_VLM_CARD=0000:ba:00.0` and
`SPEC_TO_INSPECTOR_MODELS_DIR=/home/devcloud/week2/run-1/models`:

    # The whole split, as the bench batches it. Both parts are scored before the columns are compared,
    # so this stops with exit 1 and names every stale board, having left both runs behind.
    SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 SPEC_TO_INSPECTOR_RUNS_DIR=/home/devcloud/before-final/runs \
        .venv/bin/spec-to-inspector bench --results /home/devcloud/before-final/whole/bench.json

    # The command that message names, reading those two runs and writing the labelled set and the table.
    SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 SPEC_TO_INSPECTOR_RUNS_DIR=/home/devcloud/before-final/runs \
        .venv/bin/python -m spec_to_inspector.bench.labels --run bench \
        --changes /home/devcloud/before-final/changes.json

The first exited 1, naming `pcb1 bad-029` alone. The second exited 0.

**Over the whole split, because that is what fixes the answer.** The bench scores at batch 16, and a
board on the threshold is decided by the other boards of its batch: on these same checkpoints `bad-029`
is above its threshold over the whole of pcb1 and below it in a trial of 30. A regeneration from a run
cut down by `--limit` is refused, since that run holds no sidecar for the boards it left out.

## Every row that changed

1 row of the 200. `eval/clause_labels.csv` goes from SHA-256
`0477eb9706a7772b057b1ed85cb165a37128b7211633ca62c4d00a853b807dcd` to
`44866105f3fdad88c12f70a6d41d1d0c7e14df34d9ffbc0f7cb5051c42660337`.

| Part | Board | Set | Column | Old | New |
| --- | --- | --- | --- | --- | --- |
| pcb1 | `bad-029` | One of the 135 | `region1` | no region | one type |
| | | | `region1_types` | (empty) | melt |
| | | | `region1_headings` | (empty) | 4.1 |

**The labels themselves did not change.** Each board's `visa_types`, `defects` and
`expected_headings` come from VisA's annotation through `eval/clause_mapping.md`, and the command
refuses to write if any of them would differ. `bad-029` expects heading 4.1 before and after.

**What moved it.** Scored over the whole split, `bad-029` reads 31.319490432739258 against a threshold of
31.319488525390625: above it by 1.9e-6, under the strict `>` the addition declares, where the laptop's
model left it unflagged. So it is flagged, and its one region lies on its own defect. Week 2's
`label-region-columns.json` predicted exactly this board.

`pcb4 bad-081`, the other board of these two parts on a threshold, reads 30.048744201660156 against
30.048744201660156: exactly on it, not above it, unflagged, as the column already said. It changes
nothing here, and that does not make it safe from float noise: see `on_threshold` in a run's record.
