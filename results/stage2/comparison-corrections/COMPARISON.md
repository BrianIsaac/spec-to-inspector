# The corrections comparison

The final setting with one thing changed: a store of an engineer's corrections, read into every prompt by the product's own recall.
Declared by `eval/PROTOCOL-stage2-addition-corrections-2026-11-07.md`, with its dated line. **It does not replace the final figure, which keeps its empty store.**

**This comparison measures three corrections a part standing in every prompt, not ten.** The store holds 14 (pcb1 4, pcb4 10), and the recall's limit of three gives each part the same three lines on every question.

**Figure 10.** Strict, on the 115: right on both 22, wrong on both 49, right only on the final run 20, right only with corrections 24. The exact sign test gives p = 0.6516, not below 0.05: **no figure separates them.** The lenient figure, on the 65, under its own name and never pooled: 19, 9, 27, 10, p = 0.007632, below 0.05 and **reading lower**: evidence of a change, on a figure that is not the primary test. Tested on its own at 0.05, with no correction for the other comparisons. `README.md`'s section 10 and `paired.json` are as the bench wrote them.

| | The final, on the same boards | With corrections, second run |
| --- | --- | --- |
| Strict | 36.5% (42 of 115), 28.3% to 45.6% | 40.0% (46 of 115), 31.5% to 49.1% |
| The lenient figure | 70.8% (46 of 65), 58.8% to 80.4% | 44.6% (29 of 65), 33.2% to 56.7% |
| Good boards rejected | 8.0% (16 of 201), 5.0% to 12.5% | 9.5% (19 of 201), 6.1% to 14.3% |
| The judge's answer to one area, cold, median, 95th percentile, 197 areas | 2.13 s, 2.54 s | 2.16 s, 2.58 s |
| Prompt tokens, median | 4,682 | 4,819 |
| The slowest answer | 11.02 s | 17.76 s |
| Refused answers, every board | 5: 4 padded, 1 stating a figure | 5, all padded |
| Peak on card 1 | 29,471 MiB; 29,784 MiB after the restart | 30,050 MiB |

The final's own figure over all its boards stands as it was: 46 of 135 and 46 of 65.

## What the lines did

`moves.md` has it, from the files. Reading beside the test, and not tested: **the answers go where the lines point, on the boards the lines say nothing about.** 70 of the 115 strict boards changed their answer. On pcb1 "melt" went from 47 of the 81 to 12, and "missing", named in two of its three lines, from 2 to 35. On pcb4 "dirt" went from 22 of the 34 to 1, and "damage" and "extra", the lines' targets, from 3 and 2 to 14 and 7.

That helped where the final's habit was wrong: pcb4 strict went from 5 to 12 of 34. It cost where the habit was right: pcb1 strict went from 37 to 34 of 81, and the lenient figure, which a habit of naming the commonest class can satisfy, is where the loss shows. Each part's split is a reading and has no test of its own. The direction was written in the handover before the run, from the lines alone. The good boards moved the same way: 7 of pcb1's flagged good boards now read "missing", none before.

The laptop's check moved the next similar board in 7 pairs of 7 and also moved 14 of 19 rightly judged controls (`results/stage1/corrections.json`). This is that loop's same behaviour at the scale of the set.

## How it was run, and the store

The store is `store.sqlite3`, SHA-256 `e43072ed4d3cbf2d5257cbb8e6f6c62add126675d4a0b4d7e6b8e8815077ea0c`, built by `declared_store.py.txt` as `store.json` says, each source by digest. The twenty boards are in `store.json` and the record: all twenty are left out of figures 1 to 7, six of them holding no correction, as the dated line says.

Each run is `raw/run.sh`, under `nohup`, on the tree checked by digest in `raw/tip-digests-1fe96e6.txt`. The server is the final's, started 07:27:57 UTC by the script with nothing overridden, the same process through both runs. `--batch corrections` keeps its output in `runs/<part>/corrections`, apart from the other benches' `runs/<part>/bench`.

**Every prompt held the part's three lines,** read from the machine's decisions after run 2: 111 of 111 areas asked on pcb1, 106 of 106 on pcb4, the warm-up as well. `leak` reads 217 of 401 decisions, 217 boards being flagged. Those 217 are of all 401, the twenty's included; the 197 in figure 7 are the boards counted.

## The two runs

Run 1 is `first-run.json`, `first-run.md`, `first-run.paired.json`, run 2 `bench.json`, `README.md`, `paired.json`. No void rule was met: the highest hit rate 0.0% over 55 readings in each, the named checkpoints, no correction from elsewhere. **They agree on every board:** 401 images, 0 flags, 0 scores, 0 outcomes; 215 answered on region 1, 0 headings, 0 classes, 0 sentences. All 348 fields of figures 1 to 6 are equal. Times and memory do differ, and every value is in `two-runs.md`, made by `raw/two_runs.py.txt`.

`first-run.paired.json` holds the digest of run 1's record, `first-run.json`, under the path it was written at, `bench.json`. Its two tables equal run 2's.

`raw/trial/` is a trial before run 1, 3 anomalous and 3 good boards of each part with its own runs directory: 13 questions more of the server, and no figure of anything.

## What the page cannot say

Two lines of `README.md` read as the bench wrote them and want reading with this. Figure 7's "the judge's stage took" and Figure 9 are of the whole run, all 401 boards, as the page says at its head. And "What differs between the two runs' makings" lists the protocol's files because the final ran before the later additions landed, which is no difference in the setting.
