#!/usr/bin/env bash
# The judge and the anomaly model on one card, the deck's call H: one short bench on card 0, the
# server otherwise as the script writes it, then the server back on card 1 in the final's setting.
# Every step is recorded under ~/one-card/<step>.{start,end,exit,out}. The way back runs whatever the
# first two steps did.
here=$HOME/one-card
cd "$HOME/spec-to-inspector" || exit 1
echo $$ >"$here/one-card.pid"
date -u +%FT%TZ >"$here/one-card.start"

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

docker logs spec-to-inspector-vlm >"$here/server-before-one-card.txt" 2>&1
docker inspect -f '{{.State.StartedAt}}' spec-to-inspector-vlm >"$here/server-before-one-card.started"
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
) >"$here/one-card.cards.csv" &
sampler=$!

if CARD_BDF=0000:17:00.0 step start-on-card-0 scripts/serve_vlm_xpu.sh start; then
    SPEC_TO_INSPECTOR_RUNS_DIR=$here/runs SPEC_TO_INSPECTOR_VLM_CARD=0000:17:00.0 \
        SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 \
        step bench .venv/bin/spec-to-inspector bench --limit 20 --batch one-card \
        --results "$here/bench.json" --readme "$here/README.md"
fi

sleep 5
kill "$sampler"
wait "$sampler" 2>/dev/null
docker logs spec-to-inspector-vlm >"$here/server-on-card-0.txt" 2>&1
step stop-card-0 scripts/serve_vlm_xpu.sh stop
step start-final scripts/serve_vlm_xpu.sh start
date -u +%FT%TZ >"$here/one-card.end"
