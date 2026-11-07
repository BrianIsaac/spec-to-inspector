# Addition to the Stage II protocol: the corrections loop, measured (7 November 2026)

Written on 7 November 2026 by the cockpit at the owner's ruling of 18:51 SGT
the same day (the project's decisions log), after the final run and before
any corrections run. It adds to `eval/PROTOCOL-stage2.md` and edits nothing
in it. The comparison's record holds this file's SHA-256 beside the
protocol's and the other additions'. The pane that runs it may refute any
figure declared here before the first run, in its handover and with its
reasons; a refutation changes this file by a dated line, never silently.

## What it measures

What a store of an engineer's corrections does to the judge over the whole
set, in both directions: the boards it moves to the right clause and the
boards it moves off one. The final figure keeps its empty store and is not
re-read. On the laptop a single correction moved the next similar board to
the corrected clause in 7 pairs of 7 and also moved 14 of 19 boards that
were rightly judged before; Stage I claimed nothing of accuracy from it.
This comparison is the machine's measurement of the same loop at the scale
the product would meet.

## What is declared before the run

- **The setting is the final's** in everything but the store: FP16, the
  machine-trained checkpoints held by digest, the same prompt, the same
  pattern, the server by `scripts/serve_vlm_xpu.sh` with nothing
  overridden, cold.
- **The store.** For each part, ten of its single-defect boards are drawn
  by a seeded rule (`random.Random(20261107)`, the boards sorted by image
  id, `sample(10)`), and the store holds one correction for each: the
  judged class and clause are what the final run's tracked record answered
  for that board, the corrected class and clause are the label's
  (`eval/clause_labels.csv`, `region1_types` and `region1_headings`), and
  the note is the corrected clause's heading as the specification's clause
  table prints it. Nothing is written by hand. The store is built by a
  script in the repository with a test, from the record and the labels, and
  its file's SHA-256 is in the comparison's record. **The twenty boards are
  excluded from every figure of this comparison**, since the store holds
  their answers.
- **The recall** is the product's own, the settings' default strategy and
  its limit of three, named in the record.
- **The figure** is the protocol's figure 10 over the 115 single-defect
  boards not in the store (pcb1 81, pcb4 34), the tracked final record
  against this comparison's second run on the same 115: right on both,
  wrong on both, right only on the final, right only with corrections, and
  the two-sided exact sign test on the two "only" counts at 0.05, said to
  be tested on its own. The lenient figure over the 65, none of which is in
  the store, is reported under its own name the same way and never pooled.
  Figure 7's answer time is read beside it: a prompt with corrections in it
  is longer.

## What is recorded

Two runs, the second after nothing is changed, in
`results/stage2/comparison-corrections/`, the first kept as `first-run.*`:
each run's record, page, server log and `paired.json`; the store file and
the script that built it; `two-runs.md` with every value that differs. The
bench today voids a run in which a correction stood in a prompt. It gains a
declared mode, one flag naming the store, under which the void rule becomes
"a correction stood in a prompt from a store other than the declared one",
the store's digest goes into the record, and `missing_for_final` names the
run as this comparison; without the flag nothing changes. Code with tests
on the laptop before the machine, as the pages fix was.

## What this does not change

The final figure, its three runs, the three comparisons of 7 November, the
whole batch. The good board's picture keeps its own addition, when built.
