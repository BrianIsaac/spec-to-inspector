# The `fp8` comparison's two runs: every figure that differs

Made from the two records alone, field by field: `first-run.json` and `bench.json`. A field not listed
reads the same in both.

| Part of the record | Fields | Fields that differ |
| --- | --- | --- |
| Figures 1 to 6: `scores` | 339 | 0 |
| Figure 7: `times` | 44 | 24 |
| Figure 8: `inspector` | 6 | 4 |
| Figures 7 and 9: `runs` | 52 | 6 |
| Figure 9: `judge_memory` | 8 | 2 |
| The warm-up | 3 | 1 |
| The cold | 8 | 0 |
| Refused answers | 42 | 0 |

## Figure 7: `times`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `anomaly_seconds_per_image.pcb1` | 0.0992 | 0.0991 |
| `anomaly_seconds_per_image.pcb4` | 0.0897 | 0.0903 |
| `flagged_image_seconds.maximum` | 13.9186 | 13.9562 |
| `flagged_image_seconds.mean` | 2.2462 | 2.2368 |
| `flagged_image_seconds.minimum` | 1.7945 | 1.7790 |
| `flagged_image_seconds.p50` | 2.0562 | 2.0477 |
| `flagged_image_seconds.p95` | 2.3865 | 2.3742 |
| `judge_stage_seconds` | 467.0964 | 465.0581 |
| `measure_and_draw_seconds.maximum` | 0.4523 | 0.4589 |
| `measure_and_draw_seconds.mean` | 0.0912 | 0.0869 |
| `measure_and_draw_seconds.minimum` | 0.0414 | 0.0331 |
| `measure_and_draw_seconds.p50` | 0.0634 | 0.0601 |
| `measure_and_draw_seconds.p95` | 0.2473 | 0.2449 |
| `parse_seconds` | 6.7034 | 6.7297 |
| `vlm_seconds_per_area.maximum` | 13.5746 | 13.6137 |
| `vlm_seconds_per_area.mean` | 2.0605 | 2.0552 |
| `vlm_seconds_per_area.minimum` | 1.6485 | 1.6391 |
| `vlm_seconds_per_area.p50` | 1.8598 | 1.8630 |
| `vlm_seconds_per_area.p95` | 2.2030 | 2.1788 |
| `vlm_seconds_per_flagged_image.maximum` | 13.5746 | 13.6137 |
| `vlm_seconds_per_flagged_image.mean` | 2.0605 | 2.0552 |
| `vlm_seconds_per_flagged_image.minimum` | 1.6485 | 1.6391 |
| `vlm_seconds_per_flagged_image.p50` | 1.8598 | 1.8630 |
| `vlm_seconds_per_flagged_image.p95` | 2.2030 | 2.1788 |

## Figure 8: `inspector`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `minutes_all_parts` | 23.4378 | 23.4383 |
| `minutes_by_part.pcb1` | 11.7580 | 11.7584 |
| `minutes_by_part.pcb4` | 11.7916 | 11.7920 |
| `parse_seconds` | 6.7034 | 6.7297 |

## Figures 7 and 9: `runs`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `pcb1.inference_seconds` | 19.8303 | 19.8150 |
| `pcb1.load_seconds` | 2.5371 | 2.3827 |
| `pcb1.seconds_per_image` | 0.0992 | 0.0991 |
| `pcb4.inference_seconds` | 18.0299 | 18.1451 |
| `pcb4.load_seconds` | 1.6695 | 1.7473 |
| `pcb4.seconds_per_image` | 0.0897 | 0.0903 |

## Figure 9: `judge_memory`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `card_before_mib` | 27394 | 29515 |
| `samples` | 608 | 607 |

## The warm-up

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `seconds` | 6.0940 | 1.7882 |
