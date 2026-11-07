# Stage II: what the machine measured

Written by `spec-to-inspector bench --limit 3 --batch corrections --results /home/devcloud/corrections-run/trial/bench.json --readme /home/devcloud/corrections-run/trial/README.md --declared-store results/stage2/comparison-corrections/store.sqlite3` on 2026-11-07 (2026-11-07T14:33:58+00:00).
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

**This is a partial run** (6 labelled images, the first 3 of each kind per part; parts pcb1, pcb4). Its figures are not the protocol's.

**This run is not final.** Its record lacks what the protocol asks of a final run:

- the whole labelled set: this is a partial run.
- the final setting: this is the corrections comparison.

The 20 boards the store was drawn from are left out of figures 1 to 7, since it holds their answers. Figure 9 is the card's and has no boards to leave out, and the judge's stage's time is the whole run's.

## The figures

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Clause-citation accuracy, strict, single-defect images | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |
| Clause-citation accuracy, strict, single-defect images, pcb1 only | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |
| Clause-citation accuracy, strict, single-defect images, pcb4 only | 0 of 0 | 0 | - |
| Clause-citation accuracy, lenient, multi-defect images | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |
| Clause-citation accuracy per region, one defect type under region 1 | 66.7% (4 of 6) | 6 | 30.0% to 90.3% |
| Anomalous boards referred for review | 0.0% (0 of 6) | 6 | 0.0% to 39.0% |
| Good boards rejected (false rejects) | 0.0% (0 of 6) | 6 | 0.0% to 39.0% |
| Good boards flagged by the anomaly model | 0.0% (0 of 6) | 6 | 0.0% to 39.0% |

| Figure | Value |
| --- | --- |
| A flagged image, end to end, median | 2.63 s (p95 2.86 s, n 6) |
| The VLM's answer to one flagged area, cold, median | 2.21 s (p95 2.32 s, n 6) |
| From specification to a working inspector, one part | 11.8 min (parse 7.2 s measured here; fit as recorded at training: pcb1 699 s, pcb4 701 s) |
| From specification to a working inspector, all parts in turn | 23.4 min |
| Peak GPU memory, VLM server while judging | not read |
| Peak GPU memory, the card while judging | 29,786 MiB |

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

During this run the highest of 2 rates in its log is 0.0%, and its counters added 0 tokens of hits of 0 looked for. Any rate above 0.0% voids a run, so a run that has a record has none. The log of this run is `/home/devcloud/corrections-run/trial/bench.server-log.20261107T143310Z.txt`.

## What else the run was made of

- The warm-up: one question before the judge's clock, on pcb1 bad-000, in 2.06 s; its answer is not recorded.
- The reason's pattern: `^[^0-9\n\r"\\]{1,240}$`.
- The labelled set: `eval/clause_labels.csv` (SHA-256 `44866105f3fdad88`), 6 anomalous test images: 3 single-defect, 3 multi-defect.
- The specification: `specs/pcb-spec.pdf`, parsed in 7.2 s into 16 clauses under 11 numbered headings, equal to the tracked `specs/pcb-spec.clauses.json`.
- The corrections: the declared store, below. 6 of 12 decisions had a correction in a prompt (`decision.corrected.in_prompt`), and 6 boards were flagged.

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
| Strict accuracy | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |
| Strict accuracy, pcb1 only | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |
| Strict accuracy, pcb4 only | 0 of 0 | 0 | - |
| Flagged by the anomaly model | 100.0% (3 of 3) | 3 | 43.9% to 100.0% |
| Flagged by the anomaly model, pcb1 only | 100.0% (3 of 3) | 3 | 43.9% to 100.0% |
| Flagged by the anomaly model, pcb4 only | 0 of 0 | 0 | - |
| Region 1 lies on the labelled defect | 100.0% (3 of 3) | 3 | 43.9% to 100.0% |
| Region 1 lies on the labelled defect, pcb1 only | 100.0% (3 of 3) | 3 | 43.9% to 100.0% |
| Region 1 lies on the labelled defect, pcb4 only | 0 of 0 | 0 | - |
| Strict accuracy, flagged images only (conditional) | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |
| Strict accuracy, flagged images only (conditional), pcb1 only | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |
| Strict accuracy, flagged images only (conditional), pcb4 only | 0 of 0 | 0 | - |
| Strict accuracy, region 1 on the defect only (conditional) | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |
| Strict accuracy, region 1 on the defect only (conditional), pcb1 only | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |
| Strict accuracy, region 1 on the defect only (conditional), pcb4 only | 0 of 0 | 0 | - |

For the correct citations, what code then did (the row is a measurement's outcome, not
what is scored):

- Row of the clause table applied: 4.4 2.
- Outcome of region 1: reject 2.

## 2. The lenient figure: the multi-defect images

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Lenient accuracy | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |
| Lenient accuracy, pcb1 only | 0 of 0 | 0 | - |
| Lenient accuracy, pcb4 only | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |

## 3. The per-region figure

Images, single and multi, whose region 1 lies on exactly one of VisA's defect types,
scored against that type's heading.

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Per-region accuracy | 66.7% (4 of 6) | 6 | 30.0% to 90.3% |
| Per-region accuracy, pcb1 only | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |
| Per-region accuracy, pcb4 only | 66.7% (2 of 3) | 3 | 20.8% to 93.9% |

## 4. The confusion tables

Rows are the expected defect type; columns are the type of the heading cited, or why
there is no citation.

pcb1, single-defect images:

| Expected \ cited | missing | bent | Images |
| --- | --- | --- | --- |
| **bent** | 1 | 2 | 3 |

pcb1, images with one type under region 1, by that type:

| Expected \ cited | missing | bent | Images |
| --- | --- | --- | --- |
| **bent** | 1 | 2 | 3 |

pcb4, images with one type under region 1, by that type:

| Expected \ cited | damage | burnt | Images |
| --- | --- | --- | --- |
| **dirt** | 1 | 0 | 1 |
| **burnt** | 0 | 2 | 2 |

Citations on labelled images whose named class is not the class of the heading cited: 0.

## 5. Needs review, by cause, on the anomalous boards

- Boards: 6 anomalous; 0 not flagged by the anomaly model; of the flagged, reject 6.
- Boards referred for review: 0.0% (0 of 6), 95% interval 0.0% to 39.0%. By cause: none.
- Areas put to the judge on those boards: 6; reject 6.
- Areas referred for review: 0.0% (0 of 6), 95% interval 0.0% to 39.0%. By cause: none.

## 6. False alarms on the good boards

| Part | Good boards | Flagged | Rejected (false rejects), 95% interval | Referred | Accepted after judging |
| --- | --- | --- | --- | --- | --- |
| all | 6 | 0.0% (0 of 6) | 0.0% (0 of 6), 0.0% to 39.0% | 0.0% (0 of 6) | 0.0% (0 of 6) |
| pcb1 | 3 | 0.0% (0 of 3) | 0.0% (0 of 3), 0.0% to 56.1% | 0.0% (0 of 3) | 0.0% (0 of 3) |
| pcb4 | 3 | 0.0% (0 of 3) | 0.0% (0 of 3), 0.0% to 56.1% | 0.0% (0 of 3) | 0.0% (0 of 3) |

- What the judge cited on region 1 of the flagged good boards: none.
- Boards: 6 good; 6 not flagged by the anomaly model; of the flagged, none.
- Boards referred for review: 0.0% (0 of 6), 95% interval 0.0% to 39.0%. By cause: none.
- Areas put to the judge on those boards: 0; none.
- Areas referred for review: 0 of 0, 95% interval -. By cause: none.

## 7. Time per image, by stage

| Stage | Time |
| --- | --- |
| Parse the specification (once per specification; includes loading the parser's models) | 7.2 s |
| Anomaly model, pcb1, per image (batch 16; scoring and writing maps, masks and crops) | 458 ms |
| Anomaly model, pcb4, per image (batch 16; scoring and writing maps, masks and crops) | 186 ms |
| Measure and draw a flagged image's areas, the rule, the decision | 0.10 s (p95 0.24 s, n 6) |
| The VLM's answer to one area, cold | 2.21 s (p95 2.32 s, n 6) |
| The VLM's answers to one flagged image | 2.21 s (p95 2.32 s, n 6) |
| A flagged image, end to end | 2.63 s (p95 2.86 s, n 6) |

6 flagged images, 6 areas asked (1.00 an image); the judge's stage took 14 s in all. An image that is not flagged costs the anomaly model's time only. Prompt tokens, median: 4,856; answer tokens, median: 36; output rate, median: -.

## 8. Minutes from specification to a working inspector

| Part | Parse, measured in this run | Fit, as recorded at training | Together |
| --- | --- | --- | --- |
| pcb1 | 7.2 s | 699 s | 11.8 min |
| pcb4 | 7.2 s | 701 s | 11.8 min |
| all parts, one after another | 7.2 s | 1400 s | 23.4 min |

Training is not repeated by the bench: the fit time is the one in each model's own
training record. 23.4 minutes is every part of this run in turn.

## 9. Peak GPU memory, by stage

| Stage | The stage's own process | The card | The card before | Readings |
| --- | --- | --- | --- | --- |
| Anomaly model scoring, pcb1 | 2,551 MiB (the bench's process) | 2,593 MiB | 1,592 MiB | 4 at 0.5 s |
| Anomaly model scoring, pcb4 | 2,552 MiB (the bench's process) | 2,594 MiB | 2,050 MiB | 2 at 0.5 s |
| Judging | not read (the VLM server) | 29,786 MiB | 29,784 MiB | 18 at 0.5 s |

Read from `xpu-smi`, sampled by the bench: the anomaly model on pcb1, card 0000:17:00.0, under ZE_AFFINITY_MASK=0; the anomaly model on pcb4, card 0000:17:00.0, under ZE_AFFINITY_MASK=0; the judge, card 0000:ba:00.0. Each stage has a card to itself, so the card stands for the process.
Where a process's own figure says `not read`: the judge's server runs in a container: xpu-smi ps does not list its process, even under sudo, and ss shows no pid, so its own figure is null and its card stands for it.

## Repeating it

The judge's server is started by `scripts/serve_vlm_xpu.sh start`, none of its settings
overridden, and this run's command is started on the machine as:

```
SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 .venv/bin/spec-to-inspector bench --limit 3 --batch corrections --results /home/devcloud/corrections-run/trial/bench.json --readme /home/devcloud/corrections-run/trial/README.md --declared-store results/stage2/comparison-corrections/store.sqlite3
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
- Not the final figure, which keeps its empty store. This is what a store of corrections does to the boards it does not hold, read by the paired table.
- One specification, one model, one precision, one machine.
- Not a figure against Stage I. The host, the precision, the server and the answer
  pattern all differ, and no figure separates them.
- The labels are VisA's annotation mapped to clauses by a written table,
  `eval/clause_mapping.md`.
