# The three final runs: every figure that differs

Made from the three records alone, field by field: `first-run.json`, `bench.json` (the tracked figure)
and `after-restart.json`. The server was stopped and started between run 2 and run 3. The protocol asks
every value to be reported if any figure differs. A field not listed reads the same in all three.

| Part of the record | Fields | Fields that differ |
| --- | --- | --- |
| Figures 1 to 6: `scores` | 343 | 0 |
| Figure 7: `times` | 44 | 24 |
| Figure 8: `inspector` | 6 | 4 |
| Figures 7 and 9: `runs` | 52 | 6 |
| Figure 9: `judge_memory` | 8 | 3 |
| The warm-up | 3 | 1 |
| The cold | 7 | 1 |
| The boards on the threshold | 27 | 0 |
| Refused answers | 36 | 0 |

## What the bench counted, against the run before

| | Images | Flag differs | Score differs | Board outcome differs | Areas | Heading differs | Class differs | Sentence differs | Figures equal |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Run 2 against run 1 | 401 | 0 | 0 | 0 | 217 | 0 | 0 | 0 | True |
| Run 3 against run 2 | 401 | 0 | 0 | 0 | 217 | 0 | 0 | 0 | True |

## Figure 7: `times`

| Field | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| `anomaly_seconds_per_image.pcb1` | 0.0989 | 0.0993 | 0.0994 |
| `anomaly_seconds_per_image.pcb4` | 0.0894 | 0.0903 | 0.0902 |
| `flagged_image_seconds.maximum` | 11.1621 | 11.1939 | 11.1713 |
| `flagged_image_seconds.mean` | 2.5176 | 2.5212 | 2.5231 |
| `flagged_image_seconds.minimum` | 1.9927 | 1.9826 | 1.9732 |
| `flagged_image_seconds.p50` | 2.3265 | 2.3327 | 2.3333 |
| `flagged_image_seconds.p95` | 2.7351 | 2.7283 | 2.7411 |
| `judge_stage_seconds` | 526.0586 | 526.6978 | 527.0939 |
| `measure_and_draw_seconds.maximum` | 0.4713 | 0.4658 | 0.4611 |
| `measure_and_draw_seconds.mean` | 0.0908 | 0.0916 | 0.0918 |
| `measure_and_draw_seconds.minimum` | 0.0417 | 0.0380 | 0.0427 |
| `measure_and_draw_seconds.p50` | 0.0640 | 0.0650 | 0.0648 |
| `measure_and_draw_seconds.p95` | 0.2484 | 0.2501 | 0.2515 |
| `parse_seconds` | 6.0103 | 6.4543 | 6.9762 |
| `vlm_seconds_per_area.maximum` | 10.9946 | 11.0247 | 11.0020 |
| `vlm_seconds_per_area.mean` | 2.3326 | 2.3347 | 2.3364 |
| `vlm_seconds_per_area.minimum` | 1.8463 | 1.8351 | 1.8266 |
| `vlm_seconds_per_area.p50` | 2.1245 | 2.1234 | 2.1173 |
| `vlm_seconds_per_area.p95` | 2.5394 | 2.5409 | 2.5564 |
| `vlm_seconds_per_flagged_image.maximum` | 10.9946 | 11.0247 | 11.0020 |
| `vlm_seconds_per_flagged_image.mean` | 2.3326 | 2.3347 | 2.3364 |
| `vlm_seconds_per_flagged_image.minimum` | 1.8463 | 1.8351 | 1.8266 |
| `vlm_seconds_per_flagged_image.p50` | 2.1245 | 2.1234 | 2.1173 |
| `vlm_seconds_per_flagged_image.p95` | 2.5394 | 2.5409 | 2.5564 |

## Figure 8: `inspector`

| Field | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| `minutes_all_parts` | 23.4263 | 23.4337 | 23.4424 |
| `minutes_by_part.pcb1` | 11.7464 | 11.7538 | 11.7625 |
| `minutes_by_part.pcb4` | 11.7800 | 11.7874 | 11.7961 |
| `parse_seconds` | 6.0103 | 6.4543 | 6.9762 |

## Figures 7 and 9: `runs`

| Field | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| `pcb1.inference_seconds` | 19.7802 | 19.8556 | 19.8777 |
| `pcb1.load_seconds` | 2.3873 | 2.6368 | 2.5782 |
| `pcb1.seconds_per_image` | 0.0989 | 0.0993 | 0.0994 |
| `pcb4.inference_seconds` | 17.9781 | 18.1492 | 18.1326 |
| `pcb4.load_seconds` | 1.6974 | 1.7328 | 1.6690 |
| `pcb4.seconds_per_image` | 0.0894 | 0.0903 | 0.0902 |

## Figure 9: `judge_memory`

| Field | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| `card_before_mib` | 29471 | 29471 | 27765 |
| `card_peak_mib` | 29471 | 29471 | 29784 |
| `samples` | 688 | 688 | 689 |

## The warm-up

| Field | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| `seconds` | 1.9989 | 1.9779 | 6.2789 |

## The cold

| Field | Run 1 | Run 2 | Run 3 |
| --- | --- | --- | --- |
| `hit_rate_readings` | 54 | 54 | 53 |
