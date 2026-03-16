"""Evaluation models for the multi-agent admission deliberation system."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class AgentRole(Enum):
    """Roles in the 5-agent admission panel."""

    ACADEMIC = "academic"
    REFERENCE = "reference"
    MOTIVATION = "motivation"
    DEVILS_ADVOCATE = "devils_advocate"
    CHAIR = "chair"


class Decision(Enum):
    """Final admission recommendation."""

    ACCEPT = "accept"
    REJECT = "reject"
    WAITLIST = "waitlist"


class AgentScorecard(BaseModel, frozen=True):
    """One specialist agent's evaluation of a candidate.

    Attributes
    ----------
    role
        Which agent produced this scorecard.
    scores
        Dimension name to integer score (1-10).
    justifications
        Dimension name to 1-2 sentence justification.
    """

    role: AgentRole
    scores: dict[str, int]
    justifications: dict[str, str]


class Conflict(BaseModel, frozen=True):
    """A semantic disagreement detected by the Chair.

    Attributes
    ----------
    dimension
        The scoring dimension in conflict.
    agents_involved
        The 2+ agents who disagree.
    nature
        Chair's description of the conflict.
    debate_question
        The specific question the Chair poses for debate.
    """

    dimension: str
    agents_involved: tuple[AgentRole, ...]
    nature: str
    debate_question: str


class DebateEntry(BaseModel, frozen=True):
    """One agent's argument in a targeted debate round.

    Attributes
    ----------
    role
        The agent making the argument.
    round_number
        Debate round (1 or 2).
    argument
        The agent's defense or rebuttal.
    """

    role: AgentRole
    round_number: int
    argument: str


class DebateTranscript(BaseModel, frozen=True):
    """Full transcript of a targeted debate on one dimension.

    Attributes
    ----------
    conflict_dimension
        Which dimension this debate addressed.
    entries
        Ordered sequence of debate entries.
    """

    conflict_dimension: str
    entries: tuple[DebateEntry, ...]


class PanelVerdict(BaseModel, frozen=True):
    """Final output of the deliberation protocol for one candidate.

    Attributes
    ----------
    candidate_id
        Unique identifier (e.g. ``"2024-25_round1_42"``).
    scorecards
        Individual scorecards from each specialist agent.
    debates
        Debate transcripts, empty if no disagreements.
    final_scores
        Chair's final 8-dimension scores (1-10).
    composite_score
        Weighted average of final_scores.
    decision
        Accept, reject, or waitlist.
    justification
        Chair's 2-3 sentence justification.
    """

    candidate_id: str
    scorecards: tuple[AgentScorecard, ...]
    debates: tuple[DebateTranscript, ...]
    final_scores: dict[str, int]
    composite_score: float
    decision: Decision
    justification: str
