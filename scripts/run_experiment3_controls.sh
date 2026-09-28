#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"
GLIMMER_PYTHON="${GLIMMER_PYTHON:-$PYTHON}"
SOURCE="${SOURCE:-experiments/03_definition_to_carrier/results/rolling}"
OUTPUT="${OUTPUT:-runs/experiment3_controls}"
TRIALS="${TRIALS:-20}"
export HF_HUB_OFFLINE=1
export PYTHONUNBUFFERED=1
models=(Qwen2.5-0.5B-Instruct Qwen2.5-3B-Instruct Mistral-7B-Instruct-v0.1 Meta-Llama-3.1-8B-Instruct Muse-Glimmer-30B)
mkdir -p "$OUTPUT"
trap 'echo "FAILED at line $LINENO (exit $?)"' ERR
for name in "${models[@]}"; do
    "$PYTHON" scripts/run_marker_controls.py --input "$SOURCE/$name.csv" \
        --output "$OUTPUT/$name.csv" --trials "$TRIALS" --validate-only
done
cp docs/REPRODUCIBILITY.md "$OUTPUT/SETUP.md"
for name in "${models[@]}"; do
    idle_checks=0
    while (( idle_checks < 3 )); do
        processes="$(nvidia-smi --query-compute-apps=pid --format=csv,noheader,nounits)"
        if [[ -z "$processes" ]]; then
            idle_checks=$((idle_checks + 1))
        else
            idle_checks=0
            echo "$(date -Is) Waiting for GPU compute processes to exit: $processes"
        fi
        sleep 20
    done
    executable="$PYTHON"
    if [[ "$name" == Muse-Glimmer-30B ]]; then executable="$GLIMMER_PYTHON"; fi
    echo "$(date -Is) Starting controls: $name"
    "$executable" scripts/run_marker_controls.py --input "$SOURCE/$name.csv" \
        --output "$OUTPUT/$name.csv" --trials "$TRIALS" 2>&1 | tee "$OUTPUT/$name.log"
done
echo "$(date -Is) COMPLETE: all five control sets and heatmaps"
