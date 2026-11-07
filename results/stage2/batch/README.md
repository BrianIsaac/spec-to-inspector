# Stage II: the whole batch, end to end

One command per part, `spec-to-inspector inspect`, from the specification's PDF to the reject cards, over every board of the test split of pcb1 and pcb4, on the machine, in the final's setting. Two runs, the second after nothing was changed. This page is made from the files beside it by `python -m spec_to_inspector.batch.page`.

**It gives no accuracy figure.** The final figure stands, in `results/stage2/final/`, and is not re-read from a batch. Run 2's records are `pcb1.json` and `pcb4.json`; run 1's are kept as `first-run.pcb1.json` and `first-run.pcb4.json`; every value that differs between them is in `two-runs.md`.

## The digests, read before the first run

`sha256sum ~/week2/run-2/models/patchcore/*/model.ckpt` read against `results/stage2/checkpoints.json`; the raw reading is `raw/digests-week2.txt`.

| Part | The named checkpoint | Week 2's second training | Bytes | Bytes differing |
| --- | --- | --- | --- | --- |
| pcb1 | `b71ff0c3db7e780c6198db5686569fa59de4a56b5663557b56d90e237b37a855` | `9dd23b43305fff934edbfbdcd60446a63187dfcf856610e7eab475b7df2271eb` | 668,469,863 | 36 |
| pcb4 | `cc571d9a4c56ee791888a2f6ce73e7db2f7f46b57c7aeb683ce7ba447f03ccb4` | `fc19950beba2363e66065e3370b952bfaadc98beaa9ea28ce9f74fe4b726b303` | 668,469,863 | 35 |

## The runs

Times UTC, as the wrapper wrote them; the raw files are under `raw/`. Pids are the wrapper's for a run and the process's for a part. A run's wall clock includes the 5 s the wrapper waits after the last part, so that a last reading of the cards falls after it.

| Step | Start | End | Wall clock | Pid | Exit |
| --- | --- | --- | --- | --- | --- |
| run-1 | 2026-11-07T11:51:45Z | 2026-11-07T12:02:18Z | 10 min 33 s | 1483205 | 0 |
| run-1, pcb1 | 2026-11-07T11:51:45Z | 2026-11-07T11:56:47Z | 5 min 2 s | 1483211 | 0 |
| run-1, pcb4 | 2026-11-07T11:56:47Z | 2026-11-07T12:02:13Z | 5 min 26 s | 1493688 | 0 |
| run-2 | 2026-11-07T12:03:24Z | 2026-11-07T12:13:58Z | 10 min 34 s | 1506753 | 0 |
| run-2, pcb1 | 2026-11-07T12:03:24Z | 2026-11-07T12:08:27Z | 5 min 3 s | 1506759 | 0 |
| run-2, pcb4 | 2026-11-07T12:08:27Z | 2026-11-07T12:13:53Z | 5 min 26 s | 1517200 | 0 |

## What became of the boards

| Run | Part | Boards | Accepted | Rejected | Referred | By cause | Cards |
| --- | --- | --- | --- | --- | --- | --- | --- |
| run-1 | pcb1 | 200 | 91 | 95 | 14 | no clause applies 1, not measured 8, outside every zone 5 | 95 |
| run-1 | pcb4 | 201 | 95 | 99 | 7 | not measured 3, outside every zone 4 | 99 |
| run-1 | both | 401 | 186 | 194 | 21 |  | 194 |
| run-2 | pcb1 | 200 | 91 | 95 | 14 | no clause applies 1, not measured 8, outside every zone 5 | 95 |
| run-2 | pcb4 | 201 | 95 | 99 | 7 | not measured 3, outside every zone 4 | 99 |
| run-2 | both | 401 | 186 | 194 | 21 |  | 194 |

## Against the final's second run, board by board

Each run's line for each board against `results/stage2/final/bench.json`, by every field that is not a time: how many boards differ. This asks whether `inspect` and the bench are one pipeline in the one setting. It re-reads no figure.

| Run | Boards | score | flagged | regions_found | citation | cited_heading | cited_class | sentence | row_id | outcome | review_cause |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| run-1 | 401 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| run-2 | 401 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

## The reject cards and the report, on disk

Each size is in MiB, as the files' bytes and then as allocated on the disk. The report is `report.html` and its stylesheet; the run's directory is everything the part's run left on the machine. Run 2's reports are kept under `raw/reports/`; their links to the cards work on the machine, where the cards are.

| Run | Part | The report | The cards | The run's directory |
| --- | --- | --- | --- | --- |
| run-1 | pcb1 | 0.08, 0.09 | 0.31, 0.37 | 115.7, 119.0 |
| run-1 | pcb4 | 0.08, 0.09 | 0.35, 0.39 | 116.0, 119.4 |
| run-2 | pcb1 | 0.08, 0.09 | 0.31, 0.37 | 115.7, 119.0 |
| run-2 | pcb4 | 0.08, 0.09 | 0.35, 0.39 | 116.0, 119.4 |

## Figure 7: time per image, by stage

After the warm-up, by the bench's own function over both parts. Each time with a distribution is its median, then its 95th percentile.

| Stage | run-1 | run-2 |
| --- | --- | --- |
| Parsing the specification, pcb1's run | 7.18 s | 7.14 s |
| Parsing the specification, pcb4's run | 6.18 s | 5.85 s |
| The anomaly model, per image, pcb1, with its file writing | 0.0987 s | 0.0993 s |
| The anomaly model, per image, pcb4, with its file writing | 0.0990 s | 0.0990 s |
| Measuring and drawing, per flagged image | 0.06 s, 0.24 s | 0.06 s, 0.25 s |
| The VLM, per question | 2.13 s, 2.55 s | 2.13 s, 2.56 s |
| The VLM, per flagged image | 2.13 s, 2.55 s | 2.13 s, 2.56 s |
| A flagged image, end to end | 2.34 s, 2.73 s | 2.34 s, 2.73 s |
| Flagged images | 217 | 217 |
| Questions asked | 217 | 217 |
| The judge's stage, both parts | 8 min 47 s | 8 min 47 s |
| Writing the cards and the report, both parts | 0.11 s | 0.12 s |

## Figure 8: minutes from specification to a working inspector

The parse time measured in this run plus the fit time recorded when each part's model was trained on the machine, week 2's first training. Training is not repeated here. Both parts is the pcb1 run's parse and both fits, since a specification is parsed once.

| Run | Part | Parse | Fit | Minutes |
| --- | --- | --- | --- | --- |
| run-1 | pcb1 | 7.18 s | 698.8 s | 11.77 |
| run-1 | pcb4 | 6.18 s | 700.8 s | 11.78 |
| run-1 | both | 7.18 s | 1399.6 s | 23.45 |
| run-2 | pcb1 | 7.14 s | 698.8 s | 11.77 |
| run-2 | pcb4 | 5.85 s | 700.8 s | 11.78 |
| run-2 | both | 7.14 s | 1399.6 s | 23.45 |

## Figure 9: peak GPU memory by stage

From `xpu-smi`, both cards read every 5 s; card 0 is the anomaly model's, `0000:17:00.0, under ZE_AFFINITY_MASK=0`, and card 1 the judge's, `0000:ba:00.0`. Each part's readings are the file its record names, and the wrapper's own for the whole of each run, across the gap between the two processes, are `raw/<run>.cards.csv`. A stage shorter than the interval can have no reading, so a peak here is a sample's and can miss a shorter one: the final's bench read at 0.5 s.

| Run | Part | Stage | Card 0, MiB | Card 1, MiB | Readings |
| --- | --- | --- | --- | --- | --- |
| run-1 | pcb1 | parse | 44 | 29786 | 2 |
| run-1 | pcb1 | score | 2596 | 29786 | 5 |
| run-1 | pcb1 | judge | 962 | 29786 | 50 |
| run-1 | pcb1 | server log | 784 | 29786 | 2 |
| run-1 | pcb1 | report | 784 | 29784 | 1 |
| run-1 | pcb4 | parse | 42 | 29784 | 2 |
| run-1 | pcb4 | score | 2595 | 29784 | 4 |
| run-1 | pcb4 | warm-up | 962 | 29784 | 1 |
| run-1 | pcb4 | judge | 962 | 29784 | 55 |
| run-1 | pcb4 | server log | 782 | 29784 | 2 |
| run-1 | pcb4 | report | 782 | 29784 | 1 |
| run-1 | the whole run, the wrapper's |  | 2596 | 29788 | 127 |
| run-2 | pcb1 | parse | 44 | 29786 | 2 |
| run-2 | pcb1 | score | 2596 | 29786 | 5 |
| run-2 | pcb1 | judge | 964 | 29786 | 50 |
| run-2 | pcb1 | server log | 784 | 29786 | 2 |
| run-2 | pcb1 | report | 784 | 29786 | 2 |
| run-2 | pcb4 | parse | 42 | 29784 | 2 |
| run-2 | pcb4 | score | 2596 | 29784 | 4 |
| run-2 | pcb4 | warm-up | 962 | 29784 | 1 |
| run-2 | pcb4 | judge | 962 | 29784 | 55 |
| run-2 | pcb4 | server log | 782 | 29784 | 2 |
| run-2 | pcb4 | report | 782 | 29784 | 1 |
| run-2 | the whole run, the wrapper's |  | 2596 | 29786 | 127 |

## The final's setting, as each record read it

| Run | Part | Checkpoint | Corrections in a prompt | Highest hit rate, readings | Clause table equals the tracked | Warm-up |
| --- | --- | --- | --- | --- | --- | --- |
| run-1 | pcb1 | `b71ff0c3db7e780c...` | 0 of 200 | 0.0%, 27 | True | 1.97 s |
| run-1 | pcb4 | `cc571d9a4c56ee79...` | 0 of 201 | 0.0%, 28 | True | 2.24 s |
| run-2 | pcb1 | `b71ff0c3db7e780c...` | 0 of 200 | 0.0%, 27 | True | 1.98 s |
| run-2 | pcb4 | `cc571d9a4c56ee79...` | 0 of 201 | 0.0%, 28 | True | 2.26 s |

The server, as it said of itself: `command` -c source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1; exec vllm serve --model /root/.cache/huggingface/hub/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b --served-model-name qwen3-vl-8b-instruct --dtype=float16 --enforce-eager --port 8131 --host 127.0.0.1 --trust-remote-code --disable-sliding-window --gpu-memory-util=0.9 --max-model-len=32768 --max-num-batched-tokens=32768 --block-size 64 --limit-mm-per-prompt '{"image": 2}' --mm-processor-kwargs '{"size": {"shortest_edge": 1048576, "longest_edge": 16777216}}' --no-enable-prefix-caching --mm-processor-cache-gb 0 -tp=1; `dtype` float16; `image` intel/llm-scaler-vllm:0.26.0-b1; `image_digest` sha256:70e7eafdd52c281263f2a19266086b88e55064402a17ef731ba5657c4bd86490; `image_label_revision` ac12083301cbdbe06135882d401f7877b0b512db; `image_label_version` 20260608; `max_model_len` 32768; `served_model` qwen3-vl-8b-instruct; `vllm_version` 0.26.1.dev0+g568afb3a1.d20260831; `weights_revision` 0c351dd01ed87e9c1b53cbc748cba10e6187ff3b.

## What the record is made of

Every file by its SHA-256, in each record under `protocol`:

| File | SHA-256 |
| --- | --- |
| `eval/PROTOCOL-stage2.md` | `ebbd8cc1cb25172f7d74cddf8190e0826204eb6b3c8cc7e1da83a565ead4e3f6` |
| `eval/PROTOCOL-stage2-addition-designators-pattern-2026-11-07.md` | `84c8d198200b11a45e4eac8735611c20681cf5a9db5f0d4a2063330ac4f7c65b` |
| `eval/PROTOCOL-stage2-addition-region-columns-2026-11-07.md` | `8d8d4ef19e95354a4a1ab220e6eb9dc51865c87b2ae6e9f9da1464bdd4c5b1b1` |
| `eval/PROTOCOL-stage2-addition-whole-batch-2026-11-07.md` | `03a4154bb25cacd8a48bdb5b49e59594820bf67200c0620dc63d99d10c284040` |
