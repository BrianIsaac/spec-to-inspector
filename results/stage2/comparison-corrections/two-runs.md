# The corrections comparison's two runs: every value that differs

Made from the two records alone, field by field: `first-run.json` and `bench.json`, by `raw/two_runs.py.txt`. A field not listed reads the same in both.

## The boards

| Boards in both | flagged | score | citation | cited_heading | cited_class | sentence |
| --- | --- | --- | --- | --- | --- | --- |
| 401 | 0 | 0 | 0 | 0 | 0 | 0 |

## The fields of the record

| Part of the record | Fields | Fields that differ |
| --- | --- | --- |
| Board by board: `observations` | 8405 | 618 |
| Corrections in a prompt: `leak` | 2 | 0 |
| Figure 7: `times` | 44 | 24 |
| Figure 8: `inspector` | 6 | 4 |
| Figure 9: `judge_memory` | 8 | 2 |
| Figures 1 to 6: `scores` | 348 | 0 |
| Figures 7 and 9: `runs` | 52 | 7 |
| How the judge was asked: `judge` | 43 | 3 |
| Refused answers | 36 | 0 |
| The boards on the threshold | 27 | 0 |
| The specification | 10 | 1 |
| The store: `declared_store` | 31 | 0 |
| What the record is made of | 61 | 11 |

## Board by board: `observations`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `observations[pcb1 bad-000].areas[0].seconds` | 1.9795 | 1.9968 |
| `observations[pcb1 bad-000].judge_seconds` | 2.0298 | 2.0418 |
| `observations[pcb1 bad-001].areas[0].seconds` | 2.3043 | 2.3174 |
| `observations[pcb1 bad-001].judge_seconds` | 2.4300 | 2.4426 |
| `observations[pcb1 bad-002].areas[0].seconds` | 2.2074 | 2.2145 |
| `observations[pcb1 bad-002].judge_seconds` | 2.3164 | 2.3223 |
| `observations[pcb1 bad-003].areas[0].seconds` | 2.0961 | 2.0998 |
| `observations[pcb1 bad-003].judge_seconds` | 2.2070 | 2.2176 |
| `observations[pcb1 bad-004].areas[0].seconds` | 2.0767 | 2.0840 |
| `observations[pcb1 bad-004].judge_seconds` | 2.1913 | 2.1974 |
| `observations[pcb1 bad-005].areas[0].seconds` | 2.1557 | 2.1548 |
| `observations[pcb1 bad-005].judge_seconds` | 2.3259 | 2.3236 |
| `observations[pcb1 bad-006].areas[0].seconds` | 2.0642 | 2.0713 |
| `observations[pcb1 bad-006].judge_seconds` | 2.1980 | 2.2046 |
| `observations[pcb1 bad-007].areas[0].seconds` | 2.1121 | 2.1148 |
| `observations[pcb1 bad-007].judge_seconds` | 2.3526 | 2.3572 |
| `observations[pcb1 bad-008].areas[0].seconds` | 2.0844 | 2.0888 |
| `observations[pcb1 bad-008].judge_seconds` | 2.2184 | 2.2212 |
| `observations[pcb1 bad-009].areas[0].seconds` | 2.1073 | 2.1162 |
| `observations[pcb1 bad-009].judge_seconds` | 2.2612 | 2.2662 |
| `observations[pcb1 bad-010].areas[0].seconds` | 2.1161 | 2.0941 |
| `observations[pcb1 bad-010].judge_seconds` | 2.2255 | 2.1966 |
| `observations[pcb1 bad-011].areas[0].seconds` | 2.0992 | 2.1014 |
| `observations[pcb1 bad-011].judge_seconds` | 2.2140 | 2.2187 |
| `observations[pcb1 bad-012].areas[0].seconds` | 2.1497 | 2.1511 |
| `observations[pcb1 bad-012].judge_seconds` | 2.2811 | 2.2779 |
| `observations[pcb1 bad-013].areas[0].seconds` | 2.1453 | 2.1420 |
| `observations[pcb1 bad-013].judge_seconds` | 2.2976 | 2.2935 |
| `observations[pcb1 bad-014].areas[0].seconds` | 2.1613 | 2.1567 |
| `observations[pcb1 bad-014].judge_seconds` | 2.4041 | 2.4003 |
| `observations[pcb1 bad-015].areas[0].seconds` | 2.0134 | 2.0069 |
| `observations[pcb1 bad-015].judge_seconds` | 2.0622 | 2.0604 |
| `observations[pcb1 bad-016].areas[0].seconds` | 2.0849 | 2.0791 |
| `observations[pcb1 bad-016].judge_seconds` | 2.1818 | 2.1768 |
| `observations[pcb1 bad-017].areas[0].seconds` | 2.0229 | 2.0114 |
| `observations[pcb1 bad-017].judge_seconds` | 2.0740 | 2.0625 |
| `observations[pcb1 bad-018].areas[0].seconds` | 2.0223 | 2.0055 |
| `observations[pcb1 bad-018].judge_seconds` | 2.0742 | 2.0589 |
| `observations[pcb1 bad-019].areas[0].seconds` | 2.5189 | 2.4995 |
| `observations[pcb1 bad-019].judge_seconds` | 2.5726 | 2.5519 |
| `observations[pcb1 bad-020].judge_seconds` | 0.0014 | 0.0013 |
| `observations[pcb1 bad-021].areas[0].seconds` | 2.0607 | 2.0498 |
| `observations[pcb1 bad-021].judge_seconds` | 2.1381 | 2.1264 |
| `observations[pcb1 bad-022].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb1 bad-023].areas[0].seconds` | 2.0801 | 2.0677 |
| `observations[pcb1 bad-023].judge_seconds` | 2.1403 | 2.1298 |
| `observations[pcb1 bad-024].areas[0].seconds` | 2.1726 | 2.1599 |
| `observations[pcb1 bad-024].judge_seconds` | 2.2222 | 2.2096 |
| `observations[pcb1 bad-025].judge_seconds` | 0.0014 | 0.0013 |
| `observations[pcb1 bad-026].areas[0].seconds` | 2.0190 | 2.0113 |
| `observations[pcb1 bad-026].judge_seconds` | 2.0722 | 2.0568 |
| `observations[pcb1 bad-027].areas[0].seconds` | 2.0230 | 2.0066 |
| `observations[pcb1 bad-027].judge_seconds` | 2.0671 | 2.0623 |
| `observations[pcb1 bad-028].areas[0].seconds` | 2.0837 | 2.0791 |
| `observations[pcb1 bad-028].judge_seconds` | 2.1450 | 2.1432 |
| `observations[pcb1 bad-029].areas[0].seconds` | 2.2034 | 2.1939 |
| `observations[pcb1 bad-029].judge_seconds` | 2.2434 | 2.2451 |
| `observations[pcb1 bad-030].areas[0].seconds` | 2.1550 | 2.1431 |
| `observations[pcb1 bad-030].judge_seconds` | 2.2122 | 2.2024 |
| `observations[pcb1 bad-031].areas[0].seconds` | 2.1049 | 2.0979 |
| `observations[pcb1 bad-031].judge_seconds` | 2.1541 | 2.1426 |
| `observations[pcb1 bad-032].areas[0].seconds` | 2.0999 | 2.0909 |
| `observations[pcb1 bad-032].judge_seconds` | 2.1760 | 2.1616 |
| `observations[pcb1 bad-033].areas[0].seconds` | 2.0418 | 2.0363 |
| `observations[pcb1 bad-033].judge_seconds` | 2.0934 | 2.0850 |
| `observations[pcb1 bad-034].areas[0].seconds` | 1.9901 | 1.9839 |
| `observations[pcb1 bad-034].judge_seconds` | 2.0405 | 2.0351 |
| `observations[pcb1 bad-035].areas[0].seconds` | 2.1694 | 2.1613 |
| `observations[pcb1 bad-035].judge_seconds` | 2.2171 | 2.2103 |
| `observations[pcb1 bad-036].areas[0].seconds` | 2.5324 | 2.5284 |
| `observations[pcb1 bad-036].judge_seconds` | 2.5709 | 2.5791 |
| `observations[pcb1 bad-037].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb1 bad-038].areas[0].seconds` | 2.1088 | 2.0865 |
| `observations[pcb1 bad-038].judge_seconds` | 2.1816 | 2.1606 |
| `observations[pcb1 bad-039].areas[0].seconds` | 2.1528 | 2.1298 |
| `observations[pcb1 bad-039].judge_seconds` | 2.2184 | 2.1950 |
| `observations[pcb1 bad-040].areas[0].seconds` | 2.3774 | 2.3728 |
| `observations[pcb1 bad-040].judge_seconds` | 2.7505 | 2.7393 |
| `observations[pcb1 bad-041].areas[0].seconds` | 2.1849 | 2.1868 |
| `observations[pcb1 bad-041].judge_seconds` | 2.4620 | 2.4697 |
| `observations[pcb1 bad-042].areas[0].seconds` | 1.9610 | 1.9653 |
| `observations[pcb1 bad-042].judge_seconds` | 2.0756 | 2.0796 |
| `observations[pcb1 bad-043].areas[0].seconds` | 2.7103 | 2.7024 |
| `observations[pcb1 bad-043].judge_seconds` | 3.2001 | 3.1591 |
| `observations[pcb1 bad-044].areas[0].seconds` | 2.0309 | 2.0137 |
| `observations[pcb1 bad-044].judge_seconds` | 2.2146 | 2.2011 |
| `observations[pcb1 bad-045].areas[0].seconds` | 2.0234 | 2.0204 |
| `observations[pcb1 bad-045].judge_seconds` | 2.2154 | 2.2119 |
| `observations[pcb1 bad-046].areas[0].seconds` | 2.0399 | 2.0369 |
| `observations[pcb1 bad-046].judge_seconds` | 2.2899 | 2.2940 |
| `observations[pcb1 bad-047].areas[0].seconds` | 2.1199 | 2.1118 |
| `observations[pcb1 bad-047].judge_seconds` | 2.1840 | 2.1701 |
| `observations[pcb1 bad-048].judge_seconds` | 0.0015 | 0.0004 |
| `observations[pcb1 bad-049].areas[0].seconds` | 2.0155 | 2.0209 |
| `observations[pcb1 bad-049].judge_seconds` | 2.1554 | 2.1500 |
| `observations[pcb1 bad-050].areas[0].seconds` | 2.0438 | 2.0312 |
| `observations[pcb1 bad-050].judge_seconds` | 2.2868 | 2.2696 |
| `observations[pcb1 bad-051].areas[0].seconds` | 2.1182 | 2.0950 |
| `observations[pcb1 bad-051].judge_seconds` | 2.2098 | 2.1912 |
| `observations[pcb1 bad-052].areas[0].seconds` | 2.0211 | 2.0219 |
| `observations[pcb1 bad-052].judge_seconds` | 2.0950 | 2.0999 |
| `observations[pcb1 bad-053].areas[0].seconds` | 2.0433 | 2.0076 |
| `observations[pcb1 bad-053].judge_seconds` | 2.1946 | 2.1595 |
| `observations[pcb1 bad-054].areas[0].seconds` | 2.0025 | 2.0056 |
| `observations[pcb1 bad-054].judge_seconds` | 2.2016 | 2.2026 |
| `observations[pcb1 bad-055].areas[0].seconds` | 2.0279 | 2.0140 |
| `observations[pcb1 bad-055].judge_seconds` | 2.2135 | 2.1959 |
| `observations[pcb1 bad-056].areas[0].seconds` | 2.1672 | 2.1692 |
| `observations[pcb1 bad-056].judge_seconds` | 2.3458 | 2.3505 |
| `observations[pcb1 bad-057].areas[0].seconds` | 2.0814 | 2.0744 |
| `observations[pcb1 bad-057].judge_seconds` | 2.1344 | 2.1282 |
| `observations[pcb1 bad-058].areas[0].seconds` | 2.1156 | 2.1150 |
| `observations[pcb1 bad-058].judge_seconds` | 2.1669 | 2.1644 |
| `observations[pcb1 bad-059].areas[0].seconds` | 2.0786 | 2.0595 |
| `observations[pcb1 bad-059].judge_seconds` | 2.3079 | 2.2971 |
| `observations[pcb1 bad-060].judge_seconds` | 0.0013 | 0.0015 |
| `observations[pcb1 bad-061].areas[0].seconds` | 2.1704 | 2.1710 |
| `observations[pcb1 bad-061].judge_seconds` | 2.2161 | 2.2172 |
| `observations[pcb1 bad-062].areas[0].seconds` | 2.3292 | 2.3208 |
| `observations[pcb1 bad-062].judge_seconds` | 2.3799 | 2.3712 |
| `observations[pcb1 bad-063].areas[0].seconds` | 1.9820 | 1.9633 |
| `observations[pcb1 bad-063].judge_seconds` | 2.0330 | 2.0150 |
| `observations[pcb1 bad-064].areas[0].seconds` | 2.2165 | 2.2054 |
| `observations[pcb1 bad-064].judge_seconds` | 2.2666 | 2.2571 |
| `observations[pcb1 bad-065].areas[0].seconds` | 2.0780 | 2.0810 |
| `observations[pcb1 bad-065].judge_seconds` | 2.1365 | 2.1514 |
| `observations[pcb1 bad-066].areas[0].seconds` | 2.0181 | 2.0239 |
| `observations[pcb1 bad-066].judge_seconds` | 2.0730 | 2.0788 |
| `observations[pcb1 bad-067].areas[0].seconds` | 2.1759 | 2.1702 |
| `observations[pcb1 bad-067].judge_seconds` | 2.2270 | 2.2193 |
| `observations[pcb1 bad-068].areas[0].seconds` | 2.3147 | 2.3042 |
| `observations[pcb1 bad-068].judge_seconds` | 2.4131 | 2.4028 |
| `observations[pcb1 bad-069].areas[0].seconds` | 2.1531 | 2.1501 |
| `observations[pcb1 bad-069].judge_seconds` | 2.2056 | 2.2020 |
| `observations[pcb1 bad-070].areas[0].seconds` | 2.1592 | 2.1421 |
| `observations[pcb1 bad-070].judge_seconds` | 2.2300 | 2.2132 |
| `observations[pcb1 bad-071].areas[0].seconds` | 2.5207 | 2.5221 |
| `observations[pcb1 bad-071].judge_seconds` | 2.5919 | 2.5936 |
| `observations[pcb1 bad-072].areas[0].seconds` | 2.0933 | 2.0850 |
| `observations[pcb1 bad-072].judge_seconds` | 2.1584 | 2.1509 |
| `observations[pcb1 bad-073].areas[0].seconds` | 1.9989 | 2.0044 |
| `observations[pcb1 bad-073].judge_seconds` | 2.0489 | 2.0554 |
| `observations[pcb1 bad-074].areas[0].seconds` | 1.9752 | 1.9708 |
| `observations[pcb1 bad-074].judge_seconds` | 2.0258 | 2.0214 |
| `observations[pcb1 bad-075].areas[0].seconds` | 2.0240 | 2.0245 |
| `observations[pcb1 bad-075].judge_seconds` | 2.0738 | 2.0733 |
| `observations[pcb1 bad-076].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb1 bad-077].areas[0].seconds` | 2.1714 | 2.1507 |
| `observations[pcb1 bad-077].judge_seconds` | 2.2241 | 2.2025 |
| `observations[pcb1 bad-078].areas[0].seconds` | 1.9663 | 1.9629 |
| `observations[pcb1 bad-078].judge_seconds` | 2.0154 | 2.0123 |
| `observations[pcb1 bad-079].areas[0].seconds` | 2.2592 | 2.2576 |
| `observations[pcb1 bad-079].judge_seconds` | 2.3070 | 2.3063 |
| `observations[pcb1 bad-080].areas[0].seconds` | 2.1141 | 2.0898 |
| `observations[pcb1 bad-080].judge_seconds` | 2.1807 | 2.1563 |
| `observations[pcb1 bad-081].areas[0].seconds` | 1.9932 | 1.9935 |
| `observations[pcb1 bad-081].judge_seconds` | 2.0460 | 2.0446 |
| `observations[pcb1 bad-082].areas[0].seconds` | 2.0861 | 2.0801 |
| `observations[pcb1 bad-082].judge_seconds` | 2.1396 | 2.1339 |
| `observations[pcb1 bad-083].areas[0].seconds` | 2.2313 | 2.2216 |
| `observations[pcb1 bad-083].judge_seconds` | 2.2837 | 2.2751 |
| `observations[pcb1 bad-084].areas[0].seconds` | 2.2460 | 2.2459 |
| `observations[pcb1 bad-084].judge_seconds` | 2.3288 | 2.3276 |
| `observations[pcb1 bad-085].areas[0].seconds` | 2.0631 | 2.0495 |
| `observations[pcb1 bad-085].judge_seconds` | 2.1097 | 2.0973 |
| `observations[pcb1 bad-086].areas[0].seconds` | 1.9966 | 1.9974 |
| `observations[pcb1 bad-086].judge_seconds` | 2.0488 | 2.0506 |
| `observations[pcb1 bad-087].areas[0].seconds` | 2.3279 | 2.3269 |
| `observations[pcb1 bad-087].judge_seconds` | 2.3768 | 2.3760 |
| `observations[pcb1 bad-088].areas[0].seconds` | 1.9955 | 2.0045 |
| `observations[pcb1 bad-088].judge_seconds` | 2.0500 | 2.0549 |
| `observations[pcb1 bad-089].areas[0].seconds` | 2.1995 | 2.1904 |
| `observations[pcb1 bad-089].judge_seconds` | 2.2562 | 2.2499 |
| `observations[pcb1 bad-090].areas[0].seconds` | 2.3042 | 2.3072 |
| `observations[pcb1 bad-090].judge_seconds` | 2.3621 | 2.3642 |
| `observations[pcb1 bad-091].areas[0].seconds` | 1.9890 | 1.9906 |
| `observations[pcb1 bad-091].judge_seconds` | 2.0367 | 2.0353 |
| `observations[pcb1 bad-092].areas[0].seconds` | 2.7846 | 2.7786 |
| `observations[pcb1 bad-092].judge_seconds` | 2.8598 | 2.8500 |
| `observations[pcb1 bad-093].areas[0].seconds` | 2.2942 | 2.2898 |
| `observations[pcb1 bad-093].judge_seconds` | 2.3648 | 2.3545 |
| `observations[pcb1 bad-094].areas[0].seconds` | 2.2595 | 2.2664 |
| `observations[pcb1 bad-094].judge_seconds` | 2.3093 | 2.3153 |
| `observations[pcb1 bad-095].areas[0].seconds` | 2.0535 | 2.0631 |
| `observations[pcb1 bad-095].judge_seconds` | 2.1032 | 2.1129 |
| `observations[pcb1 bad-096].judge_seconds` | 0.0018 | 0.0013 |
| `observations[pcb1 bad-097].areas[0].seconds` | 1.9718 | 1.9667 |
| `observations[pcb1 bad-097].judge_seconds` | 2.0242 | 2.0202 |
| `observations[pcb1 bad-098].areas[0].seconds` | 1.9929 | 1.9949 |
| `observations[pcb1 bad-098].judge_seconds` | 2.0425 | 2.0461 |
| `observations[pcb1 bad-099].areas[0].seconds` | 2.1043 | 2.1085 |
| `observations[pcb1 bad-099].judge_seconds` | 2.1718 | 2.1763 |
| `observations[pcb1 good-0011].judge_seconds` | 0.0013 | 0.0012 |
| `observations[pcb1 good-0013].judge_seconds` | 0.0011 | 0.0013 |
| `observations[pcb1 good-0016].judge_seconds` | 0.0012 | 0.0011 |
| `observations[pcb1 good-0024].judge_seconds` | 0.0009 | 0.0009 |
| `observations[pcb1 good-0026].judge_seconds` | 0.0003 | 0.0011 |
| `observations[pcb1 good-0027].judge_seconds` | 0.0014 | 0.0013 |
| `observations[pcb1 good-0046].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb1 good-0100].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb1 good-0107].judge_seconds` | 0.0029 | 0.0031 |
| `observations[pcb1 good-0159].judge_seconds` | 0.0010 | 0.0009 |
| `observations[pcb1 good-0168].judge_seconds` | 0.0011 | 0.0012 |
| `observations[pcb1 good-0170].judge_seconds` | 0.0009 | 0.0002 |
| `observations[pcb1 good-0172].judge_seconds` | 0.0011 | 0.0009 |
| `observations[pcb1 good-0174].areas[0].seconds` | 2.7097 | 2.7161 |
| `observations[pcb1 good-0174].judge_seconds` | 2.7654 | 2.7666 |
| `observations[pcb1 good-0178].judge_seconds` | 0.0006 | 0.0006 |
| `observations[pcb1 good-0187].judge_seconds` | 0.0010 | 0.0004 |
| `observations[pcb1 good-0196].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb1 good-0208].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb1 good-0214].areas[0].seconds` | 1.9257 | 1.9166 |
| `observations[pcb1 good-0214].judge_seconds` | 1.9827 | 1.9723 |
| `observations[pcb1 good-0215].judge_seconds` | 0.0011 | 0.0010 |
| `observations[pcb1 good-0237].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb1 good-0261].areas[0].seconds` | 2.0130 | 2.0167 |
| `observations[pcb1 good-0261].judge_seconds` | 2.0619 | 2.0655 |
| `observations[pcb1 good-0286].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb1 good-0294].judge_seconds` | 0.0013 | 0.0014 |
| `observations[pcb1 good-0297].judge_seconds` | 0.0010 | 0.0011 |
| `observations[pcb1 good-0303].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb1 good-0306].areas[0].seconds` | 2.3390 | 2.3348 |
| `observations[pcb1 good-0306].judge_seconds` | 2.3915 | 2.3834 |
| `observations[pcb1 good-0320].judge_seconds` | 0.0011 | 0.0002 |
| `observations[pcb1 good-0333].areas[0].seconds` | 2.4033 | 2.3973 |
| `observations[pcb1 good-0333].judge_seconds` | 2.4496 | 2.4424 |
| `observations[pcb1 good-0363].judge_seconds` | 0.0009 | 0.0010 |
| `observations[pcb1 good-0377].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb1 good-0394].judge_seconds` | 0.0010 | 0.0009 |
| `observations[pcb1 good-0400].judge_seconds` | 0.0009 | 0.0003 |
| `observations[pcb1 good-0402].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb1 good-0417].judge_seconds` | 0.0002 | 0.0002 |
| `observations[pcb1 good-0423].judge_seconds` | 0.0006 | 0.0002 |
| `observations[pcb1 good-0427].judge_seconds` | 0.0014 | 0.0013 |
| `observations[pcb1 good-0457].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb1 good-0469].judge_seconds` | 0.0009 | 0.0003 |
| `observations[pcb1 good-0479].judge_seconds` | 0.0014 | 0.0013 |
| `observations[pcb1 good-0483].judge_seconds` | 0.0010 | 0.0008 |
| `observations[pcb1 good-0484].judge_seconds` | 0.0012 | 0.0012 |
| `observations[pcb1 good-0488].judge_seconds` | 0.0010 | 0.0004 |
| `observations[pcb1 good-0490].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb1 good-0514].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb1 good-0518].areas[0].seconds` | 2.0967 | 2.0846 |
| `observations[pcb1 good-0518].judge_seconds` | 2.1610 | 2.1220 |
| `observations[pcb1 good-0520].judge_seconds` | 0.0009 | 0.0010 |
| `observations[pcb1 good-0525].judge_seconds` | 0.0009 | 0.0003 |
| `observations[pcb1 good-0545].judge_seconds` | 0.0010 | 0.0004 |
| `observations[pcb1 good-0552].judge_seconds` | 0.0020 | 0.0011 |
| `observations[pcb1 good-0569].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb1 good-0615].judge_seconds` | 0.0009 | 0.0004 |
| `observations[pcb1 good-0617].judge_seconds` | 0.0094 | 0.0009 |
| `observations[pcb1 good-0619].judge_seconds` | 0.0009 | 0.0010 |
| `observations[pcb1 good-0621].areas[0].seconds` | 2.0966 | 2.0904 |
| `observations[pcb1 good-0621].judge_seconds` | 2.1442 | 2.1374 |
| `observations[pcb1 good-0629].judge_seconds` | 0.0010 | 0.0009 |
| `observations[pcb1 good-0631].judge_seconds` | 0.0009 | 0.0002 |
| `observations[pcb1 good-0648].judge_seconds` | 0.0014 | 0.0013 |
| `observations[pcb1 good-0654].judge_seconds` | 0.0009 | 0.0006 |
| `observations[pcb1 good-0657].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb1 good-0659].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb1 good-0674].areas[0].seconds` | 2.0073 | 2.0164 |
| `observations[pcb1 good-0674].judge_seconds` | 2.0683 | 2.0659 |
| `observations[pcb1 good-0684].areas[0].seconds` | 2.1371 | 2.1470 |
| `observations[pcb1 good-0684].judge_seconds` | 2.1854 | 2.1914 |
| `observations[pcb1 good-0685].judge_seconds` | 0.0009 | 0.0003 |
| `observations[pcb1 good-0688].judge_seconds` | 0.0008 | 0.0008 |
| `observations[pcb1 good-0690].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb1 good-0694].areas[0].seconds` | 2.1947 | 2.1921 |
| `observations[pcb1 good-0694].judge_seconds` | 2.2562 | 2.2520 |
| `observations[pcb1 good-0705].areas[0].seconds` | 2.0940 | 2.0969 |
| `observations[pcb1 good-0705].judge_seconds` | 2.1390 | 2.1443 |
| `observations[pcb1 good-0725].judge_seconds` | 0.0014 | 0.0009 |
| `observations[pcb1 good-0730].areas[0].seconds` | 2.0727 | 2.0400 |
| `observations[pcb1 good-0730].judge_seconds` | 2.2055 | 2.1638 |
| `observations[pcb1 good-0735].judge_seconds` | 0.0009 | 0.0010 |
| `observations[pcb1 good-0739].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb1 good-0751].areas[0].seconds` | 2.0027 | 2.0012 |
| `observations[pcb1 good-0751].judge_seconds` | 2.0423 | 2.0400 |
| `observations[pcb1 good-0755].judge_seconds` | 0.0014 | 0.0033 |
| `observations[pcb1 good-0764].areas[0].seconds` | 2.1518 | 2.1461 |
| `observations[pcb1 good-0764].judge_seconds` | 2.2011 | 2.1945 |
| `observations[pcb1 good-0768].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb1 good-0779].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb1 good-0784].judge_seconds` | 0.0014 | 0.0013 |
| `observations[pcb1 good-0796].judge_seconds` | 0.0006 | 0.0006 |
| `observations[pcb1 good-0797].areas[0].seconds` | 2.3216 | 2.3236 |
| `observations[pcb1 good-0797].judge_seconds` | 2.3677 | 2.3663 |
| `observations[pcb1 good-0800].judge_seconds` | 0.0011 | 0.0010 |
| `observations[pcb1 good-0804].judge_seconds` | 0.0031 | 0.0010 |
| `observations[pcb1 good-0811].judge_seconds` | 0.0009 | 0.0010 |
| `observations[pcb1 good-0844].judge_seconds` | 0.0003 | 0.0010 |
| `observations[pcb1 good-0869].judge_seconds` | 0.0009 | 0.0002 |
| `observations[pcb1 good-0871].judge_seconds` | 0.0009 | 0.0010 |
| `observations[pcb1 good-0892].judge_seconds` | 0.0010 | 0.0009 |
| `observations[pcb1 good-0900].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb1 good-0920].areas[0].seconds` | 2.4724 | 2.4779 |
| `observations[pcb1 good-0920].judge_seconds` | 2.5634 | 2.5690 |
| `observations[pcb1 good-0923].areas[0].seconds` | 2.1612 | 2.1745 |
| `observations[pcb1 good-0923].judge_seconds` | 2.2080 | 2.2202 |
| `observations[pcb1 good-0935].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb1 good-0940].judge_seconds` | 0.0004 | 0.0013 |
| `observations[pcb1 good-0952].judge_seconds` | 0.0009 | 0.0009 |
| `observations[pcb1 good-0957].areas[0].seconds` | 2.1999 | 2.1783 |
| `observations[pcb1 good-0957].judge_seconds` | 2.2366 | 2.2231 |
| `observations[pcb1 good-0964].judge_seconds` | 0.0010 | 0.0004 |
| `observations[pcb1 good-0971].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb1 good-0974].areas[0].seconds` | 1.9163 | 1.9237 |
| `observations[pcb1 good-0974].judge_seconds` | 1.9552 | 1.9652 |
| `observations[pcb1 good-0989].judge_seconds` | 0.0014 | 0.0013 |
| `observations[pcb1 good-0994].judge_seconds` | 0.0010 | 0.0004 |
| `observations[pcb1 good-1000].judge_seconds` | 0.0010 | 0.0008 |
| `observations[pcb4 bad-000].areas[0].seconds` | 2.2472 | 2.2383 |
| `observations[pcb4 bad-000].judge_seconds` | 2.3345 | 2.3262 |
| `observations[pcb4 bad-001].areas[0].seconds` | 2.0151 | 1.9945 |
| `observations[pcb4 bad-001].judge_seconds` | 2.0697 | 2.0544 |
| `observations[pcb4 bad-002].areas[0].seconds` | 2.3416 | 2.3173 |
| `observations[pcb4 bad-002].judge_seconds` | 2.6157 | 2.5910 |
| `observations[pcb4 bad-003].areas[0].seconds` | 2.2193 | 2.2074 |
| `observations[pcb4 bad-003].judge_seconds` | 2.2938 | 2.2681 |
| `observations[pcb4 bad-004].areas[0].seconds` | 2.5256 | 2.5196 |
| `observations[pcb4 bad-004].judge_seconds` | 2.5999 | 2.5966 |
| `observations[pcb4 bad-005].areas[0].seconds` | 2.2920 | 2.2867 |
| `observations[pcb4 bad-005].judge_seconds` | 2.3394 | 2.3355 |
| `observations[pcb4 bad-006].areas[0].seconds` | 2.2566 | 2.2520 |
| `observations[pcb4 bad-006].judge_seconds` | 2.3646 | 2.3596 |
| `observations[pcb4 bad-007].areas[0].seconds` | 1.9385 | 1.9306 |
| `observations[pcb4 bad-007].judge_seconds` | 1.9894 | 1.9810 |
| `observations[pcb4 bad-008].areas[0].seconds` | 2.2727 | 2.2601 |
| `observations[pcb4 bad-008].judge_seconds` | 2.3260 | 2.3107 |
| `observations[pcb4 bad-009].areas[0].seconds` | 2.1727 | 2.1654 |
| `observations[pcb4 bad-009].judge_seconds` | 2.2251 | 2.2167 |
| `observations[pcb4 bad-010].areas[0].seconds` | 2.2393 | 2.2273 |
| `observations[pcb4 bad-010].judge_seconds` | 2.3654 | 2.3409 |
| `observations[pcb4 bad-011].areas[0].seconds` | 2.4270 | 2.4126 |
| `observations[pcb4 bad-011].judge_seconds` | 2.5226 | 2.5027 |
| `observations[pcb4 bad-012].areas[0].seconds` | 2.3235 | 2.3107 |
| `observations[pcb4 bad-012].judge_seconds` | 2.4248 | 2.4101 |
| `observations[pcb4 bad-013].areas[0].seconds` | 2.1986 | 2.1773 |
| `observations[pcb4 bad-013].judge_seconds` | 2.2880 | 2.2674 |
| `observations[pcb4 bad-014].areas[0].seconds` | 2.6040 | 2.5956 |
| `observations[pcb4 bad-014].judge_seconds` | 2.6803 | 2.6758 |
| `observations[pcb4 bad-015].areas[0].seconds` | 2.2819 | 2.2600 |
| `observations[pcb4 bad-015].judge_seconds` | 2.3635 | 2.3536 |
| `observations[pcb4 bad-016].areas[0].seconds` | 2.5145 | 2.5037 |
| `observations[pcb4 bad-016].judge_seconds` | 2.5835 | 2.5729 |
| `observations[pcb4 bad-017].areas[0].seconds` | 2.3190 | 2.3064 |
| `observations[pcb4 bad-017].judge_seconds` | 2.4877 | 2.4750 |
| `observations[pcb4 bad-018].areas[0].seconds` | 2.0397 | 2.0222 |
| `observations[pcb4 bad-018].judge_seconds` | 2.1067 | 2.0911 |
| `observations[pcb4 bad-019].areas[0].seconds` | 2.1354 | 2.1244 |
| `observations[pcb4 bad-019].judge_seconds` | 2.2324 | 2.2243 |
| `observations[pcb4 bad-020].areas[0].seconds` | 2.2756 | 2.2594 |
| `observations[pcb4 bad-020].judge_seconds` | 2.3278 | 2.3138 |
| `observations[pcb4 bad-021].areas[0].seconds` | 2.3052 | 2.2952 |
| `observations[pcb4 bad-021].judge_seconds` | 2.4298 | 2.4225 |
| `observations[pcb4 bad-022].areas[0].seconds` | 2.2685 | 2.2519 |
| `observations[pcb4 bad-022].judge_seconds` | 2.3271 | 2.3103 |
| `observations[pcb4 bad-023].areas[0].seconds` | 2.1588 | 2.1431 |
| `observations[pcb4 bad-023].judge_seconds` | 2.2284 | 2.2146 |
| `observations[pcb4 bad-024].areas[0].seconds` | 2.2832 | 2.2726 |
| `observations[pcb4 bad-024].judge_seconds` | 2.4021 | 2.3897 |
| `observations[pcb4 bad-025].areas[0].seconds` | 2.1841 | 2.1719 |
| `observations[pcb4 bad-025].judge_seconds` | 2.2560 | 2.2440 |
| `observations[pcb4 bad-026].areas[0].seconds` | 2.3475 | 2.3451 |
| `observations[pcb4 bad-026].judge_seconds` | 2.4248 | 2.4205 |
| `observations[pcb4 bad-027].areas[0].seconds` | 2.2709 | 2.2634 |
| `observations[pcb4 bad-027].judge_seconds` | 2.3706 | 2.3628 |
| `observations[pcb4 bad-028].areas[0].seconds` | 2.1558 | 2.1635 |
| `observations[pcb4 bad-028].judge_seconds` | 2.2277 | 2.2361 |
| `observations[pcb4 bad-029].areas[0].seconds` | 2.3026 | 2.2987 |
| `observations[pcb4 bad-029].judge_seconds` | 2.3867 | 2.3811 |
| `observations[pcb4 bad-030].areas[0].seconds` | 2.4118 | 2.4051 |
| `observations[pcb4 bad-030].judge_seconds` | 2.4788 | 2.4772 |
| `observations[pcb4 bad-031].areas[0].seconds` | 2.3217 | 2.3308 |
| `observations[pcb4 bad-031].judge_seconds` | 2.4192 | 2.4315 |
| `observations[pcb4 bad-032].areas[0].seconds` | 2.2148 | 2.2168 |
| `observations[pcb4 bad-032].judge_seconds` | 2.2988 | 2.3006 |
| `observations[pcb4 bad-033].areas[0].seconds` | 2.1851 | 2.1892 |
| `observations[pcb4 bad-033].judge_seconds` | 2.2834 | 2.2853 |
| `observations[pcb4 bad-034].areas[0].seconds` | 2.2914 | 2.2712 |
| `observations[pcb4 bad-034].judge_seconds` | 2.4288 | 2.4099 |
| `observations[pcb4 bad-035].areas[0].seconds` | 2.0280 | 2.0273 |
| `observations[pcb4 bad-035].judge_seconds` | 2.1102 | 2.1196 |
| `observations[pcb4 bad-036].areas[0].seconds` | 2.2725 | 2.2729 |
| `observations[pcb4 bad-036].judge_seconds` | 2.3838 | 2.3869 |
| `observations[pcb4 bad-037].areas[0].seconds` | 2.3586 | 2.3527 |
| `observations[pcb4 bad-037].judge_seconds` | 2.4634 | 2.4554 |
| `observations[pcb4 bad-038].areas[0].seconds` | 2.1173 | 2.1110 |
| `observations[pcb4 bad-038].judge_seconds` | 2.1707 | 2.1511 |
| `observations[pcb4 bad-039].areas[0].seconds` | 2.2515 | 2.2336 |
| `observations[pcb4 bad-039].judge_seconds` | 2.3700 | 2.3482 |
| `observations[pcb4 bad-040].areas[0].seconds` | 2.2851 | 2.2642 |
| `observations[pcb4 bad-040].judge_seconds` | 2.4680 | 2.4453 |
| `observations[pcb4 bad-041].areas[0].seconds` | 2.3366 | 2.3308 |
| `observations[pcb4 bad-041].judge_seconds` | 2.4331 | 2.4285 |
| `observations[pcb4 bad-042].areas[0].seconds` | 2.2312 | 2.2186 |
| `observations[pcb4 bad-042].judge_seconds` | 2.2953 | 2.2800 |
| `observations[pcb4 bad-043].areas[0].seconds` | 2.3150 | 2.3050 |
| `observations[pcb4 bad-043].judge_seconds` | 2.4210 | 2.4108 |
| `observations[pcb4 bad-044].areas[0].seconds` | 2.6734 | 2.6886 |
| `observations[pcb4 bad-044].judge_seconds` | 2.7524 | 2.7642 |
| `observations[pcb4 bad-045].areas[0].seconds` | 2.1477 | 2.1477 |
| `observations[pcb4 bad-045].judge_seconds` | 2.4072 | 2.4008 |
| `observations[pcb4 bad-046].judge_seconds` | 0.0016 | 0.0013 |
| `observations[pcb4 bad-047].areas[0].seconds` | 2.1562 | 2.1493 |
| `observations[pcb4 bad-047].judge_seconds` | 2.2079 | 2.2006 |
| `observations[pcb4 bad-048].areas[0].seconds` | 2.3775 | 2.3779 |
| `observations[pcb4 bad-048].judge_seconds` | 2.4294 | 2.4280 |
| `observations[pcb4 bad-049].areas[0].seconds` | 2.1506 | 2.1542 |
| `observations[pcb4 bad-049].judge_seconds` | 2.4093 | 2.4162 |
| `observations[pcb4 bad-050].areas[0].seconds` | 2.4383 | 2.4445 |
| `observations[pcb4 bad-050].judge_seconds` | 2.4896 | 2.4998 |
| `observations[pcb4 bad-051].areas[0].seconds` | 2.1629 | 2.1687 |
| `observations[pcb4 bad-051].judge_seconds` | 2.2165 | 2.2101 |
| `observations[pcb4 bad-052].areas[0].seconds` | 2.5141 | 2.5162 |
| `observations[pcb4 bad-052].judge_seconds` | 2.7474 | 2.7513 |
| `observations[pcb4 bad-053].areas[0].seconds` | 2.6098 | 2.5948 |
| `observations[pcb4 bad-053].judge_seconds` | 2.8610 | 2.8443 |
| `observations[pcb4 bad-054].areas[0].seconds` | 2.2651 | 2.2585 |
| `observations[pcb4 bad-054].judge_seconds` | 2.3211 | 2.3127 |
| `observations[pcb4 bad-055].areas[0].seconds` | 1.9758 | 1.9630 |
| `observations[pcb4 bad-055].judge_seconds` | 2.0255 | 2.0139 |
| `observations[pcb4 bad-056].areas[0].seconds` | 2.3067 | 2.2996 |
| `observations[pcb4 bad-056].judge_seconds` | 2.3685 | 2.3611 |
| `observations[pcb4 bad-057].areas[0].seconds` | 2.1854 | 2.1619 |
| `observations[pcb4 bad-057].judge_seconds` | 2.4426 | 2.4215 |
| `observations[pcb4 bad-058].areas[0].seconds` | 2.1398 | 2.1249 |
| `observations[pcb4 bad-058].judge_seconds` | 2.1940 | 2.1809 |
| `observations[pcb4 bad-059].areas[0].seconds` | 2.5624 | 2.5553 |
| `observations[pcb4 bad-059].judge_seconds` | 2.6154 | 2.6074 |
| `observations[pcb4 bad-060].areas[0].seconds` | 2.0402 | 2.0229 |
| `observations[pcb4 bad-060].judge_seconds` | 2.1122 | 2.0958 |
| `observations[pcb4 bad-061].areas[0].seconds` | 2.1822 | 2.1682 |
| `observations[pcb4 bad-061].judge_seconds` | 2.2317 | 2.2179 |
| `observations[pcb4 bad-062].areas[0].seconds` | 2.6273 | 2.6145 |
| `observations[pcb4 bad-062].judge_seconds` | 2.8619 | 2.8529 |
| `observations[pcb4 bad-063].areas[0].seconds` | 2.0495 | 2.0340 |
| `observations[pcb4 bad-063].judge_seconds` | 2.1108 | 2.0934 |
| `observations[pcb4 bad-064].areas[0].seconds` | 2.0792 | 2.0829 |
| `observations[pcb4 bad-064].judge_seconds` | 2.1302 | 2.1347 |
| `observations[pcb4 bad-065].areas[0].seconds` | 2.5088 | 2.5052 |
| `observations[pcb4 bad-065].judge_seconds` | 2.8130 | 2.8117 |
| `observations[pcb4 bad-066].areas[0].seconds` | 2.0645 | 2.0693 |
| `observations[pcb4 bad-066].judge_seconds` | 2.1294 | 2.1321 |
| `observations[pcb4 bad-067].areas[0].seconds` | 1.9651 | 1.9627 |
| `observations[pcb4 bad-067].judge_seconds` | 2.0120 | 2.0126 |
| `observations[pcb4 bad-068].areas[0].seconds` | 2.1263 | 2.1182 |
| `observations[pcb4 bad-068].judge_seconds` | 2.4555 | 2.4403 |
| `observations[pcb4 bad-069].areas[0].seconds` | 2.0076 | 1.9978 |
| `observations[pcb4 bad-069].judge_seconds` | 2.0610 | 2.0520 |
| `observations[pcb4 bad-070].areas[0].seconds` | 2.2868 | 2.2953 |
| `observations[pcb4 bad-070].judge_seconds` | 2.3383 | 2.3468 |
| `observations[pcb4 bad-071].areas[0].seconds` | 1.9915 | 1.9935 |
| `observations[pcb4 bad-071].judge_seconds` | 2.0462 | 2.0484 |
| `observations[pcb4 bad-072].judge_seconds` | 0.0014 | 0.0013 |
| `observations[pcb4 bad-073].areas[0].seconds` | 2.3487 | 2.3450 |
| `observations[pcb4 bad-073].judge_seconds` | 2.6197 | 2.6067 |
| `observations[pcb4 bad-074].areas[0].seconds` | 2.0206 | 2.0227 |
| `observations[pcb4 bad-074].judge_seconds` | 2.0759 | 2.0748 |
| `observations[pcb4 bad-075].areas[0].seconds` | 2.5396 | 2.5410 |
| `observations[pcb4 bad-075].judge_seconds` | 2.6646 | 2.6653 |
| `observations[pcb4 bad-076].areas[0].seconds` | 2.3438 | 2.3522 |
| `observations[pcb4 bad-076].judge_seconds` | 2.4344 | 2.4420 |
| `observations[pcb4 bad-077].areas[0].seconds` | 2.3536 | 2.3622 |
| `observations[pcb4 bad-077].judge_seconds` | 2.4212 | 2.4279 |
| `observations[pcb4 bad-078].areas[0].seconds` | 2.4477 | 2.4538 |
| `observations[pcb4 bad-078].judge_seconds` | 2.5359 | 2.5408 |
| `observations[pcb4 bad-079].areas[0].seconds` | 2.5148 | 2.5108 |
| `observations[pcb4 bad-079].judge_seconds` | 2.6718 | 2.6654 |
| `observations[pcb4 bad-080].areas[0].seconds` | 11.1903 | 11.1999 |
| `observations[pcb4 bad-080].judge_seconds` | 11.2704 | 11.2786 |
| `observations[pcb4 bad-081].judge_seconds` | 0.0016 | 0.0013 |
| `observations[pcb4 bad-082].areas[0].seconds` | 2.1802 | 2.1567 |
| `observations[pcb4 bad-082].judge_seconds` | 2.2420 | 2.2188 |
| `observations[pcb4 bad-083].areas[0].seconds` | 2.8960 | 2.8989 |
| `observations[pcb4 bad-083].judge_seconds` | 2.9632 | 2.9672 |
| `observations[pcb4 bad-084].areas[0].seconds` | 2.1578 | 2.1668 |
| `observations[pcb4 bad-084].judge_seconds` | 2.2226 | 2.2339 |
| `observations[pcb4 bad-085].areas[0].seconds` | 17.7313 | 17.7391 |
| `observations[pcb4 bad-085].judge_seconds` | 17.7840 | 17.7899 |
| `observations[pcb4 bad-086].areas[0].seconds` | 2.5355 | 2.5327 |
| `observations[pcb4 bad-086].judge_seconds` | 2.5981 | 2.5946 |
| `observations[pcb4 bad-087].areas[0].seconds` | 2.9393 | 2.9397 |
| `observations[pcb4 bad-087].judge_seconds` | 3.0339 | 3.0295 |
| `observations[pcb4 bad-088].areas[0].seconds` | 2.1357 | 2.1340 |
| `observations[pcb4 bad-088].judge_seconds` | 2.1924 | 2.1908 |
| `observations[pcb4 bad-089].areas[0].seconds` | 2.2662 | 2.2758 |
| `observations[pcb4 bad-089].judge_seconds` | 2.4845 | 2.4993 |
| `observations[pcb4 bad-090].areas[0].seconds` | 2.1830 | 2.1865 |
| `observations[pcb4 bad-090].judge_seconds` | 2.3087 | 2.3088 |
| `observations[pcb4 bad-091].areas[0].seconds` | 2.3217 | 2.3407 |
| `observations[pcb4 bad-091].judge_seconds` | 2.3905 | 2.4078 |
| `observations[pcb4 bad-092].areas[0].seconds` | 2.0960 | 2.1069 |
| `observations[pcb4 bad-092].judge_seconds` | 2.1768 | 2.1884 |
| `observations[pcb4 bad-093].areas[0].seconds` | 2.5767 | 2.5787 |
| `observations[pcb4 bad-093].judge_seconds` | 2.6658 | 2.6681 |
| `observations[pcb4 bad-094].areas[0].seconds` | 2.0276 | 2.0346 |
| `observations[pcb4 bad-094].judge_seconds` | 2.0801 | 2.0860 |
| `observations[pcb4 bad-095].areas[0].seconds` | 17.7626 | 17.7614 |
| `observations[pcb4 bad-095].judge_seconds` | 17.8670 | 17.8683 |
| `observations[pcb4 bad-096].areas[0].seconds` | 2.2935 | 2.3008 |
| `observations[pcb4 bad-096].judge_seconds` | 2.3452 | 2.3532 |
| `observations[pcb4 bad-097].areas[0].seconds` | 2.3530 | 2.3533 |
| `observations[pcb4 bad-097].judge_seconds` | 2.4186 | 2.4203 |
| `observations[pcb4 bad-098].areas[0].seconds` | 2.0220 | 2.0279 |
| `observations[pcb4 bad-098].judge_seconds` | 2.0737 | 2.0794 |
| `observations[pcb4 bad-099].areas[0].seconds` | 2.2334 | 2.2304 |
| `observations[pcb4 bad-099].judge_seconds` | 2.3317 | 2.3306 |
| `observations[pcb4 good-0011].areas[0].seconds` | 2.4123 | 2.4079 |
| `observations[pcb4 good-0011].judge_seconds` | 2.4544 | 2.4466 |
| `observations[pcb4 good-0013].judge_seconds` | 0.0003 | 0.0002 |
| `observations[pcb4 good-0016].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0024].judge_seconds` | 0.0004 | 0.0010 |
| `observations[pcb4 good-0026].areas[0].seconds` | 2.2018 | 2.1796 |
| `observations[pcb4 good-0026].judge_seconds` | 2.2551 | 2.2189 |
| `observations[pcb4 good-0027].judge_seconds` | 0.0003 | 0.0003 |
| `observations[pcb4 good-0046].judge_seconds` | 0.0010 | 0.0009 |
| `observations[pcb4 good-0100].judge_seconds` | 0.0003 | 0.0003 |
| `observations[pcb4 good-0107].judge_seconds` | 0.0014 | 0.0014 |
| `observations[pcb4 good-0159].judge_seconds` | 0.0008 | 0.0003 |
| `observations[pcb4 good-0168].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0170].judge_seconds` | 0.0004 | 0.0008 |
| `observations[pcb4 good-0172].judge_seconds` | 0.0009 | 0.0008 |
| `observations[pcb4 good-0174].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb4 good-0178].judge_seconds` | 0.0011 | 0.0012 |
| `observations[pcb4 good-0187].judge_seconds` | 0.0003 | 0.0010 |
| `observations[pcb4 good-0196].judge_seconds` | 0.0005 | 0.0010 |
| `observations[pcb4 good-0208].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0214].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0215].judge_seconds` | 0.0009 | 0.0004 |
| `observations[pcb4 good-0237].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0261].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0286].judge_seconds` | 0.0022 | 0.0011 |
| `observations[pcb4 good-0294].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0297].judge_seconds` | 0.0003 | 0.0003 |
| `observations[pcb4 good-0303].judge_seconds` | 0.0011 | 0.0010 |
| `observations[pcb4 good-0306].judge_seconds` | 0.0011 | 0.0010 |
| `observations[pcb4 good-0320].areas[0].seconds` | 2.1788 | 2.2002 |
| `observations[pcb4 good-0320].judge_seconds` | 2.2218 | 2.2420 |
| `observations[pcb4 good-0333].judge_seconds` | 0.0003 | 0.0002 |
| `observations[pcb4 good-0363].judge_seconds` | 0.0005 | 0.0011 |
| `observations[pcb4 good-0377].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb4 good-0394].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0400].judge_seconds` | 0.0004 | 0.0007 |
| `observations[pcb4 good-0402].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0417].judge_seconds` | 0.0015 | 0.0014 |
| `observations[pcb4 good-0423].areas[0].seconds` | 2.1522 | 2.1518 |
| `observations[pcb4 good-0423].judge_seconds` | 2.2029 | 2.2022 |
| `observations[pcb4 good-0427].judge_seconds` | 0.0003 | 0.0009 |
| `observations[pcb4 good-0457].judge_seconds` | 0.0002 | 0.0002 |
| `observations[pcb4 good-0469].judge_seconds` | 0.0004 | 0.0007 |
| `observations[pcb4 good-0479].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0483].judge_seconds` | 0.0010 | 0.0007 |
| `observations[pcb4 good-0484].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb4 good-0488].judge_seconds` | 0.0003 | 0.0010 |
| `observations[pcb4 good-0490].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb4 good-0514].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0518].judge_seconds` | 0.0007 | 0.0002 |
| `observations[pcb4 good-0520].judge_seconds` | 0.0002 | 0.0003 |
| `observations[pcb4 good-0525].judge_seconds` | 0.0004 | 0.0007 |
| `observations[pcb4 good-0545].judge_seconds` | 0.0003 | 0.0008 |
| `observations[pcb4 good-0552].judge_seconds` | 0.0003 | 0.0009 |
| `observations[pcb4 good-0569].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0615].areas[0].seconds` | 2.1906 | 2.1870 |
| `observations[pcb4 good-0615].judge_seconds` | 2.2336 | 2.2293 |
| `observations[pcb4 good-0617].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0619].judge_seconds` | 0.0004 | 0.0010 |
| `observations[pcb4 good-0621].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0629].judge_seconds` | 0.0008 | 0.0003 |
| `observations[pcb4 good-0631].judge_seconds` | 0.0004 | 0.0007 |
| `observations[pcb4 good-0648].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0654].judge_seconds` | 0.0006 | 0.0007 |
| `observations[pcb4 good-0657].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb4 good-0659].judge_seconds` | 0.0010 | 0.0011 |
| `observations[pcb4 good-0674].judge_seconds` | 0.0006 | 0.0009 |
| `observations[pcb4 good-0684].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0685].judge_seconds` | 0.0004 | 0.0007 |
| `observations[pcb4 good-0688].areas[0].seconds` | 2.0633 | 2.0540 |
| `observations[pcb4 good-0688].judge_seconds` | 2.1060 | 2.0965 |
| `observations[pcb4 good-0690].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb4 good-0694].judge_seconds` | 0.0007 | 0.0002 |
| `observations[pcb4 good-0705].judge_seconds` | 0.0009 | 0.0010 |
| `observations[pcb4 good-0725].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0730].judge_seconds` | 0.0012 | 0.0010 |
| `observations[pcb4 good-0735].judge_seconds` | 0.0003 | 0.0008 |
| `observations[pcb4 good-0739].judge_seconds` | 0.0010 | 0.0011 |
| `observations[pcb4 good-0751].judge_seconds` | 0.0012 | 0.0011 |
| `observations[pcb4 good-0755].judge_seconds` | 0.0003 | 0.0003 |
| `observations[pcb4 good-0764].judge_seconds` | 0.0011 | 0.0010 |
| `observations[pcb4 good-0768].judge_seconds` | 0.0003 | 0.0002 |
| `observations[pcb4 good-0779].judge_seconds` | 0.0006 | 0.0010 |
| `observations[pcb4 good-0784].areas[0].seconds` | 2.0869 | 2.0805 |
| `observations[pcb4 good-0784].judge_seconds` | 2.1288 | 2.1228 |
| `observations[pcb4 good-0796].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb4 good-0797].judge_seconds` | 0.0010 | 0.0011 |
| `observations[pcb4 good-0800].judge_seconds` | 0.0003 | 0.0003 |
| `observations[pcb4 good-0804].judge_seconds` | 0.0003 | 0.0004 |
| `observations[pcb4 good-0811].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb4 good-0844].judge_seconds` | 0.0014 | 0.0013 |
| `observations[pcb4 good-0869].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb4 good-0871].areas[0].seconds` | 2.1757 | 2.1723 |
| `observations[pcb4 good-0871].judge_seconds` | 2.2424 | 2.2399 |
| `observations[pcb4 good-0892].judge_seconds` | 0.0003 | 0.0009 |
| `observations[pcb4 good-0900].judge_seconds` | 0.0011 | 0.0010 |
| `observations[pcb4 good-0920].judge_seconds` | 0.0010 | 0.0010 |
| `observations[pcb4 good-0923].judge_seconds` | 0.0003 | 0.0003 |
| `observations[pcb4 good-0935].judge_seconds` | 0.0013 | 0.0011 |
| `observations[pcb4 good-0940].judge_seconds` | 0.0007 | 0.0003 |
| `observations[pcb4 good-0952].judge_seconds` | 0.0003 | 0.0003 |
| `observations[pcb4 good-0957].judge_seconds` | 0.0011 | 0.0011 |
| `observations[pcb4 good-0964].judge_seconds` | 0.0004 | 0.0010 |
| `observations[pcb4 good-0971].judge_seconds` | 0.0011 | 0.0010 |
| `observations[pcb4 good-0974].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb4 good-0977].judge_seconds` | 0.0013 | 0.0013 |
| `observations[pcb4 good-0990].areas[0].seconds` | 2.1564 | 2.1588 |
| `observations[pcb4 good-0990].judge_seconds` | 2.2021 | 2.2027 |
| `observations[pcb4 good-0994].judge_seconds` | 0.0003 | 0.0009 |
| `observations[pcb4 good-1001].judge_seconds` | 0.0009 | 0.0007 |

## Figure 7: `times`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `times.anomaly_seconds_per_image.pcb1` | 0.0995 | 0.0995 |
| `times.anomaly_seconds_per_image.pcb4` | 0.0899 | 0.0902 |
| `times.flagged_image_seconds.maximum` | 17.9569 | 17.9585 |
| `times.flagged_image_seconds.mean` | 2.5885 | 2.5833 |
| `times.flagged_image_seconds.minimum` | 2.0547 | 2.0648 |
| `times.flagged_image_seconds.p50` | 2.3360 | 2.3301 |
| `times.flagged_image_seconds.p95` | 2.8399 | 2.8394 |
| `times.judge_stage_seconds` | 538.2532 | 537.1209 |
| `times.measure_and_draw_seconds.maximum` | 0.4898 | 0.4567 |
| `times.measure_and_draw_seconds.mean` | 0.0940 | 0.0934 |
| `times.measure_and_draw_seconds.minimum` | 0.0367 | 0.0374 |
| `times.measure_and_draw_seconds.p50` | 0.0649 | 0.0647 |
| `times.measure_and_draw_seconds.p95` | 0.2503 | 0.2502 |
| `times.parse_seconds` | 6.9580 | 11.5578 |
| `times.vlm_seconds_per_area.maximum` | 17.7626 | 17.7614 |
| `times.vlm_seconds_per_area.mean` | 2.3998 | 2.3949 |
| `times.vlm_seconds_per_area.minimum` | 1.9163 | 1.9166 |
| `times.vlm_seconds_per_area.p50` | 2.1612 | 2.1588 |
| `times.vlm_seconds_per_area.p95` | 2.5822 | 2.5819 |
| `times.vlm_seconds_per_flagged_image.maximum` | 17.7626 | 17.7614 |
| `times.vlm_seconds_per_flagged_image.mean` | 2.3998 | 2.3949 |
| `times.vlm_seconds_per_flagged_image.minimum` | 1.9163 | 1.9166 |
| `times.vlm_seconds_per_flagged_image.p50` | 2.1612 | 2.1588 |
| `times.vlm_seconds_per_flagged_image.p95` | 2.5822 | 2.5819 |

## Figure 8: `inspector`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `inspector.minutes_all_parts` | 23.4421 | 23.5187 |
| `inspector.minutes_by_part.pcb1` | 11.7622 | 11.8389 |
| `inspector.minutes_by_part.pcb4` | 11.7958 | 11.8725 |
| `inspector.parse_seconds` | 6.9580 | 11.5578 |

## Figure 9: `judge_memory`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `judge_memory.card_before_mib` | 29784 | 30048 |
| `judge_memory.samples` | 703 | 702 |

## Figures 7 and 9: `runs`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `runs.pcb1.inference_seconds` | 19.8935 | 19.9094 |
| `runs.pcb1.load_seconds` | 2.5406 | 3.0195 |
| `runs.pcb1.memory.card_before_mib` | 1592 | 1594 |
| `runs.pcb1.seconds_per_image` | 0.0995 | 0.0995 |
| `runs.pcb4.inference_seconds` | 18.0650 | 18.1372 |
| `runs.pcb4.load_seconds` | 1.6776 | 2.0689 |
| `runs.pcb4.seconds_per_image` | 0.0899 | 0.0902 |

## How the judge was asked: `judge`

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `judge.cold.server_log.path` | results/stage2/comparison-corrections/bench.server-log.20261107T143502Z.txt | results/stage2/comparison-corrections/bench.server-log.20261107T144630Z.txt |
| `judge.cold.server_log.sha256` | 2ee726a6cdc89344bbe2ea7510322659a4467300cfda33eceb25b27d29a6d681 | 535422143dcad89b2cf3b1b9644a598d944f3924cc2261234ffca8f6800523f7 |
| `judge.warm_up.seconds` | 2.0453 | 2.0044 |

## The specification

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `specification.parse_seconds` | 6.9580 | 11.5578 |

## What the record is made of

| Field | Run 1 | Run 2 |
| --- | --- | --- |
| `measured_at` | 2026-11-07T14:45:08+00:00 | 2026-11-07T14:56:41+00:00 |
| `repeat.areas_compared` | None | 215 |
| `repeat.class_differs` | None | 0 |
| `repeat.figures_equal` | None | True |
| `repeat.flag_differs` | None | 0 |
| `repeat.heading_differs` | None | 0 |
| `repeat.images_compared` | None | 401 |
| `repeat.outcome_differs` | None | 0 |
| `repeat.previous_measured_at` | None | 2026-11-07T14:45:08+00:00 |
| `repeat.score_differs` | None | 0 |
| `repeat.sentence_differs` | None | 0 |
