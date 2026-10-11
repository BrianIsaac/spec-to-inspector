# The mapping from VisA defect type to clause

This is the written table of the plan's decision 8. The labelled set
(`eval/clause_labels.csv`) is not labelled by hand: VisA's `image_anno.csv`
names the defect types of each anomalous image, and this table says which
numbered heading of the demo specification (`specs/pcb-spec.pdf`, clause
table `specs/pcb-spec.clauses.json`) covers each type.

It is the table of the specification unit's report
(`docs/plans/progress/u3-2026-10-10-report.md`, "What U4, U5 and U7 can
assume"), verbatim, with its rule column. It was written with the
specification on 10 October 2026, before the judge existed and before any
model was run on the labelled set.

| Part | VisA type | Mask value | Heading | Clause ids | Rule |
| --- | --- | --- | --- | --- | --- |
| pcb1 | melt | 2 | 4.1 Stray or bridging solder | 4.1 | reject, any zone |
| pcb1 | scratch | 3 | 4.2 Scratch | 4.2.1 (A), 4.2.2 (B) | reject over 1.0 mm, 2.0 mm |
| pcb1 | missing | 4 | 4.3 Missing component | 4.3 | reject, any zone |
| pcb1 | bent | 1 | 4.4 Bent header pin | 4.4 | reject, any zone |
| pcb4 | dirt | 7 | 5.1 Foreign material | 5.1.1 (A), 5.1.2 (B), 5.1.3 (C) | reject over 0.5, 1.0, 2.0 mm |
| pcb4 | missing | 3 | 5.2 Missing component | 5.2 | reject, any zone |
| pcb4 | extra | 5 | 5.3 Extra component or object | 5.3 | reject, any zone |
| pcb4 | wrong place | 6 | 5.4 Misplaced component | 5.4 | reject, any zone |
| pcb4 | damage | 4 | 5.5 Damaged component or board | 5.5 | reject, any zone |
| pcb4 | scratch | 2 | 5.6 Scratch | 5.6.1 (A), 5.6.2 (B), 5.6.3 (C) | reject over 1.0, 2.0, 3.0 mm |
| pcb4 | burnt | 1 | 5.7 Burn mark | 5.7 | reject, any zone |

How to read it:

- **VisA type** is the word in the `label` column of `<part>/image_anno.csv`.
  An image with several defects lists several, comma-separated.
- **Mask value** is the value VisA's ground-truth mask gives that type's
  pixels (`<part>/Data/Masks/Anomaly/*.png`). VisA does not document the
  numbering; it was read from the masks and holds on all 400 anomalous
  images of the four PCB categories
  (`uv run pytest -m data tests/anomaly/test_ground_truth.py`).
- **Heading** is the numbered heading of the specification that covers the
  type. The heading is what the judge cites and what the labelled set
  expects: it does not depend on where on the board the defect lies.
- **Clause ids** are the heading's rows in the clause table. A type with a
  size limit has one row per zone of the part; which row applies is decided
  by code from the measured zone, never by the model, so the row is a
  measurement's outcome and not part of the expected label.
- **Rule** is what the rows say: reject at any size in any zone, or reject
  over the zone's limit on the longest extent.

Two things the table does not hide. VisA's `melt` on pcb1 is stray or
bridging solder, not a melted component body, so its clause is 4.1 "Stray
or bridging solder". And pcb4's `dirt` never occurs alone: every image that
carries it carries another type too, so no single-defect image expects
clause 5.1.

The table is held as data in `spec_to_inspector.bench.mapping`
(`CLAUSE_MAPPING`). The tests check that this file holds that table, that
the table agrees row for row with the tracked clause table (headings,
titles, rows and zones) and that its mask values are VisA's.
