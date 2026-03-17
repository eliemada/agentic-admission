#!/bin/bash
#SBATCH --job-name=ocr-trial
#SBATCH --partition=gpu
#SBATCH --qos=debug
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=slurm/logs/ocr-trial-%j.out
#SBATCH --error=slurm/logs/ocr-trial-%j.err

# ============================================================================
# OCR Trial Run — test RolmOCR on a handful of PDFs before scaling up.
#
# Usage:
#   sbatch slurm/ocr-trial.sh
#   sbatch slurm/ocr-trial.sh --export=MAX_PDFS=10   # override count
# ============================================================================

set -euo pipefail

MAX_PDFS="${MAX_PDFS:-5}"
VLLM_PORT=8001
PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"

cd "$PROJECT_DIR"
mkdir -p slurm/logs

# ---------------------------------------------------------------------------
# 1. Clean environment — PyTorch/vLLM bundle their own CUDA runtime,
#    so we avoid loading system CUDA modules that can conflict.
# ---------------------------------------------------------------------------
module purge

# ---------------------------------------------------------------------------
# 2. Install dependencies (uv manages Python 3.12+)
# ---------------------------------------------------------------------------
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv sync --frozen

# vLLM is infra, not an app dependency — install into the project venv
uv pip install vllm

# ---------------------------------------------------------------------------
# 3. Pre-download model weights (uses HF cache on scratch)
# ---------------------------------------------------------------------------
export HF_HOME="${SCRATCH:-/tmp}/.cache/huggingface"
echo "[$(date)] Ensuring model weights are cached at $HF_HOME ..."
uv run python -c "from huggingface_hub import snapshot_download; snapshot_download('reducto/RolmOCR')"

# ---------------------------------------------------------------------------
# 4. Start vLLM server in the background
# ---------------------------------------------------------------------------
echo "[$(date)] Starting vLLM server on port $VLLM_PORT ..."
uv run vllm serve reducto/RolmOCR \
    --port "$VLLM_PORT" \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.85 \
    --enforce-eager \
    &

VLLM_PID=$!
echo "[$(date)] vLLM PID: $VLLM_PID"

# Wait for vLLM to be ready (health endpoint)
echo "[$(date)] Waiting for vLLM to start (may take 5-10 min on V100) ..."
for i in $(seq 1 120); do
    if curl -sf "http://localhost:${VLLM_PORT}/health" > /dev/null 2>&1; then
        echo "[$(date)] vLLM is ready after ~$((i * 5))s"
        break
    fi
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        echo "[$(date)] ERROR: vLLM process died. Check logs above."
        exit 1
    fi
    sleep 5
done

# Verify it's actually up
if ! curl -sf "http://localhost:${VLLM_PORT}/health" > /dev/null 2>&1; then
    echo "[$(date)] ERROR: vLLM failed to start within 600s"
    kill "$VLLM_PID" 2>/dev/null || true
    exit 1
fi

# ---------------------------------------------------------------------------
# 5. Prepare trial input: symlink first N PDFs into a temp directory
# ---------------------------------------------------------------------------
TRIAL_DIR=$(mktemp -d "${TMPDIR:-/tmp}/ocr-trial-XXXXXX")
TRIAL_OUTPUT="${PROJECT_DIR}/data/processed/texts_trial"
INPUT_ROOT="${PROJECT_DIR}/data/processed/dossiers"

echo "[$(date)] Selecting first $MAX_PDFS PDFs from $INPUT_ROOT ..."

if [ ! -d "$INPUT_ROOT" ]; then
    echo "[$(date)] ERROR: Input directory not found: $INPUT_ROOT"
    echo "  Make sure dossier PDFs are at data/processed/dossiers/<semester>/<candidate>/*.pdf"
    kill "$VLLM_PID" 2>/dev/null || true
    exit 1
fi

COUNT=0
while IFS= read -r pdf; do
    [ "$COUNT" -ge "$MAX_PDFS" ] && break
    REL="${pdf#"$INPUT_ROOT"/}"
    DEST="${TRIAL_DIR}/${REL}"
    mkdir -p "$(dirname "$DEST")"
    ln -s "$pdf" "$DEST"
    COUNT=$((COUNT + 1))
    echo "  [$COUNT] $REL"
done < <(find "$INPUT_ROOT" -name '*.pdf' -type f | sort | head -n "$MAX_PDFS")

echo "[$(date)] Prepared $COUNT PDFs for trial in $TRIAL_DIR"

# ---------------------------------------------------------------------------
# 6. Run the extraction pipeline
# ---------------------------------------------------------------------------
export VLM_MODEL_NAME="reducto/RolmOCR"
export VLM_BASE_URL="http://localhost:${VLLM_PORT}/v1"

echo "[$(date)] Running extraction: $TRIAL_DIR -> $TRIAL_OUTPUT"
uv run python -m agentic_admission.preprocessing.text_extraction \
    --input "$TRIAL_DIR" \
    --output "$TRIAL_OUTPUT" \
    --backend api \
    --force

# ---------------------------------------------------------------------------
# 7. Report results
# ---------------------------------------------------------------------------
echo ""
echo "============================================"
echo "  TRIAL RESULTS"
echo "============================================"
echo "Output directory: $TRIAL_OUTPUT"

if [ -d "$TRIAL_OUTPUT" ]; then
    MD_COUNT=$(find "$TRIAL_OUTPUT" -name '*.md' | wc -l)
    echo "Markdown files produced: $MD_COUNT / $COUNT"
    echo ""
    echo "Sample output (first file):"
    echo "--------------------------------------------"
    FIRST_MD=$(find "$TRIAL_OUTPUT" -name '*.md' -type f | head -1)
    if [ -n "$FIRST_MD" ]; then
        head -50 "$FIRST_MD"
    else
        echo "(no markdown files found — check errors above)"
    fi
    echo "--------------------------------------------"
else
    echo "ERROR: Output directory was not created."
fi

# ---------------------------------------------------------------------------
# 8. Cleanup
# ---------------------------------------------------------------------------
rm -rf "$TRIAL_DIR"
kill "$VLLM_PID" 2>/dev/null || true
wait "$VLLM_PID" 2>/dev/null || true

echo ""
echo "[$(date)] Trial complete. If output looks good, run:"
echo "  sbatch slurm/ocr-full.sh"
