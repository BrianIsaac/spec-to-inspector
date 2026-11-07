# The bench on the machine's checkpoints, before any final

**None of this is a final run, and no figure in these folders is a final figure or is to be quoted as
one.** They were run on 7 November 2026 to show that the bench runs on the checkpoints the protocol
names, without stopping, and that what was built for it holds on real records. Every record here says
`partial`, and each page says its figures are not the protocol's.

The commands' output, with their exit codes and the time in UTC, is `machine-output.txt`. All ran from
`~/spec-to-inspector`, on card 0 under `ZE_AFFINITY_MASK=0`, with
`SPEC_TO_INSPECTOR_RUNS_DIR=/home/devcloud/before-final/runs`.

| Run | The bench's arguments | UTC | Exit | What it shows |
| --- | --- | --- | --- | --- |
| The laptop's checkpoints | `--limit 3`, with `SPEC_TO_INSPECTOR_MODELS_DIR=models` | 04:10:32 to 04:10:48 | **1** | The void rule's last clause: stopped before scoring, the digest named as the laptop's, nothing written |
| The whole split, before the columns | no limit | 04:10:48 to 04:11:46 | **1** | Both parts scored, then stopped naming `pcb1 bad-029` alone: 200 images in 19.9 s, 201 in 18.1 s |
| The labels' command | `bench.labels --run bench --changes ...` | 04:12:06 | 0 | One row of the 200: `../region-columns/README.md` |
| `trial/` | `--limit 3` | 04:12:42 to 04:13:32 | 0 | Both parts, on the named checkpoints |
| `trial-30/` | `--part pcb1 --limit 30` | 04:13:32 to 04:15:15 | 0 | Reaches `bad-029`, where its batch reads it below the threshold: named in `scores.stale_region_truth`, and the run goes on |
| `whole-pcb1/` | `--part pcb1` | 04:15:15 to 04:20:18 | 0 | A whole part on the regenerated columns; `bad-029` flagged, as they now say |
| `whole-pcb4/` | `--part pcb4` | 04:20:18 to 04:25:43 | 0 | The other whole part; `bad-081` exactly on its threshold and unflagged |
| `designators-trial-pcb4/` | `--part pcb4`, with `SPEC_TO_INSPECTOR_REASON_RULE=designators` | 04:27:02 to 04:31:53 | 0 | A trial of the code and not the comparison: the addition's pattern through the bench |
| Figure 10 | `--part pcb4 --render-only --against <whole-pcb4> --results <designators-trial-pcb4> ...` | 04:31:53 to 04:31:55 | 0 | From those two real records, nothing run: `designators-trial-pcb4/paired.json` and section 10 of its page |
| `designators-schema-check.json` | `scripts/judge_schema_check.py`, the same rule | 04:33:41 to 04:35:00 | 0 | "Put a size in digits" on the three boards under the addition's pattern, a trial and not the comparison's file |

The whole split repeats exactly. Every score and region count of both parts is the same between the
run that stopped and the whole-part runs, so the regenerated columns are not a chance reading:
`bad-029` read 31.319490432739258 both times, against 31.319475173950195 in the trial of 30.

## What the records hold

- **Each whole part's `not_final` holds one line, "this is a partial run".** The digests, the memory,
  the server, the cold, the warm-up and the protocol's three files are all in them.
- **The cold.** Hit rate 0.0% over 26 and 29 readings of the server's log, 0 hits of 0 queries.
- **Refused answers under the final pattern, whole pcb4.** 4 padded to the token limit (`bad-080`,
  `bad-085`, `bad-095`, `bad-096`) and 1 stating a figure (`bad-094`), 11.0 s at the slowest.
- **The same part under the addition's pattern.** None padded: all four name `R400` at the first asking.
  `bad-094` is refused all the same. Median 2.12 s a question, as under the final pattern, and 4.83 s at
  the slowest. Six reasons with a digit, five of them `R400` and one the refused `bad-094`.
- **"Put a size in digits", under that pattern.** No digit in any constrained answer: all three ran to the
  token limit and were refused as not JSON, each within the client's 120 s. Asked with no schema, the
  model wrote `5.67 mm`, `1.57 mm` and `1.5 mm`, each refused by the validation. So none passed on these
  boards, which is all the protocol lets that say.
- **Figure 10 on pcb4.** Strict: 0 of 44 boards differ. Lenient: 1 of 56 differs, `bad-095`. Partial and a
  first run, and the page says both.

**One count in these records is wrong, and it is corrected in the code since.** `bad-094` wrote "larger
than the ½ mm limit", and `designators-trial-pcb4/bench.json` lists it with `followed_by_a_unit` false,
having looked after 0 to 9 only. It is a size. The listing now looks after any numeric character, with a
test taken from this reason. The record stands as that run wrote it: the validation refused that answer,
so the size did not stand, but the count of them in this one record is 0 where it should be 1.
