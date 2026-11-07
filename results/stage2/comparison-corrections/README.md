# Stage II: what the machine measured

Written by `spec-to-inspector bench --batch corrections --results results/stage2/comparison-corrections/bench.json --readme results/stage2/comparison-corrections/README.md --against results/stage2/final/bench.json --declared-store results/stage2/comparison-corrections/store.sqlite3` on 2026-11-07 (2026-11-07T14:56:41+00:00).
Not edited by hand: a figure that is wrong here is wrong in its record, and the remedy
is to run the command again.

The figures follow these files, each read at the time of the run:

| File | SHA-256 |
| --- | --- |
| `eval/PROTOCOL-stage2.md` | `ebbd8cc1cb25172f7d74cddf8190e0826204eb6b3c8cc7e1da83a565ead4e3f6` |
| `eval/PROTOCOL-stage2-addition-corrections-2026-11-07.md` | `e3c9eb3fd13e8c9ee89b5c0e6f424440e6dc3f45ea04cc2d9a0b7b463d434eab` |
| `eval/PROTOCOL-stage2-addition-designators-pattern-2026-11-07.md` | `84c8d198200b11a45e4eac8735611c20681cf5a9db5f0d4a2063330ac4f7c65b` |
| `eval/PROTOCOL-stage2-addition-region-columns-2026-11-07.md` | `8d8d4ef19e95354a4a1ab220e6eb9dc51865c87b2ae6e9f9da1464bdd4c5b1b1` |
| `eval/PROTOCOL-stage2-addition-whole-batch-2026-11-07.md` | `03a4154bb25cacd8a48bdb5b49e59594820bf67200c0620dc63d99d10c284040` |

Every proportion is a count of its N with the 95% Wilson score interval. Nothing here is
a held-out figure: see the last section.

**This run is not final.** Its record lacks what the protocol asks of a final run:

- the final setting: this is the corrections comparison.

The 20 boards the store was drawn from are left out of figures 1 to 7, since it holds their answers. Figure 9 is the card's and has no boards to leave out, and the judge's stage's time is the whole run's.

## The figures

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Clause-citation accuracy, strict, single-defect images | 40.0% (46 of 115) | 115 | 31.5% to 49.1% |
| Clause-citation accuracy, strict, single-defect images, pcb1 only | 42.0% (34 of 81) | 81 | 31.8% to 52.8% |
| Clause-citation accuracy, strict, single-defect images, pcb4 only | 35.3% (12 of 34) | 34 | 21.5% to 52.1% |
| Clause-citation accuracy, lenient, multi-defect images | 44.6% (29 of 65) | 65 | 33.2% to 56.7% |
| Clause-citation accuracy per region, one defect type under region 1 | 44.7% (59 of 132) | 132 | 36.5% to 53.2% |
| Anomalous boards referred for review | 2.8% (5 of 180) | 180 | 1.2% to 6.3% |
| Good boards rejected (false rejects) | 9.5% (19 of 201) | 201 | 6.1% to 14.3% |
| Good boards flagged by the anomaly model | 13.9% (28 of 201) | 201 | 9.8% to 19.4% |

| Figure | Value |
| --- | --- |
| A flagged image, end to end, median | 2.33 s (p95 2.84 s, n 197) |
| The VLM's answer to one flagged area, cold, median | 2.16 s (p95 2.58 s, n 197) |
| From specification to a working inspector, one part | 11.8 min (parse 11.6 s measured here; fit as recorded at training: pcb1 699 s, pcb4 701 s) |
| From specification to a working inspector, all parts in turn | 23.5 min |
| Peak GPU memory, VLM server while judging | not read |
| Peak GPU memory, the card while judging | 30,050 MiB |

The lenient figure counts a citation of any of the image's defect types and is never
pooled with the strict one. The false rejects stand beside the accuracy and are never
folded into it.

## Which server answered

| Fact | Value | Read from |
| --- | --- | --- |
| vllm_version | `0.26.1.dev0+g568afb3a1.d20260831` | GET /version |
| served_model | `qwen3-vl-8b-instruct` | GET /v1/models |
| weights_revision | `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b` | GET /v1/models |
| max_model_len | `32768` | GET /v1/models |
| image | `intel/llm-scaler-vllm:0.26.0-b1` | docker inspect, Config.Image |
| image_digest | `sha256:70e7eafdd52c281263f2a19266086b88e55064402a17ef731ba5657c4bd86490` | docker image inspect, RepoDigests |
| image_label_version | `20260608` | container label org.opencontainers.image.version |
| image_label_revision | `ac12083301cbdbe06135882d401f7877b0b512db` | container label org.opencontainers.image.revision |
| command | `-c source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1; exec vllm serve --model /root/.cache/huggingface/hub/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b --served-model-name qwen3-vl-8b-instruct --dtype=float16 --enforce-eager --port 8131 --host 127.0.0.1 --trust-remote-code --disable-sliding-window --gpu-memory-util=0.9 --max-model-len=32768 --max-num-batched-tokens=32768 --block-size 64 --limit-mm-per-prompt '{"image": 2}' --mm-processor-kwargs '{"size": {"shortest_edge": 1048576, "longest_edge": 16777216}}' --no-enable-prefix-caching --mm-processor-cache-gb 0 -tp=1` | docker inspect, Args |
| dtype | `float16` | the server's log, the engine's line, dtype=torch.* |
| quantisation | `None` | the server's log, the engine's line, quantization=* |

The judge's card: Intel(R) Arc(TM) Pro B70 Graphics. Its image minimum: 1024 tokens. Up to 3 areas an image, stopping at the first reject.

The cold comes from the server's start, not the request: vLLM ignores the request's `cache_prompt`. The server's flags: `--no-enable-prefix-caching`, `--mm-processor-cache-gb 0`. Its engine's own line on the prefix cache says it is off. It started at 2026-11-07T07:27:57.966649565Z.

During this run the highest of 55 rates in its log is 0.0%, and its counters added 0 tokens of hits of 0 looked for. Any rate above 0.0% voids a run, so a run that has a record has none. The log of this run is `results/stage2/comparison-corrections/bench.server-log.20261107T144630Z.txt`.

## What else the run was made of

- The warm-up: one question before the judge's clock, on pcb1 good-0214, in 2.00 s; its answer is not recorded.
- The reason's pattern: `^[^0-9\n\r"\\]{1,240}$`.
- The labelled set: `eval/clause_labels.csv` (SHA-256 `44866105f3fdad88`), 180 anomalous test images: 115 single-defect, 65 multi-defect.
- The specification: `specs/pcb-spec.pdf`, parsed in 11.6 s into 16 clauses under 11 numbered headings, equal to the tracked `specs/pcb-spec.clauses.json`.
- The corrections: the declared store, below. 217 of 401 decisions had a correction in a prompt (`decision.corrected.in_prompt`), and 217 boards were flagged.

The anomaly models, not retrained here:

| Part | Checkpoint | SHA-256 | Trained | Image threshold | Chosen on the test |
| --- | --- | --- | --- | --- | --- |
| pcb1 | `/home/devcloud/week2/run-1/models/patchcore/pcb1/model.ckpt` | `b71ff0c3db7e780c6198db5686569fa59de4a56b5663557b56d90e237b37a855` | 2026-11-06T17:17:44+00:00 | 31.319489 | yes |
| pcb4 | `/home/devcloud/week2/run-1/models/patchcore/pcb4/model.ckpt` | `cc571d9a4c56ee791888a2f6ce73e7db2f7f46b57c7aeb683ce7ba447f03ccb4` | 2026-11-06T17:59:34+00:00 | 30.048744 | yes |

Each checkpoint was held to `results/stage2/checkpoints.json` (SHA-256 `af420d92ee128a05`) before it scored anything: another digest voids the run.

## The declared store

`results/stage2/comparison-corrections/store.sqlite3`, SHA-256 `e43072ed4d3cbf2d5257cbb8e6f6c62add126675d4a0b4d7e6b8e8815077ea0c`, holding 14 corrections. The recall is the product's own: the settings' default, `part`, at most 3 in a prompt. A correction from any other store voids the run, and so does this one's file changing during it.

| Part | Slot | The line that stood in every prompt of the part |
| --- | --- | --- |
| pcb1 | 1 | On a pcb1 board the judge called the flagged area 'melt' (clause 4.1); the engineer corrected it to 'missing' (clause 4.3). The engineer's note: Missing component. |
| pcb1 | 2 | On a pcb1 board the judge called the flagged area 'melt' (clause 4.1); the engineer corrected it to 'bent' (clause 4.4). The engineer's note: Bent header pin. |
| pcb1 | 3 | On a pcb1 board the judge called the flagged area 'melt' (clause 4.1); the engineer corrected it to 'missing' (clause 4.3). The engineer's note: Missing component. |
| pcb4 | 1 | On a pcb4 board the judge called the flagged area 'dirt' (clause 5.1); the engineer corrected it to 'damage' (clause 5.5). The engineer's note: Damaged component or board. |
| pcb4 | 2 | On a pcb4 board the judge called the flagged area 'dirt' (clause 5.1); the engineer corrected it to 'extra' (clause 5.3). The engineer's note: Extra component or object. |
| pcb4 | 3 | On a pcb4 board the judge called the flagged area 'missing' (clause 5.2); the engineer corrected it to 'extra' (clause 5.3). The engineer's note: Extra component or object. |

The boards the store was drawn from, in the draw's order. Each is left out of figures 1 to 7, whether or not it holds a correction, and keeps its line in the record:

| Part | Boards |
| --- | --- |
| pcb1 | `bad-078`, `bad-092`, `bad-052`, `bad-061`, `bad-004`, `bad-021`, `bad-085`, `bad-042`, `bad-033`, `bad-029` |
| pcb4 | `bad-077`, `bad-096`, `bad-059`, `bad-065`, `bad-011`, `bad-026`, `bad-051`, `bad-044`, `bad-038`, `bad-015` |

## The boards on the threshold

The rule is a strict `>`. A score within 0.001 of its part's threshold is decided by float noise, so the figures are read with these boards known. No margin and no `>=` is applied.

| Part | Board | Ground truth | Score | Threshold | Strictly above | This run |
| --- | --- | --- | --- | --- | --- | --- |
| pcb1 | `bad-029` | bad | 31.319490 | 31.319489 | yes | yes |
| pcb4 | `bad-081` | bad | 30.048744 | 30.048744 | no | yes |
| pcb2 | `bad-060` | bad | 29.304890 | 29.304890 | no | no: week 2's record |
| pcb3 | `bad-097` | bad | 31.543020 | 31.543051 | no | no: week 2's record |

pcb2, pcb3: the bench does not score them, having no clause to hold them to, so their figures are those of the first training on the machine and this run did not measure them.

## 1. The headline: strict accuracy on the single-defect images

The citation is the heading id the judge cited on region 1, the most anomalous area.
An image with no citation (not flagged, not asked, no valid answer, or "no clause
applies") counts as wrong.

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Strict accuracy | 40.0% (46 of 115) | 115 | 31.5% to 49.1% |
| Strict accuracy, pcb1 only | 42.0% (34 of 81) | 81 | 31.8% to 52.8% |
| Strict accuracy, pcb4 only | 35.3% (12 of 34) | 34 | 21.5% to 52.1% |
| Flagged by the anomaly model | 92.2% (106 of 115) | 115 | 85.8% to 95.8% |
| Flagged by the anomaly model, pcb1 only | 91.4% (74 of 81) | 81 | 83.2% to 95.8% |
| Flagged by the anomaly model, pcb4 only | 94.1% (32 of 34) | 34 | 80.9% to 98.4% |
| Region 1 lies on the labelled defect | 80.9% (93 of 115) | 115 | 72.7% to 87.0% |
| Region 1 lies on the labelled defect, pcb1 only | 77.8% (63 of 81) | 81 | 67.6% to 85.5% |
| Region 1 lies on the labelled defect, pcb4 only | 88.2% (30 of 34) | 34 | 73.4% to 95.3% |
| Strict accuracy, flagged images only (conditional) | 43.4% (46 of 106) | 106 | 34.4% to 52.9% |
| Strict accuracy, flagged images only (conditional), pcb1 only | 45.9% (34 of 74) | 74 | 35.1% to 57.2% |
| Strict accuracy, flagged images only (conditional), pcb4 only | 37.5% (12 of 32) | 32 | 22.9% to 54.7% |
| Strict accuracy, region 1 on the defect only (conditional) | 46.2% (43 of 93) | 93 | 36.5% to 56.3% |
| Strict accuracy, region 1 on the defect only (conditional), pcb1 only | 49.2% (31 of 63) | 63 | 37.3% to 61.2% |
| Strict accuracy, region 1 on the defect only (conditional), pcb4 only | 40.0% (12 of 30) | 30 | 24.6% to 57.7% |

For the correct citations, what code then did (the row is a measurement's outcome, not
what is scored):

- Row of the clause table applied: 4.3 12, 4.4 11, 4.1 8, 5.5 4, 5.2 4, 5.3 3, 4.2.1 2, 4.2.2 1, 5.7 1.
- Outcome of region 1: reject 45, needs review: not measured 1.

## 2. The lenient figure: the multi-defect images

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Lenient accuracy | 44.6% (29 of 65) | 65 | 33.2% to 56.7% |
| Lenient accuracy, pcb1 only | 33.3% (3 of 9) | 9 | 12.1% to 64.6% |
| Lenient accuracy, pcb4 only | 46.4% (26 of 56) | 56 | 34.0% to 59.3% |

## 3. The per-region figure

Images, single and multi, whose region 1 lies on exactly one of VisA's defect types,
scored against that type's heading.

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Per-region accuracy | 44.7% (59 of 132) | 132 | 36.5% to 53.2% |
| Per-region accuracy, pcb1 only | 47.1% (32 of 68) | 68 | 35.7% to 58.8% |
| Per-region accuracy, pcb4 only | 42.2% (27 of 64) | 64 | 30.9% to 54.4% |

## 4. The confusion tables

Rows are the expected defect type; columns are the type of the heading cited, or why
there is no citation.

pcb1, single-defect images:

| Expected \ cited | melt | scratch | missing | bent | not flagged | Images |
| --- | --- | --- | --- | --- | --- | --- |
| **melt** | 8 | 0 | 19 | 9 | 5 | 41 |
| **scratch** | 4 | 3 | 2 | 2 | 1 | 12 |
| **missing** | 0 | 0 | 12 | 2 | 1 | 15 |
| **bent** | 0 | 0 | 2 | 11 | 0 | 13 |

pcb4, single-defect images:

| Expected \ cited | dirt | missing | extra | damage | burnt | not flagged | Images |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **missing** | 0 | 4 | 4 | 5 | 1 | 2 | 16 |
| **extra** | 0 | 1 | 3 | 4 | 1 | 0 | 9 |
| **wrong place** | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| **damage** | 1 | 0 | 0 | 4 | 0 | 0 | 5 |
| **scratch** | 0 | 1 | 0 | 0 | 0 | 0 | 1 |
| **burnt** | 0 | 0 | 0 | 1 | 1 | 0 | 2 |

pcb1, images with one type under region 1, by that type:

| Expected \ cited | melt | scratch | missing | bent | Images |
| --- | --- | --- | --- | --- | --- |
| **melt** | 7 | 0 | 13 | 10 | 30 |
| **scratch** | 4 | 3 | 3 | 2 | 12 |
| **missing** | 0 | 0 | 11 | 2 | 13 |
| **bent** | 0 | 0 | 2 | 11 | 13 |

pcb4, images with one type under region 1, by that type:

| Expected \ cited | dirt | missing | extra | damage | burnt | no valid answer | Images |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **dirt** | 1 | 0 | 0 | 2 | 0 | 0 | 3 |
| **missing** | 0 | 7 | 5 | 9 | 0 | 0 | 21 |
| **extra** | 0 | 1 | 6 | 6 | 2 | 0 | 15 |
| **wrong place** | 0 | 2 | 4 | 1 | 0 | 1 | 8 |
| **damage** | 0 | 0 | 0 | 10 | 0 | 0 | 10 |
| **scratch** | 0 | 1 | 0 | 1 | 0 | 0 | 2 |
| **burnt** | 0 | 0 | 0 | 2 | 3 | 0 | 5 |

Citations on labelled images whose named class is not the class of the heading cited: 0.

## 5. Needs review, by cause, on the anomalous boards

- Boards: 180 anomalous; 11 not flagged by the anomaly model; of the flagged, reject 164, needs review 5.
- Boards referred for review: 2.8% (5 of 180), 95% interval 1.2% to 6.3%. By cause: not measured 2, malformed answer 2, outside every zone 1.
- Areas put to the judge on those boards: 169; reject 164, needs review 5.
- Areas referred for review: 3.0% (5 of 169), 95% interval 1.3% to 6.7%. By cause: not measured 2, malformed answer 2, outside every zone 1.

## 6. False alarms on the good boards

| Part | Good boards | Flagged | Rejected (false rejects), 95% interval | Referred | Accepted after judging |
| --- | --- | --- | --- | --- | --- |
| all | 201 | 13.9% (28 of 201) | 9.5% (19 of 201), 6.1% to 14.3% | 4.0% (8 of 201) | 0.5% (1 of 201) |
| pcb1 | 100 | 19.0% (19 of 100) | 14.0% (14 of 100), 8.5% to 22.1% | 5.0% (5 of 100) | 0.0% (0 of 100) |
| pcb4 | 101 | 8.9% (9 of 101) | 5.0% (5 of 101), 2.1% to 11.1% | 3.0% (3 of 101) | 1.0% (1 of 101) |

- What the judge cited on region 1 of the flagged good boards: 4.3 7, 4.2 5, 4.1 4, 5.3 4, 4.4 2, 5.1 2, no clause applies 1, 5.7 1, 5.5 1, 5.6 1.
- Boards: 201 good; 173 not flagged by the anomaly model; of the flagged, reject 19, needs review 8, accept 1.
- Boards referred for review: 4.0% (8 of 201), 95% interval 2.0% to 7.7%. By cause: outside every zone 7, no clause applies 1.
- Areas put to the judge on those boards: 28; reject 19, needs review 8, accept 1.
- Areas referred for review: 28.6% (8 of 28), 95% interval 15.3% to 47.1%. By cause: outside every zone 7, no clause applies 1.

## 7. Time per image, by stage

| Stage | Time |
| --- | --- |
| Parse the specification (once per specification; includes loading the parser's models) | 11.6 s |
| Anomaly model, pcb1, per image (batch 16; scoring and writing maps, masks and crops) | 100 ms |
| Anomaly model, pcb4, per image (batch 16; scoring and writing maps, masks and crops) | 90 ms |
| Measure and draw a flagged image's areas, the rule, the decision | 0.06 s (p95 0.25 s, n 197) |
| The VLM's answer to one area, cold | 2.16 s (p95 2.58 s, n 197) |
| The VLM's answers to one flagged image | 2.16 s (p95 2.58 s, n 197) |
| A flagged image, end to end | 2.33 s (p95 2.84 s, n 197) |

197 flagged images, 197 areas asked (1.00 an image); the judge's stage took 537 s in all. An image that is not flagged costs the anomaly model's time only. Prompt tokens, median: 4,819; answer tokens, median: 35; output rate, median: -.

## 8. Minutes from specification to a working inspector

| Part | Parse, measured in this run | Fit, as recorded at training | Together |
| --- | --- | --- | --- |
| pcb1 | 11.6 s | 699 s | 11.8 min |
| pcb4 | 11.6 s | 701 s | 11.9 min |
| all parts, one after another | 11.6 s | 1400 s | 23.5 min |

Training is not repeated by the bench: the fit time is the one in each model's own
training record. 23.5 minutes is every part of this run in turn.

## 9. Peak GPU memory, by stage

| Stage | The stage's own process | The card | The card before | Readings |
| --- | --- | --- | --- | --- |
| Anomaly model scoring, pcb1 | 2,552 MiB (the bench's process) | 2,596 MiB | 1,594 MiB | 24 at 0.5 s |
| Anomaly model scoring, pcb4 | 2,552 MiB (the bench's process) | 2,596 MiB | 2,050 MiB | 22 at 0.5 s |
| Judging | not read (the VLM server) | 30,050 MiB | 30,048 MiB | 702 at 0.5 s |

Read from `xpu-smi`, sampled by the bench: the anomaly model on pcb1, card 0000:17:00.0, under ZE_AFFINITY_MASK=0; the anomaly model on pcb4, card 0000:17:00.0, under ZE_AFFINITY_MASK=0; the judge, card 0000:ba:00.0. Each stage has a card to itself, so the card stands for the process.
Where a process's own figure says `not read`: the judge's server runs in a container: xpu-smi ps does not list its process, even under sudo, and ss shows no pid, so its own figure is null and its card stands for it.

## 10. The paired table, against the final run

Against the final run's record, `results/stage2/final/bench.json` (SHA-256 `ece9864d4ff3f8f9`). The pairs are the boards, the labelled set `eval/clause_labels.csv`.

| Figure | Boards | Right on both | Wrong on both | Right only on the final run | Right only on the comparison | Differing | Exact sign test, p | Below 0.05 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Strict, single-defect | 115 | 22 | 49 | 20 | 24 | 44 | 0.6516 | no |
| Lenient, multi-defect | 65 | 19 | 9 | 27 | 10 | 37 | 0.007632 | yes |

- **The strict figure, the primary test.** p = 0.6516, not below 0.05: no figure separates them.
- **The lenient figure.** p = 0.007632: the lenient figure passes the test, which is evidence of a change, the comparison reading lower. It is reported under its own name, is never pooled and offsets nothing of the strict figure; this is not the primary test.

This comparison is tested on its own at 0.05, with no correction for the others.

Left out of both tables, since the store was drawn from them: `pcb1 bad-004`, `pcb1 bad-021`, `pcb1 bad-029`, `pcb1 bad-033`, `pcb1 bad-042`, `pcb1 bad-052`, `pcb1 bad-061`, `pcb1 bad-078`, `pcb1 bad-085`, `pcb1 bad-092`, `pcb4 bad-011`, `pcb4 bad-015`, `pcb4 bad-026`, `pcb4 bad-038`, `pcb4 bad-044`, `pcb4 bad-051`, `pcb4 bad-059`, `pcb4 bad-065`, `pcb4 bad-077`, `pcb4 bad-096`.

The answer time on the same boards, each over the areas that run asked of them: a prompt with corrections in it is longer.

| Run | The VLM's answer to one area, cold | Prompt tokens, median |
| --- | --- | --- |
| The final run | 2.13 s (p95 2.54 s, n 197) | 4,682 |
| The comparison | 2.16 s (p95 2.58 s, n 197) | 4,819 |

What differs between the two runs' makings:

- the protocol's files: ['ebbd8cc1cb25172f7d74cddf8190e0826204eb6b3c8cc7e1da83a565ead4e3f6', '84c8d198200b11a45e4eac8735611c20681cf5a9db5f0d4a2063330ac4f7c65b', '8d8d4ef19e95354a4a1ab220e6eb9dc51865c87b2ae6e9f9da1464bdd4c5b1b1'] against ['ebbd8cc1cb25172f7d74cddf8190e0826204eb6b3c8cc7e1da83a565ead4e3f6', 'e3c9eb3fd13e8c9ee89b5c0e6f424440e6dc3f45ea04cc2d9a0b7b463d434eab', '84c8d198200b11a45e4eac8735611c20681cf5a9db5f0d4a2063330ac4f7c65b', '8d8d4ef19e95354a4a1ab220e6eb9dc51865c87b2ae6e9f9da1464bdd4c5b1b1', '03a4154bb25cacd8a48bdb5b49e59594820bf67200c0620dc63d99d10c284040']
- the declared store: None against 'e43072ed4d3cbf2d5257cbb8e6f6c62add126675d4a0b4d7e6b8e8815077ea0c'

The boards that differ:

| Part | Board | Expected | The final run cited | The comparison cited | Right on |
| --- | --- | --- | --- | --- | --- |
| pcb1 | `bad-005` | 4.4 | 4.1 | 4.4 | the comparison |
| pcb1 | `bad-006` | 4.4 | 4.4 | 4.3 | the final run |
| pcb1 | `bad-007` | 4.4 | 4.1 | 4.4 | the comparison |
| pcb1 | `bad-014` | 4.4 | 4.1 | 4.4 | the comparison |
| pcb1 | `bad-018` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-024` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-026` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-028` | 4.1 | 4.1 | 4.4 | the final run |
| pcb1 | `bad-030` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-034` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-038` | 4.1 | 4.1 | 4.4 | the final run |
| pcb1 | `bad-041` | 4.3 | 4.1 | 4.3 | the comparison |
| pcb1 | `bad-043` | 4.3 | 4.2 | 4.3 | the comparison |
| pcb1 | `bad-044` | 4.3 | 4.1 | 4.3 | the comparison |
| pcb1 | `bad-045` | 4.3 | 4.1 | 4.3 | the comparison |
| pcb1 | `bad-046` | 4.3 | 4.2 | 4.3 | the comparison |
| pcb1 | `bad-049` | 4.3 | 4.1 | 4.3 | the comparison |
| pcb1 | `bad-054` | 4.3 | 4.2 | 4.3 | the comparison |
| pcb1 | `bad-055` | 4.3 | 4.2 | 4.3 | the comparison |
| pcb1 | `bad-056` | 4.3 | 4.1 | 4.3 | the comparison |
| pcb1 | `bad-058` | 4.3 | 4.2 | 4.3 | the comparison |
| pcb1 | `bad-059` | 4.3 | 4.1 | 4.3 | the comparison |
| pcb1 | `bad-062` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-063` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-064` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-066` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-068` | 4.1 | 4.1 | 4.4 | the final run |
| pcb1 | `bad-070` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-072` | 4.1 | 4.1 | 4.4 | the final run |
| pcb1 | `bad-073` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-074` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-077` | 4.1 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-082` | 4.1 | 4.1 | 4.4 | the final run |
| pcb1 | `bad-087` | 4.2 | 4.1 | 4.2 | the comparison |
| pcb1 | `bad-090` | 4.2 | 4.1 | 4.2 | the comparison |
| pcb4 | `bad-012` | 5.5 | 5.1 | 5.5 | the comparison |
| pcb4 | `bad-023` | 5.5 | 5.1 | 5.5 | the comparison |
| pcb4 | `bad-027` | 5.7 | 5.1 | 5.7 | the comparison |
| pcb4 | `bad-041` | 5.3 | 5.1 | 5.3 | the comparison |
| pcb4 | `bad-066` | 5.2 | 5.2 | 5.3 | the final run |
| pcb4 | `bad-067` | 5.2 | 5.1 | 5.2 | the comparison |
| pcb4 | `bad-069` | 5.2 | 5.1 | 5.2 | the comparison |
| pcb4 | `bad-073` | 5.2 | 5.1 | 5.2 | the comparison |
| pcb4 | `bad-094` | 5.3 | 5.1 | 5.3 | the comparison |
| pcb1 | `bad-051` | 4.1, 4.3 | 4.1 | 4.4 | the final run |
| pcb1 | `bad-069` | 4.1, 4.2 | 4.1 | 4.3 | the final run |
| pcb1 | `bad-080` | 4.1, 4.2 | 4.1 | 4.4 | the final run |
| pcb1 | `bad-084` | 4.1, 4.2 | 4.1 | 4.4 | the final run |
| pcb1 | `bad-097` | 4.1, 4.2 | 4.1 | 4.3 | the final run |
| pcb4 | `bad-002` | 5.7, 5.1 | 5.1 | 5.5 | the final run |
| pcb4 | `bad-004` | 5.7, 5.1 | 5.1 | 5.5 | the final run |
| pcb4 | `bad-009` | 5.5, 5.1 | 5.7 | 5.5 | the comparison |
| pcb4 | `bad-016` | 5.2, 5.1 | 5.1 | 5.5 | the final run |
| pcb4 | `bad-017` | 5.2, 5.5 | 5.7 | 5.5 | the comparison |
| pcb4 | `bad-022` | 5.6, 5.5 | 5.7 | 5.5 | the comparison |
| pcb4 | `bad-024` | 5.5, 5.3 | 5.1 | 5.5 | the comparison |
| pcb4 | `bad-030` | 5.7, 5.3 | 5.7 | 5.5 | the final run |
| pcb4 | `bad-031` | 5.3, 5.1 | 5.1 | 5.5 | the final run |
| pcb4 | `bad-036` | 5.6, 5.3 | 5.1 | 5.3 | the comparison |
| pcb4 | `bad-037` | 5.3, 5.1 | 5.2 | 5.3 | the comparison |
| pcb4 | `bad-042` | 5.3, 5.1 | 5.2 | 5.3 | the comparison |
| pcb4 | `bad-047` | 5.6, 5.2, 5.1 | 5.2 | 5.5 | the final run |
| pcb4 | `bad-050` | 5.2, 5.1 | 5.1 | 5.5 | the final run |
| pcb4 | `bad-058` | 5.2, 5.5, 5.3 | 5.1 | 5.5 | the comparison |
| pcb4 | `bad-060` | 5.2, 5.5 | 5.1 | 5.2 | the comparison |
| pcb4 | `bad-070` | 5.2, 5.1 | 5.1 | 5.5 | the final run |
| pcb4 | `bad-071` | 5.6, 5.2 | 5.1 | 5.2 | the comparison |
| pcb4 | `bad-074` | 5.2, 5.1 | 5.1 | 5.3 | the final run |
| pcb4 | `bad-075` | 5.6, 5.1 | 5.1 | 5.5 | the final run |
| pcb4 | `bad-078` | 5.6, 5.1 | 5.1 | 5.3 | the final run |
| pcb4 | `bad-080` | 5.4, 5.1 | 5.1 | 5.3 | the final run |
| pcb4 | `bad-082` | 5.4, 5.1 | 5.1 | 5.2 | the final run |
| pcb4 | `bad-084` | 5.3, 5.1 | 5.1 | 5.5 | the final run |
| pcb4 | `bad-085` | 5.4, 5.1 | 5.1 | no valid answer | the final run |
| pcb4 | `bad-087` | 5.3, 5.1 | 5.1 | 5.5 | the final run |
| pcb4 | `bad-088` | 5.4, 5.1 | 5.1 | 5.5 | the final run |
| pcb4 | `bad-089` | 5.2, 5.4 | 5.2 | 5.5 | the final run |
| pcb4 | `bad-092` | 5.4, 5.1 | 5.1 | 5.3 | the final run |
| pcb4 | `bad-095` | 5.4, 5.1 | 5.1 | no valid answer | the final run |
| pcb4 | `bad-097` | 5.4, 5.1 | 5.1 | 5.3 | the final run |
| pcb4 | `bad-098` | 5.4, 5.1 | 5.1 | 5.3 | the final run |

## Repeating it

The judge's server is started by `scripts/serve_vlm_xpu.sh start`, none of its settings
overridden, and this run's command is started on the machine as:

```
SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 .venv/bin/spec-to-inspector bench --batch corrections --results results/stage2/comparison-corrections/bench.json --readme results/stage2/comparison-corrections/README.md --against results/stage2/final/bench.json --declared-store results/stage2/comparison-corrections/store.sqlite3
```

This run was compared with the run of the same command before it (2026-11-07T14:45:08+00:00), image by image:

- 401 images in both runs: 0 flagged in one and not the other, 0 with another anomaly score, 0 with another board outcome.
- 215 images answered on region 1 in both runs: 0 with another heading cited, 0 with another class named, 0 with another sentence.
- Images that differ in anything but the sentence: none.
- Every counted figure of the protocol is equal in the two runs.

## The refused answers

5 answers were refused. Each is sent back once with what was wrong with it; a second refusal refers the area to an engineer.

| Kind | Answers |
| --- | --- |
| padded to the token limit | 5 |
| not JSON | 0 |
| reason over the character limit | 0 |
| reason states a figure | 0 |
| otherwise invalid | 0 |

### Padded to the token limit

5 answers ran to the token limit with the string unclosed, and were refused as not JSON.

| Part | Board | Area | Asking | Kind |
| --- | --- | --- | --- | --- |
| pcb4 | `bad-080` | 1 | 1 | padded to the token limit |
| pcb4 | `bad-085` | 1 | 1 | padded to the token limit |
| pcb4 | `bad-085` | 1 | 2 | padded to the token limit |
| pcb4 | `bad-095` | 1 | 1 | padded to the token limit |
| pcb4 | `bad-095` | 1 | 2 | padded to the token limit |

## What these figures are not

- Not held out. VisA's PCB test split is the only labelled data there is. The anomaly
  model's threshold is chosen on this same split, the judge's prompt was written with
  sight of answers on some of these images, and the protocol was written after a bench
  had been read on the same set.
- Not the final figure, which keeps its empty store. This is what a store of corrections does to the boards it does not hold, read by the paired table.
- One specification, one model, one precision, one machine.
- Not a figure against Stage I. The host, the precision, the server and the answer
  pattern all differ, and no figure separates them.
- The labels are VisA's annotation mapped to clauses by a written table,
  `eval/clause_mapping.md`.
