#!/usr/bin/env bash
# One run of the corrections comparison on the machine. Usage: run.sh <run-name> [trial]
# Writes ~/corrections-run/<name>.{pid,start,end,exit,out,cards.csv}. Both cards are read every 5 s
# from before the bench starts until after it ends. A trial is 3 anomalous and 3 good boards of each
# part, into a record and a runs directory of its own, with no figure 10.
name=$1
trial=${2:-}
here=$HOME/corrections-run
folder=results/stage2/comparison-corrections
cd "$HOME/spec-to-inspector" || exit 1
echo $$ >"$here/$name.pid"
date -u +%FT%TZ >"$here/$name.start"

read_card() {
    xpu-smi --query-gpu=memory.used --id="$1" --format=csv,noheader,nounits 2>/dev/null
}

(
    echo "utc,card_0_mib,card_1_mib"
    next=$(date +%s)
    while :; do
        echo "$(date -u +%FT%TZ),$(read_card 0000:17:00.0),$(read_card 0000:ba:00.0)"
        next=$((next + 5))
        wait_for=$((next - $(date +%s)))
        [ "$wait_for" -gt 0 ] && sleep "$wait_for"
    done
) >"$here/$name.cards.csv" &
sampler=$!

if [ "$trial" = trial ]; then
    mkdir -p "$here/trial"
    SPEC_TO_INSPECTOR_RUNS_DIR=$here/trial/runs SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 \
        .venv/bin/spec-to-inspector bench --limit 3 --batch corrections \
        --declared-store "$folder/store.sqlite3" \
        --results "$here/trial/bench.json" --readme "$here/trial/README.md" \
        >"$here/$name.out" 2>&1 &
else
    SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 \
        .venv/bin/spec-to-inspector bench --batch corrections \
        --declared-store "$folder/store.sqlite3" \
        --against results/stage2/final/bench.json \
        --results "$folder/bench.json" --readme "$folder/README.md" \
        >"$here/$name.out" 2>&1 &
fi
process=$!
echo "$process" >"$here/$name.process"
wait "$process"
code=$?

sleep 5
kill "$sampler"
wait "$sampler" 2>/dev/null
echo "$code" >"$here/$name.exit"
date -u +%FT%TZ >"$here/$name.end"
