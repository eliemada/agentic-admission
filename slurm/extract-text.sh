#!/bin/bash
#SBATCH --job-name=extract-text
#SBATCH --partition=gpu
#SBATCH --qos=debug
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=slurm/logs/extract-text-%j.out
#SBATCH --error=slurm/logs/extract-text-%j.err

# ============================================================================
# Phase 1: Extract text from text-based PDFs (fast, CPU-only).
#
# Scanned PDFs are identified but NOT processed — run ocr-full.sh after
# to handle those with RolmOCR.
#
# Usage:
#   sbatch slurm/extract-text.sh
#   sbatch slurm/extract-text.sh --export=FORCE=1   # re-process all
# ============================================================================

set -euo pipefail

FORCE="${FORCE:-0}"
PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"

cd "$PROJECT_DIR"
mkdir -p slurm/logs

# ---------------------------------------------------------------------------
# 1. Install dependencies
# ---------------------------------------------------------------------------
module purge
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv sync --frozen

# ---------------------------------------------------------------------------
# 2. Run Phase 1 only (backend=none skips OCR)
# ---------------------------------------------------------------------------
INPUT_ROOT="${PROJECT_DIR}/data/processed/dossiers"
OUTPUT_ROOT="${PROJECT_DIR}/data/processed/texts"

if [ ! -d "$INPUT_ROOT" ]; then
    echo "[$(date)] ERROR: Input directory not found: $INPUT_ROOT"
    exit 1
fi

TOTAL_PDFS=$(find "$INPUT_ROOT" -name '*.pdf' -type f | wc -l)
echo "[$(date)] Found $TOTAL_PDFS PDFs in $INPUT_ROOT"

FORCE_FLAG=""
if [ "$FORCE" = "1" ]; then
    FORCE_FLAG="--force"
fi

echo "[$(date)] Phase 1: extracting embedded text ..."
uv run python -m agentic_admission.preprocessing.text_extraction \
    --input "$INPUT_ROOT" \
    --output "$OUTPUT_ROOT" \
    --backend none \
    $FORCE_FLAG

# ---------------------------------------------------------------------------
# 3. Report
# ---------------------------------------------------------------------------
echo ""
echo "============================================"
echo "  PHASE 1 RESULTS"
echo "============================================"

if [ -d "$OUTPUT_ROOT" ]; then
    FINAL_MDS=$(find "$OUTPUT_ROOT" -name '*.md' -type f | wc -l)
    REMAINING=$((TOTAL_PDFS - FINAL_MDS))
    echo "Total PDFs:       $TOTAL_PDFS"
    echo "Text extracted:   $FINAL_MDS"
    echo "Need OCR:         $REMAINING"
    echo ""
    echo "To OCR the remaining scanned PDFs, run:"
    echo "  sbatch slurm/ocr-full.sh"
fi

echo ""
echo "[$(date)] Phase 1 complete."
