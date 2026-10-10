#!/usr/bin/env bash
# The judge's VLM server on the laptop: llama.cpp's llama-server, OpenAI-compatible, serving
# Qwen3-VL-8B-Instruct (Qwen's own Q4_K_M weights and F16 projector) from one GPU.
#
#   scripts/serve_vlm.sh build    clone llama.cpp at the pinned tag and build llama-server for CUDA
#   scripts/serve_vlm.sh fetch    download the weights and the projector, and verify their digests
#   scripts/serve_vlm.sh start    build and fetch if needed, start the server, wait until it answers
#   scripts/serve_vlm.sh stop     stop the llama-server listening on the port, by pid
#   scripts/serve_vlm.sh status   say whether it is up, with its pid and its GPU memory
#   scripts/serve_vlm.sh run      as start, but in the foreground
#
# Where things live comes from the settings (`.env` or SPEC_TO_INSPECTOR_* variables): the
# weights under <models_dir>/qwen3-vl-8b-instruct-gguf/, the clone and the build under
# <llama_cpp_dir>/, the address from vlm_url. Only the laptop backend is started here; a
# vLLM or llm-scaler server on the B70 is a URL and a model name in the settings.
set -euo pipefail
cd "$(dirname "$0")/.."

LLAMA_REPO="https://github.com/ggml-org/llama.cpp"
LLAMA_TAG="v0.6.0"
LLAMA_COMMIT="d81235049384534c167caea52b85a694f6103d14"
CUDA_ROOT="${CUDA_ROOT:-/usr/local/cuda-13.0}"
CUDA_ARCHITECTURE="120"
BUILD_JOBS="${BUILD_JOBS:-8}"

WEIGHTS_REPO="Qwen/Qwen3-VL-8B-Instruct-GGUF"
WEIGHTS_REVISION="f982a07559d4a2f6c8744d840bf6fccab30eea96"
MODEL_FILE="Qwen3VL-8B-Instruct-Q4_K_M.gguf"
MODEL_SHA256="67d1659bfe71b89d50b45a4ad1a9e5b997e5bb16ce5da66a6a6167abd569e9e2"
MMPROJ_FILE="mmproj-Qwen3VL-8B-Instruct-F16.gguf"
MMPROJ_SHA256="ca524100ebf825c9a870db1c580d03879e0da0ab2541697e2458e64891cf9d38"

CONTEXT_TOKENS=16384
# The fewest tokens an image is given; a small crop is enlarged to it. llama.cpp warns that
# Qwen-VL needs 1024 to see properly. IMAGE_MIN_TOKENS=0 leaves the model's own minimum.
IMAGE_MIN_TOKENS="${IMAGE_MIN_TOKENS:-1024}"
START_TIMEOUT_SECONDS=300
STOP_TIMEOUT_SECONDS=30

mapfile -t SETTINGS < <(uv run python -m spec_to_inspector.judge.serving)
MODELS_DIR="${SETTINGS[0]}"
LLAMA_DIR="${SETTINGS[1]}"
HOST="${SETTINGS[2]}"
PORT="${SETTINGS[3]}"
MODEL_NAME="${SETTINGS[4]}"

WEIGHTS_DIR="$MODELS_DIR/qwen3-vl-8b-instruct-gguf"
SOURCE_DIR="$LLAMA_DIR/src"
BUILD_DIR="$LLAMA_DIR/build"
SERVER="$BUILD_DIR/bin/llama-server"
LOG_FILE="$LLAMA_DIR/llama-server.log"

seconds_since() {
    echo $(($(date +%s) - $1))
}

build() {
    local started
    started=$(date +%s)
    mkdir -p "$LLAMA_DIR"
    if [[ ! -d "$SOURCE_DIR/.git" ]]; then
        git clone --depth 1 --branch "$LLAMA_TAG" "$LLAMA_REPO" "$SOURCE_DIR"
    fi
    local head
    head=$(git -C "$SOURCE_DIR" rev-parse HEAD)
    if [[ "$head" != "$LLAMA_COMMIT" ]]; then
        echo "$SOURCE_DIR is at $head, not $LLAMA_TAG ($LLAMA_COMMIT): remove it and build again" >&2
        exit 1
    fi
    cmake -S "$SOURCE_DIR" -B "$BUILD_DIR" \
        -DCMAKE_BUILD_TYPE=Release \
        -DGGML_CUDA=ON \
        -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCHITECTURE" \
        -DCMAKE_CUDA_COMPILER="$CUDA_ROOT/bin/nvcc" \
        -DCUDAToolkit_ROOT="$CUDA_ROOT" \
        -DLLAMA_BUILD_TESTS=OFF \
        -DLLAMA_BUILD_EXAMPLES=OFF \
        -DLLAMA_USE_PREBUILT_UI=OFF \
        -DLLAMA_OPENSSL=OFF
    cmake --build "$BUILD_DIR" --target llama-server -j "$BUILD_JOBS"
    echo "Built $SERVER at $LLAMA_TAG in $(seconds_since "$started") s:" \
        "source $(du -sh "$SOURCE_DIR" | cut -f1), build $(du -sh "$BUILD_DIR" | cut -f1)"
}

fetch_one() {
    local name=$1 digest=$2 target="$WEIGHTS_DIR/$1"
    if [[ ! -f "$target" ]]; then
        curl --fail --location --continue-at - --output "$target.part" \
            "https://huggingface.co/$WEIGHTS_REPO/resolve/$WEIGHTS_REVISION/$name"
        mv "$target.part" "$target"
    fi
    echo "$digest  $target" | sha256sum --check --quiet
    echo "Verified $target: $(stat --format=%s "$target") bytes, sha256 $digest"
}

fetch() {
    local started
    started=$(date +%s)
    mkdir -p "$WEIGHTS_DIR"
    fetch_one "$MODEL_FILE" "$MODEL_SHA256"
    fetch_one "$MMPROJ_FILE" "$MMPROJ_SHA256"
    echo "Weights ready in $(seconds_since "$started") s under $WEIGHTS_DIR"
}

listening_pid() {
    ss -ltnpH "sport = :$PORT" | grep -oP 'pid=\K[0-9]+' | head -n 1 || true
}

ensure_ready() {
    [[ -x "$SERVER" ]] || build
    [[ -f "$WEIGHTS_DIR/$MODEL_FILE" && -f "$WEIGHTS_DIR/$MMPROJ_FILE" ]] || fetch
    local pid
    pid=$(listening_pid)
    if [[ -n "$pid" ]]; then
        echo "port $PORT is already taken by pid $pid ($(cat "/proc/$pid/comm" 2>/dev/null))" >&2
        exit 1
    fi
}

# One slot holds the whole 16K context, and the prompt cache keeps the last prompt's prefix
# in it: the clause table comes first in every prompt, so only what follows it is evaluated.
server_arguments() {
    SERVER_ARGUMENTS=(
        --model "$WEIGHTS_DIR/$MODEL_FILE"
        --mmproj "$WEIGHTS_DIR/$MMPROJ_FILE"
        --alias "$MODEL_NAME"
        --host "$HOST"
        --port "$PORT"
        --ctx-size "$CONTEXT_TOKENS"
        --parallel 1
        --n-gpu-layers 99
        --cache-prompt
        --jinja
        --no-webui
    )
    if [[ "$IMAGE_MIN_TOKENS" != 0 ]]; then
        SERVER_ARGUMENTS+=(--image-min-tokens "$IMAGE_MIN_TOKENS")
    fi
}

# Stop one process of ours: ask it to end, wait, and only then insist.
end_process() {
    local pid=$1 waited=0
    kill "$pid" 2>/dev/null || return 0
    while kill -0 "$pid" 2>/dev/null; do
        if ((waited >= STOP_TIMEOUT_SECONDS * 5)); then
            echo "pid $pid did not end within $STOP_TIMEOUT_SECONDS s of SIGTERM: sending SIGKILL" >&2
            kill -KILL "$pid" 2>/dev/null || true
            break
        fi
        sleep 0.2
        waited=$((waited + 1))
    done
}

start() {
    ensure_ready
    server_arguments
    local started server_pid
    started=$(date +%s)
    # A script's background child is not a process group leader, so setsid does not fork:
    # the pid of the job is the server's own.
    nohup setsid "$SERVER" "${SERVER_ARGUMENTS[@]}" >"$LOG_FILE" 2>&1 &
    server_pid=$!
    until curl --silent --fail --output /dev/null "http://$HOST:$PORT/health"; do
        if ! kill -0 "$server_pid" 2>/dev/null; then
            echo "llama-server exited while starting; see $LOG_FILE" >&2
            exit 1
        fi
        if (($(seconds_since "$started") > START_TIMEOUT_SECONDS)); then
            echo "llama-server did not answer within $START_TIMEOUT_SECONDS s; see $LOG_FILE" >&2
            end_process "$server_pid"
            exit 1
        fi
        sleep 1
    done
    echo "llama-server is up on http://$HOST:$PORT/v1 as $MODEL_NAME" \
        "(pid $(listening_pid), ready in $(seconds_since "$started") s, log $LOG_FILE)"
}

stop() {
    local pid
    pid=$(listening_pid)
    if [[ -z "$pid" ]]; then
        echo "nothing is listening on port $PORT"
        return
    fi
    if [[ "$(cat "/proc/$pid/comm" 2>/dev/null || true)" != "llama-server" ]]; then
        echo "pid $pid on port $PORT is not llama-server: left alone" >&2
        exit 1
    fi
    end_process "$pid"
    echo "stopped llama-server, pid $pid"
}

status() {
    local pid
    pid=$(listening_pid)
    if [[ -z "$pid" ]]; then
        echo "down: nothing is listening on port $PORT"
        return 1
    fi
    local memory
    memory=$(nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader,nounits \
        2>/dev/null | awk -F', ' -v pid="$pid" '$1 == pid { print $2 }' || true)
    echo "up: pid $pid on http://$HOST:$PORT/v1, ${memory:-unknown} MiB on the GPU"
}

case "${1:-}" in
    build) build ;;
    fetch) fetch ;;
    start) start ;;
    stop) stop ;;
    status) status ;;
    run)
        ensure_ready
        server_arguments
        exec "$SERVER" "${SERVER_ARGUMENTS[@]}"
        ;;
    *)
        echo "usage: scripts/serve_vlm.sh build|fetch|start|stop|status|run" >&2
        exit 2
        ;;
esac
