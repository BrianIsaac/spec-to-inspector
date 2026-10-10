# Spot-check of the labelled set, 11 October 2026

For the operator. The plan's decision 8: the labels of `eval/clause_labels.csv`
are derived from VisA's own annotation through the table of
`eval/clause_mapping.md`, and 20 of them are checked by hand against the image.
These are the 20. No pane has looked at them: the two right-hand columns are
yours.

For each row: open the image (paths are from the repository root, after `uv run
spec-to-inspector data fetch`); see whether it shows the VisA defect type or
types named, and whether the clause named is the one of `specs/pcb-spec.pdf`
that covers that defect. Write `yes` under Agrees, or `no` and what you see
under Note. A `no` is a finding about VisA's annotation or about the mapping
table, and either way it goes in the deck's sentence about the labels.

How the rows were chosen: stratified by part and defect type, one row at least
for each type, the rest in proportion to the number of images that carry the
type; within a type, in the order of the SHA-256 of `20261011:<image path>`. The
command is `uv run python -m spec_to_inspector.bench.spot_check`, and it gives
these rows every time.

| # | Part | Image | VisA type(s) | Expected clause(s) | Agrees | Note |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | pcb1 | `data/visa/pcb1/Data/Images/Anomaly/032.JPG` | melt | 4.1 Stray or bridging solder |  |  |
| 2 | pcb1 | `data/visa/pcb1/Data/Images/Anomaly/063.JPG` | melt | 4.1 Stray or bridging solder |  |  |
| 3 | pcb1 | `data/visa/pcb1/Data/Images/Anomaly/034.JPG` | melt | 4.1 Stray or bridging solder |  |  |
| 4 | pcb1 | `data/visa/pcb1/Data/Images/Anomaly/026.JPG` | melt | 4.1 Stray or bridging solder |  |  |
| 5 | pcb1 | `data/visa/pcb1/Data/Images/Anomaly/091.JPG` | scratch | 4.2 Scratch |  |  |
| 6 | pcb1 | `data/visa/pcb1/Data/Images/Anomaly/088.JPG` | scratch | 4.2 Scratch |  |  |
| 7 | pcb1 | `data/visa/pcb1/Data/Images/Anomaly/044.JPG` | missing | 4.3 Missing component |  |  |
| 8 | pcb1 | `data/visa/pcb1/Data/Images/Anomaly/010.JPG` | bent | 4.4 Bent header pin |  |  |
| 9 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/009.JPG` | damage, dirt | 5.5 Damaged component or board; 5.1 Foreign material |  |  |
| 10 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/002.JPG` | burnt, dirt | 5.7 Burn mark; 5.1 Foreign material |  |  |
| 11 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/081.JPG` | wrong place, dirt | 5.4 Misplaced component; 5.1 Foreign material |  |  |
| 12 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/070.JPG` | missing, dirt | 5.2 Missing component; 5.1 Foreign material |  |  |
| 13 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/054.JPG` | missing, damage | 5.2 Missing component; 5.5 Damaged component or board |  |  |
| 14 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/032.JPG` | extra | 5.3 Extra component or object |  |  |
| 15 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/007.JPG` | scratch, damage, extra | 5.6 Scratch; 5.5 Damaged component or board; 5.3 Extra component or object |  |  |
| 16 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/086.JPG` | scratch, extra, wrong place | 5.6 Scratch; 5.3 Extra component or object; 5.4 Misplaced component |  |  |
| 17 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/017.JPG` | missing, damage | 5.2 Missing component; 5.5 Damaged component or board |  |  |
| 18 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/058.JPG` | missing, damage, extra | 5.2 Missing component; 5.5 Damaged component or board; 5.3 Extra component or object |  |  |
| 19 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/010.JPG` | scratch, damage, dirt | 5.6 Scratch; 5.5 Damaged component or board; 5.1 Foreign material |  |  |
| 20 | pcb4 | `data/visa/pcb4/Data/Images/Anomaly/027.JPG` | burnt | 5.7 Burn mark |  |  |

Checked by: ______________________  Date: ______________
