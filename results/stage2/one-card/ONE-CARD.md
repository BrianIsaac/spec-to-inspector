# The judge and the anomaly model on one card: measured

The deck's call H, measured on 7 November 2026 under the corrections pane's brief, as a record of its own. **It is no figure of the corrections comparison and no accuracy figure.** Its store is empty, as the final's is.

The judge's container is given card 0, `CARD_BDF=0000:17:00.0 scripts/serve_vlm_xpu.sh start`, otherwise as the script writes it: 0.9 of the card and nothing else overridden. PatchCore is on card 0 as it always is. The bench is the final's with `--limit 20`: the first 20 anomalous and 20 good boards of each part, 80 boards, 42 flagged. `SPEC_TO_INSPECTOR_VLM_CARD` names card 0, so the bench reads the judge's memory there.

**There are three short benches, because the first did not answer the question.** A server just started holds 26,960 MiB and grows as it answers, so the first bench's scoring met a judge that had not been asked. The third is the one that meets a judge that has answered.

| Bench | Record | Start, end, UTC | Exit | The card, while PatchCore scored, pcb1, pcb4 | PatchCore's own | The card, while the judge answered |
| --- | --- | --- | --- | --- | --- | --- |
| 1, on a server just started | `bench.json` | 15:17:52, 15:20:14 | 0 | 29,511, 29,514 MiB | 2,551, 2,552 MiB | 30,166 MiB |
| 2, on another just started | `warm/warming.json` | 15:25:57, 15:28:19 | 0 | 29,511, 29,512 MiB | 2,551, 2,552 MiB | 30,166 MiB |
| 3, on bench 2's server, **already warm** | `warm/beside-warm.json` | 15:28:19, 15:30:36 | 0 | **31,975, 31,978 MiB** | 2,551, 2,552 MiB | 30,344 MiB |

**The figure: 31,978 MiB of the card's 32,656 MiB, with PatchCore scoring beside a judge that has answered.** That leaves 678 MiB. The deck's 32,065 was two peaks added; this is a reading, every 0.5 s by the bench and every 5 s by the wrappers, whose `warm/warm.cards.csv` agrees at 31,978.

**It costs nothing it can be seen to cost, on these boards.** Scoring is 0.161 s and 0.097 s an image in each bench. The judge's answer is 2.10 to 2.13 s at the median and 2.28 to 2.29 s at the 95th percentile, on these 42 areas. The warm-up is 6.3 s on a server just started and 1.97 s on the warm one. All three benches agree with each other on every board: flag, score, heading, sentence, outcome. Against the final's second run on the same 80: 0 flags, 0 headings, 0 classes, 0 outcomes, 1 sentence (pcb4 `bad-017`), and 12 scores, which is the limit changing the batches and not the card.

**What it does not say.**

- **The two take turns.** The bench scores and then judges, so PatchCore and the judge are never computing at once: only their memory is on the card together. A line that scores and judges at the same moment has not been run.
- **Short benches.** 80 boards, not the 401, and the headroom is 678 MiB. PatchCore's own peak was 2,552 MiB here and in the whole runs, and the judge's grows as it answers, so a whole batch on one card is still to run if the claim is to rest on it.
- **The record's page says "Each stage has a card to itself",** in the bench's own words in section 9, which is false here. `README.md` and the two pages under `warm/` stay as the bench wrote them, and this file corrects them. `warm/beside-warm.md` also calls it "not final", rightly.

**The server was stopped and started three times for this and is back,** each by the script: on card 1 in the final's setting, nothing overridden, started 15:30:41 UTC, up in 126 s. `run.sh` and `run-warm.sh` are the wrappers. Every step's times and exit are beside them, and the logs before each stop were saved first (`server-before-one-card.txt`, `server-on-card-0.txt`, `warm/server-before.txt`, `warm/server-on-card-0.txt`).
