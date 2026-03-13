"""Intake: scan dossier trees, match to candidates, and ingest archives."""

from agentic_admission.intake.adapter import ingest
from agentic_admission.intake.matcher import match_dossiers_to_candidates
from agentic_admission.intake.scanner import scan_dossier_tree
from agentic_admission.intake.validator import triage_batch, triage_dossier

__all__ = [
    "ingest",
    "match_dossiers_to_candidates",
    "scan_dossier_tree",
    "triage_batch",
    "triage_dossier",
]
