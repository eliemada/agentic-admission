# SCITAS SLURM Scripts for Text Extraction

## Two-Phase Pipeline

1. **Phase 1** (`extract-text.sh`): Fast PyMuPDF text extraction for text-based PDFs (no GPU)
2. **Phase 2** (`ocr-full.sh`): RolmOCR via vLLM for scanned/image PDFs (GPU required)

## Quick Start

```bash
ssh <username>@izar.epfl.ch
cd ~/projects/agentic-admission
git pull

# Step 1: Extract text from all text-based PDFs (fast)
sbatch slurm/extract-text.sh

# Step 2: Check how many need OCR
find data/processed/texts -name '*.md' | wc -l   # done
# Compare with total:
find data/processed/dossiers -name '*.pdf' | wc -l

# Step 3: OCR the remaining scanned PDFs
sbatch slurm/ocr-full.sh
```

## Scripts

| Script | Purpose | Time | GPU |
|--------|---------|------|-----|
| `extract-text.sh` | Phase 1: PyMuPDF text extraction | ~10 min | 1 (uses debug QOS) |
| `ocr-trial.sh` | Test OCR on 5 PDFs | 1h | 1 |
| `ocr-full.sh` | Phase 1 + Phase 2 (full pipeline) | 12h | 1 |

## Incremental Processing

All scripts skip already-processed files. If a job times out, just resubmit:
```bash
sbatch slurm/ocr-full.sh   # picks up where it left off
```

## Logs

```bash
tail -f slurm/logs/<script>-<jobid>.out
tail -f slurm/logs/<script>-<jobid>.err
```
