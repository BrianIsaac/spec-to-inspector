#!/usr/bin/env bash
here=$HOME/corrections-run
cd "$HOME/spec-to-inspector" || exit 1
echo $$ >"$here/marked-tests.pid"
date -u +%FT%TZ >"$here/marked-tests.start"
ZE_AFFINITY_MASK=0 .venv/bin/python -m pytest -p no:cacheprovider -m "data or xpu" -q >"$here/marked-tests.out" 2>&1
code=$?
echo "$code" >"$here/marked-tests.exit"
date -u +%FT%TZ >"$here/marked-tests.end"
