# The corrections comparison: what moved

Made from `results/stage2/final/bench.json` and this folder's `bench.json` by `raw/two_runs.py.txt`. The final against the second run, on the boards figure 10 counts, by its reader of right and wrong. A reading beside the sign test and not a test of its own.

## The figures on the same boards

The final's counted by the bench's `score` on the boards this comparison counts, the comparison's as its record holds them. Each has its 95% interval. The sign test is on the first and the fourth rows' pairs, in `paired.json`; the others are readings.

| Figure | The final, on the same boards | With corrections |
| --- | --- | --- |
| Strict | 36.5% (42 of 115), 28.3% to 45.6% | 40.0% (46 of 115), 31.5% to 49.1% |
| Strict, pcb1 | 45.7% (37 of 81), 35.3% to 56.5% | 42.0% (34 of 81), 31.8% to 52.8% |
| Strict, pcb4 | 14.7% (5 of 34), 6.4% to 30.1% | 35.3% (12 of 34), 21.5% to 52.1% |
| Lenient | 70.8% (46 of 65), 58.8% to 80.4% | 44.6% (29 of 65), 33.2% to 56.7% |
| Lenient, pcb1 | 88.9% (8 of 9), 56.5% to 98.0% | 33.3% (3 of 9), 12.1% to 64.6% |
| Lenient, pcb4 | 67.9% (38 of 56), 54.8% to 78.6% | 46.4% (26 of 56), 34.0% to 59.3% |
| Per region | 38.6% (51 of 132), 30.8% to 47.2% | 44.7% (59 of 132), 36.5% to 53.2% |
| Anomalous boards referred | 3.9% (7 of 180), 1.9% to 7.8% | 2.8% (5 of 180), 1.2% to 6.3% |
| Good boards rejected | 8.0% (16 of 201), 5.0% to 12.5% | 9.5% (19 of 201), 6.1% to 14.3% |
| Good boards referred | 5.0% (10 of 201), 2.7% to 8.9% | 4.0% (8 of 201), 2.0% to 7.7% |

## Strict, the 115

| Part | Boards | Right on the final | Right with corrections | Right only on the final | Right only with corrections | Answers that changed at all |
| --- | --- | --- | --- | --- | --- | --- |
| pcb1 | 81 | 37 | 34 | 19 | 16 | 46 |
| pcb4 | 34 | 5 | 12 | 1 | 8 | 24 |

What the judge said on pcb1's boards here, region 1:

| Answer | The final | With corrections |
| --- | --- | --- |
| bent 4.4 | 14 | 24 |
| melt 4.1 | 47 | 12 |
| missing 4.3 | 2 | 35 |
| not flagged | 7 | 7 |
| scratch 4.2 | 11 | 3 |

What the judge said on pcb4's boards here, region 1:

| Answer | The final | With corrections |
| --- | --- | --- |
| burnt 5.7 | 1 | 3 |
| damage 5.5 | 3 | 14 |
| dirt 5.1 | 22 | 1 |
| extra 5.3 | 2 | 7 |
| missing 5.2 | 3 | 7 |
| not flagged | 2 | 2 |
| scratch 5.6 | 1 | 0 |

## Lenient, the 65

| Part | Boards | Right on the final | Right with corrections | Right only on the final | Right only with corrections | Answers that changed at all |
| --- | --- | --- | --- | --- | --- | --- |
| pcb1 | 9 | 8 | 3 | 5 | 0 | 6 |
| pcb4 | 56 | 38 | 26 | 22 | 10 | 42 |

What the judge said on pcb1's boards here, region 1:

| Answer | The final | With corrections |
| --- | --- | --- |
| bent 4.4 | 1 | 4 |
| melt 4.1 | 5 | 0 |
| missing 4.3 | 1 | 4 |
| not flagged | 1 | 1 |
| scratch 4.2 | 1 | 0 |

What the judge said on pcb4's boards here, region 1:

| Answer | The final | With corrections |
| --- | --- | --- |
| burnt 5.7 | 9 | 3 |
| damage 5.5 | 4 | 26 |
| dirt 5.1 | 35 | 3 |
| extra 5.3 | 1 | 16 |
| missing 5.2 | 6 | 5 |
| no valid answer | 0 | 2 |
| not flagged | 1 | 1 |

## The good boards, none of them drawn

What the judge said on pcb1's flagged good boards, region 1:

| Answer | The final | With corrections |
| --- | --- | --- |
| bent 4.4 | 1 | 2 |
| melt 4.1 | 5 | 4 |
| missing 4.3 | 0 | 7 |
| no clause applies | 1 | 1 |
| scratch 4.2 | 12 | 5 |

What the judge said on pcb4's flagged good boards, region 1:

| Answer | The final | With corrections |
| --- | --- | --- |
| burnt 5.7 | 0 | 1 |
| damage 5.5 | 0 | 1 |
| dirt 5.1 | 7 | 2 |
| extra 5.3 | 1 | 4 |
| missing 5.2 | 1 | 0 |
| scratch 5.6 | 0 | 1 |
