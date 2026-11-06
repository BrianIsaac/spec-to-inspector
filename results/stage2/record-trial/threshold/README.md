# Stage II: what the machine measured

Written by `spec-to-inspector bench --part pcb1 --limit 30 --batch threshold --results /home/devcloud/week3-record/threshold/bench.json --readme /home/devcloud/week3-record/threshold/README.md` on 2026-11-06 (2026-11-06T22:18:14+00:00).
Not edited by hand: a figure that is wrong here is wrong in its record, and the remedy
is to run the command again.

The figures follow these files, each read at the time of the run:

| File | SHA-256 |
| --- | --- |
| `eval/PROTOCOL-stage2.md` | `ebbd8cc1cb25172f7d74cddf8190e0826204eb6b3c8cc7e1da83a565ead4e3f6` |
| `eval/PROTOCOL-stage2-addition-region-columns-2026-11-07.md` | `8d8d4ef19e95354a4a1ab220e6eb9dc51865c87b2ae6e9f9da1464bdd4c5b1b1` |

Every proportion is a count of its N with the 95% Wilson score interval. Nothing here is
a held-out figure: see the last section.

**This is a partial run** (30 labelled images, the first 30 of each kind per part; parts pcb1). Its figures are not the protocol's.

**This run is not final.** Its record lacks what the protocol asks of a final run:

- the whole labelled set: this is a partial run.

## The figures

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Clause-citation accuracy, strict, single-defect images | 53.6% (15 of 28) | 28 | 35.8% to 70.5% |
| Clause-citation accuracy, strict, single-defect images, pcb1 only | 53.6% (15 of 28) | 28 | 35.8% to 70.5% |
| Clause-citation accuracy, lenient, multi-defect images | 50.0% (1 of 2) | 2 | 9.5% to 90.5% |
| Clause-citation accuracy per region, one defect type under region 1 | 61.9% (13 of 21) | 21 | 40.9% to 79.2% |
| Anomalous boards referred for review | 6.7% (2 of 30) | 30 | 1.8% to 21.3% |
| Good boards rejected (false rejects) | 3.3% (1 of 30) | 30 | 0.6% to 16.7% |
| Good boards flagged by the anomaly model | 10.0% (3 of 30) | 30 | 3.5% to 25.6% |

| Figure | Value |
| --- | --- |
| A flagged image, end to end, median | 2.38 s (p95 2.64 s, n 29) |
| The VLM's answer to one flagged area, cold, median | 2.15 s (p95 2.34 s, n 29) |
| From specification to a working inspector, one part | 12.3 min (parse 6.3 s measured here; fit as recorded at training: pcb1 729 s) |
| From specification to a working inspector, all parts in turn | 12.3 min |
| Peak GPU memory, VLM server while judging | not read |
| Peak GPU memory, the card while judging | 29,471 MiB |

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

The judge's card: Intel(R) Arc(TM) Pro B70 Graphics. Its image minimum: 1024 tokens. Up to 3 areas an image, stopping at the first reject.

The cold comes from the server's start, not the request: vLLM ignores the request's `cache_prompt`. The server's flags: `--no-enable-prefix-caching`, `--mm-processor-cache-gb 0`. Its engine's own line on the prefix cache says it is off. It started at 2026-11-06T15:40:16.517468169Z.

During this run the highest of 8 rates in its log is 0.0%, and its counters added 0 tokens of hits of 0 looked for. Any rate above 0.0% voids a run, so a run that has a record has none. The log of this run is `/home/devcloud/week3-record/threshold/bench.server-log.20261106T221634Z.txt`.

## What else the run was made of

- The warm-up: one question before the judge's clock, on pcb1 good-0214, in 1.98 s; its answer is not recorded.
- The reason's pattern: `^[^0-9\n\r"\\]{1,240}$`.
- The labelled set: `eval/clause_labels.csv` (SHA-256 `0477eb9706a7772b`), 30 anomalous test images: 28 single-defect, 2 multi-defect.
- The specification: `specs/pcb-spec.pdf`, parsed in 6.3 s into 16 clauses under 11 numbered headings, equal to the tracked `specs/pcb-spec.clauses.json`.
- The corrections store empty: 0 of 60 decisions had a correction in a prompt (`decision.corrected.in_prompt`).

The anomaly models, not retrained here:

| Part | Checkpoint | SHA-256 | Trained | Image threshold | Chosen on the test |
| --- | --- | --- | --- | --- | --- |
| pcb1 | `models/patchcore/pcb1/model.ckpt` | `6250fb1451f4412057e54d1dc676a2a69e3d4d7575ac48d5fad281bb7f9ec187` | 2026-10-10T16:13:34+00:00 | 31.319473 | yes |

## The boards on the threshold

The rule is a strict `>`. A score within 0.001 of its part's threshold is decided by float noise, so the figures are read with these boards known. No margin and no `>=` is applied.

| Part | Board | Ground truth | Score | Threshold | Strictly above | This run |
| --- | --- | --- | --- | --- | --- | --- |
| pcb1 | `bad-029` | bad | 31.319450 | 31.319473 | no | yes |
| pcb2 | `bad-060` | bad | 29.304890 | 29.304890 | no | no: week 2's record |
| pcb3 | `bad-097` | bad | 31.543020 | 31.543051 | no | no: week 2's record |

pcb2, pcb3: the bench does not score them, having no clause to hold them to, so their figures are those of the first training on the machine and this run did not measure them.

## 1. The headline: strict accuracy on the single-defect images

The citation is the heading id the judge cited on region 1, the most anomalous area.
An image with no citation (not flagged, not asked, no valid answer, or "no clause
applies") counts as wrong.

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Strict accuracy | 53.6% (15 of 28) | 28 | 35.8% to 70.5% |
| Strict accuracy, pcb1 only | 53.6% (15 of 28) | 28 | 35.8% to 70.5% |
| Flagged by the anomaly model | 89.3% (25 of 28) | 28 | 72.8% to 96.3% |
| Flagged by the anomaly model, pcb1 only | 89.3% (25 of 28) | 28 | 72.8% to 96.3% |
| Region 1 lies on the labelled defect | 75.0% (21 of 28) | 28 | 56.6% to 87.3% |
| Region 1 lies on the labelled defect, pcb1 only | 75.0% (21 of 28) | 28 | 56.6% to 87.3% |
| Strict accuracy, flagged images only (conditional) | 60.0% (15 of 25) | 25 | 40.7% to 76.6% |
| Strict accuracy, flagged images only (conditional), pcb1 only | 60.0% (15 of 25) | 25 | 40.7% to 76.6% |
| Strict accuracy, region 1 on the defect only (conditional) | 61.9% (13 of 21) | 21 | 40.9% to 79.2% |
| Strict accuracy, region 1 on the defect only (conditional), pcb1 only | 61.9% (13 of 21) | 21 | 40.9% to 79.2% |

For the correct citations, what code then did (the row is a measurement's outcome, not
what is scored):

- Row of the clause table applied: 4.4 8, 4.1 7.
- Outcome of region 1: reject 15.

## 2. The lenient figure: the multi-defect images

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Lenient accuracy | 50.0% (1 of 2) | 2 | 9.5% to 90.5% |
| Lenient accuracy, pcb1 only | 50.0% (1 of 2) | 2 | 9.5% to 90.5% |

## 3. The per-region figure

Images, single and multi, whose region 1 lies on exactly one of VisA's defect types,
scored against that type's heading.

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Per-region accuracy | 61.9% (13 of 21) | 21 | 40.9% to 79.2% |
| Per-region accuracy, pcb1 only | 61.9% (13 of 21) | 21 | 40.9% to 79.2% |

## 4. The confusion tables

Rows are the expected defect type; columns are the type of the heading cited, or why
there is no citation.

pcb1, single-defect images:

| Expected \ cited | melt | scratch | bent | not flagged | Images |
| --- | --- | --- | --- | --- | --- |
| **melt** | 7 | 2 | 2 | 3 | 14 |
| **bent** | 6 | 0 | 8 | 0 | 14 |

pcb1, images with one type under region 1, by that type:

| Expected \ cited | melt | bent | Images |
| --- | --- | --- | --- |
| **melt** | 5 | 2 | 7 |
| **bent** | 6 | 8 | 14 |

Citations on labelled images whose named class is not the class of the heading cited: 0.

## 5. Needs review, by cause, on the anomalous boards

- Boards: 30 anomalous; 4 not flagged by the anomaly model; of the flagged, reject 24, needs review 2.
- Boards referred for review: 6.7% (2 of 30), 95% interval 1.8% to 21.3%. By cause: not measured 2.
- Areas put to the judge on those boards: 26; reject 24, needs review 2.
- Areas referred for review: 7.7% (2 of 26), 95% interval 2.1% to 24.1%. By cause: not measured 2.

## 6. False alarms on the good boards

| Part | Good boards | Flagged | Rejected (false rejects), 95% interval | Referred | Accepted after judging |
| --- | --- | --- | --- | --- | --- |
| all | 30 | 10.0% (3 of 30) | 3.3% (1 of 30), 0.6% to 16.7% | 6.7% (2 of 30) | 0.0% (0 of 30) |
| pcb1 | 30 | 10.0% (3 of 30) | 3.3% (1 of 30), 0.6% to 16.7% | 6.7% (2 of 30) | 0.0% (0 of 30) |

- What the judge cited on region 1 of the flagged good boards: 4.2 3.
- Boards: 30 good; 27 not flagged by the anomaly model; of the flagged, needs review 2, reject 1.
- Boards referred for review: 6.7% (2 of 30), 95% interval 1.8% to 21.3%. By cause: not measured 2.
- Areas put to the judge on those boards: 3; needs review 2, reject 1.
- Areas referred for review: 66.7% (2 of 3), 95% interval 20.8% to 93.9%. By cause: not measured 2.

## 7. Time per image, by stage

| Stage | Time |
| --- | --- |
| Parse the specification (once per specification; includes loading the parser's models) | 6.3 s |
| Anomaly model, pcb1, per image (batch 16; scoring and writing maps, masks and crops) | 128 ms |
| Measure and draw a flagged image's areas, the rule, the decision | 0.10 s (p95 0.21 s, n 29) |
| The VLM's answer to one area, cold | 2.15 s (p95 2.34 s, n 29) |
| The VLM's answers to one flagged image | 2.15 s (p95 2.34 s, n 29) |
| A flagged image, end to end | 2.38 s (p95 2.64 s, n 29) |

29 flagged images, 29 areas asked (1.00 an image); the judge's stage took 66 s in all. An image that is not flagged costs the anomaly model's time only. Prompt tokens, median: 4,670; answer tokens, median: 36; output rate, median: -.

## 8. Minutes from specification to a working inspector

| Part | Parse, measured in this run | Fit, as recorded at training | Together |
| --- | --- | --- | --- |
| pcb1 | 6.3 s | 729 s | 12.3 min |
| all parts, one after another | 6.3 s | 729 s | 12.3 min |

Training is not repeated by the bench: the fit time is the one in each model's own
training record. 12.3 minutes is every part of this run in turn.

## 9. Peak GPU memory, by stage

| Stage | The stage's own process | The card | The card before | Readings |
| --- | --- | --- | --- | --- |
| Anomaly model scoring, pcb1 | 2,552 MiB (the bench's process) | 2,594 MiB | 1,592 MiB | 9 at 0.5 s |
| Judging | not read (the VLM server) | 29,471 MiB | 29,471 MiB | 86 at 0.5 s |

Read from `xpu-smi`, sampled by the bench: the anomaly model on pcb1, card 0000:17:00.0, under ZE_AFFINITY_MASK=0; the judge, card 0000:ba:00.0. Each stage has a card to itself, so the card stands for the process.
Where a process's own figure says `not read`: the judge's server runs in a container: xpu-smi ps does not list its process, even under sudo, and ss shows no pid, so its own figure is null and its card stands for it.

## Repeating it

The judge's server is started by `scripts/serve_vlm_xpu.sh start`, none of its settings
overridden, and this run's command is started on the machine as:

```
SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 .venv/bin/spec-to-inspector bench --part pcb1 --limit 30 --batch threshold --results /home/devcloud/week3-record/threshold/bench.json --readme /home/devcloud/week3-record/threshold/README.md
```

This run was compared with the run of the same command before it (2026-11-06T21:31:22+00:00), image by image:

- 60 images in both runs: 0 flagged in one and not the other, 0 with another anomaly score, 0 with another board outcome.
- 29 images answered on region 1 in both runs: 0 with another heading cited, 0 with another class named, 0 with another sentence.
- Images that differ in anything but the sentence: none.
- Every counted figure of the protocol is equal in the two runs.

## What these figures are not

- Not held out. VisA's PCB test split is the only labelled data there is. The anomaly
  model's threshold is chosen on this same split, the judge's prompt was written with
  sight of answers on some of these images, and the protocol was written after a bench
  had been read on the same set.
- Not a figure for the corrections loop: the store is empty throughout.
- One specification, one model, one precision, one machine.
- Not a figure against Stage I. The host, the precision, the server and the answer
  pattern all differ, and no figure separates them.
- The labels are VisA's annotation mapped to clauses by a written table,
  `eval/clause_mapping.md`.
