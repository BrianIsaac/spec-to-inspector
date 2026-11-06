# Stage II week 2: PatchCore on the B70, beside the laptop's figures

Measured on 6 November 2026, 17:05 to 19:55 UTC, on card 0 of the machine in
`../week1/machine.md`, under `ZE_AFFINITY_MASK=0`, with the judge's server running on card 1. The
laptop's figures are `results/stage1/anomaly.json`. Written by hand from the records beside this
page. Stage I's settings throughout: `wide_resnet50_2`, 256 px, 10% coreset, seed 0, FP32, training
and evaluation batches of 32, 8 loader workers.

**Read this as: PyTorch XPU is the anomaly model's path on this machine.** It scores 1.3 to 1.4 times
as fast as the laptop, trains about 4% faster, and gives the laptop's model but for a few patches.
OpenVINO, exported and run as below, gives the same scores to 0.0004, at about half PyTorch XPU's
speed and, at batch 16, about six times its memory on the card.

## The table

| Figure | Laptop, CUDA | B70, PyTorch XPU | B70, OpenVINO on `GPU.0`, FP32 |
| --- | --- | --- | --- |
| Command, below | A | B | C |
| Training, whole fit | 722 to 734 s; 8 trainings, each part twice | **693 to 704 s**; 8 trainings, each part twice; run 1 697 to 704, run 2 693 to 699 | Not measured: nothing trains through OpenVINO. Its model is PyTorch XPU's |
| of which embedding | 4.47 to 4.94 s; 4 | 3.96 to 4.37 s; 8 | |
| of which coreset | 707 to 711 s; 4 | 680 to 691 s; 8 | |
| Export, then compile | | | Batch 16: 12.0 to 15.2 s, then 32.7 to 33.8 s. Batch 1: 10.1 to 10.7 s, then 5.1 to 6.1 s; 8 each |
| Peak in training, PyTorch's count: allocated, reserved | 7.79 to 7.82 GiB, 8.63 to 8.66 GiB; 4 | 7.76 to 7.79 GiB, 8.87 to 8.91 GiB; 8, equal between runs | Not measured: no training |
| Peak in training, the whole card | Not measured: Stage I did not sample during training | **10,345 to 10,785 MiB**; 8, within 2 MiB between runs | Not measured: no training, and the export runs on the CPU |
| Images a second, the model alone, batch 1 | 21.56 to 21.74; passes 21.51 to 21.83 | **29.61 to 30.04**; passes 29.59 to 30.10 | 14.28 to 16.22; passes 14.27 to 16.31 |
| The same, batch 16 | 23.53 to 25.11; passes 23.45 to 25.12 | **34.69 to 35.22**; passes 34.68 to 35.22 | 16.20 to 18.69; passes 16.18 to 18.75 |
| Images a second, from the files, batch 1 | 20.35 to 20.58; passes 20.01 to 20.59 | **25.93 to 26.36**; passes 25.83 to 26.51 | 13.39 to 15.26; passes 13.36 to 15.30 |
| The same, batch 16 | 22.35 to 22.86; passes 21.84 to 22.87 | **29.46 to 30.42**; passes 29.40 to 30.44 | 14.99 to 17.26; passes 14.96 to 17.37 |
| A whole scored run, files written, batch 16 | 17.0 to 18.8 s; 4 | 17.15 to 19.38 s; 8 | 22.71 to 24.31 s; 8 |
| Peak scoring, PyTorch's count, batch 1: allocated, reserved | 1.19 to 1.20 GiB, 1.60 to 1.71 GiB; 4 | 1.16 to 1.17 GiB, 1.19 GiB; 8 | Not measured: the plugin keeps no such counter |
| The same, batch 16 | 1.33 to 1.34 GiB, 1.60 to 1.70 GiB; 4 | 1.30 to 1.31 GiB, 1.73 GiB; 8 | Not measured, as above |
| Peak scoring, the whole card | Not measured alone: the laptop's card also held the judge. The process, PCB1 and PCB4: 1,848 to 2,028 MiB | 2,899 to 2,963 MiB over both batches; 4,005 to 4,069 MiB in the scored run, in the process that had just trained; 8 each | **Batch 16: 18,153 to 18,400 MiB. Batch 1: 2,700 to 2,943 MiB**; 8 each |
| Weights on the card | 666 to 669 MB; 4 | The same; 8 | 667 to 669 MB of `.bin`; 8 |
| First use before any clock | Not measured | 5.34 to 5.42 s, then 2.66 to 2.70 s on a second pass; 2 of each, whole warm-up | First request 1.10 to 1.49 s at batch 16, 0.43 to 0.46 s at batch 1; 8 each |
| Largest score difference, over each part | The reference | From the laptop's: 1.03368, 0.02856, 0.00018, 0.00052 | From PyTorch XPU's: 0.00041, 0.00027, 0.00033, 0.00040 |
| Median score difference, over the parts | The reference | 0.000034 to 0.000042 | 0.000053 to 0.000069 |
| Flagged boards: PCB1, PCB2, PCB3, PCB4 | 110, 104, 105, 106 | 111, 104, 105, 106 | 110, 104, 105, 107 |
| Image AUROC of the scored run, in points | 92.97, 92.33, 92.08, 98.71 | 93.05, 92.32, 92.08, 98.71 | 93.05, 92.33, 92.08, 98.71 |
| The same run repeated | Thresholds, AUROC, flags and regions all equal on all 4 parts | **Scores and maps bit-identical**, memory banks identical, 802 boards | **Scores and maps bit-identical**, 802 boards |

A range is over the four parts and, on the B70, both runs. "Passes" is every timed pass behind it:
3 a figure, on each part's test split of 200 or 201 boards. Figures for the laptop's inference are
one run; the B70's are two.

**A.** Stage I: `uv run spec-to-inspector train --all --bench --results results/stage1/anomaly.json`,
then `--reuse`. The second trainings: `train --category pcb1 --category pcb4` on 10 October and
`train --category pcb2 --category pcb3` on 7 November, the latter beside other work on the laptop
(`laptop/second-training.json`).

**B.** `ZE_AFFINITY_MASK=0 .venv/bin/python -m spec_to_inspector.anomaly.card_run pytorch --root
~/week2/run-N`, N = 1 and 2 (`run-N/anomaly.json`, in the laptop's layout, and
`run-N/card-pytorch.json`).

**C.** `ZE_AFFINITY_MASK=0 .venv/bin/python -m spec_to_inspector.anomaly.card_run openvino --root
~/week2/run-N` (`run-N/card-openvino.json`, `run-N/openvino-bench-<part>.json`). Each run exports
its own trained model.

Three things to hold beside the columns:

- **"The model alone" is not quite the same clock.** PyTorch's batches are on the card before the
  clock starts; OpenVINO's are copied from the host inside it. "From the files" is like for like.
- **OpenVINO's graph takes one batch size,** so a short last batch is filled out: a pass at batch 16
  computes 208 images to answer 200 or 201, up to 4% more than PyTorch's. It does not close the gap.
- **The harness itself did not change a figure.** B has a warm-up and reads `xpu-smi` every half
  second; the laptop's command has neither. That command on PCB4 here (`plain/anomaly.json`) fits in
  699.0 s against 700.8 and 697.6, at 29.77, 34.70, 26.30 and 30.06 images a second. Its embedding
  takes 4.87 s against 3.98 and 3.96, which is what first use costs a training.

## What training on XPU does

Week 1 found the largest difference 0.00053 with the laptop's checkpoints scored on XPU. **That
holds on all four parts, and training on XPU adds to it on three of them, on a handful of boards.**

| Compared, largest score difference | PCB1 | PCB2 | PCB3 | PCB4 |
| --- | --- | --- | --- | --- |
| Inference only: the laptop's checkpoints, CUDA against XPU | 0.00023 | 0.00031 | 0.00021 | 0.00053 |
| Training only: the laptop's checkpoints against XPU-trained, both on XPU | 1.03367 | 0.02856 | 0.00015 | 0.00020 |
| Largest difference in any anomaly map, training only | 6.89 | 4.52 | 0.00021 | 3.84 |
| Boards moved more than 0.001 by training | 11 of 200 | 3 of 200 | 0 of 201 | 0 of 201 |
| Bank rows found in the laptop's bank | 89,182 of 92,569 | 91,984 of 92,262 | 92,672 of 92,672 | 92,499 of 92,569 |
| Coreset picks in step before the first difference | 794 | 1,101 | 814 | 1,245 |

- **Mechanism, measured as far as this:** the two selections start from the same pick and agree for
  about a thousand picks of 92,000. Then they part, and mostly go on to choose the same patches in
  another order: the rows found in the other bank differ by about 0.0001. PCB3 ends with every row
  the same; PCB1 ends 3,387 rows different, some of them 25 away. That a near-tie in a float32
  distance is what first parts them is a reading, not measured.
- Thresholds move by at most 0.00005, against values near 30. PCB1's AUROC moves by 0.08 points and
  PCB2's by 0.01, and no flag moves but the threshold board's below.
- It is the device and not the run: two trainings on XPU give identical banks, as two on CUDA give
  identical thresholds.

## The board on the threshold

Every board whose flag differs anywhere above is the one board of its part that sits on the
threshold. Anomalib's adaptive threshold is set at a board's score, and the rule is a strict `>`.

| Part | Board | Next nearest board | Where its flag differs |
| --- | --- | --- | --- |
| PCB1 | `bad-029`, score equal to the threshold on the laptop | 0.0149 away | Flagged only as trained and scored on XPU, 0.0000019 above; not through OpenVINO, 0.000023 below |
| PCB2 | `bad-060`, equal | 0.0345 away | Nowhere |
| PCB3 | `bad-097`, 0.00003 away | 0.0094 away | Nowhere |
| PCB4 | `bad-081`, equal | 0.125 away | Flagged only through OpenVINO, 0.000017 above |

So these two flips say nothing of either path: floating-point noise decides such a board on any
device. Both are defective boards, and a flip costs a false pass or gains a judged area on one board
a part. `boards.csv` has every board's score, flag and regions in all six runs.

**This reaches the bench.** `eval/clause_labels.csv` holds what each board's region 1 lies on, made
from the laptop's model, and the bench stops if a model's regions disagree. Checked against each
model (`label-region-columns.json`): the laptop's checkpoints on XPU pass, XPU-trained stop on PCB1
`bad-029`, and OpenVINO on PCB4 `bad-081`. PCB1 `bad-029` is one of the 135 single-defect boards.

## The OpenVINO path, and what it needed

OpenVINO 2026.4.1 with `onnx` 1.23.2, `onnx-ir` 1.1.0, `onnxscript` 0.7.2 and `ml-dtypes` 0.6.0,
added to the `xpu` group. **`nncf` is not: the brief named it, and it cannot be installed.** Every
release caps numpy below 2.5 and the project's numpy is 2.5.3, shared with the laptop. Only Anomalib's
INT8 compression imports it, and FP32 and FP16 do not need it. `raw/environment.txt` has the proof
that the laptop's environment is unchanged: `uv export --frozen` byte-identical, 185 packages.

Anomalib's defaults would have given wrong figures here, quietly in two cases. All four are handled
in `anomaly/ov_model.py`:

| The default | What it does | Done instead |
| --- | --- | --- |
| The plugin's precision | **Infers in FP16** though the weights are FP32: its `INFERENCE_PRECISION_HINT` reads `f16` unasked | Asks for `f32`, reads it back, refuses otherwise. Also refuses FP16 weights |
| The post-processor in the export | Normalises and clips the score and the map; every threshold downstream is raw | Switched off in the exported copy |
| A dynamic batch | Comes out fixed at 2, by PatchCore's chunk loop | One graph per batch size, named |
| Opset 14 | A downgrade from 18 fails and prints a traceback | Opset 18 |

**Other precisions.** Measured: FP32 only. Offered, not measured: the plugin's FP16, and Anomalib's
`FP16`, `INT8`, `INT8_PTQ` and `INT8_ACQ` compressions, the last three of which need `nncf`.

`GPU.0` names the card under the mask, though OpenVINO then lists only `CPU` and `GPU`. Card 1 did
not move: 29,455.73 to 29,455.77 MiB over 1,830 readings every 5 s through all of it
(`raw/cards-every-5s.txt`, from run 1's second part on).

**Not explained, only measured:**

- **Why OpenVINO holds 18 GiB at batch 16.** About 1 GiB for each image over one, by subtraction,
  which would fit each unrolled chunk of the search keeping its own working matrices. Not looked into.
- **Why it runs at half PyTorch's speed.** Batch 16 gains it about what it gains PyTorch, about 15%.
  Not looked into, and no OpenVINO setting but the precision was tried.
- **Why its speed differs by part** (PCB3 fastest, PCB4 slowest, about 14% apart) in the same order
  in both runs, with banks within 0.5% of one size, while PyTorch's stays within 2%.

Its card figure climbs by about 80 MiB with each part in the one process, so each range's low end
is the first part and is the cleaner figure.

## The memory reader, on the machine

`bench` and `judge.timing` now fill the fields that were null in week 1, shown on a trial of 12
boards and two questions (`reader/`, not figures of anything else): the anomaly stage's process
2,549 to 2,552 MiB and card 2,591 to 2,596 MiB, and the judge's card 29,456 MiB. The judge's own process is
still null: `xpu-smi ps` does not list a process in a container, even under `sudo`, and `ss` does not
show its pid unprivileged. `pytest -m xpu` on the machine: 7 passed, twice over at the tip
(`raw/pytest-xpu.txt`).

## Limits

- One machine, one card, one seed, on the VisA test split the thresholds were chosen on.
- Speed is of this card on this model; nothing here is a general figure for the B70.
- Card peaks are `xpu-smi` every half second, so a spike shorter than that is missed. PyTorch's
  counters are exact for what they count. The gap between them on training, 1.2 to 1.7 GiB, was not
  divided up; after `empty_cache` a busy process was seen to keep about 2 GiB in the driver's pool.
- About 98% of training is the coreset, and the card's rate there (135 picks a second) is about the
  laptop's (130). Anomalib's selection synchronises the XPU at every pick, by its source; what that
  costs was not measured.
