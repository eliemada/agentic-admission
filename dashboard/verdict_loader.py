"""Load real verdict JSON files for the review dashboard."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pyarrow.parquet as pq

_ROLE_DISPLAY = {
    "academic": "Academic",
    "reference": "Reference",
    "motivation": "Motivation",
    "devils_advocate": "Devil's Advocate",
    "chair": "Chair",
}

_DECISION_TO_STATUS = {
    "accept": "admit",
    "reject": "reject",
    "waitlist": "discuss",
}

_SEMESTER_RE = re.compile(r"^(\d{4}-\d{2}-(?:fall|spring|summer))")


def _parse_scores(raw: dict | str) -> dict[str, int]:
    """Parse scores that may be a dict or a Python repr string."""
    if isinstance(raw, dict):
        return {k: int(v) for k, v in raw.items()}
    if isinstance(raw, str) and raw.startswith("{"):
        try:
            return {k: int(v) for k, v in ast.literal_eval(raw).items()}
        except (ValueError, SyntaxError):
            return {}
    return {}


def _parse_justifications(raw: dict | str) -> dict[str, dict[str, list[str]]]:
    """Parse justifications that may be structured pros/cons or legacy strings.

    Returns a dict mapping dimension name to {"pros": [...], "cons": [...]}.
    Handles both new structured format and legacy single-string format.
    """
    if isinstance(raw, str) and raw.startswith("{"):
        try:
            raw = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return {}
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, list[str]]] = {}
    for dim, val in raw.items():
        if isinstance(val, dict) and ("pros" in val or "cons" in val):
            result[dim] = {
                "pros": list(val.get("pros", [])),
                "cons": list(val.get("cons", [])),
            }
        elif isinstance(val, str):
            result[dim] = {"pros": [val] if val else [], "cons": []}
        else:
            result[dim] = {"pros": [], "cons": []}
    return result


def _parse_role(raw: str) -> str:
    """Parse role from either 'AgentRole.ACADEMIC' or 'academic' format."""
    if "." in raw:
        return raw.rsplit(".", maxsplit=1)[-1].lower()
    return raw.lower()


def _parse_decision(raw: str) -> str:
    """Parse decision from either 'Decision.REJECT' or 'reject' format."""
    if "." in raw:
        return raw.rsplit(".", maxsplit=1)[-1].lower()
    return raw.lower()


def _extract_institution_from_scorecard(scorecard: dict) -> str:
    """Try to extract institution name from the academic evaluator's justification."""
    role = _parse_role(scorecard.get("role", ""))
    if role != "academic":
        return ""
    justifications = _parse_justifications(scorecard.get("justifications", {}))
    inst = justifications.get("institution_quality", {})
    if isinstance(inst, dict):
        pros = inst.get("pros", [])
        return pros[0] if pros else ""
    return str(inst) if inst else ""


def _scorecard_to_evaluation(scorecard: dict) -> dict:
    """Convert a scorecard dict to the dashboard evaluation format."""
    role_key = _parse_role(scorecard.get("role", ""))
    scores = _parse_scores(scorecard.get("scores", {}))
    justifications = _parse_justifications(scorecard.get("justifications", {}))

    # Determine per-agent decision based on scores
    avg_score = sum(scores.values()) / len(scores) if scores else 5
    if avg_score >= 7:
        agent_decision = "ACCEPT"
    elif avg_score >= 5:
        agent_decision = "DISCUSS"
    else:
        agent_decision = "REJECT"

    return {
        "role": _ROLE_DISPLAY.get(role_key, role_key),
        "decision": agent_decision,
        "confidence": min(avg_score / 10.0, 1.0),
        "justifications": justifications,
        "scores": scores,
        "document_references": [],
    }


def load_verdict(path: Path) -> dict | None:
    """Load a single verdict JSON and convert to dashboard format.

    Parameters
    ----------
    path
        Path to a verdict JSON file.

    Returns
    -------
    dict | None
        Dashboard-formatted candidate dict, or None if parsing fails.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    candidate_id = data.get("candidate_id", path.stem)
    decision = _parse_decision(data.get("decision", "reject"))
    status = _DECISION_TO_STATUS.get(decision, "pending")
    composite = data.get("composite_score", 0.0)
    raw_justification = data.get("justification", "")
    if isinstance(raw_justification, dict):
        verdict_pros = list(raw_justification.get("pros", []))
        verdict_cons = list(raw_justification.get("cons", []))
    elif isinstance(raw_justification, str):
        verdict_pros = [raw_justification] if raw_justification else []
        verdict_cons = []
    else:
        verdict_pros = []
        verdict_cons = []

    # Extract GPA data if present
    gpa_data = data.get("gpa", {})
    gpa_value = gpa_data.get("gpa_value", "")
    gpa_scale = gpa_data.get("gpa_scale", "")
    gpa_normalized = gpa_data.get("gpa_normalized", 0.0)
    gpa_grading_system = gpa_data.get("grading_system", "")
    gpa_institution = gpa_data.get("institution_name", "")
    gpa_confidence = gpa_data.get("confidence", 0.0)

    # Parse final scores
    final_scores = _parse_scores(data.get("final_scores", {}))

    # Parse scorecards into evaluations
    scorecards = data.get("scorecards", [])
    evaluations = [_scorecard_to_evaluation(sc) for sc in scorecards]

    # Extract institution info from academic evaluator's justification
    institution_summary = ""
    for sc in scorecards:
        text = _extract_institution_from_scorecard(sc)
        if text:
            # Take first sentence as the school summary
            institution_summary = text.split(".")[0] + "." if "." in text else text
            break

    # Extract semester from candidate_id (e.g. "2020-21-fall_arnoux" -> "2020-21-fall")
    m = _SEMESTER_RE.match(candidate_id)
    semester = m.group(1) if m else "unknown"

    # Build documents list from scorecard roles
    doc_types = set()
    for sc in data.get("scorecards", []):
        role = _parse_role(sc.get("role", ""))
        if role == "academic":
            doc_types.update(["transcript", "diploma"])
        elif role == "reference":
            doc_types.add("recommendation_letter")
        elif role == "motivation":
            doc_types.update(["motivation_letter", "cv"])
        elif role == "devils_advocate":
            doc_types.update(["transcript", "motivation_letter", "recommendation_letter", "cv"])

    # Parse debates into display-friendly format
    raw_debates = data.get("debates", [])
    debate_summary = ""
    parsed_debates: list[dict] = []
    if raw_debates:
        debate_dims = [d.get("conflict_dimension", "") for d in raw_debates]
        debate_summary = f"Debates on: {', '.join(debate_dims)}. "
        for db in raw_debates:
            entries = []
            for entry in db.get("entries", []):
                entries.append({
                    "role": _ROLE_DISPLAY.get(_parse_role(entry.get("role", "")), entry.get("role", "")),
                    "round_number": entry.get("round_number", 0),
                    "argument": entry.get("argument", ""),
                })
            parsed_debates.append({
                "conflict_dimension": db.get("conflict_dimension", ""),
                "entries": entries,
            })

    return {
        "candidate_id": candidate_id,
        "semester": semester,
        "school": gpa_institution or institution_summary,
        "school_country": "",
        "gpa": gpa_value,
        "gpa_max": gpa_scale,
        "gpa_normalized": gpa_normalized,
        "gpa_grading_system": gpa_grading_system,
        "gpa_confidence": gpa_confidence,
        "study_level": "",
        "gender": "",
        "verdict_pros": verdict_pros,
        "verdict_cons": verdict_cons,
        "status": status,
        "confidence": min(composite / 10.0, 1.0),
        "evaluations": evaluations,
        "debates": parsed_debates,
        "moderator": {
            "pros": verdict_pros,
            "cons": verdict_cons,
            "decision": decision.upper(),
            "composite": composite,
            "debate_summary": debate_summary,
        },
        "final_scores": final_scores,
        "documents": sorted(doc_types),
        "minor_recommendation": data.get("minor_recommendation"),
    }


def _load_parquet_index(parquet_path: Path) -> dict[str, dict[str, str]]:
    """Build lookup from (semester, folder_name) to candidate metadata.

    Parameters
    ----------
    parquet_path
        Path to ``all_candidates.parquet``.

    Returns
    -------
    dict[str, dict]
        Mapping from candidate_id to metadata dict.
    """
    if not parquet_path.exists():
        return {}

    # Import matcher utilities
    import sys
    sys.path.insert(0, str(parquet_path.parent.parent / "src"))
    from agentic_admission.intake.matcher import name_to_folder_candidates, semester_from_record

    table = pq.read_table(parquet_path)
    rows = table.to_pydict()
    n = table.num_rows

    index: dict[str, dict[str, str]] = {}
    for i in range(n):
        year = str(rows["academic_year"][i] or "")
        round_ = str(rows["admission_round"][i] or "")
        name = str(rows["name"][i] or "")

        sem = semester_from_record(year, round_)
        if not sem:
            continue

        for fk in name_to_folder_candidates(name):
            cid = f"{sem}_{fk}"
            decision = str(rows.get("decision_final", [""])[i] or "")
            decision_section = str(rows.get("decision_section", [""])[i] or "")
            index[cid] = {
                "school": str(rows.get("school_name", [""])[i] or ""),
                "school_country": str(rows.get("school_country", [""])[i] or ""),
                "gpa": str(rows.get("gpa_candidate", [""])[i] or ""),
                "gpa_max": str(rows.get("gpa_max", [""])[i] or ""),
                "study_level": str(rows.get("study_level", [""])[i] or ""),
                "gender": str(rows.get("gender", [""])[i] or ""),
                "committee_decision": decision or decision_section,
            }

    return index


def _build_name_index(anonymized_root: Path) -> dict[str, str]:
    """Build mapping from ``semester_hash`` to real candidate name.

    Uses ``path_mapping.parquet`` to resolve hashes to original folder names,
    then matches against cohort JSON files for full names.

    Returns
    -------
    dict[str, str]
        Mapping from candidate_id (``"semester_hash"``) to display name.
    """
    mapping_path = anonymized_root / "path_mapping.parquet"
    if not mapping_path.exists():
        return {}

    # Step 1: hash -> original folder name
    table = pq.read_table(mapping_path)
    rows = table.to_pydict()
    hash_to_folder: dict[str, str] = {}
    for anon, orig in zip(rows["anonymized_path"], rows["original_path"]):
        parts_a = anon.split("/")
        parts_o = orig.split("/")
        if len(parts_a) >= 2 and len(parts_o) >= 2:
            cid = f"{parts_a[0]}_{parts_a[1]}"
            if cid not in hash_to_folder:
                hash_to_folder[cid] = parts_o[1]

    # Step 2: folder name -> full name from cohort JSONs
    folder_to_name: dict[str, str] = {}
    cohort_dir = anonymized_root.parent
    for cohort_file in cohort_dir.glob("cohort_*.json"):
        try:
            candidates = json.loads(cohort_file.read_text(encoding="utf-8"))
            for c in candidates:
                fname = c.get("folder_name", "")
                full = c.get("full_name", "")
                if fname and full:
                    folder_to_name[fname] = full
        except (json.JSONDecodeError, OSError):
            continue

    # Step 3: merge
    result: dict[str, str] = {}
    for cid, folder in hash_to_folder.items():
        name = folder_to_name.get(folder)
        if name:
            result[cid] = name
        else:
            # Fallback: capitalize the folder name
            result[cid] = folder.replace("_", " ").title()

    return result


def load_all_verdicts(
    evaluations_dir: Path,
    parquet_path: Path | None = None,
) -> list[dict]:
    """Load all verdict JSONs from a directory, enriched with Parquet metadata.

    Parameters
    ----------
    evaluations_dir
        Directory containing ``*.json`` verdict files.
    parquet_path
        Path to ``all_candidates.parquet``. If provided, enriches verdicts
        with school, GPA, and committee decision data.

    Returns
    -------
    list[dict]
        Dashboard-formatted candidate dicts, sorted by candidate_id.
    """
    if not evaluations_dir.is_dir():
        return []

    # Load Parquet index if available
    if parquet_path is None:
        parquet_path = evaluations_dir.parent / "all_candidates.parquet"
    parquet_index = _load_parquet_index(parquet_path)

    # Load name deanonymization index
    anonymized_root = evaluations_dir.parent / "anonymized"
    name_index = _build_name_index(anonymized_root)

    verdicts = []
    for path in sorted(evaluations_dir.glob("*.json")):
        v = load_verdict(path)
        if v is None:
            continue

        # Enrich with committee decision only (ground truth for comparison).
        # GPA, school, etc. must come from agent analysis, not Parquet —
        # new candidates won't have Parquet entries.
        meta = parquet_index.get(v["candidate_id"], {})
        if meta:
            v["committee_decision"] = meta.get("committee_decision", "")

        # Deanonymize candidate name
        v["candidate_name"] = name_index.get(v["candidate_id"], "")

        verdicts.append(v)

    return verdicts


def get_available_semesters(evaluations_dir: Path) -> list[str]:
    """Get unique semesters from verdict files.

    Parameters
    ----------
    evaluations_dir
        Directory containing ``*.json`` verdict files.

    Returns
    -------
    list[str]
        Sorted list of semester names.
    """
    verdicts = load_all_verdicts(evaluations_dir)
    semesters = sorted({v["semester"] for v in verdicts})
    return semesters or ["(no evaluations)"]
