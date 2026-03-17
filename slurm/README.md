# SCITAS SLURM Scripts for OCR Pipeline

## Quick Start

```bash
# 1. SSH into the cluster
ssh <username>@izar.epfl.ch

# 2. Clone the repo (or pull latest)
cd $SCRATCH
git clone <repo-url> agentic-admission
cd agentic-admission

# 3. Copy your .env
cp .env.example .env
# Edit .env: set VLM_MODEL_NAME=reducto/RolmOCR

# 4. Install Python deps
module load gcc python cuda
pip install uv
uv sync --frozen

# 5. Trial run (5 PDFs)
sbatch slurm/ocr-trial.sh

# 6. Check output
cat slurm/logs/ocr-trial-<jobid>.out

# 7. If trial looks good → full run
sbatch slurm/ocr-full.sh
```

## Scripts

| Script | Purpose | Time | GPUs |
|--------|---------|------|------|
| `ocr-trial.sh` | Test on first 5 PDFs | 1h | 1 |
| `ocr-full.sh` | Process all dossiers | 12h | 1 |

## Logs

All logs go to `slurm/logs/`. Check with:
```bash
tail -f slurm/logs/ocr-trial-<jobid>.out
```
