# More than one question in flight: measured

The deck's call I, measured on 7 November 2026 under the corrections pane's brief, as a record of its own. **It is no figure of the corrections comparison and no accuracy figure.** Its store is empty, as the final's is.

`in_flight.py.txt` asks pcb1's 111 flagged boards twice through the bench's own `judge_image` and one `ChatClient`, first one at a time and then two at once, against the judge's server in its final setting, on card 1, cold, with nothing written into the run. One part, one pass each way, one concurrency. `run.sh` is its wrapper. 15:07:44 to 15:15:03 UTC, pid 1774474 then 1774477, exit 0. Every value is in `in-flight.json`.

| | One at a time | Two at once |
| --- | --- | --- |
| Boards, areas asked, server lost | 111, 111, 0 | 111, 111, 0 |
| The whole pass | 251.7 s | 180.2 s |
| Boards a minute | 26.5 | 37.0 |
| The answer to one area, as the client waits for it, median | 2.14 s | 3.12 s |
| The same, 95th percentile | 2.57 s | 4.17 s |
| The slowest | 2.98 s | 4.59 s |
| Boards against the final's own answers: another heading, another class | 0, 0 | 1, 1 (`bad-041`) |
| Another sentence | 0 | 2 (`bad-003`, `bad-041`) |
| Another outcome | 0 | 0 |

**What it says.** Two at once gets 40% more boards through in a given time, and each question waits 46% longer at the median. **The answers are not quite the same:** one at a time reproduces the final on all 111, and two at once changes one citation of the 111 and one more sentence, though no board's outcome. So a second question in flight is not free of the answers, and a figure measured one at a time does not carry over to it word for word. The server's log, `in-flight.server-log.txt`, reads at most 2 running and 0 waiting over its 43 readings. Both cards were read every 5 s: `in-flight.cards.csv`, card 1 at 30,050 MiB throughout, so two at once took no more than one at a time here.

**What it does not say.** One part, once each way, and two is the only number tried. The order was fixed, one at a time first.
