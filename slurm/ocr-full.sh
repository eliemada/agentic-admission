#!/bin/bash
#SBATCH --job-name=ocr-full
#SBATCH --partition=gpu
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=12:00:00
#SBATCH --output=slurm/logs/ocr-full-%j.out
#SBATCH --error=slurm/logs/ocr-full-%j.err

# ============================================================================
# Full OCR Run — process all dossier PDFs with RolmOCR.
#
# Skips already-converted files by default (incremental).
# Use --export=FORCE=1 to re-process everything.
#
# Usage:
#   sbatch slurm/ocr-full.sh
#   sbatch slurm/ocr-full.sh --export=FORCE=1   # re-process all
# ============================================================================

set -euo pipefail

VLLM_PORT=8001
FORCE="${FORCE:-0}"
PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"

cd "$PROJECT_DIR"
mkdir -p slurm/logs

# ---------------------------------------------------------------------------
# 1. Load modules
# ---------------------------------------------------------------------------
module purge
module load gcc python cuda

# ---------------------------------------------------------------------------
# 2. Install dependencies
# ---------------------------------------------------------------------------
if ! command -v uv &> /dev/null; then
    pip install --user uv
fi
uv sync --frozen

# vLLM is infra, not an app dependency — install it alongside
pip install --user vllm

# ---------------------------------------------------------------------------
# 3. Pre-download model weights
# ---------------------------------------------------------------------------
export HF_HOME="${SCRATCH:-/tmp}/.cache/huggingface"
echo "[$(date)] Ensuring model weights are cached at $HF_HOME ..."
uv run python -c "from huggingface_hub import snapshot_download; snapshot_download('reducto/RolmOCR')"

# ---------------------------------------------------------------------------
# 4. Start vLLM server
# ---------------------------------------------------------------------------
echo "[$(date)] Starting vLLM server on port $VLLM_PORT ..."
export VLLM_USE_V1=1
uv run vllm serve reducto/RolmOCR \
    --port "$VLLM_PORT" \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.90 \
    &

VLLM_PID=$!

# Cleanup on exit
cleanup() {
    echo "[$(date)] Shutting down vLLM (PID $VLLM_PID) ..."
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
}
trap cleanup EXIT

# Wait for vLLM
echo "[$(date)] Waiting for vLLM to start ..."
for i in $(seq 1 60); do
    if curl -sf "http://localhost:${VLLM_PORT}/health" > /dev/null 2>&1; then
        echo "[$(date)] vLLM is ready after ~${i}s"
        break
    fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "[$(date)] ERROR: vLLM process died."
        exit 1
    fi
    sleep 5
done

if ! curl -sf "http://localhost:${VLLM_PORT}/health" > /dev/null 2>&1; then
    echo "[$(date)] ERROR: vLLM failed to start within 300s"
    exit 1
fi

# ---------------------------------------------------------------------------
# 5. Count input files
# ---------------------------------------------------------------------------
INPUT_ROOT="${PROJECT_DIR}/data/processed/dossiers"
OUTPUT_ROOT="${PROJECT_DIR}/data/processed/texts"

if [ ! -d "$INPUT_ROOT" ]; then
    echo "[$(date)] ERROR: Input directory not found: $INPUT_ROOT"
    exit 1
fi

TOTAL_PDFS=$(find "$INPUT_ROOT" -name '*.pdf' -type f | wc -l)
echo "[$(date)] Found $TOTAL_PDFS PDFs in $INPUT_ROOT"

if [ -d "$OUTPUT_ROOT" ]; then
    EXISTING_MDS=$(find "$OUTPUT_ROOT" -name '*.md' -type f | wc -l)
    echo "[$(date)] Existing markdown files: $EXISTING_MDS"
fi

# ---------------------------------------------------------------------------
# 6. Run the extraction pipeline
# ---------------------------------------------------------------------------
export VLM_MODEL_NAME="reducto/RolmOCR"
export VLM_BASE_URL="http://localhost:${VLLM_PORT}/v1"

FORCE_FLAG=""
if [ "$FORCE" = "1" ]; then
    FORCE_FLAG="--force"
    echo "[$(date)] FORCE mode: re-processing all files"
fi

echo "[$(date)] Starting extraction ..."
uv run python -m agentic_admission.preprocessing.text_extraction \
    --input "$INPUT_ROOT" \
    --output "$OUTPUT_ROOT" \
    --backend api \
    $FORCE_FLAG

# ---------------------------------------------------------------------------
# 7. Final report
# ---------------------------------------------------------------------------
echo ""
echo "============================================"
echo "  FULL RUN RESULTS"
echo "============================================"

if [ -d "$OUTPUT_ROOT" ]; then
    FINAL_MDS=$(find "$OUTPUT_ROOT" -name '*.md' -type f | wc -l)
    echo "Total PDFs:      $TOTAL_PDFS"
    echo "Markdown files:  $FINAL_MDS"
    echo "Output dir:      $OUTPUT_ROOT"
else
    echo "ERROR: Output directory was not created."
fi

echo ""
echo "[$(date)] Full extraction complete."
