#!/bin/bash
#SBATCH --job-name=anon-full
#SBATCH --partition=gpu
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=06:00:00
#SBATCH --output=slurm/logs/anon-full-%j.out
#SBATCH --error=slurm/logs/anon-full-%j.err

# ============================================================================
# Full Anonymization — detect and redact PII from all extracted texts.
#
# Uses GLiNER on GPU for fast NER inference + Presidio for redaction.
# Incremental: skips already-anonymized files unless FORCE=1.
#
# Usage:
#   sbatch slurm/anonymize-full.sh
#   sbatch --export=FORCE=1 slurm/anonymize-full.sh   # re-process all
# ============================================================================

set -euo pipefail

FORCE="${FORCE:-0}"
PROJECT_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"

cd "$PROJECT_DIR"
mkdir -p slurm/logs

# ---------------------------------------------------------------------------
# 1. Clean environment — let uv manage Python
# ---------------------------------------------------------------------------
module purge

# ---------------------------------------------------------------------------
# 2. Install dependencies
# ---------------------------------------------------------------------------
export PATH="$HOME/.local/bin:$PATH"
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
uv sync --frozen

# GLiNER model cache
export HF_HOME="${SCRATCH:-/tmp}/.cache/huggingface"

# ---------------------------------------------------------------------------
# 3. Count input files
# ---------------------------------------------------------------------------
INPUT_ROOT="data/processed/texts"
OUTPUT_ROOT="data/processed/anonymized"

TOTAL_MDS=$(find "$INPUT_ROOT" -name '*.md' -type f | wc -l)
echo "[$(date)] Found $TOTAL_MDS markdown files to anonymize"

if [ -d "$OUTPUT_ROOT" ]; then
    EXISTING=$(find "$OUTPUT_ROOT" -name '*.md' -type f | wc -l)
    echo "[$(date)] Already anonymized: $EXISTING"
fi

# ---------------------------------------------------------------------------
# 4. Run anonymization pipeline
# ---------------------------------------------------------------------------
FORCE_FLAG=""
if [ "$FORCE" = "1" ]; then
    FORCE_FLAG="--force"
    echo "[$(date)] FORCE mode: re-processing all files"
fi

echo "[$(date)] Starting full anonymization (GLiNER on GPU) ..."

uv run python -m agentic_admission.anonymizer.presidio_pipeline \
    --input "$INPUT_ROOT" \
    --output "$OUTPUT_ROOT" \
    $FORCE_FLAG

# ---------------------------------------------------------------------------
# 5. Final report
# ---------------------------------------------------------------------------
echo ""
echo "============================================"
echo "  ANONYMIZATION RESULTS"
echo "============================================"

if [ -d "$OUTPUT_ROOT" ]; then
    FINAL=$(find "$OUTPUT_ROOT" -name '*.md' -type f | wc -l)
    echo "Input files:       $TOTAL_MDS"
    echo "Anonymized files:  $FINAL"
    echo "Output dir:        $OUTPUT_ROOT"
else
    echo "ERROR: Output directory was not created."
fi

echo ""
echo "[$(date)] Anonymization complete."
