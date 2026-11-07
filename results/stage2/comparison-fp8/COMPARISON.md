# The `fp8` comparison

The final setting with one thing changed: the judge's weights are Qwen's own FP8 build,
`Qwen/Qwen3-VL-8B-Instruct-FP8`, revision `9cdc6310a8cb770ce18efaf4e9935334512aee45`, 10.59 GB. **It does not replace the
final figure, whichever is higher.**

**Figure 10.** Strict, on the 135: right on both 45, wrong on both 83, right only on the final run 1, right only on this
comparison 6. The exact sign test gives p = 0.125, not below 0.05: **no figure separates them.** The lenient figure, on the
65, not primary: 45, 16, 1, 3, p = 0.625, so it is no evidence of a change. Tested on its own at 0.05, with no correction for
there being three comparisons. `README.md`'s section 10 and `paired.json` are as the bench wrote them.

| | This comparison, second run | The final run |
| --- | --- | --- |
| Strict | 37.8% (51 of 135), 30.0% to 46.2% | 34.1% (46 of 135), 26.6% to 42.4% |
| The lenient figure | 73.8% (48 of 65), 62.0% to 83.0% | 70.8% (46 of 65), 58.8% to 80.4% |
| The judge's answer to one area, cold, median, 95th percentile | 1.86 s, 2.18 s | 2.12 s, 2.54 s |
| Peak on card 1 | 29,515 MiB | 29,471 MiB; 29,784 MiB after the restart |
| Refused answers | 6, all padded to the token limit | 5: 4 padded, 1 stating a figure |

Those two times and two memory figures are readings beside the test, not moves: the protocol's test is on the citations.

## How it was started, and the flags

`serve-fp8.sh` here is `scripts/serve_vlm_xpu.sh` with `WEIGHTS_REPO` and `WEIGHTS_REVISION` changed and nothing else.

**The weights require nothing in place of `--dtype=float16`.** The protocol's table allowed for something. vLLM's FP8 config
lists `half` among its activation types, the engine's own line reads `quantization=fp8` with `dtype=torch.float16`, and
it served. The start, as `judge.server.command` in `bench.json` holds it, is the final start with that path.

The record's `judge.server.dtype` therefore says `float16` here too. The FP8 is read from `weights_revision`, the command and
the engine's line in `raw/server-fp8-whole.txt`. vLLM's line gives 10.88 GiB for the weights, 3.01 GiB of peak activation and
2.21 GiB of non-torch memory, with a key-value cache of 91,712 tokens, 2.80 times a 32K context.

The weights' digests equal those Hugging Face gives for the revision: `e2dea2e85e643ef7045c31a485a426631a1e0a84e463f8b2c7e9c6682a06eafd`
and `3dc64ec934af27a7007d265014e907aff9e16658d409e5cd4cf79869bf2bd8c1`. Downloaded with `hf download`, 06:35:18 to 06:36:50 UTC.

## The two runs, and the page

Run 1 is `first-run.json` and `first-run.md`, run 2 `bench.json` and `README.md`. No void rule was met: 0 of 401 decisions with a
correction, the highest hit rate 0.0% over 48 readings in each, the named checkpoints. They agree on all 339 fields of figures 1
to 6. `two-runs.md` has every value that differs. pcb4 `bad-045` is padded twice and has no valid answer, so 216 areas compare
where 217 were asked.

**`README.md` now says what this run is.** Its two wrong lines were put right on 7 November by the bench's `--render-only` from the
same record, and no figure on it moved: it says this is the `fp8` comparison and so not final, and under "Repeating it" that `serve-fp8.sh`
started it, with the one flag against the protocol's. Its `quantisation` row reads "not recorded", since this record was written before
the field; the engine's line in `raw/server-fp8-whole.txt` reads `quantization=fp8`. `bench.json`'s own `not_final` still reads empty, and
`first-run.md` keeps both old lines, each as written with its run.
