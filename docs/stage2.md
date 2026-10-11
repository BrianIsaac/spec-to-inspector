# Stage II: the plan on one Intel Arc Pro B70

Stage I was built and measured on a laptop. Stage II moves the same
pipeline to the contest's platform, the ASUS UGen Intel Arc Pro B70 with
32 GB, in the virtual machine the organiser provides.

**Nothing on this page has been run on a B70.** Every memory figure for the
B70 is planned from the vendors' file sizes and the model's configuration,
and is marked as a plan. Every figure marked "measured" was measured on the
laptop and is in `results/stage1/`.

## The assumption about the organiser's VM

The organiser will provide a virtual machine through its SDV system, with
booking opening on 26 October 2026. Its specification is not yet published,
so this plan rests on a stated assumption:

> **One whole Intel Arc Pro B70 (32 GB)**, reached through a booked remote
> session, with no camera or USB device and limited outbound network.

Confidence in that assumption is medium. What changes if it is wrong:

| If the VM is | Then |
| --- | --- |
| more than one card | the stages run side by side instead of taking turns; nothing is lost |
| a share of a card (the B70 supports up to four SR-IOV virtual functions, each well under the whole 32 GB) | the judge drops to a 4-bit build, the stages run strictly in turn, and the relevant clauses are retrieved instead of the whole specification being held in context |
| Windows only | OpenVINO carries both models; PyTorch XPU also runs on Windows 11; the vLLM path, which is a Linux container, is in doubt |
| without containers | the plain `uv` environment and upstream vLLM's XPU build, instead of Intel's llm-scaler image |
| without outbound network | the pinned environment and the weights are carried in; the pipeline needs no network once installed |

The pipeline is batch work over files. It needs no camera and no live feed,
and every step resumes where it stopped, so a booked session is not lost to
a reconnect.

## The memory plan, stage by stage

| Stage | Resident on the card | On the laptop, measured | On the B70, planned |
| --- | --- | --- | --- |
| Parse a born-digital specification | nothing: docling runs on the CPU | 0 GB | 0 GB |
| Parse a scanned specification | PaddleOCR-VL-1.6, 958.6M parameters at FP16 | not built in Stage I | about 2 GB of weights plus its cache; unloaded before training |
| Train the anomaly model | PatchCore: `wide_resnet50_2` features and the memory bank while the coreset is chosen | 7.82 GiB allocated, 8.66 GiB reserved, for 904 images at 256 px | the laptop's figure carried over, in FP32; it scales with the number of training images |
| Score boards | the PatchCore inference model | 0.62 GiB resident, 1.34 GiB peak allocated at batch 16 | 6.4 GB set aside, several times the laptop's need |
| Judge | Qwen3-VL-8B-Instruct and its context cache | 4-bit (Q4_K_M) with a 16K context: 8,780 MiB peak | FP16: 17.53 GB of weights; FP8: 10.59 GB |

The configuration this leads to on one card:

- **Training runs before the judge is loaded.** It is done once per
  specification and its peak is under 9 GiB.
- **Scoring and judging are resident together during a batch.** The judge's
  server takes 80% of the card, 25.6 GB; the remaining 6.4 GB is for the
  anomaly model.
- **Inside the judge's 25.6 GB.** The model's key-value cache costs 147,456
  bytes a token at FP16 (36 layers, 8 key-value heads, head dimension 128),
  so a 32K-token context is 4.83 GB. At FP16 the weights leave about 8 GB of
  cache, about 54,000 tokens: one 32K context with room to spare. At FP8
  they leave about 15 GB, about 100,000 tokens: three 32K contexts. The
  vision encoder's working memory comes out of the same allowance and is not
  yet counted.

Why this needs the 32 GB: on the laptop's 12 GB the judge fits only at
4-bit with a 16K context, and training cannot run while it is loaded. The
demonstration specification is 6 pages and 2,868 tokens, and a prompt with
its clause table and two pictures is about 4,700 tokens, so 16K is enough
for it. A real customer's specification is longer. Holding the whole of one
in context, at full precision, beside the anomaly model, is what the B70's
memory is for. Whether it does so at a useful speed is a Stage II
measurement: no measured figure for a vision-language model on a B70 has
been published by anyone, and this page quotes none.

## The serving stack

| Part | Stage I, the laptop | Stage II, the B70 |
| --- | --- | --- |
| Anomaly model | PatchCore through Anomalib 2.7.0 on PyTorch 2.14 CUDA, full float32 | PatchCore on PyTorch XPU in FP32, or exported to OpenVINO |
| Judge's model | Qwen3-VL-8B-Instruct, Qwen's own 4-bit GGUF with the F16 projector | Qwen3-VL-8B-Instruct at FP16, or Qwen's own FP8 build |
| Judge's server | llama.cpp `llama-server` at tag `v0.6.0`, OpenAI-compatible | Intel's llm-scaler vLLM image at a pinned tag (`0.26.0-b1`, never `latest`) where containers are allowed; upstream vLLM's XPU build otherwise |
| Judge's client | one OpenAI-compatible client, answers constrained to a JSON schema | the same client; the server is two settings, `SPEC_TO_INSPECTOR_VLM_URL` and `SPEC_TO_INSPECTOR_VLM_MODEL` |
| Parser, measurement, rule, corrections, console | CPU, plain Python, one SQLite file, server-rendered pages | unchanged |

Choices made with their reasons:

- **FP16 on llm-scaler.** llm-scaler lists Qwen3-VL-8B-Instruct at FP16, FP8
  and Int4, and its own examples serve at FP16. BF16 with image input has an
  open bug there, so BF16 on upstream vLLM is kept as an alternative to test,
  not the first choice.
- **FP32 for PatchCore.** Its backbone is convolutions, and there is an open,
  unconfirmed report of half-precision convolutions misbehaving on the B70.
  FP32 costs little at this model's size.
- **A pinned image tag.** A later llm-scaler tag has an open regression with
  two cards. A single-card plan does not meet it, but the tag is pinned and
  tested all the same.

What is not yet known and is checked first:

- Whether vLLM or llm-scaler accepts the judge's answer schema, with its
  `pattern` and its nullable `enum`, under its own constrained decoding.
  Only llama.cpp has been run.
- Whether Anomalib's PatchCore runs on the B70 through PyTorch XPU. Anomalib
  2.7.0 has the accelerator and an OpenVINO export; its notes name Arc A-series
  cards, not the B70. The anomaly code in this repository asks for CUDA today.

## What Stage II will measure

Stage II runs from 6 November to 4 December 2026. Each week ends with
figures committed to this repository beside the laptop's.

| Week | Work | Output |
| --- | --- | --- |
| 1, 6 to 12 November: bring-up | Read the card the VM exposes (name, memory, whole card or virtual function). Install the pinned environment. Check PyTorch XPU and OpenVINO. Start the judge's server. | The VM's measured shape; the answer schema accepted or adapted |
| 2, 13 to 19 November: the anomaly model | PatchCore on PyTorch XPU in FP32 and through OpenVINO | Training time, images per second and peak memory, against the laptop's |
| 3, 20 to 26 November: the judge at full precision | Qwen3-VL-8B-Instruct at FP16 and at FP8, with the whole specification in context | Answer time, throughput, and clause-citation accuracy on the same 200 labelled boards the laptop measured at 4-bit |
| 4, 27 November to 4 December: the full run | A whole batch end to end; memory per stage against the plan above; the corrections loop across the batch | The final video recorded from the VM session; the repository with its measured B70 figures |

The laptop's headline is the figure Stage II most needs to move: the
prototype cites the right clause on 52 of 135 single-defect boards (38.5%,
95% interval 30.7% to 46.9%). The anomaly model is not what holds it down:
on 109 of the 135 the most anomalous area lies on the labelled defect. The
judge names the wrong defect class, and the same crops described freely are
described well. Stage II tests three things against that figure, on the
same boards and by the same protocol (`eval/PROTOCOL.md`):

1. **Full precision instead of 4-bit.** The one change the B70's memory buys
   outright. Whether it raises the figure is not known.
2. **A picture of a good board beside the crop.** The judge sees a defect
   with nothing to compare it against. Showing the same place on a good
   board needs the boards registered first, since they wander in the frame;
   that is Stage II work.
3. **The corrections loop, measured.** On the laptop a single correction
   moved the next similar board to the corrected clause in 7 pairs of 7, and
   also moved 14 of 19 boards that were rightly judged before. Stage II
   measures what a store of corrections does to the whole set, in both
   directions.

What we need from the environment: one Arc Pro B70, a Linux or Windows 11
session, and a way to copy files in and out. This plan will be fitted to
the organiser's Computing Platform Guide when it is published.
