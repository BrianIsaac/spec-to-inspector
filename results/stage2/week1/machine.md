# The Stage II machine, measured

Read on 6 November 2026, 15:05 to 16:15 UTC (23:05 to 00:15 SGT), over `ssh asus-b70`. The whole
output of every command in the first table is in `raw/shape.txt`, in the order they ran.

## The shape

| What | Measured | Command |
| --- | --- | --- |
| Cards | Two Intel Arc Pro B70 Graphics, devices 0 and 1, state normal | `xpu-smi discovery` |
| Card 0 | PCI `0000:17:00.0`, `/dev/dri/card1`, render node `renderD128`, function type physical | `xpu-smi discovery`, `ls -la /dev/dri/by-path` |
| Card 1 | PCI `0000:ba:00.0`, `/dev/dri/card2`, render node `renderD129`, function type physical | the same |
| Whole cards or shares | Whole: 4 virtual functions possible, 0 made | `cat /sys/class/drm/card1/device/sriov_numvfs sriov_totalvfs` |
| PCI id | `8086:e223`, Battlemage G31, subsystem `8086:1701`, SKU type "Production ES", stepping A0 | `xpu-smi discovery -d 0`, `-d 1`, `lspci -nnk` |
| Memory on each card | 32,656 MiB physical, 31,023 MiB largest allocation | `xpu-smi discovery -d 0`, `-d 1` |
| The same through PyTorch | 34,242,297,856 bytes (31.89 GiB) on each | `torch.xpu.mem_get_info`, `checks.json` |
| The same through OpenCL | 32,530,182,144 bytes (30.3 GiB) global and largest allocation | `clinfo` |
| Execution units | 256, 8 slices, 4 sub-slices per slice, 8 threads per EU, SIMD 16, 2,800 MHz | `xpu-smi discovery -d 0` |
| ECC | Disabled | `xpu-smi discovery -d 0` |
| Double precision | Yes (`has_fp64`), and FP16 | `torch.xpu.get_device_capability(0)` |
| Kernel | `7.0.0-34-generic`, driver `xe` | `uname -a`, `lspci -nnk` |
| Operating system | Ubuntu 26.04.1 LTS | `cat /etc/os-release` |
| Driver, as `xpu-smi` names it | 17012470; firmware version empty, status normal | `xpu-smi discovery -d 0` |
| Compute runtime | 26.22.38646.7 (`intel-opencl-icd`, `libze-intel-gpu1`, `intel-ocloc`); `1.15.38646+7` as Level Zero reports it | `dpkg -l`, `clinfo`, `checks.json` |
| Level Zero loader | 1.28.6 (`libze1`) | `dpkg -l` |
| Graphics compiler | `libigc2` 2.36.5 | `dpkg -l` |
| `xpu-smi` | 2.0.0 | `dpkg -l` |
| `clinfo` platforms | Intel OpenCL Graphics with both cards; Intel OpenCL with the Xeon | `clinfo -l` |
| Processor | Intel Xeon 6787P: 2 sockets, 86 cores each, 344 threads, 4 NUMA nodes | `lscpu` |
| Memory | 251 GiB, no swap | `free -h` |
| Disk | 867 GB on `/`, 819 GB free when first read | `df -h /` |
| Containers | Docker 29.8.1, user in the `docker` and `render` groups | `docker --version`, `id` |
| System Python | 3.14.4 | `python3 --version` |

`xpu-smi discovery -d` also prints `DMI reader failed ... Cannot access DMI tables` on each card,
and PCIe generation and width as N/A. Neither was looked into: nothing here depends on them.

### Which card is which, measured

`xpu-smi`'s numbering, PyTorch's and the card the judge is mapped to agree, and this was measured,
not assumed. With the judge's server on PCI `0000:ba:00.0`, `xpu-smi` shows it on device 1. With
PatchCore loaded on `xpu:0`, device 0 rose from 315 to 1,860 MiB and device 1 did not move (27,233
MiB before and after; `checks.json`).

## Two cards against the plan's one

`docs/stage2.md` assumed one whole card and marked that "medium". The machine has two whole cards
in one bare-metal host, not a virtual machine and not a booked session. Its own table says of this
case "the stages run side by side instead of taking turns; nothing is lost", and that holds. Card 0
carries the anomaly model and card 1 the judge. The judge's container is given only card 1's
devices, unprivileged, so it cannot reach card 0.

## The plan's memory table, with a card each

Measured here unless marked. "Plan" is what `docs/stage2.md` says.

| Stage | Card | Plan, on one shared card | With a card each |
| --- | --- | --- | --- |
| Parse a born-digital specification | none | 0 GB | 0 GB: docling on the CPU, 6.9 s and 13.2 s in the two bench runs |
| Parse a scanned specification | 0, in turn | about 2 GB | not run; still planned |
| Train the anomaly model | 0 | under 9 GiB, before the judge is loaded, as the laptop's 7.82 GiB allocated | not yet measured, week 2. It need no longer come before the judge: the two never share a card |
| Score boards | 0 | 6.4 GB set aside | 668 MB resident, 1.17 GiB peak allocated, 1.27 GiB peak reserved at batch 1; the card at 2,594 MiB at most while scoring at batch 16. The card's 32 GB is far more than it needs |
| Judge: the server's share | 1 | 80% of the card, 25.6 GB | **90%**: at 80% vLLM refuses a 32K context (below) |
| Judge: weights | 1 | FP16 17.53 GB | 17.34 GiB as vLLM loads it; 16.33 GiB on disk |
| Judge: left for its cache at FP16 | 1 | "about 8 GB", "about 54,000 tokens" at 80% | **2.97 GiB at 80%, 6.16 GiB and 44,800 tokens at 90%** |
| Judge: the card while answering | 1 | not given | 26,960 MiB once up; at most 29,456 MiB over two bench runs, with 1,024-token images |
| Judge at FP8 | 1 | 10.59 GB, about 15 GB of cache, three 32K contexts | not run, week 3; see below |

The plan's cost of a token holds: 147,456 bytes at FP16. vLLM asks 4.5 GiB for 32,768 tokens,
which is that figure exactly.

What the plan left out is what it said it had not counted: "The vision encoder's working memory
comes out of the same allowance and is not yet counted." At both shares vLLM's figure is 5.2 GiB
under the share less the weights (0.8 x 31.89 - 17.34 = 8.17 GiB against 2.97; 0.9 x 31.89 - 17.34
= 11.36 against 6.16). That constant 5.2 GiB is arithmetic from two measurements; which parts it
is made of was not measured.

At 80% vLLM says its largest context is 21,568 tokens, which would hold the demonstration
specification's prompts of about 4,600 tokens. The refusal is in
`raw/serve-fp16-util-0.8-refused.txt`. At 90% it serves 32,768 tokens with 1.37 times that to spare
(`raw/serve-fp16-util-0.9-prefix-cache-on.txt`).

If the same 5.2 GiB holds at FP8, its cache is about 13 GiB at 90%, close to the plan's three 32K
contexts, and about 10 GiB at the plan's 80%, about two. That is a plan, not a measurement.

## The environment's pinned parts on the machine

| Part | Version | Where it comes from |
| --- | --- | --- |
| uv | 0.13.5, the laptop's own | `https://astral.sh/uv/0.13.5/install.sh` |
| Python | 3.12.15 | through uv |
| torch | 2.14.1+xpu | PyTorch's XPU index |
| torchvision | 0.29.1+xpu | PyTorch's XPU index |
| torchcodec | 0.17.0+cpu | PyTorch's XPU index, which carries no XPU build of it |
| triton-xpu | 3.8.0 | PyTorch's XPU index; `torch` 2.14.1+xpu requires it, and PyPI's stops at 3.3.0b1 |
| anomalib | 2.7.0, without an extra | PyPI |
| lightning | 2.6.6 | PyPI |
| openvino | 2026.4.1 | PyPI; only in the `xpu` group |
| intel-sycl-rt | 2026.1.0 | PyPI |

193 packages, 8.5 GB in `.venv`.

## The judge's server

| Part | Value |
| --- | --- |
| Image | `intel/llm-scaler-vllm:0.26.0-b1`, published 2 September 2026 |
| Image digest | `sha256:70e7eafdd52c281263f2a19266086b88e55064402a17ef731ba5657c4bd86490` |
| Inside it | vLLM 0.26.1.dev0+g568afb3a1, torch 2.12.0+xpu, transformers 5.8.0, xgrammar 0.2.3 |
| Weights | `Qwen/Qwen3-VL-8B-Instruct`, revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`, 16.33 GiB, BF16 on disk |
| Precision served | FP16: `--dtype=float16`, and vLLM logs "Casting torch.bfloat16 to torch.float16" |
| Start-up | 126 s and 124 s, from `docker run` to `/health` answering, with the weights in the page cache. Of that, 5 s loading the weights and about 60 s warming up after the cache is sized |
| Memory on card 1 | 26,960 MiB once up; 42 MiB before |
| Card 0 meanwhile | 42 MiB |

## Pages read, on 6 November 2026

| Page | Read with | What it says |
| --- | --- | --- |
| <https://docs.pytorch.org/docs/stable/notes/get_start_xpu.html> (served as the 2.15 page, last updated 29 September 2026) | headless browser | Battlemage is validated on Ubuntu 24.04 and 26.04; `torch.xpu.is_available()`; the index is `https://download.pytorch.org/whl/xpu`. It names the Arc B-Series, not the B70 |
| <https://github.com/open-edge-platform/anomalib/blob/lib/v2.7.0/docs/source/markdown/guides/how_to/training_on_intel_gpus/index.md> | headless browser | `SingleXPUStrategy` and `XPUAccelerator`; "only single GPU training is supported"; "tested on Arc 750 and Arc 770". It does not name the B70 |
| `anomalib-2.7.0.dist-info/METADATA`, and `anomalib/engine/accelerator/xpu.py` in the wheel | read locally | The `xpu` extra lists torch, torchvision, torchcodec, triton-xpu and pytorch-triton-xpu; `parse_devices(1)` gives `[1]` |
| <https://download.pytorch.org/whl/xpu/> for torch, torchvision, torchcodec, triton-xpu | `curl` | The versions in the table above |
| <https://github.com/intel/llm-scaler>, `vllm/README.md` on `main` | `curl` | How to map a single card; `--dtype=float16`, `--gpu-memory-util=0.9`, `--block-size 64`. Read today on `main`, not at the image's tag |
| `https://hub.docker.com/v2/repositories/intel/llm-scaler-vllm/tags` | `curl` | `0.26.0-b1` exists; also `0.26.0-b2`, `0.31.0-b1-experimental`, `1.5` |
| `~/demos/02_hello_world_vllm`, `~/demos/10_defect_detection` on the machine | read there | Intel starts stock `vllm/vllm-openai-xpu:v0.26.0` with `--dtype=bfloat16`, `--max-model-len 8192`, `--privileged`, and lists Qwen3-VL-8B as needing 22 GB. None of it was run |

`github.com/intel/gpu-ai-skills` was not cloned: the brief allowed it and nothing here needed it.
The `xpu-smi discovery` output has no field for the Level Zero loader or the runtime, so those two
are from `dpkg` and from what the runtime itself reports.
