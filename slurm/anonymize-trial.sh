#!/bin/bash
#SBATCH --job-name=anon-trial
#SBATCH --partition=gpu
#SBATCH --qos=debug
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --output=slurm/logs/anon-trial-%j.out
#SBATCH --error=slurm/logs/anon-trial-%j.err

# ============================================================================
# Anonymization Trial — process a small sample to verify PII detection.
#
# Usage:
#   sbatch slurm/anonymize-trial.sh
# ============================================================================

set -euo pipefail

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

# Download spaCy model if missing (use uv pip, not spacy download which needs pip)
uv run python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null \
    || uv pip install "en_core_web_sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"

# GLiNER model cache
export HF_HOME="${SCRATCH:-/tmp}/.cache/huggingface"

# ---------------------------------------------------------------------------
# 3. Run anonymization on 20-file sample
# ---------------------------------------------------------------------------
echo "[$(date)] Starting anonymization trial (20 files) ..."

uv run python -m agentic_admission.anonymizer.presidio_pipeline \
    --input data/processed/texts \
    --output data/processed/anonymized \
    --sample 20

echo ""
echo "[$(date)] Trial complete. Check output in data/processed/anonymized/"
echo ""

# Show a sample of what was anonymized
echo "=== Sample anonymized files ==="
SAMPLE_FILE=$(find data/processed/anonymized -name '*.md' -type f | head -1)
if [ -n "$SAMPLE_FILE" ]; then
    echo "--- $SAMPLE_FILE ---"
    head -50 "$SAMPLE_FILE"
fi
