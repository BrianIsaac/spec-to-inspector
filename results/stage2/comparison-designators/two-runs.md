# The `designators` comparison's two runs: every figure that differs

Made from the two records alone, field by field: `first-run.json` and `bench.json`. A field not listed
reads the same in both.

| Part of the record | Fields | Fields that differ |
| --- | --- | --- |
| Figures 1 to 6: `scores` | 343 | 0 |
| Figure 7: `times` | 44 | 24 |
| Figure 8: `inspector` | 6 | 4 |
| Figures 7 and 9: `runs` | 52 | 6 |
| Figure 9: `judge_memory` | 8 | 1 |
| The warm-up | 3 | 1 |
| The cold | 8 | 0 |
| Refused answers | 12 | 0 |

## Figure 7: `times`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `anomaly_seconds_per_image.pcb1` | 0.0993 | 0.0991 |
| `anomaly_seconds_per_image.pcb4` | 0.0901 | 0.0905 |
| `flagged_image_seconds.maximum` | 4.9752 | 4.9721 |
| `flagged_image_seconds.mean` | 2.3635 | 2.3624 |
| `flagged_image_seconds.minimum` | 1.9861 | 1.9747 |
| `flagged_image_seconds.p50` | 2.3310 | 2.3316 |
| `flagged_image_seconds.p95` | 2.6416 | 2.6607 |
| `judge_stage_seconds` | 492.4958 | 492.2269 |
| `measure_and_draw_seconds.maximum` | 0.4648 | 0.4623 |
| `measure_and_draw_seconds.mean` | 0.0910 | 0.0906 |
| `measure_and_draw_seconds.minimum` | 0.0387 | 0.0326 |
| `measure_and_draw_seconds.p50` | 0.0639 | 0.0627 |
| `measure_and_draw_seconds.p95` | 0.2476 | 0.2462 |
| `parse_seconds` | 6.8340 | 6.7783 |
| `vlm_seconds_per_area.maximum` | 4.8331 | 4.8338 |
| `vlm_seconds_per_area.mean` | 2.1778 | 2.1769 |
| `vlm_seconds_per_area.minimum` | 1.8395 | 1.8333 |
| `vlm_seconds_per_area.p50` | 2.1238 | 2.1275 |
| `vlm_seconds_per_area.p95` | 2.4378 | 2.4523 |
| `vlm_seconds_per_flagged_image.maximum` | 4.8331 | 4.8338 |
| `vlm_seconds_per_flagged_image.mean` | 2.1778 | 2.1769 |
| `vlm_seconds_per_flagged_image.minimum` | 1.8395 | 1.8333 |
| `vlm_seconds_per_flagged_image.p50` | 2.1238 | 2.1275 |
| `vlm_seconds_per_flagged_image.p95` | 2.4378 | 2.4523 |

## Figure 8: `inspector`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `minutes_all_parts` | 23.4400 | 23.4391 |
| `minutes_by_part.pcb1` | 11.7602 | 11.7592 |
| `minutes_by_part.pcb4` | 11.7937 | 11.7928 |
| `parse_seconds` | 6.8340 | 6.7783 |

## Figures 7 and 9: `runs`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `pcb1.inference_seconds` | 19.8557 | 19.8249 |
| `pcb1.load_seconds` | 2.5156 | 2.5796 |
| `pcb1.seconds_per_image` | 0.0993 | 0.0991 |
| `pcb4.inference_seconds` | 18.1135 | 18.1806 |
| `pcb4.load_seconds` | 1.6518 | 1.6653 |
| `pcb4.seconds_per_image` | 0.0901 | 0.0905 |

## Figure 9: `judge_memory`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `card_before_mib` | 27766 | 29784 |

## The warm-up

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `seconds` | 5.4688 | 1.9864 |
