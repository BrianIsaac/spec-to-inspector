# Third-party models, data and software

Everything Spec to Inspector uses that its author did not write: each model,
dataset and library, with its licence and where it comes from. The
repository's own code and documents are under Apache-2.0 (`LICENSE`).

Read on 11 October 2026: each model's licence from its model card on
Hugging Face, each project's from its repository, each Python package's
from the metadata of the version `uv.lock` pins. What Stage II uses on the
organiser's machine, and the packages only its `xpu` group brings, were read the
same way on 7 November 2026. The four that week 2 added to that group, `ml-dtypes`,
`onnx`, `onnx-ir` and `onnxscript`, were read that day in the wheels `uv.lock` pins,
at the hashes it pins, and in each project's repository at the matching tag.

## Summary

- **No part of the product is under a non-commercial licence.** Every model
  is Apache-2.0 or CDLA-Permissive-2.0; the dataset is CC BY 4.0; the
  libraries are permissive (MIT, BSD, Apache-2.0, ISC, PSF) with a few
  under weak copyleft (MPL-2.0, and LGPL libraries bundled inside four
  wheels), all of which permit commercial use. On the machine, Intel's runtime
  packages are under Intel's own licences, which permit business use.
- Nothing third-party is redistributed in this repository except images
  derived from VisA, with attribution (below), and the deck's typefaces,
  vendored with the deck's source with their licence files beside them in
  the full repository and embedded as subsets in `deck/deck.pdf`. Models and
  data are downloaded by the documented commands; packages are installed
  by `uv`.
- Four points a reader should know, each set out under "Notes": Anomalib's
  code describes VisA's licence differently from VisA's owner; the anomaly
  model's backbone was pretrained on ImageNet; the laptop's CUDA runtime is
  NVIDIA's proprietary software, which the machine does not use; and the
  machine's runtime is Intel's proprietary software, which the laptop does not
  use.

## Data

| Dataset | Used for | Licence | Source |
| --- | --- | --- | --- |
| VisA (Visual Anomaly dataset), the four PCB categories and `split_csv/` of `VisA_20220922.tar` | Training the anomaly model on good boards; the test split behind every figure in `results/stage1/` and `results/stage2/`; the photographs in the demonstration specification | CC BY 4.0 ("The data is released under the CC BY 4.0 license", the owner's README) | <https://github.com/amazon-science/spot-diff> |

Citation, as the owner asks:

> Yang Zou, Jongheon Jeong, Latha Pemula, Dongqing Zhang and Onkar Dabeer.
> "SPot-the-Difference Self-Supervised Pre-training for Anomaly Detection
> and Segmentation." ECCV 2022. arXiv:2207.14315.

What in this repository is derived from VisA, and how it was changed:

- `specs/figures/*.jpg` and the same pictures inside `specs/pcb-spec.pdf`:
  single images, cropped, resized, and drawn over with zone outlines or a
  defect outline. Each caption names the category and the image number.
- `docs/screens/`: screenshots of the console showing VisA test images,
  their crops and anomaly heatmaps, in the full repository; the public
  copy keeps the one the README shows.
- `eval/clause_labels.csv`: VisA's per-image defect annotation, mapped to
  the demonstration specification's clauses by the table in
  `eval/clause_mapping.md`.

The dataset itself is not in the repository: `uv run spec-to-inspector data
fetch` streams it from Amazon's bucket and verifies it.

The demonstration specification (`specs/pcb-spec.md`, `specs/pcb-spec.pdf`)
was written for this entry in the style of a customer's document. It is not
a real customer's document, and it neither quotes nor paraphrases any
published standard.

## Models

Used by the Stage I prototype:

| Model | Version | Used for | Licence | Source |
| --- | --- | --- | --- | --- |
| Qwen3-VL-8B-Instruct, GGUF: `Qwen3VL-8B-Instruct-Q4_K_M.gguf` (5.03 GB) and `mmproj-Qwen3VL-8B-Instruct-F16.gguf` (1.16 GB) | revision `f982a07559d4a2f6c8744d840bf6fccab30eea96`, each file's SHA-256 pinned in `scripts/serve_vlm.sh` | The judge: names the defect class and the clause | Apache-2.0 | <https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF> |
| Qwen3-VL-8B-Instruct, `tokenizer.json` only | as published | Counting the specification's size in the judge's tokens | Apache-2.0 | <https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct> |
| `wide_resnet50_2.racm_in1k` (timm), pretrained on ImageNet-1k | as timm 1.0.30 fetches it | The feature extractor inside PatchCore, the anomaly model | Apache-2.0 | <https://huggingface.co/timm/wide_resnet50_2.racm_in1k> |
| docling layout model, `docling-layout-heron` | as docling 2.135.0 fetches it | Reading the specification PDF's layout | Apache-2.0 | <https://huggingface.co/docling-project/docling-layout-heron> |
| docling models (table structure), `docling-models` v2.3.0 | as docling 2.135.0 fetches it | Reading the specification PDF's tables | CDLA-Permissive-2.0 and Apache-2.0 | <https://huggingface.co/docling-project/docling-models> |

Used once, for a comparison, and not part of the product:

| Model | Used for | Licence | Source |
| --- | --- | --- | --- |
| `resnet18.a1_in1k` (timm) | Re-measuring a published reference figure with the paper's backbone (`results/stage1/anomaly-reference-resnet18.json`) | Apache-2.0 | <https://huggingface.co/timm/resnet18.a1_in1k> |
| `resnet18.tv_in1k` (timm, torchvision's weights) | The same check with other pretrained weights (`results/stage1/anomaly-reference-resnet18-tv.json`) | BSD-3-Clause | <https://huggingface.co/timm/resnet18.tv_in1k> |

The PatchCore memory banks under `models/patchcore/` are built on the
user's machine by `spec-to-inspector train` from VisA's good images; they
are not distributed.

Used on the organiser's machine in Stage II (`results/stage2/week1/machine.md`,
`results/stage2/week2/README.md`):

| Component | Version | Used for | Licence | Source |
| --- | --- | --- | --- | --- |
| Qwen3-VL-8B-Instruct at FP16 | revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`, pinned in `scripts/serve_vlm_xpu.sh` | The judge at full precision | Apache-2.0, read at that revision | <https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct> |
| Qwen3-VL-8B-Instruct-FP8 | revision `9cdc6310a8cb770ce18efaf4e9935334512aee45`, pinned in `results/stage2/comparison-fp8/serve-fp8.sh` | The judge at 8-bit, Qwen's own build: a comparison declared in `eval/PROTOCOL-stage2.md`, run twice on 7 November 2026 (`results/stage2/comparison-fp8/COMPARISON.md`). It does not replace the final figure | Apache-2.0, read at that revision | <https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-FP8> |
| Intel llm-scaler, its vLLM image | `intel/llm-scaler-vllm:0.26.0-b1`, digest in `machine.md` | Serving the judge on card 1; see note 6 | Apache-2.0, the project's `LICENSE` on `main` | <https://github.com/intel/llm-scaler> |
| vLLM | 0.26.1.dev0, inside that image | Serving the judge | Apache-2.0, the project's `LICENSE` on `main` | <https://github.com/vllm-project/vllm> |
| OpenVINO | 2026.4.1, in the `xpu` group | Measured beside PyTorch XPU: PatchCore through Anomalib's export, on `GPU.0` in FP32, with `onnx` and `onnxscript`. Nothing in the pipeline runs through it | Apache-2.0 | <https://github.com/openvinotoolkit/openvino> |

Planned for Stage II and not yet run:

| Component | Planned use | Licence | Source |
| --- | --- | --- | --- |
| PaddleOCR-VL-1.6 | Scanned specifications | Apache-2.0 | <https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6> |

## Software outside the Python environment

| Software | Version | Used for | Licence | Source |
| --- | --- | --- | --- | --- |
| llama.cpp (`llama-server`) | tag `v0.6.0`, commit `d81235049384534c167caea52b85a694f6103d14`, built from source by `scripts/serve_vlm.sh` | Serving the judge on the laptop | MIT | <https://github.com/ggml-org/llama.cpp> |
| NVIDIA CUDA Toolkit | 13.0 | Compiling llama.cpp for the laptop's GPU | NVIDIA Software License Agreement (proprietary) | <https://developer.nvidia.com/cuda-toolkit> |
| Google Chrome, headless | the machine's own | Printing `specs/pcb-spec.pdf` from its Markdown source | Google's terms; a tool only, nothing of it is distributed | <https://www.google.com/chrome/> |
| Chromium, through Playwright | as Playwright 1.63.0 installs it | The scripted walk that takes the screenshots (development only) | BSD-3-Clause | <https://www.chromium.org/> |
| SQLite | the one in Python's standard library | The corrections store | Public domain | <https://www.sqlite.org/copyright.html> |
| CPython | 3.12 | Everything | PSF-2.0 | <https://www.python.org/> |
| uv | 0.7 or later | Installing and running the project | Apache-2.0 OR MIT | <https://github.com/astral-sh/uv> |
| Liberation Sans | subset, embedded in `specs/pcb-spec.pdf` | The specification's typeface | SIL Open Font License 1.1 | <https://github.com/liberationfonts/liberation-fonts> |
| IBM Plex Sans | 1.1.0 (release `@ibm/plex-sans@1.1.0`): five WOFF2 files and two TTF files, unmodified, vendored with the deck's source; embedded as subsets in `deck/deck.pdf` | The deck's titles, body and tables; the TTF files set the charts' labels | SIL Open Font License 1.1 (its `OFL.txt` beside the files) | <https://github.com/IBM/plex> |
| IBM Plex Mono | 2.5.0 (release `@ibm/plex-mono@2.5.0`): three WOFF2 files, unmodified, vendored with the deck's source; embedded as subsets in `deck/deck.pdf` | The deck's labels, figures and code | SIL Open Font License 1.1 (its `OFL.txt` beside the files) | <https://github.com/IBM/plex> |

The console ships no fonts: its stylesheet names system fonts. The two
IBM Plex families are vendored for the deck's theme in the full repository,
fetched from the family's own releases on 11 October 2026 and embedded
in `deck/deck.pdf` as subsets.

## Notes

1. **VisA's licence, and what Anomalib's code says of it.** VisA's owner
   releases the data under CC BY 4.0 (the README of
   `amazon-science/spot-diff`, read 11 October 2026). The docstrings of
   Anomalib 2.7.0's VisA modules (`anomalib/data/datasets/image/visa.py`,
   `anomalib/data/datamodules/image/visa.py`) describe it as CC BY-NC-SA
   4.0. The owner's statement is the licence; this file follows it, and
   notes the difference so that nobody finds it later and wonders.
2. **ImageNet pretraining.** The anomaly model's feature extractor,
   `wide_resnet50_2.racm_in1k`, is published under Apache-2.0 and was
   pretrained on ImageNet-1k, whose images are offered for non-commercial
   research. This repository neither uses nor distributes ImageNet. The
   same is true of nearly every pretrained vision backbone; it is stated
   here rather than left unsaid.
3. **NVIDIA's CUDA runtime.** On the laptop, PyTorch's `cu130` build pulls
   in fifteen NVIDIA runtime packages (cuBLAS, cuDNN and others) under
   NVIDIA's proprietary licence, which permits commercial use and limits
   redistribution. They are installed by `uv` from the package index and
   are not in this repository. The organiser's machine, with its two Intel
   Arc Pro B70s, uses PyTorch's XPU build and none of them.
4. **Weak copyleft.** `certifi`, `hypothesis` (development only) and
   `tqdm` are MPL-2.0. Four wheels bundle a library under the LGPL or the
   GPL with the GCC runtime exception: `opencv-python-headless` (FFmpeg),
   `shapely` (GEOS), and `numpy` and `scipy` (libgfortran, libquadmath).
   None is modified, and each permits commercial use. `ml-dtypes`, in the `xpu`
   group only and through `onnx`, is Apache-2.0, and its README says its pre-compiled
   wheels are built with Eigen, under MPL-2.0; the wheel carries that licence as
   `LICENSE.eigen`. A development tool apart
   from these: `av`, which `faster-whisper` needs for the video's captions,
   bundles FFmpeg with `libx264` and `libx265`, which are GPL. It is in the `dev`
   group only and no part of the product or of this repository.
5. **Intel's runtime.** On the machine, PyTorch's XPU build pulls in Intel's
   oneAPI runtime packages, marked in the table below. Their metadata names
   the Intel End User License Agreement for Developer Tools (August 2024, read in
   `intel-cmplr-lic-rt`), which grants use "for Your personal or business use", or
   the Intel Simplified Software License (October 2022, read in `onemkl-license`),
   which grants use and redistribution in binary form. Both forbid reverse
   engineering. They are installed by `uv` from the package index and are not in
   this repository.
6. **The server's image.** The image is pulled by `scripts/serve_vlm_xpu.sh`, and
   neither it nor anything in it is in this repository. Besides vLLM it holds
   torch 2.12.0+xpu, transformers 5.8.0, xgrammar 0.2.3 and Intel's oneAPI
   runtime (`machine.md`). Its contents were not read package by package, and its
   tag has no matching tag in the project's git repository, so the licence above
   is the project's on `main`.

## Python packages

Every package in `uv.lock`, direct and transitive, development tools
included, at the locked version. The project's own direct dependencies are
listed in `pyproject.toml`; the rest arrive through them, most through
Anomalib and docling. The `cuda` group is the default and the `xpu` group the
machine's: a package only the `xpu` group brings says so beside its version. Where a package's metadata gives a classifier
rather than an identifier, the identifier here is its project's stated
licence.

| Package | Version | Licence |
| --- | --- | --- |
| [accelerate](https://pypi.org/project/accelerate/) | 1.15.0 | Apache-2.0 |
| [aiohappyeyeballs](https://pypi.org/project/aiohappyeyeballs/) | 2.7.1 | PSF-2.0 |
| [aiohttp](https://pypi.org/project/aiohttp/) | 3.14.4 | Apache-2.0 AND MIT |
| [aiosignal](https://pypi.org/project/aiosignal/) | 1.4.0 | Apache-2.0 |
| [annotated-doc](https://pypi.org/project/annotated-doc/) | 0.0.5 | MIT |
| [annotated-types](https://pypi.org/project/annotated-types/) | 0.8.0 | MIT |
| [anomalib](https://pypi.org/project/anomalib/) | 2.7.0 | Apache-2.0 |
| [antlr4-python3-runtime](https://pypi.org/project/antlr4-python3-runtime/) | 4.9.3 | BSD-3-Clause |
| [anyio](https://pypi.org/project/anyio/) | 4.15.1 | MIT |
| [attrs](https://pypi.org/project/attrs/) | 26.1.0 | MIT |
| [av](https://pypi.org/project/av/) | 19.0.1 | BSD-3-Clause (the wheel bundles FFmpeg with libx264 and libx265, GPL; see note 4) |
| [beautifulsoup4](https://pypi.org/project/beautifulsoup4/) | 4.15.0 | MIT |
| [certifi](https://pypi.org/project/certifi/) | 2026.10.19 | MPL-2.0 |
| [charset-normalizer](https://pypi.org/project/charset-normalizer/) | 3.5.2 | MIT |
| [click](https://pypi.org/project/click/) | 8.5.0 | BSD-3-Clause |
| [cloudpickle](https://pypi.org/project/cloudpickle/) | 3.1.2 | BSD-3-Clause |
| [colorlog](https://pypi.org/project/colorlog/) | 6.12.0 | MIT |
| [contourpy](https://pypi.org/project/contourpy/) | 1.4.0 | BSD-3-Clause |
| [ctranslate2](https://pypi.org/project/ctranslate2/) | 4.8.2 | MIT |
| [cuda-bindings](https://pypi.org/project/cuda-bindings/) | 13.4.3 | Apache-2.0 |
| [cuda-pathfinder](https://pypi.org/project/cuda-pathfinder/) | 1.8.3 | Apache-2.0 |
| [cuda-toolkit](https://pypi.org/project/cuda-toolkit/) | 13.0.3.0 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [cycler](https://pypi.org/project/cycler/) | 0.12.1 | BSD-3-Clause |
| [defusedxml](https://pypi.org/project/defusedxml/) | 0.7.1 | PSF-2.0 |
| [dill](https://pypi.org/project/dill/) | 0.4.1 | BSD-3-Clause |
| [doclang](https://pypi.org/project/doclang/) | 0.7.3 | Apache-2.0 |
| [docling](https://pypi.org/project/docling/) | 2.135.0 | MIT |
| [docling-core](https://pypi.org/project/docling-core/) | 2.101.1 | MIT |
| [docling-ibm-models](https://pypi.org/project/docling-ibm-models/) | 4.0.3 | MIT |
| [docling-parse](https://pypi.org/project/docling-parse/) | 7.22.2 | MIT |
| [docling-slim](https://pypi.org/project/docling-slim/) | 2.135.0 | MIT |
| [docstring-parser](https://pypi.org/project/docstring-parser/) | 0.18.0 | MIT |
| [dpcpp-cpp-rt](https://pypi.org/project/dpcpp-cpp-rt/) | 2026.1.0 (`xpu` group) | Intel End User License Agreement for Developer Tools (proprietary) |
| [einops](https://pypi.org/project/einops/) | 0.8.2 | MIT |
| [et-xmlfile](https://pypi.org/project/et-xmlfile/) | 2.0.0 | MIT |
| [faker](https://pypi.org/project/faker/) | 40.41.0 | MIT |
| [fastapi](https://pypi.org/project/fastapi/) | 0.143.0 | MIT |
| [faster-whisper](https://pypi.org/project/faster-whisper/) | 1.2.1 | MIT |
| [filelock](https://pypi.org/project/filelock/) | 4.0.12 | MIT |
| [filetype](https://pypi.org/project/filetype/) | 1.2.0 | MIT |
| [flatbuffers](https://pypi.org/project/flatbuffers/) | 25.12.19 | Apache-2.0 |
| [fonttools](https://pypi.org/project/fonttools/) | 4.66.1 | MIT |
| [freia](https://pypi.org/project/freia/) | 0.2 | MIT |
| [frozenlist](https://pypi.org/project/frozenlist/) | 1.8.0 | Apache-2.0 |
| [fsspec](https://pypi.org/project/fsspec/) | 2026.9.0 | BSD-3-Clause |
| [greenlet](https://pypi.org/project/greenlet/) | 3.5.6 | MIT AND PSF-2.0 |
| [h11](https://pypi.org/project/h11/) | 0.16.0 | MIT |
| [hf-xet](https://pypi.org/project/hf-xet/) | 1.7.0 | Apache-2.0 |
| [httpcore](https://pypi.org/project/httpcore/) | 1.0.9 | BSD-3-Clause |
| [httpcore2](https://pypi.org/project/httpcore2/) | 2.13.1 | BSD-3-Clause |
| [httpx](https://pypi.org/project/httpx/) | 0.28.1 | BSD-3-Clause |
| [httpx2](https://pypi.org/project/httpx2/) | 2.13.1 | BSD-3-Clause |
| [huggingface-hub](https://pypi.org/project/huggingface-hub/) | 1.33.0 | Apache-2.0 |
| [hypothesis](https://pypi.org/project/hypothesis/) | 6.168.5 | MPL-2.0 |
| [idna](https://pypi.org/project/idna/) | 3.20 | BSD-3-Clause |
| [imagecodecs](https://pypi.org/project/imagecodecs/) | 2026.8.16 | BSD-3-Clause |
| [imageio](https://pypi.org/project/imageio/) | 2.38.1 | BSD-2-Clause |
| [impi-rt](https://pypi.org/project/impi-rt/) | 2021.18.1 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [iniconfig](https://pypi.org/project/iniconfig/) | 2.3.1 | MIT |
| [intel-cmplr-lib-rt](https://pypi.org/project/intel-cmplr-lib-rt/) | 2026.1.0 (`xpu` group) | Intel End User License Agreement for Developer Tools (proprietary) |
| [intel-cmplr-lib-ur](https://pypi.org/project/intel-cmplr-lib-ur/) | 2026.1.0 (`xpu` group) | Intel End User License Agreement for Developer Tools (proprietary) |
| [intel-cmplr-lic-rt](https://pypi.org/project/intel-cmplr-lic-rt/) | 2026.1.0 (`xpu` group) | Intel End User License Agreement for Developer Tools (proprietary) |
| [intel-opencl-rt](https://pypi.org/project/intel-opencl-rt/) | 2026.1.0 (`xpu` group) | Intel End User License Agreement for Developer Tools (proprietary) |
| [intel-openmp](https://pypi.org/project/intel-openmp/) | 2026.1.0 (`xpu` group) | Intel End User License Agreement for Developer Tools (proprietary) |
| [intel-pti](https://pypi.org/project/intel-pti/) | 1.0.1 (`xpu` group) | MIT |
| [intel-sycl-rt](https://pypi.org/project/intel-sycl-rt/) | 2026.1.0 (`xpu` group) | Intel End User License Agreement for Developer Tools (proprietary) |
| [jinja2](https://pypi.org/project/jinja2/) | 3.1.6 | BSD-3-Clause |
| [joblib](https://pypi.org/project/joblib/) | 1.6.0 | BSD-3-Clause |
| [jsonargparse](https://pypi.org/project/jsonargparse/) | 4.46.0 | MIT |
| [jsonref](https://pypi.org/project/jsonref/) | 1.1.0 | MIT |
| [jsonschema](https://pypi.org/project/jsonschema/) | 4.26.0 | MIT |
| [jsonschema-specifications](https://pypi.org/project/jsonschema-specifications/) | 2025.9.1 | MIT |
| [kiwisolver](https://pypi.org/project/kiwisolver/) | 1.5.1 | BSD-3-Clause |
| [kornia](https://pypi.org/project/kornia/) | 0.8.3 | Apache-2.0 |
| [kornia-rs](https://pypi.org/project/kornia-rs/) | 0.2.0 | Apache-2.0 |
| [langcodes](https://pypi.org/project/langcodes/) | 3.5.1 | MIT |
| [latex2mathml](https://pypi.org/project/latex2mathml/) | 3.81.1 | MIT |
| [lazy-loader](https://pypi.org/project/lazy-loader/) | 0.6 | BSD-3-Clause |
| [lightning](https://pypi.org/project/lightning/) | 2.6.6 | Apache-2.0 |
| [lightning-utilities](https://pypi.org/project/lightning-utilities/) | 0.15.3 | Apache-2.0 |
| [lxml](https://pypi.org/project/lxml/) | 6.1.3 | BSD-3-Clause |
| [mail-parser](https://pypi.org/project/mail-parser/) | 4.8.0 | Apache-2.0 |
| [markdown-it-py](https://pypi.org/project/markdown-it-py/) | 4.2.0 | MIT |
| [marko](https://pypi.org/project/marko/) | 2.2.4 | MIT |
| [markupsafe](https://pypi.org/project/markupsafe/) | 3.0.4 | BSD-3-Clause |
| [matplotlib](https://pypi.org/project/matplotlib/) | 3.11.2 | Matplotlib licence (PSF-based, BSD-compatible) |
| [mdurl](https://pypi.org/project/mdurl/) | 0.1.2 | MIT |
| [mkl](https://pypi.org/project/mkl/) | 2026.1.0 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [ml-dtypes](https://pypi.org/project/ml-dtypes/) | 0.6.0 (`xpu` group) | Apache-2.0 (the wheel is built with Eigen, MPL-2.0; see note 4) |
| [mpire](https://pypi.org/project/mpire/) | 2.10.2 | MIT |
| [mpmath](https://pypi.org/project/mpmath/) | 1.3.0 | BSD-3-Clause |
| [multidict](https://pypi.org/project/multidict/) | 6.9.1 | Apache-2.0 |
| [multiprocess](https://pypi.org/project/multiprocess/) | 0.70.19 | BSD-3-Clause |
| [narwhals](https://pypi.org/project/narwhals/) | 2.26.0 | MIT |
| [networkx](https://pypi.org/project/networkx/) | 3.7 | BSD-3-Clause |
| [nodeenv](https://pypi.org/project/nodeenv/) | 1.11.0 | BSD-3-Clause |
| [numpy](https://pypi.org/project/numpy/) | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (the wheel bundles libgfortran, GPL-3.0-or-later WITH GCC-exception-3.1) |
| [nvidia-cublas](https://pypi.org/project/nvidia-cublas/) | 13.1.1.3 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-cuda-cupti](https://pypi.org/project/nvidia-cuda-cupti/) | 13.0.85 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-cuda-nvrtc](https://pypi.org/project/nvidia-cuda-nvrtc/) | 13.0.88 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-cuda-runtime](https://pypi.org/project/nvidia-cuda-runtime/) | 13.0.96 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-cudnn-cu13](https://pypi.org/project/nvidia-cudnn-cu13/) | 9.24.0.43 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-cufft](https://pypi.org/project/nvidia-cufft/) | 12.0.0.61 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-cufile](https://pypi.org/project/nvidia-cufile/) | 1.15.1.6 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-curand](https://pypi.org/project/nvidia-curand/) | 10.4.0.35 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-cusolver](https://pypi.org/project/nvidia-cusolver/) | 12.0.4.66 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-cusparse](https://pypi.org/project/nvidia-cusparse/) | 12.6.3.3 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-cusparselt-cu13](https://pypi.org/project/nvidia-cusparselt-cu13/) | 0.8.1 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-nccl-cu13](https://pypi.org/project/nvidia-nccl-cu13/) | 2.30.7 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-nvjitlink](https://pypi.org/project/nvidia-nvjitlink/) | 13.4.92 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-nvshmem-cu13](https://pypi.org/project/nvidia-nvshmem-cu13/) | 3.4.5 | NVIDIA proprietary (NVIDIA Software License Agreement) |
| [nvidia-nvtx](https://pypi.org/project/nvidia-nvtx/) | 13.0.85 | Apache-2.0 |
| [olefile](https://pypi.org/project/olefile/) | 0.47 | BSD-2-Clause |
| [omegaconf](https://pypi.org/project/omegaconf/) | 2.3.1 | BSD-3-Clause |
| [oneccl](https://pypi.org/project/oneccl/) | 2022.1.1 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [oneccl-devel](https://pypi.org/project/oneccl-devel/) | 2022.1.1 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [onemkl-license](https://pypi.org/project/onemkl-license/) | 2026.1.0 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [onemkl-sycl-blas](https://pypi.org/project/onemkl-sycl-blas/) | 2026.1.0 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [onemkl-sycl-dft](https://pypi.org/project/onemkl-sycl-dft/) | 2026.1.0 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [onemkl-sycl-lapack](https://pypi.org/project/onemkl-sycl-lapack/) | 2026.1.0 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [onemkl-sycl-rng](https://pypi.org/project/onemkl-sycl-rng/) | 2026.1.0 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [onemkl-sycl-sparse](https://pypi.org/project/onemkl-sycl-sparse/) | 2026.1.0 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [onnx](https://pypi.org/project/onnx/) | 1.23.2 (`xpu` group) | Apache-2.0 (the wheel links abseil-cpp, Apache-2.0, and protobuf and nanobind, BSD-3-Clause) |
| [onnx-ir](https://pypi.org/project/onnx-ir/) | 1.1.0 (`xpu` group) | Apache-2.0 |
| [onnxruntime](https://pypi.org/project/onnxruntime/) | 1.31.0 | MIT |
| [onnxscript](https://pypi.org/project/onnxscript/) | 0.7.2 (`xpu` group) | MIT |
| [opencv-python-headless](https://pypi.org/project/opencv-python-headless/) | 5.0.0.93 | Apache-2.0 (the wheel bundles FFmpeg under LGPL-2.1-or-later) |
| [openpyxl](https://pypi.org/project/openpyxl/) | 3.1.5 | MIT |
| [opentelemetry-api](https://pypi.org/project/opentelemetry-api/) | 1.45.1 | Apache-2.0 |
| [openvino](https://pypi.org/project/openvino/) | 2026.4.1 (`xpu` group) | Apache-2.0 |
| [openvino-telemetry](https://pypi.org/project/openvino-telemetry/) | 2025.2.0 (`xpu` group) | Apache-2.0 |
| [packaging](https://pypi.org/project/packaging/) | 26.3 | Apache-2.0 OR BSD-2-Clause |
| [pandas](https://pypi.org/project/pandas/) | 3.0.6 | BSD-3-Clause |
| [pillow](https://pypi.org/project/pillow/) | 12.3.0 | MIT-CMU |
| [platformdirs](https://pypi.org/project/platformdirs/) | 4.12.4 | MIT |
| [playwright](https://pypi.org/project/playwright/) | 1.63.0 | Apache-2.0 |
| [pluggy](https://pypi.org/project/pluggy/) | 1.6.0 | MIT |
| [polyfactory](https://pypi.org/project/polyfactory/) | 3.3.0 | MIT |
| [propcache](https://pypi.org/project/propcache/) | 0.5.4 | Apache-2.0 |
| [protobuf](https://pypi.org/project/protobuf/) | 7.36.2 | BSD-3-Clause |
| [psutil](https://pypi.org/project/psutil/) | 7.2.2 | BSD-3-Clause |
| [pyclipper](https://pypi.org/project/pyclipper/) | 1.4.0 | MIT |
| [pydantic](https://pypi.org/project/pydantic/) | 2.14.0 | MIT |
| [pydantic-core](https://pypi.org/project/pydantic-core/) | 2.50.0 | MIT |
| [pydantic-settings](https://pypi.org/project/pydantic-settings/) | 2.15.0 | MIT |
| [pyee](https://pypi.org/project/pyee/) | 13.0.1 | MIT |
| [pyelftools](https://pypi.org/project/pyelftools/) | 0.33 (`xpu` group) | Public domain |
| [pygments](https://pypi.org/project/pygments/) | 2.21.0 | BSD-2-Clause |
| [pylatexenc](https://pypi.org/project/pylatexenc/) | 2.11 | MIT |
| [pyparsing](https://pypi.org/project/pyparsing/) | 3.3.3 | MIT |
| [pypdfium2](https://pypi.org/project/pypdfium2/) | 5.14.0 | BSD-3-Clause OR Apache-2.0 (bundles PDFium, BSD-3-Clause and Apache-2.0) |
| [pyright](https://pypi.org/project/pyright/) | 1.1.414 | MIT |
| [pytest](https://pypi.org/project/pytest/) | 9.1.1 | MIT |
| [python-dateutil](https://pypi.org/project/python-dateutil/) | 2.9.0.post0 | Apache-2.0 OR BSD-3-Clause |
| [python-docx](https://pypi.org/project/python-docx/) | 1.2.0 | MIT |
| [python-dotenv](https://pypi.org/project/python-dotenv/) | 1.2.4 | BSD-3-Clause |
| [python-multipart](https://pypi.org/project/python-multipart/) | 0.0.32 | Apache-2.0 |
| [python-oxmsg](https://pypi.org/project/python-oxmsg/) | 0.0.2 | MIT |
| [python-pptx](https://pypi.org/project/python-pptx/) | 1.0.2 | MIT |
| [pytorch-lightning](https://pypi.org/project/pytorch-lightning/) | 2.6.6 | Apache-2.0 |
| [pyyaml](https://pypi.org/project/pyyaml/) | 6.0.3 | MIT |
| [pyzes](https://pypi.org/project/pyzes/) | 0.1.2 (`xpu` group) | MIT |
| [rapidocr](https://pypi.org/project/rapidocr/) | 3.10.0 | Apache-2.0 |
| [referencing](https://pypi.org/project/referencing/) | 0.37.0 | MIT |
| [regex](https://pypi.org/project/regex/) | 2026.9.29 | Apache-2.0 AND CNRI-Python |
| [requests](https://pypi.org/project/requests/) | 2.34.2 | Apache-2.0 |
| [rich](https://pypi.org/project/rich/) | 15.0.0 | MIT |
| [rich-argparse](https://pypi.org/project/rich-argparse/) | 1.8.0 | MIT |
| [rpds-py](https://pypi.org/project/rpds-py/) | 2026.9.1 | MIT |
| [rtree](https://pypi.org/project/rtree/) | 1.4.1 | MIT |
| [ruff](https://pypi.org/project/ruff/) | 0.16.10 | MIT |
| [safetensors](https://pypi.org/project/safetensors/) | 0.8.0 | Apache-2.0 |
| [scikit-image](https://pypi.org/project/scikit-image/) | 0.26.0 | BSD-3-Clause |
| [scikit-learn](https://pypi.org/project/scikit-learn/) | 1.9.1 | BSD-3-Clause |
| [scipy](https://pypi.org/project/scipy/) | 1.18.1 | BSD-3-Clause (the wheel bundles libgfortran, GPL-3.0-or-later WITH GCC-exception-3.1) |
| [semchunk](https://pypi.org/project/semchunk/) | 3.2.5 | MIT |
| [setuptools](https://pypi.org/project/setuptools/) | 84.0.0 | MIT |
| [shapely](https://pypi.org/project/shapely/) | 2.2.0 | BSD-3-Clause (the wheel bundles GEOS under LGPL-2.1) |
| [shellingham](https://pypi.org/project/shellingham/) | 1.5.4 | ISC |
| [six](https://pypi.org/project/six/) | 1.17.0 | MIT |
| [sortedcontainers](https://pypi.org/project/sortedcontainers/) | 2.4.0 | Apache-2.0 |
| [soupsieve](https://pypi.org/project/soupsieve/) | 2.10 | MIT |
| [starlette](https://pypi.org/project/starlette/) | 1.7.0 | BSD-3-Clause |
| [sympy](https://pypi.org/project/sympy/) | 1.14.0 | BSD-3-Clause |
| [tabulate](https://pypi.org/project/tabulate/) | 0.10.0 | MIT |
| [tbb](https://pypi.org/project/tbb/) | 2023.1.0 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [tcmlib](https://pypi.org/project/tcmlib/) | 1.5.0 (`xpu` group) | Intel Simplified Software License (proprietary) |
| [threadpoolctl](https://pypi.org/project/threadpoolctl/) | 3.7.0 | BSD-3-Clause |
| [tifffile](https://pypi.org/project/tifffile/) | 2026.9.20 | BSD-3-Clause |
| [timm](https://pypi.org/project/timm/) | 1.0.30 | Apache-2.0 |
| [tokenizers](https://pypi.org/project/tokenizers/) | 0.23.2 | Apache-2.0 |
| [torch](https://pypi.org/project/torch/) | 2.14.1+cu130; 2.14.1+xpu (`xpu` group) | Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT |
| [torchcodec](https://pypi.org/project/torchcodec/) | 0.17.0+cu130; 0.17.0+cpu (`xpu` group) | BSD-3-Clause |
| [torchmetrics](https://pypi.org/project/torchmetrics/) | 1.9.0 | Apache-2.0 |
| [torchvision](https://pypi.org/project/torchvision/) | 0.29.1+cu130; 0.29.1+xpu (`xpu` group) | BSD-3-Clause |
| [tqdm](https://pypi.org/project/tqdm/) | 4.70.1 | MPL-2.0 AND MIT |
| [transformers](https://pypi.org/project/transformers/) | 5.19.0 | Apache-2.0 |
| [tree-sitter](https://pypi.org/project/tree-sitter/) | 0.26.0 | MIT |
| [tree-sitter-c](https://pypi.org/project/tree-sitter-c/) | 0.24.2 | MIT |
| [tree-sitter-javascript](https://pypi.org/project/tree-sitter-javascript/) | 0.25.0 | MIT |
| [tree-sitter-python](https://pypi.org/project/tree-sitter-python/) | 0.25.0 | MIT |
| [tree-sitter-typescript](https://pypi.org/project/tree-sitter-typescript/) | 0.23.2 | MIT |
| [triton](https://pypi.org/project/triton/) | 3.8.0 | MIT |
| [triton-xpu](https://pypi.org/project/triton-xpu/) | 3.8.0 (`xpu` group) | MIT |
| [truststore](https://pypi.org/project/truststore/) | 0.10.4 | MIT |
| [typer](https://pypi.org/project/typer/) | 0.26.8 | MIT |
| [typeshed-client](https://pypi.org/project/typeshed-client/) | 2.13.0 | MIT |
| [typing-extensions](https://pypi.org/project/typing-extensions/) | 4.16.0 | PSF-2.0 |
| [typing-inspection](https://pypi.org/project/typing-inspection/) | 0.4.4 | MIT |
| [umf](https://pypi.org/project/umf/) | 1.1.0 (`xpu` group) | Apache-2.0 WITH LLVM-exception |
| [urllib3](https://pypi.org/project/urllib3/) | 2.8.0 | MIT |
| [uvicorn](https://pypi.org/project/uvicorn/) | 0.54.0 | BSD-3-Clause |
| [websockets](https://pypi.org/project/websockets/) | 16.1.1 | BSD-3-Clause |
| [xlsxwriter](https://pypi.org/project/xlsxwriter/) | 3.2.9 | BSD-2-Clause |
| [yarl](https://pypi.org/project/yarl/) | 1.25.1 | Apache-2.0 |
