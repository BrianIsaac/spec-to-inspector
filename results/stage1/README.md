# Stage I: what the laptop prototype measured

Written by `spec-to-inspector bench` on 2026-10-11 (2026-10-10T20:13:03+00:00).
Not edited by hand: a figure that is wrong here is wrong in `bench.json`, and the
remedy is to run the command again.

The figures follow `eval/PROTOCOL.md` (SHA-256 `0109f982f5e96121`),
which was written before the run. Every proportion is a count of its N with the 95%
Wilson score interval. Nothing here is a held-out figure: see the last section.

## The figures the deck quotes

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Clause-citation accuracy, strict, single-defect images | 38.5% (52 of 135) | 135 | 30.7% to 46.9% |
| Clause-citation accuracy, strict, single-defect images, pcb1 only | 46.2% (42 of 91) | 91 | 36.3% to 56.3% |
| Clause-citation accuracy, strict, single-defect images, pcb4 only | 22.7% (10 of 44) | 44 | 12.8% to 37.0% |
| Clause-citation accuracy, lenient, multi-defect images | 58.5% (38 of 65) | 65 | 46.3% to 69.6% |
| Clause-citation accuracy per region, one defect type under region 1 | 40.5% (60 of 148) | 148 | 33.0% to 48.6% |
| Anomalous boards referred for review | 7.0% (14 of 200) | 200 | 4.2% to 11.4% |
| Good boards rejected (false rejects) | 8.0% (16 of 201) | 201 | 5.0% to 12.5% |
| Good boards flagged by the anomaly model | 13.9% (28 of 201) | 201 | 9.8% to 19.4% |

| Figure | Value |
| --- | --- |
| A flagged image, end to end, median | 3.53 s (p95 4.03 s, n 216) |
| The VLM's answer to one flagged area, cold, median | 3.36 s (p95 3.82 s, n 218) |
| From specification to a working inspector, one part | 12.3 min (parse 8.1 s measured here; fit as recorded at training: pcb1 729 s, pcb4 726 s) |
| From specification to a working inspector, all parts in turn | 24.4 min |
| Peak GPU memory, VLM server while judging | 8,780 MiB |
| Peak GPU memory, the card while judging | 10,109 MiB |

The lenient figure counts a citation of any of the image's defect types and is never
pooled with the strict one. The false rejects stand beside the accuracy and are never
folded into it.

## How it was run

- The labelled set: `eval/clause_labels.csv` (SHA-256 `0477eb9706a7772b`), 200 anomalous test images: 135 single-defect, 65 multi-defect. Labels are VisA's defect annotation mapped to clauses by the written table `eval/clause_mapping.md`.
- The specification: `specs/pcb-spec.pdf`, parsed in 8.1 s into 16 clauses under 11 numbered headings, equal to the tracked `specs/pcb-spec.clauses.json`.
- The judge: `qwen3-vl-8b-instruct` at `http://127.0.0.1:8131/v1` (model_alias qwen3-vl-8b-instruct, model_file Qwen3VL-8B-Instruct-Q4_K_M.gguf, model_ftype Q4_K - Medium, build_info b1-d812350, total_slots 1, n_ctx 16384); image minimum 1024 tokens; GPU NVIDIA GeForce RTX 5070 Ti Laptop GPU; up to 3 areas an image, stopping at the first reject.
- Every question asked cold (`cache_prompt` false), so the answers repeat.
- The corrections store empty: 0 of 401 decisions had a correction in a prompt (`decision.corrected.in_prompt`).
- The anomaly models are the trained ones, not retrained: pcb1 trained 2026-10-10T16:13:34+00:00, image threshold 31.319 (chosen on the test split); pcb4 trained 2026-10-10T16:00:38+00:00, image threshold 30.049 (chosen on the test split).

## 1. The headline: strict accuracy on the single-defect images

The citation is the heading id the judge cited on region 1, the most anomalous area.
An image with no citation (not flagged, not asked, no valid answer, or "no clause
applies") counts as wrong.

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Strict accuracy | 38.5% (52 of 135) | 135 | 30.7% to 46.9% |
| Strict accuracy, pcb1 only | 46.2% (42 of 91) | 91 | 36.3% to 56.3% |
| Strict accuracy, pcb4 only | 22.7% (10 of 44) | 44 | 12.8% to 37.0% |
| Flagged by the anomaly model | 92.6% (125 of 135) | 135 | 86.9% to 95.9% |
| Flagged by the anomaly model, pcb1 only | 91.2% (83 of 91) | 91 | 83.6% to 95.5% |
| Flagged by the anomaly model, pcb4 only | 95.5% (42 of 44) | 44 | 84.9% to 98.7% |
| Region 1 lies on the labelled defect | 80.7% (109 of 135) | 135 | 73.3% to 86.5% |
| Region 1 lies on the labelled defect, pcb1 only | 75.8% (69 of 91) | 91 | 66.1% to 83.5% |
| Region 1 lies on the labelled defect, pcb4 only | 90.9% (40 of 44) | 44 | 78.8% to 96.4% |
| Strict accuracy, flagged images only (conditional) | 41.6% (52 of 125) | 125 | 33.3% to 50.4% |
| Strict accuracy, flagged images only (conditional), pcb1 only | 50.6% (42 of 83) | 83 | 40.1% to 61.1% |
| Strict accuracy, flagged images only (conditional), pcb4 only | 23.8% (10 of 42) | 42 | 13.5% to 38.5% |
| Strict accuracy, region 1 on the defect only (conditional) | 44.0% (48 of 109) | 109 | 35.1% to 53.4% |
| Strict accuracy, region 1 on the defect only (conditional), pcb1 only | 55.1% (38 of 69) | 69 | 43.4% to 66.2% |
| Strict accuracy, region 1 on the defect only (conditional), pcb4 only | 25.0% (10 of 40) | 40 | 14.2% to 40.2% |

For the correct citations, what code then did (the row is a measurement's outcome, not
what is scored):

- Row of the clause table applied: 4.1 28, 4.4 9, 5.2 7, 4.3 2, 5.5 2, no row 1, 4.2.1 1, 4.2.2 1, 5.3 1.
- Outcome of region 1: reject 50, needs review: outside every zone 1, needs review: not measured 1.

## 2. The lenient figure: the multi-defect images

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Lenient accuracy | 58.5% (38 of 65) | 65 | 46.3% to 69.6% |
| Lenient accuracy, pcb1 only | 88.9% (8 of 9) | 9 | 56.5% to 98.0% |
| Lenient accuracy, pcb4 only | 53.6% (30 of 56) | 56 | 40.7% to 66.0% |

## 3. The per-region figure

Images, single and multi, whose region 1 lies on exactly one of VisA's defect types,
scored against that type's heading.

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Per-region accuracy | 40.5% (60 of 148) | 148 | 33.0% to 48.6% |
| Per-region accuracy, pcb1 only | 54.1% (40 of 74) | 74 | 42.8% to 64.9% |
| Per-region accuracy, pcb4 only | 27.0% (20 of 74) | 74 | 18.2% to 38.1% |

## 4. The confusion tables

Rows are the expected defect type; columns are the type of the heading cited, or why
there is no citation.

pcb1, single-defect images:

| Expected \ cited | melt | scratch | missing | bent | no clause applies | not flagged | Images |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **melt** | 28 | 8 | 0 | 4 | 0 | 6 | 46 |
| **scratch** | 10 | 3 | 0 | 0 | 0 | 1 | 14 |
| **missing** | 8 | 3 | 2 | 1 | 2 | 1 | 17 |
| **bent** | 5 | 0 | 0 | 9 | 0 | 0 | 14 |

pcb4, single-defect images:

| Expected \ cited | dirt | missing | extra | damage | burnt | no valid answer | not flagged | Images |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **missing** | 6 | 7 | 0 | 0 | 4 | 0 | 2 | 19 |
| **extra** | 4 | 1 | 1 | 0 | 6 | 0 | 0 | 12 |
| **wrong place** | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 2 |
| **damage** | 4 | 0 | 0 | 2 | 1 | 0 | 0 | 7 |
| **scratch** | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 2 |
| **burnt** | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |

pcb1, images with one type under region 1, by that type:

| Expected \ cited | melt | scratch | missing | bent | no clause applies | Images |
| --- | --- | --- | --- | --- | --- | --- |
| **melt** | 27 | 1 | 0 | 4 | 0 | 32 |
| **scratch** | 11 | 2 | 0 | 0 | 0 | 13 |
| **missing** | 6 | 4 | 2 | 1 | 2 | 15 |
| **bent** | 5 | 0 | 0 | 9 | 0 | 14 |

pcb4, images with one type under region 1, by that type:

| Expected \ cited | dirt | missing | extra | damage | burnt | no valid answer | Images |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **dirt** | 3 | 0 | 0 | 0 | 0 | 0 | 3 |
| **missing** | 10 | 8 | 0 | 0 | 6 | 0 | 24 |
| **extra** | 7 | 1 | 2 | 0 | 8 | 0 | 18 |
| **wrong place** | 3 | 2 | 0 | 0 | 2 | 2 | 9 |
| **damage** | 3 | 0 | 0 | 4 | 5 | 0 | 12 |
| **scratch** | 2 | 0 | 0 | 0 | 1 | 0 | 3 |
| **burnt** | 2 | 0 | 0 | 0 | 3 | 0 | 5 |

Citations on labelled images whose named class is not the class of the heading cited: 0.

## 5. Needs review, by cause, on the anomalous boards

- Boards: 200 anomalous; 12 not flagged by the anomaly model; of the flagged, reject 174, needs review 14.
- Boards referred for review: 7.0% (14 of 200), 95% interval 4.2% to 11.4%. By cause: not measured 8, malformed answer 3, outside every zone 2, no clause applies 1.
- Areas put to the judge on those boards: 190; reject 174, needs review 16.
- Areas referred for review: 8.4% (16 of 190), 95% interval 5.2% to 13.2%. By cause: not measured 8, outside every zone 3, malformed answer 3, no clause applies 2.

## 6. False alarms on the good boards

| Part | Good boards | Flagged | Rejected (false rejects), 95% interval | Referred | Accepted after judging |
| --- | --- | --- | --- | --- | --- |
| all | 201 | 13.9% (28 of 201) | 8.0% (16 of 201), 5.0% to 12.5% | 4.5% (9 of 201) | 1.5% (3 of 201) |
| pcb1 | 100 | 19.0% (19 of 100) | 11.0% (11 of 100), 6.3% to 18.6% | 6.0% (6 of 100) | 2.0% (2 of 100) |
| pcb4 | 101 | 8.9% (9 of 101) | 5.0% (5 of 101), 2.1% to 11.1% | 3.0% (3 of 101) | 1.0% (1 of 101) |

- What the judge cited on region 1 of the flagged good boards: 4.2 10, 4.1 8, 5.1 7, no clause applies 1, 5.3 1, 5.6 1.
- Boards: 201 good; 173 not flagged by the anomaly model; of the flagged, reject 16, needs review 9, accept 3.
- Boards referred for review: 4.5% (9 of 201), 95% interval 2.4% to 8.3%. By cause: outside every zone 7, not measured 1, no clause applies 1.
- Areas put to the judge on those boards: 28; reject 16, needs review 9, accept 3.
- Areas referred for review: 32.1% (9 of 28), 95% interval 17.9% to 50.7%. By cause: outside every zone 7, not measured 1, no clause applies 1.

## 7. Time per image, by stage

| Stage | Time |
| --- | --- |
| Parse the specification (once per specification; includes loading the parser's models) | 8.1 s |
| Anomaly model, pcb1, per image (batch 16; scoring and writing maps, masks and crops) | 86 ms |
| Anomaly model, pcb4, per image (batch 16; scoring and writing maps, masks and crops) | 96 ms |
| Measure and draw a flagged image's areas, the rule, the decision | 0.06 s (p95 0.21 s, n 216) |
| The VLM's answer to one area, cold | 3.36 s (p95 3.82 s, n 218) |
| The VLM's answers to one flagged image | 3.36 s (p95 3.82 s, n 216) |
| A flagged image, end to end | 3.53 s (p95 4.03 s, n 216) |

216 flagged images, 218 areas asked (1.01 an image); the judge's stage took 809 s in all. An image that is not flagged costs the anomaly model's time only. Prompt tokens, median: 4,683; answer tokens, median: 39; output rate, median: 62.4 tokens a second.

## 8. Minutes from specification to a working inspector

| Part | Parse, measured in this run | Fit, as recorded at training | Together |
| --- | --- | --- | --- |
| pcb1 | 8.1 s | 729 s | 12.3 min |
| pcb4 | 8.1 s | 726 s | 12.2 min |
| all parts, one after another | 8.1 s | 1455 s | 24.4 min |

Training is not repeated by the bench: the fit time is the one in each model's own
training record. A rebuilt model has the same thresholds to the last digit.

## 9. Peak GPU memory, by stage

| Stage | The stage's own process | The card | The card before | Readings |
| --- | --- | --- | --- | --- |
| Anomaly model scoring, pcb1 | 2,028 MiB (the bench's process) | 10,813 MiB | 10,813 MiB | 1 at 0.5 s |
| Anomaly model scoring, pcb4 | 1,848 MiB (the bench's process) | 11,197 MiB | not read | 26 at 0.5 s |
| Judging | 8,780 MiB (the VLM server) | 10,109 MiB | 10,091 MiB | 1501 at 0.5 s |

Read from `nvidia-smi` for the process concerned. While the anomaly model scores, the
VLM server is resident too, so the card's figure in those rows is both together. Training pcb1 peaked at 8,003 MiB allocated, as recorded then. Training pcb4 peaked at 8,003 MiB allocated, as recorded then.

## Reproducing

```
uv sync
uv run spec-to-inspector data fetch
scripts/serve_vlm.sh start
uv run spec-to-inspector bench
scripts/serve_vlm.sh stop
```

This file holds one run. Run the command again and the next record says how many
of its answers differ from this one.

## What these figures are not

- Not held out. VisA's PCB test split is the only labelled data; the anomaly model's
  thresholds were chosen on it, and the judge's prompt was written with sight of some
  of its images.
- Not a figure for the corrections loop: the store is empty throughout.
- One demonstration specification, one model at one quantisation, one laptop GPU.
- The labels are VisA's annotation mapped to clauses by a written table; 20 rows are
  for the operator to check by hand (`eval/spot-check-2026-10-11.md`).

## Files

- `bench.json`: this run, whole: every figure with its N and interval, and one line per
  image from which any of them can be counted again.
- `anomaly.json`, `spec.json`, `judge.json`, `corrections.json` and their siblings: the
  earlier units' own measurements.
