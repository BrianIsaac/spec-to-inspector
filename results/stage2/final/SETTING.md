# The setting of the final run, declared before it

Written on 7 November 2026, 13:56 SGT (05:56 UTC), and committed before the first of the three runs. The
setting is `eval/PROTOCOL-stage2.md`'s, "The setting, declared before the run". It is declared here, not
chosen here: nothing below is a choice of this run's, and the final figure is this one setting whatever it
reads.

## The law of the run

| File | SHA-256 |
| --- | --- |
| `eval/PROTOCOL-stage2.md` | `ebbd8cc1cb25172f7d74cddf8190e0826204eb6b3c8cc7e1da83a565ead4e3f6` |
| `eval/PROTOCOL-stage2-addition-region-columns-2026-11-07.md` | `8d8d4ef19e95354a4a1ab220e6eb9dc51865c87b2ae6e9f9da1464bdd4c5b1b1` |
| `eval/PROTOCOL-stage2-addition-designators-pattern-2026-11-07.md` | `84c8d198200b11a45e4eac8735611c20681cf5a9db5f0d4a2063330ac4f7c65b` |
| `eval/clause_labels.csv` | `44866105f3fdad88c12f70a6d41d1d0c7e14df34d9ffbc0f7cb5051c42660337` |
| `results/stage2/checkpoints.json` | `af420d92ee128a051f2d779b6f731b81a6e433d5168b142e52ee559cf2779815` |
| `scripts/serve_vlm_xpu.sh` | `211d3c0b6914108c14fbf9c5ca07df222d0cc84725aa0032a8d45ee12c462bf1` |

The code on the machine is `master` at `f005c9e`: all 444 tracked files outside `results/` hold the same
digests there as in that commit, by `sha256sum -c` on the machine at 05:55:57 UTC, exit 0. The three files
above that are tracked under `eval/` and `results/` were read there too.

## The judge's server, as read from the running container at 05:56:12 UTC

| | The setting | Read from |
| --- | --- | --- |
| The server | `intel/llm-scaler-vllm:0.26.0-b1`, `sha256:70e7eafdd52c281263f2a19266086b88e55064402a17ef731ba5657c4bd86490`, vLLM `0.26.1.dev0+g568afb3a1.d20260831` | `docker inspect`, `GET /version` |
| The weights and the precision | `Qwen/Qwen3-VL-8B-Instruct`, revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`, `--dtype=float16`; the engine's own line says `dtype=torch.float16` | `GET /v1/models`, the container's arguments, the log |
| Asked cold | `--no-enable-prefix-caching --mm-processor-cache-gb 0`; the engine's own line says `enable_prefix_caching=False`; all 484 hit rates in the log so far read 0.0% | The arguments, the log |
| The image size | `--mm-processor-kwargs` with `shortest_edge` 1,048,576 and `longest_edge` 16,777,216 | The arguments |
| The memory share and the context | `--gpu-memory-util=0.9 --max-model-len=32768 --max-num-batched-tokens=32768` | The arguments, `GET /v1/models` |
| The rest of the start | `--enforce-eager --disable-sliding-window --block-size 64 --limit-mm-per-prompt '{"image": 2}' -tp=1`, `--net=host`, `--shm-size=32g`, port 8131 of 127.0.0.1 | The arguments |
| A card each | The judge on card 1, `0000:ba:00.0`, the only card its container is given; the anomaly model on card 0, `0000:17:00.0`, under `ZE_AFFINITY_MASK=0` | The script, `.env` |
| The started server | Started by `scripts/serve_vlm_xpu.sh start` with no setting overridden, 2026-11-06T15:40:16 UTC, by week 1. These arguments are what that script builds at the digest above | `docker inspect` |

## The client and the rest

| | The setting |
| --- | --- |
| The warm-up | One question before the judge's clock, asked by the bench at every run; its answer is not recorded |
| The reason's pattern | `^[^0-9\n\r"\\]{1,240}$` |
| The corrections store | Empty: no store file exists under the machine's `runs/` |
| The threshold rule | A strict `>` (the region columns' addition, ruling 2) |
| The anomaly models | pcb1 `b71ff0c3db7e780c6198db5686569fa59de4a56b5663557b56d90e237b37a855`, pcb4 `cc571d9a4c56ee791888a2f6ce73e7db2f7f46b57c7aeb683ce7ba447f03ccb4`, by `SPEC_TO_INSPECTOR_MODELS_DIR=/home/devcloud/week2/run-1/models` in the machine's `.env`. The bench voids the run on any other |
| The command | `SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 .venv/bin/spec-to-inspector bench --results results/stage2/final/bench.json --readme results/stage2/final/README.md`, from `~/spec-to-inspector` |

## The three runs

Run 1 and run 2 by that command from this state, with the server as it stands. Then
`scripts/serve_vlm_xpu.sh stop` and `start`, and run 3 by the same command with
`--results results/stage2/final/after-restart.json --readme results/stage2/final/after-restart.md`, the first
of those a copy of run 2's record. The tracked figure is run 2's `bench.json`, with run 3's beside it. Run 1's
record would otherwise be replaced by run 2, so it is kept as `first-run.json` and `first-run.md`.
