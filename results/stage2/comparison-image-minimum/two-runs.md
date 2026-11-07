# The `image-minimum` comparison's two runs: every figure that differs

Made from the two records alone, field by field: `first-run.json` and `bench.json`. A field not listed
reads the same in both.

| Part of the record | Fields | Fields that differ |
| --- | --- | --- |
| Figures 1 to 6: `scores` | 332 | 12 |
| Figure 7: `times` | 44 | 26 |
| Figure 8: `inspector` | 6 | 4 |
| Figures 7 and 9: `runs` | 52 | 6 |
| Figure 9: `judge_memory` | 8 | 2 |
| The warm-up | 3 | 1 |
| The cold | 8 | 1 |
| Refused answers | 24 | 0 |

## Figures 1 to 6: `scores`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `good.all.citations.4.2` | 8 | 9 |
| `good.all.citations.no clause applies` | 3 | 2 |
| `good.all.dispositions.area_review_causes.no clause applies` | 3 | 2 |
| `good.all.dispositions.area_review_causes.not measured` | 1 | 2 |
| `good.all.dispositions.board_review_causes.no clause applies` | 3 | 2 |
| `good.all.dispositions.board_review_causes.not measured` | 1 | 2 |
| `good.by_part.pcb1.citations.4.2` | 8 | 9 |
| `good.by_part.pcb1.citations.no clause applies` | 3 | 2 |
| `good.by_part.pcb1.dispositions.area_review_causes.no clause applies` | 3 | 2 |
| `good.by_part.pcb1.dispositions.area_review_causes.not measured` | 1 | 2 |
| `good.by_part.pcb1.dispositions.board_review_causes.no clause applies` | 3 | 2 |
| `good.by_part.pcb1.dispositions.board_review_causes.not measured` | 1 | 2 |

## Figure 7: `times`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `anomaly_seconds_per_image.pcb1` | 0.0989 | 0.0992 |
| `anomaly_seconds_per_image.pcb4` | 0.0893 | 0.0898 |
| `completion_tokens.mean` | 39.7512 | 39.8018 |
| `completion_tokens.p95` | 50.0000 | 50.2000 |
| `flagged_image_seconds.maximum` | 16.3976 | 16.4228 |
| `flagged_image_seconds.mean` | 2.0022 | 2.0001 |
| `flagged_image_seconds.minimum` | 1.4279 | 1.4266 |
| `flagged_image_seconds.p50` | 1.7810 | 1.7652 |
| `flagged_image_seconds.p95` | 2.5168 | 2.5091 |
| `judge_stage_seconds` | 414.2962 | 413.7390 |
| `measure_and_draw_seconds.maximum` | 0.4582 | 0.4545 |
| `measure_and_draw_seconds.mean` | 0.0898 | 0.0894 |
| `measure_and_draw_seconds.minimum` | 0.0355 | 0.0364 |
| `measure_and_draw_seconds.p50` | 0.0632 | 0.0623 |
| `measure_and_draw_seconds.p95` | 0.2472 | 0.2481 |
| `parse_seconds` | 5.9905 | 6.6501 |
| `vlm_seconds_per_area.maximum` | 16.2361 | 16.2548 |
| `vlm_seconds_per_area.mean` | 1.8181 | 1.8160 |
| `vlm_seconds_per_area.minimum` | 1.2871 | 1.2902 |
| `vlm_seconds_per_area.p50` | 1.5992 | 1.5983 |
| `vlm_seconds_per_area.p95` | 2.1871 | 2.1893 |
| `vlm_seconds_per_flagged_image.maximum` | 16.2361 | 16.2548 |
| `vlm_seconds_per_flagged_image.mean` | 1.8181 | 1.8160 |
| `vlm_seconds_per_flagged_image.minimum` | 1.2871 | 1.2902 |
| `vlm_seconds_per_flagged_image.p50` | 1.5992 | 1.5983 |
| `vlm_seconds_per_flagged_image.p95` | 2.1871 | 2.1893 |

## Figure 8: `inspector`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `minutes_all_parts` | 23.4259 | 23.4369 |
| `minutes_by_part.pcb1` | 11.7461 | 11.7571 |
| `minutes_by_part.pcb4` | 11.7797 | 11.7907 |
| `parse_seconds` | 5.9905 | 6.6501 |

## Figures 7 and 9: `runs`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `pcb1.inference_seconds` | 19.7870 | 19.8423 |
| `pcb1.load_seconds` | 2.4247 | 2.6038 |
| `pcb1.seconds_per_image` | 0.0989 | 0.0992 |
| `pcb4.inference_seconds` | 17.9553 | 18.0527 |
| `pcb4.load_seconds` | 1.6476 | 1.6194 |
| `pcb4.seconds_per_image` | 0.0893 | 0.0898 |

## Figure 9: `judge_memory`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `card_before_mib` | 27391 | 28970 |
| `samples` | 542 | 541 |

## The warm-up

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `seconds` | 5.8028 | 1.4637 |

## The cold

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `hit_rate_readings` | 43 | 42 |
