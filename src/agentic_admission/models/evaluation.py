"""Evaluation models for multi-agent admission panel."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class AgentRole(Enum):
    """Roles in the admission evaluation panel.

    Each role brings a different perspective to the evaluation.
    """

    STRICT = "strict"
    HOLISTIC = "holistic"
    TECHNICAL = "technical"
    MODERATOR = "moderator"


class AgentEvaluation(BaseModel, frozen=True):
    """A single agent's evaluation of a candidate dossier.

    Attributes
    ----------
    role
        The agent's role in the panel.
    decision
        One of ``"ACCEPT"``, ``"REJECT"``, ``"WAITLIST"``, ``"DISCUSS"``.
    confidence
        Agent's self-reported confidence in its decision (0.0-1.0).
    reasoning
        Free-text explanation of the decision.
    scores
        Optional per-criterion scores (e.g. ``{"academic": 4, "motivation": 5}``).
    """

    role: AgentRole
    decision: str
    confidence: float
    reasoning: str
    scores: dict[str, int | float] = {}


class PanelVerdict(BaseModel, frozen=True):
    """Aggregated verdict from the full evaluation panel.

    Attributes
    ----------
    evaluations
        Individual evaluations from each panel member.
    final_decision
        The moderator's final decision (``"ACCEPT"``, ``"REJECT"``, ``"WAITLIST"``).
    report
        Human-readable summary report for this candidate.
    moderator_reasoning
        The moderator's reasoning for the final decision.
    """

    evaluations: tuple[AgentEvaluation, ...]
    final_decision: str
    report: str
    moderator_reasoning: str
