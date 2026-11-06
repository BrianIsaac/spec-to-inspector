# Addition to the Stage II protocol: the region columns, and the threshold rule (7 November 2026)

Written on 7 November 2026 by the cockpit at the owner's rulings of 04:41 SGT
the same day (the project's decisions log, "The two week-2 questions ruled"),
after week 2's record and before any run the protocol calls final. It adds
to `eval/PROTOCOL-stage2.md` and edits nothing in it. A final run's record
holds this file's SHA-256 beside the protocol's.

## What week 2 found

The protocol's line 9 holds that the anomaly models are those trained on
the machine. Week 2 trained them and found that the bench's region columns
in `eval/clause_labels.csv` were derived from the laptop's checkpoints: the
bench stops when a model's regions disagree with them, and with the
machine's checkpoints it stops on PCB1 `bad-029` (and, through OpenVINO, on
PCB4 `bad-081`; `results/stage2/week2/label-region-columns.json`). Week 2
also found that one board a part sits exactly on the anomaly threshold
(PCB1 `bad-029`, PCB2 `bad-060`, PCB3 `bad-097`, PCB4 `bad-081`); the rule is
a strict `>`, so float noise decides those four, and `bad-029` is one of
the 135 single-defect boards.

## The rulings

1. **The anomaly models stay those trained on the machine** (line 9 stands).
   The region columns of `eval/clause_labels.csv` are regenerated from the
   machine's checkpoints, the ones the protocol names by SHA-256, by the same
   code that derived them from the laptop's, before the final run. The
   regeneration is committed with: the checkpoints' digests, the command,
   and a table of every row whose region columns changed, board by board,
   with the old and new values. The labels themselves (the clause each image
   is mapped to) do not change: they come from VisA's annotations through
   `eval/clause_mapping.md`, not from any model.
2. **The threshold rule stays a strict `>`**, declared here before the run,
   as the protocol's "one setting, declared in the file before the run". The
   four boards on the threshold are named in the final run's record under
   their own heading, with each board's score and its threshold, and the
   final figure is read with that known. No margin and no `>=`.

## What this does not change

The labelled set is Stage I's: 200 boards, 135 and 65, all of them. The
void rules, the three runs, the three comparisons, the sign test and the
citation stand as the protocol writes them. Week 2's laptop-trained figures
remain a dated record and are not the final.
