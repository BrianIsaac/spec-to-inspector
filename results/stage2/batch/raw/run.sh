#!/usr/bin/env bash
# One run of the whole batch on the machine, each part in turn. Usage: run.sh <run-name>
# Writes ~/batch-run/<name>.{pid,start,end,exit,cards.csv} and <name>.<part>.{pid,start,end,exit,out}.
# Both cards are read every 5 s from before the first part starts until after the last one ends.
name=$1
here=$HOME/batch-run
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

code=0
for part in pcb1 pcb4; do
    date -u +%FT%TZ >"$here/$name.$part.start"
    SPEC_TO_INSPECTOR_DEVICE=xpu ZE_AFFINITY_MASK=0 .venv/bin/spec-to-inspector inspect \
        --category "$part" --spec specs/pcb-spec.pdf --test-split --batch batch \
        --record "results/stage2/batch/$part.json" >"$here/$name.$part.out" 2>&1 &
    process=$!
    echo "$process" >"$here/$name.$part.pid"
    wait "$process"
    code=$?
    date -u +%FT%TZ >"$here/$name.$part.end"
    echo "$code" >"$here/$name.$part.exit"
    [ "$code" -ne 0 ] && break
done

sleep 5
kill "$sampler"
wait "$sampler" 2>/dev/null
date -u +%FT%TZ >"$here/$name.end"
echo "$code" >"$here/$name.exit"
