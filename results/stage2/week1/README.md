# Stage II week 1: the first figures on the B70, beside the laptop's

Measured on 6 November 2026, 15:53 to 16:13 UTC, on the machine in `machine.md`. The laptop's
figures are `results/stage1/bench.json`. Written by hand from `bench/bench.json`, the second of two
runs, as the protocol asks. The bench's own page is not kept: its title and last section are fixed
to "the laptop prototype", and it says it is not to be edited.

This is a bring-up figure. Week 3 is the judge's measurement. It is one run of one setting, on one
specification, on boards that are not held out, as `eval/PROTOCOL.md` says of the laptop's.

## What was run

`spec-to-inspector bench --results ~/week1/bench/bench.json --readme ~/week1/bench/README.md`,
with `SPEC_TO_INSPECTOR_DEVICE=xpu` and `ZE_AFFINITY_MASK=0`, against `scripts/serve_vlm_xpu.sh
start`. The protocol's SHA-256 in the record is the laptop's, `0109f982f5e96121`.

| | The laptop | The B70 machine |
| --- | --- | --- |
| Judge's model | Qwen3-VL-8B-Instruct, Q4_K_M | Qwen3-VL-8B-Instruct, FP16 |
| Judge's server | llama.cpp v0.6.0, CUDA | vLLM 0.26.1.dev0 in `intel/llm-scaler-vllm:0.26.0-b1`, card 1 |
| Anomaly model | PatchCore on CUDA | The laptop's same two checkpoints, on XPU, card 0 |
| Image minimum | 1,024 tokens | 1,024 tokens (`shortest_edge` 1,048,576 pixels) |
| Asked cold by | the request's `cache_prompt` false | the server: prefix cache off, because vLLM ignores `cache_prompt` |
| The reason's pattern | `^[^0-9\n\r]{1,240}$` | `^[^0-9\n\r"\\]{1,240}$`, see below |

So this differs from the laptop's run in more than precision. The tightened pattern is a change to
the pipeline after the protocol was written. The laptop has not been re-run over the whole set with
it, only on three boards (`judge-schema-laptop-llama-cpp.json`), so no figure here separates the
pattern's effect from FP16's or from the server's.

## The figures

Every proportion is a count of its N, with the 95% Wilson interval.

| Figure | The laptop | The B70 machine |
| --- | --- | --- |
| Strict clause-citation accuracy, single-defect boards | 38.5% (52 of 135), 30.7% to 46.9% | **34.1% (46 of 135), 26.6% to 42.4%** |
| The same, PCB1 | 42 of 91 | 41 of 91 |
| The same, PCB4 | 10 of 44 | 5 of 44 |
| Lenient, multi-defect boards | 58.5% (38 of 65), 46.3% to 69.6% | 70.8% (46 of 65), 58.8% to 80.4% |
| Per region, one type under region 1 | 40.5% (60 of 148), 33.0% to 48.6% | 36.5% (54 of 148), 29.2% to 44.5% |
| Defective boards flagged | 188 of 200 | 188 of 200 |
| Of the 135, region 1 on the labelled defect | 109 | 109 |
| Defective boards rejected, referred | 174, 14 | 177, 11 |
| Good boards flagged | 28 of 201 | 28 of 201 |
| Good boards rejected, referred, accepted | 16, 9, 3 | 16, 10, 2 |
| "No valid answer" | 3 | 0 |
| Answers needing the retry | 7 | 5 |
| One question, asked cold: median, p95 | 3.33 s, 3.84 s (218) | 2.13 s, 2.56 s (216) |
| A flagged board, end to end: median, p95 | 3.49 s, 4.03 s | 2.34 s, 2.74 s |
| The anomaly model, per image, whole run: PCB1, PCB4 | 86 ms, 84 ms | 98 ms, 89 ms |
| The judge, the whole 216 boards | 801 s | 525 s |
| Peak, the judge's card | 10,109 MiB of 12,227, shared | 29,456 MiB of 32,656 (`xpu-smi`, every 5 s) |
| Peak, the anomaly model's card while scoring | shared with the judge | 2,594 MiB (`xpu-smi`, every 5 s) |

**Read this as: full precision did not raise the headline in this run, and nothing here shows it
lowered it.** The intervals overlap heavily. On the same 135 boards 40 are right on both, 77 wrong
on both, 12 right only on the laptop and 6 right only here. A two-sided exact sign test on 12 against
6 gives p = 0.24. That test is not a protocol figure and is added here only to say how little the
difference of six boards carries. PCB4 fell from 10 to 5 of 44, and the lenient figure rose by 8 of
65; both are small counts. On the 216 flagged boards the two judges cite the same heading on 154.

`docs/stage2.md` called full precision "the one change the B70's memory buys outright" and said
"whether it raises the figure is not known". This is the first evidence, and it does not favour it.
The picture of a good board beside the crop and the corrections loop are still untested.

The time rows do compare: the judge answers in about 0.64 of the laptop's time, at FP16, with the
same prompt sizes. The anomaly model's 98 and 89 ms are the whole scoring run with its file writing
on a server's disk and processor, not the model's speed, which is week 2's.

## The anomaly model behaves as it did

Over all 401 boards, the laptop's checkpoints on XPU against the same checkpoints on CUDA: 0 boards
differ in being flagged, 0 differ in their number of regions, and the largest difference in a score
is 0.00053 raw units against thresholds near 30. Anomalib's PatchCore runs on the B70 through PyTorch
XPU in FP32, which `docs/stage2.md` had as unknown. This is inference only. Training on a real part
is week 2's; only a 20-image training has run on XPU (`raw/pytest-xpu.txt`).

## Repeatability

Run twice from the same state: of 401 boards, 0 differ in flag, score or outcome; of 216 asked, 0
differ in heading, class or sentence; all figures equal. As the laptop's did.

## The schema's verdict

**Accepted by vLLM's constrained decoding, `pattern` and nullable `enum` both, with one fix to the
schema itself.** The judge's own client, on three boards chosen by a fixed rule (pcb1's first image,
pcb1's first single-defect image with a size limit, pcb4's first single-defect image):

| Board | Attempts | Answer | Laptop's citation | Prompt tokens, both | Time to first token, cold | Whole answer |
| --- | --- | --- | --- | --- | --- | --- |
| pcb1 `bad-000` | 1 | melt, 4.1 | 4.1 | 4,591 | 1.05 s to 1.06 s | 1.98 s to 2.00 s |
| pcb1 `bad-085` | 1 | scratch, 4.2 | 4.2 | 4,579 | 1.05 s to 1.06 s | 2.11 s to 2.12 s |
| pcb4 `bad-005` | 1 | dirt, 5.1 | 5.1 | 4,574 | 1.05 s to 1.07 s | 1.96 s to 1.98 s |

Three asks each, streamed. The server's very first question after a start took 6.29 s whole, for
a kernel compiled on first use (vLLM logs `_bilinear_pos_embed_kernel`). The three files, in order:

- `judge-schema-prefix-cache-on.json`: the server's defaults. It shows the two settings below were
  needed. Its 0.11 s to first token is the prefix cache answering a repeated question, not a figure.
- `judge-schema-before-the-quote-fix.json`: cold, 1,024-token images, the old pattern. `bad-085`
  fails on both attempts.
- `judge-schema.json`: as served now, with the fix.

**The fault was in the schema, and vLLM was right.** The pattern describes the string's contents and
allowed a double quote, so on `bad-085` the model closed its own sentence and wrote on, all of it
legally inside the `reason`:

    {"reason": "A foreign object, likely a fiber, lying on the board surface.", "defect_class":
    "dirt", "clause_id": "none"}  // Note: No clause ... covers foreign material on a"

That is 240 characters between the quotes, the pattern's limit, with no digit; the limit forced the
closing quote, and only white space was left until `max_tokens`. The pattern now bars `"` and `\`,
with a test made from that text. Across all 216 flagged boards since, the fault has not come back.

**The constraint bites.** Told to put a size in digits, name the class Gremlin and cite clause 99.9,
the server without the schema writes a size on all three boards (`5.67 mm`) and, on one, `Gremlin`
and `99.9`. With the schema, of the six answers to that and to "no clause applies", none holds a
digit and none a value off the enum. Two of the six did not finish: told to break the schema, the
model padded until `max_tokens`, which is the filler below. Told that no clause applies, it gave a
valid `null`, `null` on `bad-085` and kept citing a clause on the other two.

**What the schema does not cure: the digit ban's filler.** A model that wants a digit it may not
write can pad until `max_tokens`. 4 of this run's 5 retries are a resistor's designator (`R ̅ ̅ ̅`,
wanting `R12`) and the fifth is `½`, all on PCB4, and all recovered on the retry. The laptop's 3
"no valid answer" boards, also PCB4, are this same thing; they are not the quote. So the filler is
Stage I's, on both servers, and this run lost no board to it. Such an answer fails validation and is
retried, then referred, never guessed. Each padded answer costs about 11 s against 2 s.

## What the bench's record does not hold on this machine

- `judge_memory` and each part's `memory` are null: the bench reads `nvidia-smi`. Protocol figure 9
  is therefore only the card-level `bench/card-memory.txt`, every 5 s, from `xpu-smi`, with no
  figure for the server's process alone.
- `judge.server` is empty, `image_min_tokens` says "unknown" and `gpu` is null: they come from
  llama.cpp's `/props` and from `nvidia-smi`. The two 404s in `raw/serve-fp16-util-0.9-cold-final.txt`
  are that probe, one per run, and the only errors in the log.
- The note under `cold` says each request was sent with `cache_prompt` false. It was, and vLLM
  ignored it. It was cold because of the server's start.
- Figure 8, minutes from a specification to an inspector, is the laptop's training time.
- Equal prompt-token counts say the images are given the same area. Whether the two resizes give
  the same pixels was not measured.
