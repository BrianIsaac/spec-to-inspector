# Stage II: what the machine measured

Written by `spec-to-inspector bench --limit 20 --batch one-card --results /home/devcloud/one-card/warm/warming.json --readme /home/devcloud/one-card/warm/warming.md` on 2026-11-07 (2026-11-07T15:28:17+00:00).
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

**This is a partial run** (40 labelled images, the first 20 of each kind per part; parts pcb1, pcb4). Its figures are not the protocol's.

**This run is not final.** Its record lacks what the protocol asks of a final run:

- the whole labelled set: this is a partial run.

## The figures

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Clause-citation accuracy, strict, single-defect images | 52.0% (13 of 25) | 25 | 33.5% to 70.0% |
| Clause-citation accuracy, strict, single-defect images, pcb1 only | 63.2% (12 of 19) | 19 | 41.0% to 80.9% |
| Clause-citation accuracy, strict, single-defect images, pcb4 only | 16.7% (1 of 6) | 6 | 3.0% to 56.4% |
| Clause-citation accuracy, lenient, multi-defect images | 80.0% (12 of 15) | 15 | 54.8% to 93.0% |
| Clause-citation accuracy per region, one defect type under region 1 | 54.5% (18 of 33) | 33 | 38.0% to 70.2% |
| Anomalous boards referred for review | 5.0% (2 of 40) | 40 | 1.4% to 16.5% |
| Good boards rejected (false rejects) | 5.0% (2 of 40) | 40 | 1.4% to 16.5% |
| Good boards flagged by the anomaly model | 5.0% (2 of 40) | 40 | 1.4% to 16.5% |

| Figure | Value |
| --- | --- |
| A flagged image, end to end, median | 2.38 s (p95 2.70 s, n 42) |
| The VLM's answer to one flagged area, cold, median | 2.13 s (p95 2.29 s, n 42) |
| From specification to a working inspector, one part | 11.8 min (parse 7.0 s measured here; fit as recorded at training: pcb1 699 s, pcb4 701 s) |
| From specification to a working inspector, all parts in turn | 23.4 min |
| Peak GPU memory, VLM server while judging | not read |
| Peak GPU memory, the card while judging | 30,166 MiB |

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

The cold comes from the server's start, not the request: vLLM ignores the request's `cache_prompt`. The server's flags: `--no-enable-prefix-caching`, `--mm-processor-cache-gb 0`. Its engine's own line on the prefix cache says it is off. It started at 2026-11-07T15:23:51.34348348Z.

During this run the highest of 11 rates in its log is 0.0%, and its counters added 0 tokens of hits of 0 looked for. Any rate above 0.0% voids a run, so a run that has a record has none. The log of this run is `/home/devcloud/one-card/warm/warming.server-log.20261107T152558Z.txt`.

## What else the run was made of

- The warm-up: one question before the judge's clock, on pcb1 good-0214, in 6.32 s; its answer is not recorded.
- The reason's pattern: `^[^0-9\n\r"\\]{1,240}$`.
- The labelled set: `eval/clause_labels.csv` (SHA-256 `44866105f3fdad88`), 40 anomalous test images: 25 single-defect, 15 multi-defect.
- The specification: `specs/pcb-spec.pdf`, parsed in 7.0 s into 16 clauses under 11 numbered headings, equal to the tracked `specs/pcb-spec.clauses.json`.
- The corrections store empty: 0 of 80 decisions had a correction in a prompt (`decision.corrected.in_prompt`).

The anomaly models, not retrained here:

| Part | Checkpoint | SHA-256 | Trained | Image threshold | Chosen on the test |
| --- | --- | --- | --- | --- | --- |
| pcb1 | `/home/devcloud/week2/run-1/models/patchcore/pcb1/model.ckpt` | `b71ff0c3db7e780c6198db5686569fa59de4a56b5663557b56d90e237b37a855` | 2026-11-06T17:17:44+00:00 | 31.319489 | yes |
| pcb4 | `/home/devcloud/week2/run-1/models/patchcore/pcb4/model.ckpt` | `cc571d9a4c56ee791888a2f6ce73e7db2f7f46b57c7aeb683ce7ba447f03ccb4` | 2026-11-06T17:59:34+00:00 | 30.048744 | yes |

Each checkpoint was held to `results/stage2/checkpoints.json` (SHA-256 `af420d92ee128a05`) before it scored anything: another digest voids the run.

## The boards on the threshold

The rule is a strict `>`. A score within 0.001 of its part's threshold is decided by float noise, so the figures are read with these boards known. No margin and no `>=` is applied.

None of this run's boards (pcb1, pcb4) sits on its threshold.

| Part | Board | Ground truth | Score | Threshold | Strictly above | This run |
| --- | --- | --- | --- | --- | --- | --- |
| pcb2 | `bad-060` | bad | 29.304890 | 29.304890 | no | no: week 2's record |
| pcb3 | `bad-097` | bad | 31.543020 | 31.543051 | no | no: week 2's record |

pcb2, pcb3: the bench does not score them, having no clause to hold them to, so their figures are those of the first training on the machine and this run did not measure them.

## 1. The headline: strict accuracy on the single-defect images

The citation is the heading id the judge cited on region 1, the most anomalous area.
An image with no citation (not flagged, not asked, no valid answer, or "no clause
applies") counts as wrong.

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Strict accuracy | 52.0% (13 of 25) | 25 | 33.5% to 70.0% |
| Strict accuracy, pcb1 only | 63.2% (12 of 19) | 19 | 41.0% to 80.9% |
| Strict accuracy, pcb4 only | 16.7% (1 of 6) | 6 | 3.0% to 56.4% |
| Flagged by the anomaly model | 100.0% (25 of 25) | 25 | 86.7% to 100.0% |
| Flagged by the anomaly model, pcb1 only | 100.0% (19 of 19) | 19 | 83.2% to 100.0% |
| Flagged by the anomaly model, pcb4 only | 100.0% (6 of 6) | 6 | 61.0% to 100.0% |
| Region 1 lies on the labelled defect | 88.0% (22 of 25) | 25 | 70.0% to 95.8% |
| Region 1 lies on the labelled defect, pcb1 only | 89.5% (17 of 19) | 19 | 68.6% to 97.1% |
| Region 1 lies on the labelled defect, pcb4 only | 83.3% (5 of 6) | 6 | 43.6% to 97.0% |
| Strict accuracy, flagged images only (conditional) | 52.0% (13 of 25) | 25 | 33.5% to 70.0% |
| Strict accuracy, flagged images only (conditional), pcb1 only | 63.2% (12 of 19) | 19 | 41.0% to 80.9% |
| Strict accuracy, flagged images only (conditional), pcb4 only | 16.7% (1 of 6) | 6 | 3.0% to 56.4% |
| Strict accuracy, region 1 on the defect only (conditional) | 54.5% (12 of 22) | 22 | 34.7% to 73.1% |
| Strict accuracy, region 1 on the defect only (conditional), pcb1 only | 64.7% (11 of 17) | 17 | 41.3% to 82.7% |
| Strict accuracy, region 1 on the defect only (conditional), pcb4 only | 20.0% (1 of 5) | 5 | 3.6% to 62.4% |

For the correct citations, what code then did (the row is a measurement's outcome, not
what is scored):

- Row of the clause table applied: 4.4 9, 4.1 3, 5.5 1.
- Outcome of region 1: reject 13.

## 2. The lenient figure: the multi-defect images

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Lenient accuracy | 80.0% (12 of 15) | 15 | 54.8% to 93.0% |
| Lenient accuracy, pcb1 only | 100.0% (1 of 1) | 1 | 20.7% to 100.0% |
| Lenient accuracy, pcb4 only | 78.6% (11 of 14) | 14 | 52.4% to 92.4% |

## 3. The per-region figure

Images, single and multi, whose region 1 lies on exactly one of VisA's defect types,
scored against that type's heading.

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Per-region accuracy | 54.5% (18 of 33) | 33 | 38.0% to 70.2% |
| Per-region accuracy, pcb1 only | 64.7% (11 of 17) | 17 | 41.3% to 82.7% |
| Per-region accuracy, pcb4 only | 43.8% (7 of 16) | 16 | 23.1% to 66.8% |

## 4. The confusion tables

Rows are the expected defect type; columns are the type of the heading cited, or why
there is no citation.

pcb1, single-defect images:

| Expected \ cited | melt | scratch | bent | Images |
| --- | --- | --- | --- | --- |
| **melt** | 3 | 1 | 1 | 5 |
| **bent** | 5 | 0 | 9 | 14 |

pcb4, single-defect images:

| Expected \ cited | dirt | extra | damage | Images |
| --- | --- | --- | --- | --- |
| **damage** | 3 | 1 | 1 | 5 |
| **burnt** | 1 | 0 | 0 | 1 |

pcb1, images with one type under region 1, by that type:

| Expected \ cited | melt | bent | Images |
| --- | --- | --- | --- |
| **melt** | 2 | 1 | 3 |
| **bent** | 5 | 9 | 14 |

pcb4, images with one type under region 1, by that type:

| Expected \ cited | dirt | extra | damage | burnt | Images |
| --- | --- | --- | --- | --- | --- |
| **dirt** | 2 | 0 | 0 | 0 | 2 |
| **missing** | 1 | 0 | 0 | 0 | 1 |
| **damage** | 3 | 1 | 3 | 2 | 9 |
| **burnt** | 1 | 0 | 1 | 2 | 4 |

Citations on labelled images whose named class is not the class of the heading cited: 0.

## 5. Needs review, by cause, on the anomalous boards

- Boards: 40 anomalous; 0 not flagged by the anomaly model; of the flagged, reject 38, needs review 2.
- Boards referred for review: 5.0% (2 of 40), 95% interval 1.4% to 16.5%. By cause: not measured 2.
- Areas put to the judge on those boards: 40; reject 38, needs review 2.
- Areas referred for review: 5.0% (2 of 40), 95% interval 1.4% to 16.5%. By cause: not measured 2.

## 6. False alarms on the good boards

| Part | Good boards | Flagged | Rejected (false rejects), 95% interval | Referred | Accepted after judging |
| --- | --- | --- | --- | --- | --- |
| all | 40 | 5.0% (2 of 40) | 5.0% (2 of 40), 1.4% to 16.5% | 0.0% (0 of 40) | 0.0% (0 of 40) |
| pcb1 | 20 | 5.0% (1 of 20) | 5.0% (1 of 20), 0.9% to 23.6% | 0.0% (0 of 20) | 0.0% (0 of 20) |
| pcb4 | 20 | 5.0% (1 of 20) | 5.0% (1 of 20), 0.9% to 23.6% | 0.0% (0 of 20) | 0.0% (0 of 20) |

- What the judge cited on region 1 of the flagged good boards: 4.2 1, 5.2 1.
- Boards: 40 good; 38 not flagged by the anomaly model; of the flagged, reject 2.
- Boards referred for review: 0.0% (0 of 40), 95% interval 0.0% to 8.8%. By cause: none.
- Areas put to the judge on those boards: 2; reject 2.
- Areas referred for review: 0.0% (0 of 2), 95% interval 0.0% to 65.8%. By cause: none.

## 7. Time per image, by stage

| Stage | Time |
| --- | --- |
| Parse the specification (once per specification; includes loading the parser's models) | 7.0 s |
| Anomaly model, pcb1, per image (batch 16; scoring and writing maps, masks and crops) | 161 ms |
| Anomaly model, pcb4, per image (batch 16; scoring and writing maps, masks and crops) | 98 ms |
| Measure and draw a flagged image's areas, the rule, the decision | 0.09 s (p95 0.23 s, n 42) |
| The VLM's answer to one area, cold | 2.13 s (p95 2.29 s, n 42) |
| The VLM's answers to one flagged image | 2.13 s (p95 2.29 s, n 42) |
| A flagged image, end to end | 2.38 s (p95 2.70 s, n 42) |

42 flagged images, 42 areas asked (1.00 an image); the judge's stage took 95 s in all. An image that is not flagged costs the anomaly model's time only. Prompt tokens, median: 4,703; answer tokens, median: 34; output rate, median: -.

## 8. Minutes from specification to a working inspector

| Part | Parse, measured in this run | Fit, as recorded at training | Together |
| --- | --- | --- | --- |
| pcb1 | 7.0 s | 699 s | 11.8 min |
| pcb4 | 7.0 s | 701 s | 11.8 min |
| all parts, one after another | 7.0 s | 1400 s | 23.4 min |

Training is not repeated by the bench: the fit time is the one in each model's own
training record. 23.4 minutes is every part of this run in turn.

## 9. Peak GPU memory, by stage

| Stage | The stage's own process | The card | The card before | Readings |
| --- | --- | --- | --- | --- |
| Anomaly model scoring, pcb1 | 2,551 MiB (the bench's process) | 29,511 MiB | 28,510 MiB | 8 at 0.5 s |
| Anomaly model scoring, pcb4 | 2,552 MiB (the bench's process) | 29,512 MiB | 28,970 MiB | 5 at 0.5 s |
| Judging | not read (the VLM server) | 30,166 MiB | 28,690 MiB | 123 at 0.5 s |

Read from `xpu-smi`, sampled by the bench: the anomaly model on pcb1, card 0000:17:00.0, under ZE_AFFINITY_MASK=0; the anomaly model on pcb4, card 0000:17:00.0, under ZE_AFFINITY_MASK=0; the judge, card 0000:17:00.0. Each stage has a card to itself, so the card stands for the process.
Where a process's own figure says `not read`: the judge's server runs in a container: xpu-smi ps does not list its process, even under sudo, and ss shows no pid, so its own figure is null and its card stands for it.

## Repeating it

The judge's server is started by `scripts/serve_vlm_xpu.sh start`, none of its settings
overridden, and this run's command is started on the machine as:

```
SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 .venv/bin/spec-to-inspector bench --limit 20 --batch one-card --results /home/devcloud/one-card/warm/warming.json --readme /home/devcloud/one-card/warm/warming.md
```

This file holds one run. Run the command again and the next record says how many
of its answers differ from this one.

## The refused answers

0 answers were refused. Each is sent back once with what was wrong with it; a second refusal refers the area to an engineer.

| Kind | Answers |
| --- | --- |
| padded to the token limit | 0 |
| not JSON | 0 |
| reason over the character limit | 0 |
| reason states a figure | 0 |
| otherwise invalid | 0 |

### Padded to the token limit

No answer ran to the token limit.

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
