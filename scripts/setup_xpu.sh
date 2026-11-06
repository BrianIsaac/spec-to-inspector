#!/usr/bin/env bash
# The project's environment on an Intel Arc machine: the same lockfile as the laptop's, with the
# `xpu` dependency group in place of the default `cuda` one (see `[tool.uv]` in pyproject.toml).
#
#   scripts/setup_xpu.sh
#
# A bare `uv run` syncs back to the default groups and would swap the CUDA wheels in, so on this
# machine commands run with UV_NO_SYNC=1 in the environment, or from .venv/bin directly.
set -euo pipefail
cd "$(dirname "$0")/.."

uv sync --locked --no-group cuda --group xpu
echo "Synced the xpu group. Run commands with UV_NO_SYNC=1, for example:"
echo "  UV_NO_SYNC=1 uv run python -c 'import torch; print(torch.xpu.device_count())'"
