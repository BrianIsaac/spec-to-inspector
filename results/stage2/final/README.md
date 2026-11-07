# Stage II: what the machine measured

Written by `spec-to-inspector bench --results results/stage2/final/bench.json --readme results/stage2/final/README.md` on 2026-11-07 (2026-11-07T06:19:16+00:00).
Not edited by hand: a figure that is wrong here is wrong in its record, and the remedy
is to run the command again.

The figures follow these files, each read at the time of the run:

| File | SHA-256 |
| --- | --- |
| `eval/PROTOCOL-stage2.md` | `ebbd8cc1cb25172f7d74cddf8190e0826204eb6b3c8cc7e1da83a565ead4e3f6` |
| `eval/PROTOCOL-stage2-addition-designators-pattern-2026-11-07.md` | `84c8d198200b11a45e4eac8735611c20681cf5a9db5f0d4a2063330ac4f7c65b` |
| `eval/PROTOCOL-stage2-addition-region-columns-2026-11-07.md` | `8d8d4ef19e95354a4a1ab220e6eb9dc51865c87b2ae6e9f9da1464bdd4c5b1b1` |

Every proportion is a count of its N with the 95% Wilson score interval. Nothing here is
a held-out figure: see the last section.

This run's record holds what the protocol asks of a final run. Three runs make a figure
final: see the section on repeating it.

## The figures

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Clause-citation accuracy, strict, single-defect images | 34.1% (46 of 135) | 135 | 26.6% to 42.4% |
| Clause-citation accuracy, strict, single-defect images, pcb1 only | 45.1% (41 of 91) | 91 | 35.2% to 55.3% |
| Clause-citation accuracy, strict, single-defect images, pcb4 only | 11.4% (5 of 44) | 44 | 5.0% to 24.0% |
| Clause-citation accuracy, lenient, multi-defect images | 70.8% (46 of 65) | 65 | 58.8% to 80.4% |
| Clause-citation accuracy per region, one defect type under region 1 | 36.2% (54 of 149) | 149 | 29.0% to 44.2% |
| Anomalous boards referred for review | 5.5% (11 of 200) | 200 | 3.1% to 9.6% |
| Good boards rejected (false rejects) | 8.0% (16 of 201) | 201 | 5.0% to 12.5% |
| Good boards flagged by the anomaly model | 13.9% (28 of 201) | 201 | 9.8% to 19.4% |

| Figure | Value |
| --- | --- |
| A flagged image, end to end, median | 2.33 s (p95 2.73 s, n 217) |
| The VLM's answer to one flagged area, cold, median | 2.12 s (p95 2.54 s, n 217) |
| From specification to a working inspector, one part | 11.8 min (parse 6.5 s measured here; fit as recorded at training: pcb1 699 s, pcb4 701 s) |
| From specification to a working inspector, all parts in turn | 23.4 min |
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

During this run the highest of 54 rates in its log is 0.0%, and its counters added 0 tokens of hits of 0 looked for. Any rate above 0.0% voids a run, so a run that has a record has none. The log of this run is `results/stage2/final/bench.server-log.20261107T060922Z.txt`.

## What else the run was made of

- The warm-up: one question before the judge's clock, on pcb1 good-0214, in 1.98 s; its answer is not recorded.
- The reason's pattern: `^[^0-9\n\r"\\]{1,240}$`.
- The labelled set: `eval/clause_labels.csv` (SHA-256 `44866105f3fdad88`), 200 anomalous test images: 135 single-defect, 65 multi-defect.
- The specification: `specs/pcb-spec.pdf`, parsed in 6.5 s into 16 clauses under 11 numbered headings, equal to the tracked `specs/pcb-spec.clauses.json`.
- The corrections store empty: 0 of 401 decisions had a correction in a prompt (`decision.corrected.in_prompt`).

The anomaly models, not retrained here:

| Part | Checkpoint | SHA-256 | Trained | Image threshold | Chosen on the test |
| --- | --- | --- | --- | --- | --- |
| pcb1 | `/home/devcloud/week2/run-1/models/patchcore/pcb1/model.ckpt` | `b71ff0c3db7e780c6198db5686569fa59de4a56b5663557b56d90e237b37a855` | 2026-11-06T17:17:44+00:00 | 31.319489 | yes |
| pcb4 | `/home/devcloud/week2/run-1/models/patchcore/pcb4/model.ckpt` | `cc571d9a4c56ee791888a2f6ce73e7db2f7f46b57c7aeb683ce7ba447f03ccb4` | 2026-11-06T17:59:34+00:00 | 30.048744 | yes |

Each checkpoint was held to `results/stage2/checkpoints.json` (SHA-256 `af420d92ee128a05`) before it scored anything: another digest voids the run.

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
| Strict accuracy | 34.1% (46 of 135) | 135 | 26.6% to 42.4% |
| Strict accuracy, pcb1 only | 45.1% (41 of 91) | 91 | 35.2% to 55.3% |
| Strict accuracy, pcb4 only | 11.4% (5 of 44) | 44 | 5.0% to 24.0% |
| Flagged by the anomaly model | 93.3% (126 of 135) | 135 | 87.8% to 96.5% |
| Flagged by the anomaly model, pcb1 only | 92.3% (84 of 91) | 91 | 85.0% to 96.2% |
| Flagged by the anomaly model, pcb4 only | 95.5% (42 of 44) | 44 | 84.9% to 98.7% |
| Region 1 lies on the labelled defect | 81.5% (110 of 135) | 135 | 74.1% to 87.1% |
| Region 1 lies on the labelled defect, pcb1 only | 76.9% (70 of 91) | 91 | 67.3% to 84.4% |
| Region 1 lies on the labelled defect, pcb4 only | 90.9% (40 of 44) | 44 | 78.8% to 96.4% |
| Strict accuracy, flagged images only (conditional) | 36.5% (46 of 126) | 126 | 28.6% to 45.2% |
| Strict accuracy, flagged images only (conditional), pcb1 only | 48.8% (41 of 84) | 84 | 38.4% to 59.3% |
| Strict accuracy, flagged images only (conditional), pcb4 only | 11.9% (5 of 42) | 42 | 5.2% to 25.0% |
| Strict accuracy, region 1 on the defect only (conditional) | 38.2% (42 of 110) | 110 | 29.6% to 47.5% |
| Strict accuracy, region 1 on the defect only (conditional), pcb1 only | 52.9% (37 of 70) | 70 | 41.3% to 64.1% |
| Strict accuracy, region 1 on the defect only (conditional), pcb4 only | 12.5% (5 of 40) | 40 | 5.5% to 26.1% |

For the correct citations, what code then did (the row is a measurement's outcome, not
what is scored):

- Row of the clause table applied: 4.1 29, 4.4 9, 5.5 2, 5.2 2, 4.3 1, no row 1, 4.2.2 1, 5.3 1.
- Outcome of region 1: reject 44, needs review: outside every zone 1, needs review: not measured 1.

## 2. The lenient figure: the multi-defect images

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Lenient accuracy | 70.8% (46 of 65) | 65 | 58.8% to 80.4% |
| Lenient accuracy, pcb1 only | 88.9% (8 of 9) | 9 | 56.5% to 98.0% |
| Lenient accuracy, pcb4 only | 67.9% (38 of 56) | 56 | 54.8% to 78.6% |

## 3. The per-region figure

Images, single and multi, whose region 1 lies on exactly one of VisA's defect types,
scored against that type's heading.

| Figure | Value | N | 95% interval |
| --- | --- | --- | --- |
| Per-region accuracy | 36.2% (54 of 149) | 149 | 29.0% to 44.2% |
| Per-region accuracy, pcb1 only | 52.0% (39 of 75) | 75 | 40.9% to 62.9% |
| Per-region accuracy, pcb4 only | 20.3% (15 of 74) | 74 | 12.7% to 30.8% |

## 4. The confusion tables

Rows are the expected defect type; columns are the type of the heading cited, or why
there is no citation.

pcb1, single-defect images:

| Expected \ cited | melt | scratch | missing | bent | not flagged | Images |
| --- | --- | --- | --- | --- | --- | --- |
| **melt** | 29 | 7 | 1 | 4 | 5 | 46 |
| **scratch** | 11 | 2 | 0 | 0 | 1 | 14 |
| **missing** | 9 | 5 | 1 | 1 | 1 | 17 |
| **bent** | 5 | 0 | 0 | 9 | 0 | 14 |

pcb4, single-defect images:

| Expected \ cited | dirt | missing | extra | damage | scratch | burnt | not flagged | Images |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **missing** | 13 | 2 | 1 | 0 | 1 | 0 | 2 | 19 |
| **extra** | 7 | 1 | 1 | 1 | 0 | 2 | 0 | 12 |
| **wrong place** | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| **damage** | 4 | 0 | 1 | 2 | 0 | 0 | 0 | 7 |
| **scratch** | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 2 |
| **burnt** | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |

pcb1, images with one type under region 1, by that type:

| Expected \ cited | melt | scratch | missing | bent | Images |
| --- | --- | --- | --- | --- | --- |
| **melt** | 28 | 0 | 1 | 4 | 33 |
| **scratch** | 12 | 1 | 0 | 0 | 13 |
| **missing** | 8 | 5 | 1 | 1 | 15 |
| **bent** | 5 | 0 | 0 | 9 | 14 |

pcb4, images with one type under region 1, by that type:

| Expected \ cited | dirt | missing | extra | damage | burnt | Images |
| --- | --- | --- | --- | --- | --- | --- |
| **dirt** | 3 | 0 | 0 | 0 | 0 | 3 |
| **missing** | 19 | 4 | 1 | 0 | 0 | 24 |
| **extra** | 10 | 2 | 2 | 1 | 3 | 18 |
| **wrong place** | 9 | 0 | 0 | 0 | 0 | 9 |
| **damage** | 5 | 0 | 1 | 4 | 2 | 12 |
| **scratch** | 2 | 1 | 0 | 0 | 0 | 3 |
| **burnt** | 2 | 0 | 0 | 1 | 2 | 5 |

Citations on labelled images whose named class is not the class of the heading cited: 0.

## 5. Needs review, by cause, on the anomalous boards

- Boards: 200 anomalous; 11 not flagged by the anomaly model; of the flagged, reject 178, needs review 11.
- Boards referred for review: 5.5% (11 of 200), 95% interval 3.1% to 9.6%. By cause: not measured 9, outside every zone 2.
- Areas put to the judge on those boards: 189; reject 178, needs review 11.
- Areas referred for review: 5.8% (11 of 189), 95% interval 3.3% to 10.1%. By cause: not measured 9, outside every zone 2.

## 6. False alarms on the good boards

| Part | Good boards | Flagged | Rejected (false rejects), 95% interval | Referred | Accepted after judging |
| --- | --- | --- | --- | --- | --- |
| all | 201 | 13.9% (28 of 201) | 8.0% (16 of 201), 5.0% to 12.5% | 5.0% (10 of 201) | 1.0% (2 of 201) |
| pcb1 | 100 | 19.0% (19 of 100) | 10.0% (10 of 100), 5.5% to 17.4% | 7.0% (7 of 100) | 2.0% (2 of 100) |
| pcb4 | 101 | 8.9% (9 of 101) | 5.9% (6 of 101), 2.8% to 12.4% | 3.0% (3 of 101) | 0.0% (0 of 101) |

- What the judge cited on region 1 of the flagged good boards: 4.2 12, 5.1 7, 4.1 5, 4.4 1, no clause applies 1, 5.2 1, 5.3 1.
- Boards: 201 good; 173 not flagged by the anomaly model; of the flagged, reject 16, needs review 10, accept 2.
- Boards referred for review: 5.0% (10 of 201), 95% interval 2.7% to 8.9%. By cause: outside every zone 7, not measured 2, no clause applies 1.
- Areas put to the judge on those boards: 28; reject 16, needs review 10, accept 2.
- Areas referred for review: 35.7% (10 of 28), 95% interval 20.7% to 54.2%. By cause: outside every zone 7, not measured 2, no clause applies 1.

## 7. Time per image, by stage

| Stage | Time |
| --- | --- |
| Parse the specification (once per specification; includes loading the parser's models) | 6.5 s |
| Anomaly model, pcb1, per image (batch 16; scoring and writing maps, masks and crops) | 99 ms |
| Anomaly model, pcb4, per image (batch 16; scoring and writing maps, masks and crops) | 90 ms |
| Measure and draw a flagged image's areas, the rule, the decision | 0.06 s (p95 0.25 s, n 217) |
| The VLM's answer to one area, cold | 2.12 s (p95 2.54 s, n 217) |
| The VLM's answers to one flagged image | 2.12 s (p95 2.54 s, n 217) |
| A flagged image, end to end | 2.33 s (p95 2.73 s, n 217) |

217 flagged images, 217 areas asked (1.00 an image); the judge's stage took 527 s in all. An image that is not flagged costs the anomaly model's time only. Prompt tokens, median: 4,682; answer tokens, median: 35; output rate, median: -.

## 8. Minutes from specification to a working inspector

| Part | Parse, measured in this run | Fit, as recorded at training | Together |
| --- | --- | --- | --- |
| pcb1 | 6.5 s | 699 s | 11.8 min |
| pcb4 | 6.5 s | 701 s | 11.8 min |
| all parts, one after another | 6.5 s | 1400 s | 23.4 min |

Training is not repeated by the bench: the fit time is the one in each model's own
training record. 23.4 minutes is every part of this run in turn.

## 9. Peak GPU memory, by stage

| Stage | The stage's own process | The card | The card before | Readings |
| --- | --- | --- | --- | --- |
| Anomaly model scoring, pcb1 | 2,552 MiB (the bench's process) | 2,594 MiB | 1,592 MiB | 24 at 0.5 s |
| Anomaly model scoring, pcb4 | 2,552 MiB (the bench's process) | 2,594 MiB | 2,050 MiB | 22 at 0.5 s |
| Judging | not read (the VLM server) | 29,471 MiB | 29,471 MiB | 688 at 0.5 s |

Read from `xpu-smi`, sampled by the bench: the anomaly model on pcb1, card 0000:17:00.0, under ZE_AFFINITY_MASK=0; the anomaly model on pcb4, card 0000:17:00.0, under ZE_AFFINITY_MASK=0; the judge, card 0000:ba:00.0. Each stage has a card to itself, so the card stands for the process.
Where a process's own figure says `not read`: the judge's server runs in a container: xpu-smi ps does not list its process, even under sudo, and ss shows no pid, so its own figure is null and its card stands for it.

## Repeating it

The judge's server is started by `scripts/serve_vlm_xpu.sh start`, none of its settings
overridden, and this run's command is started on the machine as:

```
SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 .venv/bin/spec-to-inspector bench --results results/stage2/final/bench.json --readme results/stage2/final/README.md
```

This run was compared with the run of the same command before it (2026-11-07T06:06:49+00:00), image by image:

- 401 images in both runs: 0 flagged in one and not the other, 0 with another anomaly score, 0 with another board outcome.
- 217 images answered on region 1 in both runs: 0 with another heading cited, 0 with another class named, 0 with another sentence.
- Images that differ in anything but the sentence: none.
- Every counted figure of the protocol is equal in the two runs.

## The refused answers

5 answers were refused. Each is sent back once with what was wrong with it; a second refusal refers the area to an engineer.

| Kind | Answers |
| --- | --- |
| padded to the token limit | 4 |
| not JSON | 0 |
| reason over the character limit | 0 |
| reason states a figure | 1 |
| otherwise invalid | 0 |

### Padded to the token limit

4 answers ran to the token limit with the string unclosed, and were refused as not JSON.

| Part | Board | Area | Asking | Kind |
| --- | --- | --- | --- | --- |
| pcb4 | `bad-080` | 1 | 1 | padded to the token limit |
| pcb4 | `bad-085` | 1 | 1 | padded to the token limit |
| pcb4 | `bad-095` | 1 | 1 | padded to the token limit |
| pcb4 | `bad-096` | 1 | 1 | padded to the token limit |

### The other refusals

| Part | Board | Area | Asking | Kind |
| --- | --- | --- | --- | --- |
| pcb4 | `bad-094` | 1 | 1 | reason states a figure |

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
