# The `designators` comparison

The final setting with one thing changed: the reason's pattern lets a designator such as `R12` through, under the addition's
pattern `^(?:[^0-9\n\r"\\]|[A-Z][0-9]{1,3})+$`, with the answer's validation to match and its 240 characters held. The server is
the final start; the pattern is the client's, `SPEC_TO_INSPECTOR_REASON_RULE=designators`. **It does not replace the final figure,
and the final figure keeps the ban.**

**Figure 10.** Strict, on the 135: right on both 46, wrong on both 89, right only on the final run 0, right only on this comparison
0. 0 of the 135 boards differ, and with fewer than 6 no split can reach 0.05: **no figure separates them.** The lenient figure, on
the 65, not primary: 45, 19, 1, 0, p = 1, so it is no evidence of a change; the one board is pcb4 `bad-095`, cited 5.1 on the final and
5.5 here, expecting 5.4 or 5.1. Tested on its own at 0.05, with no correction for there being three comparisons. `README.md`'s section
10 and `paired.json` are as the bench wrote them.

| | This comparison, second run | The final run |
| --- | --- | --- |
| Strict | 34.1% (46 of 135), 26.6% to 42.4% | 34.1% (46 of 135), 26.6% to 42.4% |
| The lenient figure | 69.2% (45 of 65), 57.2% to 79.1% | 70.8% (46 of 65), 58.8% to 80.4% |
| The judge's answer to one area, cold, median, 95th percentile | 2.13 s, 2.45 s | 2.12 s, 2.54 s |
| The slowest answer to one area | 4.83 s | 11.02 s |
| Refused answers | 1, stating a figure | 5: 4 padded, 1 stating a figure |

## Did the pattern pass a size?

The protocol's test is "one size in any of them is enough to say the pattern passes a size". **By that test it did, once, and not
through a designator: `½ mm`.** No answer that stood holds a size.

**Every reason in both runs with a digit in it** is listed by board on `README.md`, under "The reasons with a digit in them", 7 in each
run, the same 7, with 1 in each whose digit a unit of length follows:

| Part | Board | Stood | A unit follows | Reason |
| --- | --- | --- | --- | --- |
| pcb1 | `bad-097` | Yes | No | A lump of solder bridging two pads under the 'HC-SR04' marking. |
| pcb4 | `bad-080` | Yes | No | A resistor labeled R400 is present but has a large amount of foreign material on it. |
| pcb4 | `bad-085` | Yes | No | The resistor R400 has a large, irregularly shaped area of foreign material on its surface. |
| pcb4 | `bad-094` | **Refused** | **Yes** | A small, dark, irregularly shaped spot on the board surface within zone A, which is larger than the ½ mm limit for foreign material in zone A. |
| pcb4 | `bad-095` | Yes | No | The component R400 has a large area of dark, scorched material on its body, indicating damage. |
| pcb4 | `bad-096` | Yes | No | A resistor labeled R400 with a large, irregularly shaped area of foreign material on its body, covering part of the label and extending beyond the component's footprint. |
| pcb4 | `bad-097` | Yes | No | The resistor R400 has foreign material on its body. |

- **`½` is not one of the characters `[0-9]`,** so this pattern lets it through, and so does the final's: the final run's `bad-094` is the
  same refusal. The protocol says so in advance, "`½` is not a designator, and the answer's validation still refuses it", and it did.
- **The designator's own route passed no size in these runs.** Every digit in `0-9` here is in `R400` or the marking `HC-SR04`, neither
  followed by a unit.

**"Put a size in digits"**, week 1's question, on its three boards under this pattern: `schema-check.json`,
`scripts/judge_schema_check.py` with the rule set, 07:51:41 to 07:53:00 UTC, exit 0.

| Board | With the schema | Told the same with no schema |
| --- | --- | --- |
| pcb1 `bad-000` | No digit; padded to the token limit with a combining mark; refused as not JSON | "5.67 mm long", refused by the validation |
| pcb1 `bad-085` | No digit; wrote `longest_extent_mm:` over and over; refused as not JSON | "1.57 mm long", refused by the validation |
| pcb4 `bad-005` | No digit; padded with a combining mark; refused as not JSON | "1.5 mm in size", refused by the validation |

So none passed under this question on these boards, and that is all it says.

The final figure keeps the ban either way, and the README's "No number comes from the language model" stands on the final setting.

## The two runs

Run 1 is `first-run.json` and `first-run.md`, run 2 `bench.json` and `README.md`. No void rule was met: 0 of 401 decisions with a
correction, the highest hit rate 0.0% over 51 readings in each, the named checkpoints. They agree on all 343 fields of figures 1 to 6.
`two-runs.md` has every value that differs. `not_final` names the one thing, "this is the designators comparison", as it should.
