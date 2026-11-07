# Addition to the Stage II protocol: the whole batch, end to end (7 November 2026)

Written on 7 November 2026 by the cockpit at the owner's ruling of 18:51 SGT
the same day (the project's decisions log), after the final run and before
any batch is run. It adds to `eval/PROTOCOL-stage2.md` and edits nothing in
it. The batch's record holds this file's SHA-256 beside the protocol's and
the two earlier additions'.

## What it is

The final run measured the judge's accuracy under the bench's harness. The
batch measures the pipeline as a supplier's engineer runs it: one command,
from the specification's PDF to the reject cards, over every board of the
test split of both parts, on the machine, in the final's setting (the
judge at FP16 on card 1 by `scripts/serve_vlm_xpu.sh` with nothing
overridden; the anomaly models trained on the machine, held to
`results/stage2/checkpoints.json` by digest; an empty corrections store).
It produces no accuracy figure: the final figure stands and is not re-read
from the batch.

## What is declared before the run

- **The boards:** the test split of pcb1 and pcb4 as the bench scores it,
  anomalous and good, 401 images. The Stage I deck's "500-image batch" was
  a round number set before the data was counted; there are 401 labelled
  test boards and no more, and the deck's line is corrected to say so.
- **The command:** `spec-to-inspector inspect` as the README's quick start
  gives it, from `.venv/bin/` with `SPEC_TO_INSPECTOR_DEVICE=xpu` and
  `ZE_AFFINITY_MASK=0`, the specification `specs/pcb-spec.pdf` parsed in the
  run (not the committed clause table), once per part, under `nohup`,
  started by a wrapper that writes start, end and exit.
- **Before the first run:** the digests of week 2's second training,
  `sha256sum ~/week2/run-2/models/patchcore/*/model.ckpt`, read against
  `results/stage2/checkpoints.json` and written into the record, so that the
  README's step 6 can say whether a training repeats to the byte.

## What is recorded

Two runs, the second after nothing is changed, in `results/stage2/batch/`:
the first kept as `first-run.*` beside the second as the comparisons were.
For each run: the protocol's figures 7 (time per image, by stage), 8
(minutes from specification to a working inspector, the parse time of this
run plus week 2's recorded fit time) and 9 (peak GPU memory by stage from
`xpu-smi`, both cards sampled every 5 s for the whole run, the readings
kept raw), as the bench records them or by the same readers; the whole
run's wall clock from the wrapper; the count of boards accepted, rejected
and referred, with the count of reject cards written and the report's size
on disk; the server's log for the run; every value that differs between the
two runs, in `two-runs.md`. Where `inspect` does not yet write a figure the
protocol names, it is made to, in the pipeline's own code and with tests,
before run 1, and the record says which.

## What this does not change

The final figure, its three runs, the three comparisons and their pages.
The corrections loop and the good board's picture each keep their own
addition, when built. Nothing on the machine is changed but the batch's
own output directory; the judge's server is left up in its final setting.
