#!/usr/bin/env bash
# The second half of the deck's call H: PatchCore scoring beside a judge that has already answered.
# On card 0: one short bench to warm the server, then the same bench again, whose scoring stage meets
# the server at its peak. Then the server back on card 1 in the final's setting, whatever happened.
# Every step is recorded under ~/one-card/warm/<step>.{start,end,exit,out}.
here=$HOME/one-card/warm
mkdir -p "$here"
cd "$HOME/spec-to-inspector" || exit 1
echo $$ >"$here/warm.pid"
date -u +%FT%TZ >"$here/warm.start"

read_card() {
    xpu-smi --query-gpu=memory.used --id="$1" --format=csv,noheader,nounits 2>/dev/null
}

step() {
    local name=$1
    shift
    date -u +%FT%TZ >"$here/$name.start"
    "$@" >"$here/$name.out" 2>&1
    local code=$?
    echo "$code" >"$here/$name.exit"
    date -u +%FT%TZ >"$here/$name.end"
    return "$code"
}

short_bench() {
    SPEC_TO_INSPECTOR_RUNS_DIR=$here/runs SPEC_TO_INSPECTOR_VLM_CARD=0000:17:00.0 \
        SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 \
        .venv/bin/spec-to-inspector bench --limit 20 --batch one-card \
        --results "$here/$1.json" --readme "$here/$1.md"
}

docker logs spec-to-inspector-vlm >"$here/server-before.txt" 2>&1
step stop-final scripts/serve_vlm_xpu.sh stop

(
    echo "utc,card_0_mib,card_1_mib"
    next=$(date +%s)
    while :; do
        echo "$(date -u +%FT%TZ),$(read_card 0000:17:00.0),$(read_card 0000:ba:00.0)"
        next=$((next + 5))
        wait_for=$((next - $(date +%s)))
        [ "$wait_for" -gt 0 ] && sleep "$wait_for"
    done
) >"$here/warm.cards.csv" &
sampler=$!

if CARD_BDF=0000:17:00.0 step start-on-card-0 scripts/serve_vlm_xpu.sh start; then
    step bench-warming short_bench warming
    step bench-beside-warm short_bench beside-warm
fi

sleep 5
kill "$sampler"
wait "$sampler" 2>/dev/null
docker logs spec-to-inspector-vlm >"$here/server-on-card-0.txt" 2>&1
step stop-card-0 scripts/serve_vlm_xpu.sh stop
step start-final scripts/serve_vlm_xpu.sh start
date -u +%FT%TZ >"$here/warm.end"
