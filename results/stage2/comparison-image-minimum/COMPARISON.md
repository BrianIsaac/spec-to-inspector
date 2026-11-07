# The `image-minimum` comparison

The final setting with one thing changed: the model's own image minimum, 64 tokens for a small crop, against the final's 1,024.
Started as the protocol writes it, `IMAGE_MIN_PIXELS=65536 scripts/serve_vlm_xpu.sh start`. **It does not replace the final
figure, whichever is higher.**

**Figure 10.** Strict, on the 135: right on both 38, wrong on both 82, right only on the final run 8, right only on this
comparison 7. The exact sign test gives p = 1, not below 0.05: **no figure separates them.** The lenient figure, on the 65, not
primary: 39, 12, 7, 7, p = 1, so it is no evidence of a change. Tested on its own at 0.05, with no correction for there being
three comparisons. `README.md`'s section 10 and `paired.json` are as the bench wrote them.

| | This comparison, second run | The final run |
| --- | --- | --- |
| Strict | 33.3% (45 of 135), 25.9% to 41.6% | 34.1% (46 of 135), 26.6% to 42.4% |
| The lenient figure | 70.8% (46 of 65), 58.8% to 80.4% | 70.8% (46 of 65), 58.8% to 80.4% |
| Prompt tokens, median | 2,809 | 4,682 |
| The judge's answer to one area, cold, median, 95th percentile | 1.60 s, 2.19 s | 2.12 s, 2.54 s |
| Peak on card 1 | 28,970 MiB | 29,471 MiB; 29,784 MiB after the restart |
| Refused answers | 3, all padded to the token limit | 5: 4 padded, 1 stating a figure |

The two equal lenient counts are not the same boards: 14 of the 65 differ, 7 each way. The prompt tokens show what the setting
gave: `judge.image_min_tokens` reads 64 in the record, and the median prompt is 1,873 tokens shorter.

## The two runs differ, so both are reported

No void rule was met: 0 of 401 decisions with a correction, the highest hit rate 0.0% over 43 and 42 readings, the named
checkpoints. Strict and lenient are equal in the two runs. **12 of the 332 fields of figures 1 to 6 differ, all from one good
board's answer**, the first time any repeat of this pane did. The server was the same process throughout, temperature zero and
cold, with the first run immediately after its start.

| Board | Field | Run 1 | Run 2 |
| --- | --- | --- | --- |
| pcb1 `good-0751` | Citation | No clause applies | 4.2, scratch, row 4.2.2 |
| | Review cause | No clause applies | Not measured |
| pcb4 `bad-038` | Sentence only | "A lump of foreign material on the board near the BAT+ marking." | "A small, dark spot on the board surface near the 'BAT+' marking, within zone A." |
| pcb4 `bad-077` | Sentence only | "A large area of foreign material on the board surface, covering zones A and C." | "A large blue mark on the board surface, covering zones A and C." |

So on the good boards: cited 4.2, 8 and 9; no clause applies, 3 and 2; referred as not measured, 1 and 2. The 12 fields with their
values, and every time and memory value that differs, are in `two-runs.md`. Run 1 is `first-run.json` and `first-run.md`, run 2
`bench.json` and `README.md`. The sign test uses run 2, as the protocol says.

## The page

**`README.md` now says what this run is.** Its two wrong lines were put right on 7 November by the bench's `--render-only` from the
same record, and no figure on it moved: it says this is the `image-minimum` comparison and so not final, and under "Repeating it" that
`IMAGE_MIN_PIXELS=65536` started it, with the one flag against the protocol's. Its `quantisation` row reads "not recorded", since this
record was written before the field; the engine's line in `raw/server-image-minimum-whole.txt` reads `quantization=None`. `bench.json`'s
own `not_final` still reads empty, and `first-run.md` keeps both old lines, each as written with its run.
