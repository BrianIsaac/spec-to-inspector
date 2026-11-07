# Addition to the Stage II protocol: the `designators` comparison's pattern (7 November 2026)

Written on 7 November 2026 by the cockpit at the owner's ruling of 11:10 SGT
the same day (the project's decisions log), after the record pane measured
the pattern on the judge and before the `designators` comparison is run. It
adds to `eval/PROTOCOL-stage2.md` and edits nothing in it. A final run's
record holds this file's SHA-256 beside the protocol's.

## What was measured

The protocol writes the `designators` comparison's answer pattern as
`^(?:[^0-9\n\r"\\]|[A-Z][0-9]{1,3}){1,240}$`. On the judge, cold, one asking
each (`results/stage2/record-trial/`): the board's question of 32 tokens
took 7.6 s against 2.0 s under the final pattern, and a padded answer of
256 tokens took 318.5 s against 8.7 s. The client's limit is 120 s, and a
question past it reads as the server lost, which voids the run. The cost
is the count over a group: the same language written with `+` in place of
`{1,240}` ran at the final pattern's speed on both askings, and accepts
exactly the protocol's strings (37,449 short strings exhaustively, 200,000
at random, and the limits).

## The ruling

The `designators` comparison's pattern is
`^(?:[^0-9\n\r"\\]|[A-Z][0-9]{1,3})+$`. The 240-character limit is held by
the validator on the answer, as before, not by the pattern. A padded answer
therefore runs to the token limit and is refused as not JSON, where the
counted pattern could have closed it at 240; the record counts such
refusals under their own heading, as it counts every refusal.

The other option, the protocol's pattern under a 600-second client limit,
was declined: its times would not be comparable with the final's.

## What this does not change

Everything else the protocol says of the comparison stands: it is run after
the final, two runs, in `results/stage2/comparison-designators/`, and it must
also show that the pattern never passes a size, by every digit-bearing
reason listed and by week 1's "put a size in digits" question repeated. It
does not replace the final figure.
