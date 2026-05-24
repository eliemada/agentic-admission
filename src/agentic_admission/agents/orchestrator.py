"""Orchestrator: runs the 4-phase deliberation protocol for one candidate."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Awaitable

from agentic_admission.agents.chair import (
    clamp_academic_strength_below_threshold,
    detect_disagreements,
    make_skipped_reference_scorecard,
    moderate_debate,
    synthesize,
)
from agentic_admission.agents.dossier_loader import has_meaningful_letters
from agentic_admission.agents.evaluation_profile import (
    EPFL_INTERNAL_PROFILE,
    EXTERNAL_PROFILE,
    EvaluationProfile,
    renormalize_without_reference,
)
from agentic_admission.agents.evaluators import (
    evaluate_academic,
    evaluate_devils_advocate,
    evaluate_motivation,
    evaluate_reference,
)
from agentic_admission.agents.gpa_gate import EpflInternalBand, ThresholdVerdict
from agentic_admission.agents.minor_advisor import recommend_minor
from agentic_admission.curriculum.university_profiles import (
    format_university_context,
    load_university_profiles,
)
from agentic_admission.models.evaluation import (
    AgentScorecard,
    DebateTranscript,
    MinorRecommendation,
    PanelVerdict,
)

_CLIENT_TIMEOUT: float = 120.0


def _ensure_scorecard(result: AgentScorecard | BaseException) -> AgentScorecard:
    """Re-raise evaluator failures, otherwise return the scorecard.

    The Phase-1 ``asyncio.gather(return_exceptions=True)`` returns a
    mixed tuple where any evaluator failure surfaces as a ``BaseException``.
    Evaluators must succeed for the panel to deliberate, so any exception
    here is fatal — re-raise it.
    """
    if isinstance(result, BaseException):
        raise result
    return result


def _select_profile(
    *, is_epfl_internal: bool, has_letters: bool
) -> tuple[EvaluationProfile, str | None]:
    """Pick a profile and return an optional skip reason for the reference evaluator.

    The skip reason is ``None`` when reference evaluation runs normally.
    """
    if is_epfl_internal:
        return EPFL_INTERNAL_PROFILE, "EPFL-internal candidate: letters not required"
    if not has_letters:
        return (
            renormalize_without_reference(EXTERNAL_PROFILE),
            "External candidate but no recommendation letters submitted",
        )
    return EXTERNAL_PROFILE, None


def _build_reference_task(
    *,
    profile: EvaluationProfile,
    skip_reason: str | None,
    letters_text: str,
    calibration_context: str,
    historical_letters: str,
    model: str,
    base_url: str,
    client: httpx.AsyncClient,
) -> Awaitable[AgentScorecard]:
    """Return an awaitable producing the Reference scorecard.

    When the profile says to skip the Reference evaluator, returns a
    coroutine that resolves to a sentinel scorecard. Otherwise returns
    the live :func:`evaluate_reference` coroutine. Centralizing this
    keeps :func:`evaluate_candidate` shorter and below the complexity
    threshold.
    """
    if profile.skip_reference:
        assert skip_reason is not None
        reason = skip_reason

        async def _skipped() -> AgentScorecard:
            return make_skipped_reference_scorecard(reason)

        return _skipped()

    return evaluate_reference(
        letters_text=letters_text,
        calibration_context=calibration_context,
        historical_letters=historical_letters,
        model=model,
        base_url=base_url,
        client=client,
    )


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
    school_name: str = "",
    is_epfl_internal: bool = False,
    threshold_verdict: ThresholdVerdict | None = None,
    epfl_band: EpflInternalBand | None = None,
    gpa_confidence: float = 1.0,
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
    # Enrich transcript with university profile context
    enriched_transcript = transcript_text
    if school_name:
        try:
            profiles = load_university_profiles()
            uni_ctx = format_university_context(profiles, school_name)
            if uni_ctx:
                enriched_transcript = f"{uni_ctx}\n\n{transcript_text}"
        except Exception:
            logger.debug("Could not load university profiles — continuing without")

    has_letters = has_meaningful_letters(letters_text)
    profile, skip_reason = _select_profile(
        is_epfl_internal=is_epfl_internal, has_letters=has_letters
    )
    logger.info(
        "Profile for {}: {} (skip_reference={}, has_letters={})",
        candidate_id,
        profile.name,
        profile.skip_reference,
        has_letters,
    )

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=_CLIENT_TIMEOUT, headers=headers) as client:
        # --- Phase 1: Independent evaluation (in parallel) ---
        logger.info("Phase 1: Independent evaluation for {}", candidate_id)

        academic_task = evaluate_academic(
            transcript_text=enriched_transcript, model=model, base_url=base_url, client=client
        )
        reference_task = _build_reference_task(
            profile=profile,
            skip_reason=skip_reason,
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
            full_dossier_text=full_dossier_text,
            model=model,
            base_url=base_url,
            client=client,
            is_epfl_internal=is_epfl_internal,
        )
        minor_task = recommend_minor(
            transcript_text=transcript_text,
            cv_text=cv_text,
            model=model,
            base_url=base_url,
            client=client,
            candidate_id=candidate_id,
            is_epfl_internal=is_epfl_internal,
            full_dossier_text=full_dossier_text,
        )

        # Run evaluators and minor advisor in parallel.
        # Use return_exceptions=True for ALL tasks so the shared client stays
        # alive until every task finishes (prevents "client closed" race).
        all_results = await asyncio.gather(
            academic_task,
            reference_task,
            motivation_task,
            devils_task,
            minor_task,
            return_exceptions=True,
        )

        evaluator_results = all_results[:4]
        minor_result = all_results[4]

        # Re-raise the first evaluator failure (evaluators must succeed)
        # and narrow the type to the post-check ``AgentScorecard`` form.
        scorecards: tuple[AgentScorecard, ...] = tuple(
            _ensure_scorecard(r) for r in evaluator_results
        )

        # Apply the GPA gate's clamp on academic_strength (no-op when verdict
        # is ABOVE/NEAR/UNKNOWN, or when the EPFL-internal band is ACCEPT/
        # DISCUSS — only the REJECT band clamps). Keeps Chair synthesis
        # consistent with the post-synthesis hard-reject below.
        scorecards = clamp_academic_strength_below_threshold(
            scorecards,
            threshold_verdict=threshold_verdict,
            gpa_confidence=gpa_confidence,
            epfl_band=epfl_band,
        )

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
            profile=profile,
            threshold_verdict=threshold_verdict,
            gpa_confidence=gpa_confidence,
            epfl_band=epfl_band,
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
