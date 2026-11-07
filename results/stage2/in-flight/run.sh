#!/usr/bin/env bash
# The in-flight measurement on the machine. Writes ~/in-flight/in-flight.{pid,start,end,exit,out,cards.csv}.
here=$HOME/in-flight
cd "$HOME/spec-to-inspector" || exit 1
echo $$ >"$here/in-flight.pid"
date -u +%FT%TZ >"$here/in-flight.start"
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
) >"$here/in-flight.cards.csv" &
sampler=$!
SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 .venv/bin/python "$here/in_flight.py.txt" \
    --run runs/pcb1/corrections --part pcb1 --out "$here/in-flight.json" >"$here/in-flight.out" 2>&1 &
process=$!
echo "$process" >"$here/in-flight.process"
wait "$process"
code=$?
sleep 5
kill "$sampler"
wait "$sampler" 2>/dev/null
echo "$code" >"$here/in-flight.exit"
date -u +%FT%TZ >"$here/in-flight.end"
