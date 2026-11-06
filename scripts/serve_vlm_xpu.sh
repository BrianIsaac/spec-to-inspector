#!/usr/bin/env bash
# The judge's VLM server on the B70 machine: Intel's llm-scaler vLLM image at a pinned tag, serving
# Qwen3-VL-8B-Instruct at FP16 on one card, OpenAI-compatible, started as eval/PROTOCOL-stage2.md
# declares it. The laptop's server is scripts/serve_vlm.sh. The client is the same, and these two
# settings point it here; what else differs is below, and it is the server's start that holds it:
#
#   SPEC_TO_INSPECTOR_VLM_URL=http://127.0.0.1:8131/v1
#   SPEC_TO_INSPECTOR_VLM_MODEL=qwen3-vl-8b-instruct
#
#   scripts/serve_vlm_xpu.sh start    start the container, wait until the model answers /health
#   scripts/serve_vlm_xpu.sh stop     stop and remove the container
#   scripts/serve_vlm_xpu.sh status   say whether it is up, with the card's memory
#
# Only the judge's card is mapped into the container, so it cannot touch the anomaly model's. The
# weights come from the Hugging Face cache at HF_HOME, which needs the revision below downloaded.
set -euo pipefail

IMAGE="intel/llm-scaler-vllm:0.26.0-b1"
CONTAINER="spec-to-inspector-vlm"
WEIGHTS_REPO="Qwen/Qwen3-VL-8B-Instruct"
WEIGHTS_REVISION="0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"
SERVED_NAME="qwen3-vl-8b-instruct"
PORT="${PORT:-8131}"
HF_HOME="${HF_HOME:-$HOME/hf-cache}"
# xpu-smi's device 1: the card the plan gives the judge.
CARD_BDF="${CARD_BDF:-0000:ba:00.0}"
# With a card to itself the judge need not leave room for the anomaly model. At 0.8 FP16 leaves
# 2.97 GiB of cache, which vLLM refuses for a 32K context; at 0.9 it leaves 6.16 GiB (measured).
GPU_MEMORY_UTIL="${GPU_MEMORY_UTIL:-0.9}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
# The fewest pixels an image is given: a token is 32 x 32 px, so this gives a small crop 1,024 tokens,
# the size the pipeline has had since Stage I. The model's own minimum is 65536 (256 x 256, 64
# tokens), which is the protocol's image-minimum comparison and never the final figure.
IMAGE_MIN_PIXELS="${IMAGE_MIN_PIXELS:-1048576}"
IMAGE_MAX_PIXELS=16777216
# The protocol asks every question cold. vLLM ignores the client's cache_prompt, llama.cpp's own
# switch, so the cold is the server's: PREFIX_CACHE=on is for comparing, never for a bench.
PREFIX_CACHE="${PREFIX_CACHE:-off}"
START_TIMEOUT_SECONDS=900

card_paths() {
    readlink -f "/dev/dri/by-path/pci-$CARD_BDF-card"
    readlink -f "/dev/dri/by-path/pci-$CARD_BDF-render"
}

start() {
    local card render snapshot started cache_flags=""
    if [[ "$PREFIX_CACHE" == "off" ]]; then
        cache_flags="--no-enable-prefix-caching --mm-processor-cache-gb 0"
    fi
    mapfile -t paths < <(card_paths)
    card=${paths[0]}
    render=${paths[1]}
    snapshot="/root/.cache/huggingface/hub/models--${WEIGHTS_REPO//\//--}/snapshots/$WEIGHTS_REVISION"
    started=$(date +%s)
    docker run -d \
        --name "$CONTAINER" \
        --net=host \
        --shm-size=32g \
        --device "$render:$render" \
        --device "$card:$card" \
        --mount "type=bind,source=/dev/dri/by-path/pci-$CARD_BDF-card,target=/dev/dri/by-path/pci-$CARD_BDF-card" \
        --mount "type=bind,source=/dev/dri/by-path/pci-$CARD_BDF-render,target=/dev/dri/by-path/pci-$CARD_BDF-render" \
        -v "$HF_HOME:/root/.cache/huggingface" \
        -e HF_HUB_OFFLINE=1 \
        -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 \
        -e VLLM_WORKER_MULTIPROC_METHOD=spawn \
        --entrypoint bash \
        "$IMAGE" -c "source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1; exec vllm serve \
            --model $snapshot \
            --served-model-name $SERVED_NAME \
            --dtype=float16 \
            --enforce-eager \
            --port $PORT \
            --host 127.0.0.1 \
            --trust-remote-code \
            --disable-sliding-window \
            --gpu-memory-util=$GPU_MEMORY_UTIL \
            --max-model-len=$MAX_MODEL_LEN \
            --max-num-batched-tokens=$MAX_MODEL_LEN \
            --block-size 64 \
            --limit-mm-per-prompt '{\"image\": 2}' \
            --mm-processor-kwargs '{\"size\": {\"shortest_edge\": $IMAGE_MIN_PIXELS, \"longest_edge\": $IMAGE_MAX_PIXELS}}' \
            $cache_flags \
            -tp=1"
    while ! curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; do
        if [[ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" != "true" ]]; then
            docker logs --tail 60 "$CONTAINER" >&2
            echo "the server stopped during start-up" >&2
            exit 1
        fi
        if (($(date +%s) - started > START_TIMEOUT_SECONDS)); then
            echo "the server did not answer within $START_TIMEOUT_SECONDS s" >&2
            exit 1
        fi
        sleep 2
    done
    echo "Up in $(($(date +%s) - started)) s: http://127.0.0.1:$PORT/v1, model $SERVED_NAME, $IMAGE"
}

stop() {
    docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
    echo "Stopped $CONTAINER"
}

status() {
    if curl -sf "http://127.0.0.1:$PORT/health" >/dev/null; then
        echo "Up: http://127.0.0.1:$PORT/v1, model $SERVED_NAME, $IMAGE"
    else
        echo "Not answering on port $PORT"
    fi
    docker ps --filter "name=$CONTAINER" --format '{{.Names}} {{.Status}}'
}

case "${1:-}" in
start) start ;;
stop) stop ;;
status) status ;;
*)
    echo "usage: $0 start|stop|status" >&2
    exit 2
    ;;
esac
