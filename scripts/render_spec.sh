#!/usr/bin/env bash
# Rebuild the demo specification's artefacts, from the repository root or anywhere:
#   1. the figures, from data/visa (kept as tracked when the data is not fetched);
#   2. specs/pcb-spec.pdf, printed from specs/pcb-spec.md by headless google-chrome;
#   3. specs/pcb-spec.clauses.json, parsed from the PDF by docling, and the measured
#      summary in results/stage1/spec.json.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f data/visa/manifest.json ]]; then
    uv run python -m spec_to_inspector.spec.render --figures specs/pcb-spec.md
else
    echo "data/visa is not fetched: keeping the tracked figures"
    uv run python -m spec_to_inspector.spec.render specs/pcb-spec.md
fi
uv run spec-to-inspector parse specs/pcb-spec.pdf --results results/stage1/spec.json
