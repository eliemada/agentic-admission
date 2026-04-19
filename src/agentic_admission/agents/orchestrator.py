"""Orchestrator: runs the 4-phase deliberation protocol for one candidate."""

from __future__ import annotations

import asyncio

import httpx
from loguru import logger

from agentic_admission.agents.chair import detect_disagreements, moderate_debate, synthesize
from agentic_admission.agents.evaluators import (
    evaluate_academic,
    evaluate_devils_advocate,
    evaluate_motivation,
    evaluate_reference,
)
from agentic_admission.agents.minor_advisor import recommend_minor
from agentic_admission.models.evaluation import DebateTranscript, MinorRecommendation, PanelVerdict

_CLIENT_TIMEOUT: float = 120.0


async def evaluate_candidate(
    *,
    candidate_id: str,
    transcript_text: str,
    letters_text: str,
    calibration_context: str,
    historical_letters: str,
    motivation_text: str,
    cv_text: str,
    full_dossier_text: str,
    model: str,
    base_url: str,
    api_key: str = "",
) -> PanelVerdict:
    """Run the full 4-phase deliberation protocol for a single candidate.

    A single ``httpx.AsyncClient`` is created and shared across every LLM call
    in the pipeline to avoid per-request connection overhead.

    Parameters
    ----------
    candidate_id
        Unique identifier (e.g. ``"2024-25_round1_42"``).
    transcript_text
        Markdown text of transcripts and academic records.
    letters_text
        Markdown text of recommendation letters.
    calibration_context
        Cultural calibration profile for the candidate's region.
    historical_letters
        Retrieved historical letters for comparison.
    motivation_text
        Markdown text of the motivation letter.
    cv_text
        Markdown text of the CV.
    full_dossier_text
        Concatenated markdown of all dossier documents.
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.
    api_key
        Optional API key for cloud endpoints (OpenRouter, etc.).
        When empty, no Authorization header is sent (for local vLLM).

    Returns
    -------
    PanelVerdict
        The final scorecard, recommendation, and justification.
    """
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=_CLIENT_TIMEOUT, headers=headers) as client:
        # --- Phase 1: Independent evaluation (4 agents in parallel) ---
        logger.info("Phase 1: Independent evaluation for {}", candidate_id)

        academic_task = evaluate_academic(
            transcript_text=transcript_text, model=model, base_url=base_url, client=client
        )
        reference_task = evaluate_reference(
            letters_text=letters_text,
            calibration_context=calibration_context,
            historical_letters=historical_letters,
            model=model,
            base_url=base_url,
            client=client,
        )
        motivation_task = evaluate_motivation(
            motivation_text=motivation_text,
            cv_text=cv_text,
            model=model,
            base_url=base_url,
            client=client,
        )
        devils_task = evaluate_devils_advocate(
            full_dossier_text=full_dossier_text, model=model, base_url=base_url, client=client
        )
        minor_task = recommend_minor(
            transcript_text=transcript_text,
            cv_text=cv_text,
            model=model,
            base_url=base_url,
            client=client,
        )

        # Run evaluators and minor advisor in parallel.
        # Evaluators must succeed; minor advisor is best-effort.
        scorecards_task = asyncio.gather(
            academic_task, reference_task, motivation_task, devils_task,
        )
        minor_wrapped = asyncio.gather(minor_task, return_exceptions=True)

        scorecard_list, minor_results = await asyncio.gather(
            scorecards_task, minor_wrapped,
        )
        scorecards = tuple(scorecard_list)

        minor_result = minor_results[0]
        minor_rec: MinorRecommendation | None = (
            minor_result if isinstance(minor_result, MinorRecommendation) else None
        )
        if isinstance(minor_result, BaseException):
            logger.warning("Minor recommendation failed: {}", minor_result)

        # --- Phase 2: Disagreement detection ---
        logger.info("Phase 2: Disagreement detection for {}", candidate_id)

        conflicts = await detect_disagreements(
            scorecards=scorecards, model=model, base_url=base_url, client=client
        )

        # --- Phase 3: Targeted debate (if conflicts exist) ---
        debates: tuple[DebateTranscript, ...] = ()
        if conflicts:
            logger.info(
                "Phase 3: Targeted debate on {} conflict(s) for {}", len(conflicts), candidate_id
            )
            debate_results = await asyncio.gather(
                *(
                    moderate_debate(
                        conflict=conflict,
                        scorecards=scorecards,
                        model=model,
                        base_url=base_url,
                        client=client,
                    )
                    for conflict in conflicts
                )
            )
            debates = tuple(debate_results)
        else:
            logger.info("Phase 3: No disagreements, skipping debate for {}", candidate_id)

        # --- Phase 4: Final synthesis ---
        logger.info("Phase 4: Final synthesis for {}", candidate_id)

        verdict = await synthesize(
            candidate_id=candidate_id,
            scorecards=scorecards,
            debates=debates,
            model=model,
            base_url=base_url,
            client=client,
        )

        # Attach minor recommendation to the verdict
        if minor_rec is not None:
            return PanelVerdict(
                candidate_id=verdict.candidate_id,
                scorecards=verdict.scorecards,
                debates=verdict.debates,
                final_scores=verdict.final_scores,
                composite_score=verdict.composite_score,
                decision=verdict.decision,
                justification=verdict.justification,
                minor_recommendation=minor_rec,
            )
        return verdict
