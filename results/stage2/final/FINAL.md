# The final figure of Stage II

**Strict clause-citation accuracy: 34.1%, 46 of 135 single-defect boards, 95% interval 26.6% to 42.4%.** pcb1 45.1%
(41 of 91, 35.2% to 55.3%), pcb4 11.4% (5 of 44, 5.0% to 24.0%).

It is one setting on the organiser's machine, FP16, declared before the run (`SETTING.md`) and reported whatever it
read, under `eval/PROTOCOL-stage2.md` and its two additions. It is not the best of several settings. Three runs on 7
November 2026 make it final: `first-run.json`, `bench.json`, the tracked one, and `after-restart.json`, the judge's server
stopped and started before the third. `README.md` is the page the bench wrote from the tracked record, with every figure
the protocol asks for, and is not edited by hand.

## Beside it, never in its place

| Figure | Value |
| --- | --- |
| Flagged by the anomaly model | 93.3% (126 of 135), 87.8% to 96.5% |
| Region 1 lies on the labelled defect | 81.5% (110 of 135), 74.1% to 87.1% |
| Strict accuracy, flagged images only, conditional | 36.5% (46 of 126), 28.6% to 45.2% |
| Strict accuracy, region 1 on the defect only, conditional | 38.2% (42 of 110), 29.6% to 47.5% |
| The per-region figure | 36.2% (54 of 149), 29.0% to 44.2% |
| Good boards rejected, the false rejects | 8.0% (16 of 201), 5.0% to 12.5% |
| Good boards flagged by the anomaly model | 13.9% (28 of 201), 9.8% to 19.4% |
| The judge's answer to one area, cold, median | 2.12 s, 95th percentile 2.54 s, over 217 |
| Specification to a working inspector, one part | 11.8 minutes: the parse measured here, the fit as recorded at training and not repeated |
| Peak on card 0, the anomaly model | 2,594 MiB |
| Peak on card 1, the judge | 29,471 MiB; 29,784 MiB after the restart |

**The lenient figure: 70.8%, 46 of 65 multi-defect boards, 58.8% to 80.4%.** It counts a citation of any of the board's
defect types, it claims only that, and it is never pooled with the figure above.

## The three runs

The three agree on every counted figure: 343 fields of figures 1 to 6, none differing. Each run against the one before: 401
images, 0 flags, 0 scores, 0 board outcomes; 217 areas, 0 headings, 0 classes, 0 sentences. Times and memory do differ,
and every value is in `three-runs.md`, as the protocol asks.

| Void rule | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| The server unreachable for an area | No | No | No |
| A correction in a prompt, of 401 decisions | 0 | 0 | 0 |
| The highest prefix-cache hit rate in its log | 0.0% over 54 | 0.0% over 54 | 0.0% over 53 |
| A checkpoint not the named one | No | No | No |

The logs are `bench.server-log.20261107T055656Z.txt`, `bench.server-log.20261107T060922Z.txt` and
`after-restart.server-log.20261107T062331Z.txt`. No run was void, and none was repeated.

## The boards on the threshold

The rule is a strict `>`, with no margin. The figure is read with this known.

| Part | Board | Score | Threshold | Strictly above | In this figure |
| --- | --- | --- | --- | --- | --- |
| pcb1 | `bad-029` | 31.319490 | 31.319489 | Yes | One of the 135, flagged and cited rightly: it is one of the 46. Its margin is 1.9e-6. Unflagged it would be wrong, and the figure 45 of 135 |
| pcb4 | `bad-081` | 30.048744 | 30.048744 | No | One of the 65, not flagged, so wrong in the lenient figure |
| pcb2 | `bad-060` | 29.304890 | 29.304890 | No | Not scored by the bench: week 2's figure |
| pcb3 | `bad-097` | 31.543020 | 31.543051 | No | Not scored by the bench: week 2's figure |

All three runs read the first two exactly so.

## The three comparisons

Each is from the final setting with one thing changed, two runs, in `../comparison-<name>/`. Each is reported as a
comparison, and none replaces the figure above. Each is tested on its own at 0.05, with no correction for there being three.

| Comparison | Strict | Right only on the final, only on the comparison | Sign test on the 135 | What the protocol lets it say |
| --- | --- | --- | --- | --- |
| `fp8` | 37.8% (51 of 135), 30.0% to 46.2% | 1, 6 | p = 0.125 | No figure separates them |
| `image-minimum` | 33.3% (45 of 135), 25.9% to 41.6% | 8, 7 | p = 1 | No figure separates them |
| `designators` | 34.1% (46 of 135), 26.6% to 42.4% | 0, 0 | p = 1, and with fewer than 6 boards differing no split can reach 0.05 | No figure separates them |

| Comparison | The lenient figure | Right only on the final, only on the comparison | Sign test on the 65, not primary |
| --- | --- | --- | --- |
| `fp8` | 73.8% (48 of 65), 62.0% to 83.0% | 1, 3 | p = 0.625: no evidence of a change |
| `image-minimum` | 70.8% (46 of 65), 58.8% to 80.4% | 7, 7 | p = 1: no evidence of a change |
| `designators` | 69.2% (45 of 65), 57.2% to 79.1% | 1, 0 | p = 1: no evidence of a change |

No figure moved.

## What this figure is not

- **Not held out.** VisA's PCB test split is the only labelled data there is. The anomaly model's threshold is chosen on this
  same split, the judge's prompt was written with sight of answers on some of these images, and the protocol was written
  after a bench had been read on the same set.
- **Not a figure for the corrections loop.** The store is empty throughout.
- **One specification, one model, one precision, one machine.**
- **Not a figure against Stage I.** The host, the precision, the server and the answer pattern all differ, and the experiment
  that would separate them is not run, so no figure separates them.
- **Not run blind.** Whoever ran it had read week 1's bench and the whole-part trials before it. Nothing could be tuned: the
  setting, the prompt, the schema, the clause table and the thresholds were fixed before the first run.
