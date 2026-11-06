# Stage II: the plan on two Intel Arc Pro B70s

Stage I was built and measured on a laptop. Stage II moves the same
pipeline to the contest's platform, the ASUS UGen Intel Arc Pro B70 with
32 GB, on the bare-metal machine the organiser provides. **The machine is the
subject of Stage II:** every figure the stage rests on is measured there, and is
read against the machine's own baseline run.

**This plan was written before the machine was seen, and was corrected to it
on 7 November 2026.** Every figure marked "on the machine" was measured
there on 6 November, in week 1 or week 2. A file named alone is under
`results/stage2/week1/`; week 2's are given with their whole path, under
`results/stage2/week2/`. Every figure marked "on the laptop" is in
`results/stage1/`. A figure marked as a plan or an estimate has not been
measured. Not yet run on the machine: the judge at FP8, a scanned
specification, the bench on the anomaly models trained there, and the final
run. Nothing on this page is a final figure.

## The machine

Two whole cards in one bare-metal host, read over ssh
(`results/stage2/week1/machine.md`):

| What | On the machine |
| --- | --- |
| Cards | Two Intel Arc Pro B70, physical functions: 4 virtual functions possible, 0 made |
| Memory on each card | 32,656 MiB physical, 31,023 MiB largest allocation; 31.89 GiB through PyTorch |
| Host | Intel Xeon 6787P, 344 threads; 251 GiB of memory, no swap; 867 GB of disk |
| Operating system | Ubuntu 26.04.1 LTS, kernel 7.0.0-34, driver `xe` |
| Containers | Docker 29.8.1 |
| Network | Outbound HTTPS open: the data was fetched there (`raw/data-fetch.txt`) |

Whether it has a camera or a USB device was not read; the pipeline needs
neither.

*Corrected 7 November 2026. The plan had assumed one whole B70 in a virtual
machine, reached through a booked remote session, with no camera or USB
device and limited outbound network, at medium confidence. Its row for "more
than one card" read "the stages run side by side instead of taking turns;
nothing is lost", and that holds.*

The pipeline is batch work over files. It needs no camera and no live feed,
and every step resumes where it stopped, so a session is not lost to a
reconnect.

## The memory plan, stage by stage

| Stage | Card | On the laptop | On the machine |
| --- | --- | --- | --- |
| Parse a born-digital specification | none: docling runs on the CPU | 0 GB | 0 GB (`machine.md`) |
| Parse a scanned specification | 0, in turn | not built in Stage I | a plan, not run: PaddleOCR-VL-1.6, 958.6M parameters at FP16, about 2 GB of weights plus its cache |
| Train the anomaly model | 0 | 7.82 GiB allocated, 8.66 GiB reserved, for 904 images at 256 px | 7.76 to 7.79 GiB allocated, 8.87 to 8.91 GiB reserved by PyTorch's count; 10,345 to 10,785 MiB on the whole card. 8 trainings, each of the four parts twice (`results/stage2/week2/README.md`) |
| Score boards | 0 | 0.62 GiB resident, 1.34 GiB peak allocated at batch 16 | 666 to 669 MB resident. By PyTorch's count, at batch 1: 1.16 to 1.17 GiB allocated, 1.19 GiB reserved; at batch 16: 1.30 to 1.31 GiB, 1.73 GiB. The whole card: 2,899 to 2,963 MiB over both batches, and 4,005 to 4,069 MiB in a scored run in the process that had just trained; 8 each (`results/stage2/week2/README.md`). Week 1's bench, with the laptop's checkpoints, read 2,594 MiB at most at batch 16 (`bench/card-memory.txt`) |
| Judge | 1 | 4-bit (Q4_K_M) with a 16K context: 8,780 MiB peak | FP16 with a 32K context: 17.34 GiB of weights as vLLM loads them, 16.33 GiB on disk; the card at 26,960 MiB once up, 29,456 MiB at most over two bench runs (`machine.md`, `bench/card-memory.txt`). FP8: not run |

The configuration this leads to:

- **A card each.** Card 0 carries the anomaly model and card 1 the judge. The
  judge's container is given only card 1's devices, so it cannot reach card
  0. With the judge on card 1, loading PatchCore on `xpu:0` raised device 0
  from 315 to 1,860 MiB and device 1 did not move (`checks.json`). Training
  need not come before the judge is loaded: the two never share a card. Week 2
  ran that way, with the judge's server up on card 1: from run 1's second part
  on, card 1 stayed at 29,455.73 to 29,455.77 MiB over 1,830 readings every 5 s
  (`results/stage2/week2/raw/cards-every-5s.txt`).
- **The judge's server takes 90% of its card** (`--gpu-memory-util=0.9`). At
  80% FP16 leaves 2.97 GiB of cache and vLLM refuses a 32K context, which
  asks 4.5 GiB; its largest would be 21,568 tokens
  (`raw/serve-fp16-util-0.8-refused.txt`). At 90% it leaves 6.16 GiB, 44,800
  tokens, 1.37 times a 32K context
  (`raw/serve-fp16-util-0.9-cold-final.txt`).
- **Inside the judge's share.** The key-value cache costs 147,456 bytes a
  token at FP16 (36 layers, 8 key-value heads, head dimension 128), so a
  32K-token context is 4.83 GB; that is vLLM's 4.5 GiB exactly. The cache
  comes out 5.2 GiB under the share less the weights, at both shares (0.8 x
  31.89 - 17.34 = 8.17 GiB against 2.97; 0.9 x 31.89 - 17.34 = 11.36 against
  6.16; `machine.md`). vLLM's line at start-up divides it into 3.0 GiB of peak
  activation and 2.2 GiB of non-torch memory
  (`raw/serve-fp16-util-0.9-cold-final.txt`); how much of that is the vision
  encoder was not measured.
- **FP8 is an estimate.** It has not been run. If the 5.2 GiB measured at FP16
  holds at FP8, its 10.59 GB of weights leave about 13 GiB of cache at 90%,
  close to three 32K contexts, and about 10 GiB at 80%, about two
  (`machine.md`).

*Corrected 7 November 2026. The plan had assumed one shared card: training
before the judge was loaded; the judge's server at 80%, 25.6 GB, beside 6.4
GB for the anomaly model; at FP16, 17.53 GB of weights (the same 16.33 GiB in
other units) leaving about 8 GB of cache, about 54,000 tokens, one 32K context
with room to spare; at FP8 about 15 GB, about 100,000 tokens, three 32K
contexts; the vision encoder's working memory not yet counted.*

*Corrected 7 November 2026, from week 2's record. The plan had said of training
"the laptop's figure carried over" and "its peak is under 9 GiB", and of scoring
"6.4 GB set aside, several times the laptop's need". PyTorch's count did carry
over; the whole card holds up to 10,785 MiB in training, and scoring takes at most
4,069 MiB on PyTorch XPU. Through OpenVINO at batch 16 it takes 18,153 to 18,400
MiB, which 6.4 GB would not have held.*

Why this needs the 32 GB: on the laptop's 12 GB the judge fits only at
4-bit with a 16K context, and training cannot run while it is loaded. The
demonstration specification is 6 pages and 2,868 tokens, and a prompt with
its clause table and two pictures is about 4,700 tokens (median 4,682 over
the bench, `bench/bench.json`), so 16K is enough for it. A real customer's
specification is longer. Holding the whole of one in context, at full
precision, with a card beside the anomaly model's, is what the machine's
memory is for. Whether it does so at a useful speed has one first reading,
with the demonstration specification only: asked cold at FP16 a question takes
a median of 2.13 s and a 95th percentile of 2.56 s
(`results/stage2/week1/README.md`). The plan found no published measured figure
for a vision-language model on a B70, and this page quotes none but its own.

## The serving stack

| Part | Stage I, the laptop | Stage II, the machine |
| --- | --- | --- |
| Anomaly model | PatchCore through Anomalib 2.7.0 on PyTorch 2.14 CUDA, full float32 | PatchCore through Anomalib 2.7.0 on PyTorch 2.14.1 XPU in FP32, trained and scored on card 0: the path on this machine (`results/stage2/week2/README.md`). Week 1's bench ran the laptop's checkpoints; the final run uses the models trained on the machine. Through OpenVINO 2026.4.1 it was exported and measured, and nothing in the pipeline runs through it |
| Judge's model | Qwen3-VL-8B-Instruct, Qwen's own 4-bit GGUF with the F16 projector | Qwen3-VL-8B-Instruct at FP16; Qwen's own FP8 build not yet run |
| Judge's server | llama.cpp `llama-server` at tag `v0.6.0`, OpenAI-compatible | Intel's llm-scaler vLLM image at a pinned tag (`0.26.0-b1`, never `latest`; digest in `machine.md`), vLLM 0.26.1.dev0, on card 1 |
| Judge's client | one OpenAI-compatible client, answers constrained to a JSON schema | the same client, by two settings, `SPEC_TO_INSPECTOR_VLM_URL` and `SPEC_TO_INSPECTOR_VLM_MODEL`, whose defaults already fit |
| Parser, measurement, rule, corrections, console | CPU, plain Python, one SQLite file, server-rendered pages | unchanged |

Two settings move the client. The server needs two more of its own, or it is not
the pipeline the protocol declares, and both are defaults of
`scripts/serve_vlm_xpu.sh`:

- **Asked cold.** vLLM ignores `cache_prompt`, llama.cpp's own switch, and says
  nothing: left to its defaults the prefix cache reached a 92.4% hit rate and a
  0.11 s first token (`raw/serve-fp16-util-0.9-prefix-cache-on.txt`,
  `judge-schema-prefix-cache-on.json`). The server starts with
  `--no-enable-prefix-caching --mm-processor-cache-gb 0`.
- **The laptop's image size.** vLLM's default gives a small crop 64 tokens
  against the laptop's 1,024. `--mm-processor-kwargs` sets `shortest_edge` to
  1,048,576 pixels, and on the three boards of the schema check the prompt
  tokens are the laptop's: 4,591, 4,579, 4,574 (`judge-schema.json`). Whether
  the two resizes give the same pixels was not measured.

*Corrected 7 November 2026. The plan had said of the judge's client "the same
client; the server is two settings".*

*Corrected 7 November 2026, from week 2's record. The plan had given the anomaly
model as "PatchCore on PyTorch XPU in FP32, or exported to OpenVINO", which reads
as a free choice. They agree in scores and are not equal in speed or memory:
OpenVINO, exported and run as week 2 ran it, is at about half PyTorch XPU's speed
and, at batch 16, about six times its memory on the card.*

Choices made with their reasons:

- **FP16 on llm-scaler.** llm-scaler lists Qwen3-VL-8B-Instruct at FP16, FP8
  and Int4, and its own examples serve at FP16. BF16 with image input has an
  open bug there, so BF16 on upstream vLLM is kept as an alternative to test,
  not the first choice. The weights are BF16 on disk and vLLM casts them
  (`machine.md`).
- **FP32 for PatchCore.** Its backbone is convolutions, and there is an open,
  unconfirmed report of half-precision convolutions misbehaving on the B70.
  On PyTorch FP32 costs little at this model's size. Through OpenVINO it has to
  be asked for: the plugin infers in FP16 unasked, though the weights are FP32,
  so `anomaly/ov_model.py` asks for FP32, reads it back and refuses otherwise
  (`results/stage2/week2/README.md`). Over 401 boards, the laptop's
  checkpoints on XPU against the same checkpoints on CUDA: 0 differ in being
  flagged, 0 in their number of regions, and the largest score difference is
  0.00053 (`results/stage2/week1/README.md`). That is inference alone. A model
  trained on the machine is not the laptop's bank for bank, and on a handful of
  boards its scores move further; week 2's record gives how far, part by part.
  On the machine itself the training repeats: two runs give identical banks, and
  scores and maps bit-identical over 802 boards.
- **A pinned image tag.** A later llm-scaler tag has an open regression with
  two cards. The machine has two, the container is given one, and no later
  tag has been run, so the tag stays pinned. *Corrected 7 November 2026. The
  plan had said a single-card plan does not meet the regression.*

What week 1 answered (`results/stage2/week1/README.md`):

- **vLLM accepts the judge's answer schema**, its `pattern` and its nullable
  `enum` both, under its own constrained decoding, with one fix to the schema:
  the reason's pattern allowed a double quote, and on pcb1's `bad-085` the model
  wrote the other two fields inside the string. It now bars `"` and `\`.
- **Anomalib's PatchCore runs on the B70 through PyTorch XPU**, for inference on
  the laptop's checkpoints. The anomaly code no longer asks for CUDA alone: the
  device is the setting `SPEC_TO_INSPECTOR_DEVICE`, `cuda` by default, `xpu` or
  `cpu`.

What week 2 answered (`results/stage2/week2/README.md`), on card 0, each of the
four parts in two runs, one seed, on the VisA test split the thresholds were chosen
on:

- **PatchCore trains on the B70 through PyTorch XPU**, on a whole part: a fit takes
  692.7 to 703.5 s over 8 trainings, about 98% of it the coreset (680 to 691 s), the
  embedding 3.96 to 4.37 s.
- **It scores through PyTorch XPU** at 29.61 to 30.04 images a second at batch 1 and
  34.69 to 35.22 at batch 16, the model alone; from the files, 25.93 to 26.36 and
  29.46 to 30.42. Each range is over 8 figures of 3 timed passes.
- **Anomalib's OpenVINO export runs on the B70, on `GPU.0` in FP32, and not as it
  comes.** Scores are within 0.00041 of PyTorch XPU's. It runs at 14.28 to 16.22
  images a second at batch 1 and 16.20 to 18.69 at batch 16, the model alone, and
  holds 2,700 to 2,943 MiB of the card at batch 1 and 18,153 to 18,400 MiB at batch
  16. Anomalib's `openvino` extra cannot be installed: it lists `nncf`, every release
  of which caps numpy below 2.5, and the project's is 2.5.3. Only its INT8 compression
  imports `nncf`, and no INT8 figure is measured. Three of its defaults would have
  given wrong figures or none: the export normalises and clips the score, so it is
  switched off in the exported copy; its dynamic batch comes out fixed at 2, so there
  is one graph per batch size; and its downgrade to opset 14 fails, so it stays at 18.
- **So PyTorch XPU is the anomaly model's path on this machine.** Nothing in the
  pipeline runs through OpenVINO.

*Corrected 7 November 2026, from week 2's record. The plan had said "Anomalib 2.7.0
has the accelerator and an OpenVINO export", and named the export's running as not
yet known.*

What is not yet known:

- What the final run reads. It has not been run.
- How the bench runs on the models trained on the machine. `eval/clause_labels.csv`
  holds what each board's region 1 lies on, made from the laptop's models, and the
  bench stops if a model's regions disagree. Checked against each model, the models
  trained on the machine stop on PCB1 `bad-029`, one of the 135
  (`results/stage2/week2/label-region-columns.json`). It is the one board of its part
  that sits on the threshold: Anomalib's adaptive threshold is set at a board's score,
  the rule is a strict `>`, and floating-point noise decides such a board on any
  device. One board a part sits there. How this is settled is open, and no final run
  comes before it is.
- What FP8 does, and what a specification much longer than the demonstration's
  does, to memory and to speed: week 3.
- Why OpenVINO holds 18 GiB at batch 16, why it runs at about half PyTorch XPU's speed,
  and why its speed differs by part. Each is measured and not explained, and no
  OpenVINO setting but the precision was tried. The plugin's FP16 and Anomalib's
  compressions are offered and not measured.
- What Anomalib's coreset selection costs by synchronising the XPU at every pick, on
  which most of a training is spent.

## What Stage II will measure

Stage II runs from 6 November to 4 December 2026, when the video is due. The
machine does not: its reservation ends 2 December 2026 at 11:30, as the billing
tab prints it, with no time zone shown. Each week ends with figures committed to
this repository, measured on the machine.

| Week | Work | Output |
| --- | --- | --- |
| 1, 6 to 12 November: bring-up | Read the cards the machine exposes (name, memory, whole card or virtual function). Install the pinned environment. Check PyTorch XPU and OpenVINO. Start the judge's server. | Done on 6 November, `results/stage2/week1/`: the machine's measured shape; the answer schema accepted with one fix |
| 2, 13 to 19 November: the anomaly model | PatchCore on PyTorch XPU in FP32 and through OpenVINO | Done on 6 November UTC, ahead of its week, `results/stage2/week2/`: training time, images per second and peak memory on the machine, on all four parts, in two runs |
| 3, 20 to 26 November: the judge at full precision | Qwen3-VL-8B-Instruct at FP16 and at FP8, with the whole specification in context | Answer time, throughput, and clause-citation accuracy on the 200 labelled boards, under the protocol: FP16 as the final setting, FP8 as a declared comparison |
| 4, 27 November to 4 December: the full run | A whole batch end to end; memory per stage against the plan above; the corrections loop across the batch | The final video recorded from a session on the machine; the repository with its measured B70 figures |

What the end of the reservation does to week 4: of its eight days, about five
and a half have the machine. The whole batch, the memory per stage, the
corrections loop and the recording of the final video all have to be done before
2 December at 11:30, with everything copied off by then. After that the week has
no machine: what is left of it can only work from what was copied. The weeks are
not re-planned here; that is the owner's.

**The baseline.** What Stage II rests on is a final run on the machine under
`eval/PROTOCOL-stage2.md`, in force since 7 November 2026: one setting declared
before the run, FP16, with the anomaly models trained on the machine and an empty
corrections store, reported whatever it reads. Three runs make it final, the third
after a server restart. It has not been run yet, and "What is not yet known" above
says what comes first.

Week 1's bench on the machine is a bring-up figure, never final: 34.1% strict (46
of 135, 95% interval 26.6% to 42.4%) and lenient 70.8% (46 of 65, 58.8% to 80.4%),
with the laptop's anomaly checkpoints (`results/stage2/week1/README.md`). The
anomaly model is not what holds it down: on 109 of the 135 the most anomalous area
lies on the labelled defect. The judge names the wrong defect class; asked simply
to describe four of the crops, on the laptop, it was right about what is in them.

**Stage I is history.** On a laptop, at 4-bit, under another server and an older
answer pattern, the prototype cited the right clause on 52 of 135 single-defect
boards (38.5%, 95% interval 30.7% to 46.9%). It is not re-run, nothing here says the
machine beat it or lost to it, and the experiment that would separate those
differences is not run, so no figure separates them.

Stage II tests three things on the machine, against the machine's baseline, on the
same boards. A figure is said to have moved only on a paired, two-sided exact sign
test below 0.05 on the 135; the lenient figure is reported under its own name and
never pooled.

1. **Full precision.** The baseline is FP16. FP8, Qwen's own build, is a comparison
   declared in the protocol, two runs in files of its own, beside two others: the
   model's own image minimum, and designators let through the digit ban.
2. **A picture of a good board beside the crop.** The judge sees a defect
   with nothing to compare it against. Showing the same place on a good
   board needs the boards registered first, since they wander in the frame;
   that is Stage II work. It changes the pipeline, so it gets its own dated
   addition to the protocol when it is built.
3. **The corrections loop, measured.** On the laptop a single correction
   moved the next similar board to the corrected clause in 7 pairs of 7, and
   also moved 14 of 19 boards that were rightly judged before. Stage II
   measures what a store of corrections does to the whole set, in both
   directions, by a dated addition of its own; the store stays empty in the
   baseline.

*Corrected 7 November 2026. The plan had set these three against the laptop's
headline, as "the figure Stage II most needs to move", and had called full precision
"the one change the B70's memory buys outright", saying "whether it raises the
figure is not known". The owner ruled that the machine is the subject, and the
organiser's rules ask for no comparison with a team's own hardware.*

What the plan asked of the environment, one Arc Pro B70, a Linux or Windows 11
session and a way to copy files in and out, the machine gives. Intel's user
guide for the instance is published; its commands are for Ubuntu 24.04, and the
machine is on 26.04.1.
