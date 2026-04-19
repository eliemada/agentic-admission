# Multi-Agent Deliberation System — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a 5-agent deliberation system that evaluates MTE admission dossiers using a structured protocol with cultural calibration for reference letters.

**Architecture:** 4 specialist agents evaluate a dossier in parallel, a Chair agent detects semantic disagreements, routes targeted 2-round debates, and produces a final structured scorecard. All LLM calls go through an async OpenAI-compatible client (Qwen on SCITAS via vLLM).

**Tech Stack:** Python 3.13, Pydantic v2 (structured output), httpx (async HTTP), asyncio (parallel agents), loguru (logging), pyarrow (Parquet output).

---

## Task 1: Update Evaluation Models

The existing `src/agentic_admission/models/evaluation.py` has old roles (STRICT, HOLISTIC, TECHNICAL, MODERATOR). Replace with the new 5-agent design.

**Files:**
- Modify: `src/agentic_admission/models/evaluation.py`
- Test: `tests/test_evaluation_models.py`

**Step 1: Write the failing test**

Create `tests/test_evaluation_models.py`:

```python
"""Tests for the updated evaluation models."""

from __future__ import annotations

from agentic_admission.models.evaluation import (
    AgentRole,
    AgentScorecard,
    Conflict,
    DebateEntry,
    DebateTranscript,
    Decision,
    PanelVerdict,
)


class TestAgentRole:
    def test_all_five_roles_exist(self):
        roles = {r.value for r in AgentRole}
        assert roles == {"academic", "reference", "motivation", "devils_advocate", "chair"}


class TestDecision:
    def test_all_decisions_exist(self):
        decisions = {d.value for d in Decision}
        assert decisions == {"accept", "reject", "waitlist"}


class TestAgentScorecard:
    def test_frozen(self):
        card = AgentScorecard(
            role=AgentRole.ACADEMIC,
            scores={"academic_strength": 8, "institution_quality": 7},
            justifications={"academic_strength": "Strong GPA from top-tier school."},
        )
        assert card.role == AgentRole.ACADEMIC
        assert card.scores["academic_strength"] == 8

    def test_immutable(self):
        card = AgentScorecard(
            role=AgentRole.ACADEMIC,
            scores={"academic_strength": 8},
            justifications={"academic_strength": "Solid."},
        )
        try:
            card.role = AgentRole.CHAIR  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            pass
        else:
            msg = "AgentScorecard should be frozen"
            raise AssertionError(msg)


class TestConflict:
    def test_conflict_fields(self):
        conflict = Conflict(
            dimension="reference_quality",
            agents_involved=(AgentRole.REFERENCE, AgentRole.DEVILS_ADVOCATE),
            nature="Agent 2 sees strong calibrated letter; Agent 4 flags inconsistency.",
            debate_question="Is the reference letter genuinely strong after cultural adjustment?",
        )
        assert conflict.dimension == "reference_quality"
        assert len(conflict.agents_involved) == 2


class TestDebateTranscript:
    def test_entries(self):
        entry = DebateEntry(
            role=AgentRole.REFERENCE,
            round_number=1,
            argument="The letter is strong after US calibration.",
        )
        transcript = DebateTranscript(
            conflict_dimension="reference_quality",
            entries=(entry,),
        )
        assert len(transcript.entries) == 1


class TestPanelVerdict:
    def test_verdict_fields(self):
        verdict = PanelVerdict(
            candidate_id="2024-25_round1_42",
            scorecards=(),
            debates=(),
            final_scores={
                "academic_strength": 8,
                "institution_quality": 7,
                "reference_quality": 6,
                "calibration_confidence": 7,
                "motivation_clarity": 8,
                "program_fit": 7,
                "risk_flags": 9,
                "consistency": 8,
            },
            composite_score=7.5,
            decision=Decision.ACCEPT,
            justification="Strong academic profile with well-calibrated references.",
        )
        assert verdict.decision == Decision.ACCEPT
        assert len(verdict.final_scores) == 8
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_evaluation_models.py -v`
Expected: FAIL — `AgentScorecard`, `Conflict`, `Decision`, etc. do not exist yet.

**Step 3: Write the implementation**

Replace `src/agentic_admission/models/evaluation.py` with:

```python
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
```

**Step 4: Update `src/agentic_admission/models/__init__.py`**

Replace existing exports:

```python
"""Pydantic data models for applicants, evaluations, and decisions."""

from agentic_admission.models.candidate import CandidateRecord
from agentic_admission.models.document import DocumentType, DossierDocument
from agentic_admission.models.dossier import Dossier, ProcessingStage
from agentic_admission.models.evaluation import (
    AgentRole,
    AgentScorecard,
    Conflict,
    DebateEntry,
    DebateTranscript,
    Decision,
    PanelVerdict,
)

__all__ = [
    "AgentRole",
    "AgentScorecard",
    "CandidateRecord",
    "Conflict",
    "DebateEntry",
    "DebateTranscript",
    "Decision",
    "DocumentType",
    "Dossier",
    "DossierDocument",
    "PanelVerdict",
    "ProcessingStage",
]
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_evaluation_models.py -v`
Expected: ALL PASS

**Step 6: Lint and commit**

```bash
uv run poe lint
git add src/agentic_admission/models/evaluation.py src/agentic_admission/models/__init__.py tests/test_evaluation_models.py
git commit -m "refactor: update evaluation models for 5-agent deliberation protocol"
```

---

## Task 2: Add httpx Dependency and Create LLM Client

Async client that sends chat completion requests to the OpenAI-compatible vLLM endpoint and parses structured JSON output into Pydantic models.

**Files:**
- Modify: `pyproject.toml` (add `httpx`)
- Create: `src/agentic_admission/agents/llm_client.py`
- Test: `tests/test_llm_client.py`

**Step 1: Add httpx dependency**

```bash
uv add httpx
```

**Step 2: Write the failing test**

Create `tests/test_llm_client.py`:

```python
"""Tests for the async LLM client."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from agentic_admission.agents.llm_client import ChatMessage, complete

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


class DummyOutput(BaseModel, frozen=True):
    """Tiny model for testing structured output parsing."""

    answer: str
    score: int


class TestChatMessage:
    def test_system_message(self):
        msg = ChatMessage(role="system", content="You are helpful.")
        assert msg.role == "system"

    def test_user_message(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"


class TestComplete:
    @pytest.fixture
    def mock_httpx_response(self, mocker: MockerFixture):
        """Mock httpx.AsyncClient.post to return a valid OpenAI-style response."""
        body = json.dumps({"answer": "yes", "score": 9})
        response_json = {
            "choices": [{"message": {"content": body}}],
        }
        mock_response = mocker.AsyncMock()
        mock_response.json.return_value = response_json
        mock_response.raise_for_status = mocker.Mock()
        mock_client = mocker.AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=False)
        mocker.patch("httpx.AsyncClient", return_value=mock_client)
        return mock_client

    async def test_complete_parses_structured_output(self, mock_httpx_response):
        messages = [
            ChatMessage(role="system", content="You are a test agent."),
            ChatMessage(role="user", content="Evaluate this."),
        ]
        result = await complete(
            messages=messages,
            response_model=DummyOutput,
            model="test-model",
            base_url="http://localhost:8000/v1",
        )
        assert isinstance(result, DummyOutput)
        assert result.answer == "yes"
        assert result.score == 9

    async def test_complete_sends_json_schema_in_request(self, mock_httpx_response):
        messages = [ChatMessage(role="user", content="test")]
        await complete(
            messages=messages,
            response_model=DummyOutput,
            model="test-model",
            base_url="http://localhost:8000/v1",
        )
        call_kwargs = mock_httpx_response.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["response_format"]["type"] == "json_schema"
```

**Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_llm_client.py -v`
Expected: FAIL — `llm_client` module does not exist.

**Step 4: Write the implementation**

Create `src/agentic_admission/agents/llm_client.py`:

```python
"""Async LLM client for OpenAI-compatible chat completion endpoints."""

from __future__ import annotations

import json
from typing import TypeVar

import httpx
from loguru import logger
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ChatMessage(BaseModel, frozen=True):
    """A single message in a chat conversation.

    Attributes
    ----------
    role
        One of ``"system"``, ``"user"``, ``"assistant"``.
    content
        The message text.
    """

    role: str
    content: str


async def complete(
    *,
    messages: list[ChatMessage],
    response_model: type[T],
    model: str,
    base_url: str,
    temperature: float = 0.1,
    max_tokens: int = 2048,
) -> T:
    """Send a chat completion request and parse the response into a Pydantic model.

    Parameters
    ----------
    messages
        Conversation history.
    response_model
        Pydantic model class to parse the response into (via JSON mode).
    model
        Model identifier (e.g. ``"Qwen/Qwen2.5-72B-Instruct"``).
    base_url
        Base URL of the vLLM endpoint (e.g. ``"http://localhost:8000/v1"``).
    temperature
        Sampling temperature.
    max_tokens
        Maximum tokens in the response.

    Returns
    -------
    T
        Parsed Pydantic model instance.
    """
    schema = response_model.model_json_schema()
    payload = {
        "model": model,
        "messages": [m.model_dump() for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": response_model.__name__, "schema": schema},
        },
    }

    logger.debug("LLM request to {}: model={}", base_url, model)

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(f"{base_url}/chat/completions", json=payload)
        response.raise_for_status()

    body = response.json()
    raw_content = body["choices"][0]["message"]["content"]
    parsed = json.loads(raw_content)
    return response_model.model_validate(parsed)
```

**Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_llm_client.py -v`
Expected: ALL PASS

**Step 6: Lint and commit**

```bash
uv run poe lint
git add pyproject.toml uv.lock src/agentic_admission/agents/llm_client.py tests/test_llm_client.py
git commit -m "feat: add async LLM client with structured JSON output parsing"
```

---

## Task 3: Create Agent Prompts

System prompts for each of the 5 agent roles. Pure constants, no logic.

**Files:**
- Create: `src/agentic_admission/agents/prompts.py`
- Test: `tests/test_prompts.py`

**Step 1: Write the failing test**

Create `tests/test_prompts.py`:

```python
"""Tests for agent system prompts."""

from __future__ import annotations

from agentic_admission.agents.prompts import AGENT_PROMPTS
from agentic_admission.models.evaluation import AgentRole


class TestAgentPrompts:
    def test_all_roles_have_prompts(self):
        for role in AgentRole:
            assert role in AGENT_PROMPTS, f"Missing prompt for {role}"

    def test_prompts_are_nonempty_strings(self):
        for role, prompt in AGENT_PROMPTS.items():
            assert isinstance(prompt, str)
            assert len(prompt) > 100, f"Prompt for {role} is too short"

    def test_academic_prompt_mentions_transcripts(self):
        prompt = AGENT_PROMPTS[AgentRole.ACADEMIC]
        assert "transcript" in prompt.lower()

    def test_reference_prompt_mentions_calibration(self):
        prompt = AGENT_PROMPTS[AgentRole.REFERENCE]
        assert "calibration" in prompt.lower()

    def test_devils_advocate_prompt_mentions_risk(self):
        prompt = AGENT_PROMPTS[AgentRole.DEVILS_ADVOCATE]
        assert "risk" in prompt.lower() or "weakness" in prompt.lower()

    def test_chair_prompt_mentions_disagreement(self):
        prompt = AGENT_PROMPTS[AgentRole.CHAIR]
        assert "disagreement" in prompt.lower() or "conflict" in prompt.lower()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: FAIL — module does not exist.

**Step 3: Write the implementation**

Create `src/agentic_admission/agents/prompts.py`:

```python
"""System prompts for each agent in the deliberation panel."""

from __future__ import annotations

from agentic_admission.models.evaluation import AgentRole

AGENT_PROMPTS: dict[AgentRole, str] = {
    AgentRole.ACADEMIC: (
        "You are the Academic Evaluator on an MTE admissions panel at EPFL. "
        "Your role is to assess the candidate's academic strength based on their "
        "transcript, GPA, institution ranking, and any standardized test scores (GRE). "
        "You must score two dimensions:\n"
        "- academic_strength (1-10): Quality of grades, coursework relevance, and academic trajectory.\n"
        "- institution_quality (1-10): Reputation and rigor of the candidate's institution.\n\n"
        "Consider the grading scale provided. A 3.5/4.0 from a competitive US school is different "
        "from a 14/20 in the French system. Normalize your assessment accordingly.\n\n"
        "Respond with a JSON object matching the AgentScorecard schema. Include a 1-2 sentence "
        "justification for each dimension score."
    ),
    AgentRole.REFERENCE: (
        "You are the Reference Letter Specialist on an MTE admissions panel at EPFL. "
        "Your role is to evaluate the quality and authenticity of recommendation letters, "
        "with explicit cultural calibration.\n\n"
        "You will receive:\n"
        "1. The candidate's reference letters (as markdown).\n"
        "2. A calibration profile showing typical letter characteristics from the candidate's region.\n"
        "3. 3-5 historical reference letters from similar institutions with their admission outcomes.\n\n"
        "You must score two dimensions:\n"
        "- reference_quality (1-10): Substantive quality of the recommendation after cultural adjustment. "
        "A generic superlative letter from a US professor may be a 5; a reserved but specific letter "
        "from a European professor may be a 7.\n"
        "- calibration_confidence (1-10): How confident you are in your cultural adjustment. "
        "Low if the letter's origin is ambiguous or the calibration data is sparse.\n\n"
        "Compare the candidate's letters against the historical examples provided. Look for "
        "specificity, concrete examples, and evidence of genuine familiarity with the candidate.\n\n"
        "Respond with a JSON object matching the AgentScorecard schema."
    ),
    AgentRole.MOTIVATION: (
        "You are the Motivation & Fit Evaluator on an MTE admissions panel at EPFL. "
        "Your role is to assess whether the candidate understands the MTE program, has clear "
        "goals, and demonstrates a strong fit between their background and the program's focus "
        "on management, technology, and entrepreneurship.\n\n"
        "You will receive the candidate's motivation letter, CV, and any work experience documentation.\n\n"
        "You must score two dimensions:\n"
        "- motivation_clarity (1-10): How clearly the candidate articulates why MTE, what they "
        "want to learn, and what they plan to do after. Penalize generic statements that could "
        "apply to any program.\n"
        "- program_fit (1-10): How well the candidate's background, skills, and goals align with "
        "MTE's interdisciplinary focus. Consider technical depth, business awareness, and "
        "entrepreneurial mindset.\n\n"
        "Respond with a JSON object matching the AgentScorecard schema."
    ),
    AgentRole.DEVILS_ADVOCATE: (
        "You are the Devil's Advocate on an MTE admissions panel at EPFL. "
        "Your role is to critically examine the entire dossier for weaknesses, inconsistencies, "
        "and risk factors that other evaluators might overlook.\n\n"
        "You will receive all dossier documents: transcripts, reference letters, motivation letter, "
        "and CV.\n\n"
        "You must score two dimensions:\n"
        "- risk_flags (1-10, inverse scale: 10 = no concerns, 1 = severe red flags): "
        "Look for gaps in employment, declining grades, inconsistencies between the CV and "
        "transcripts, or reference letters that seem templated.\n"
        "- consistency (1-10): How well the different parts of the dossier align. Does the "
        "motivation letter match the CV trajectory? Do the reference letters describe the same "
        "person as the transcripts suggest?\n\n"
        "Be specific about any weakness or inconsistency you find. Do not invent problems, "
        "but do not let anything slide.\n\n"
        "Respond with a JSON object matching the AgentScorecard schema."
    ),
    AgentRole.CHAIR: (
        "You are the Chair of the MTE admissions panel at EPFL. You have two responsibilities:\n\n"
        "1. DISAGREEMENT DETECTION: Given the scorecards from 4 specialist agents, identify "
        "meaningful disagreements. A disagreement is not just a score gap — it is a semantic "
        "conflict where agents interpret the same evidence differently. For each conflict, "
        "formulate a specific debate question.\n\n"
        "2. FINAL SYNTHESIS: After reviewing all scorecards and any debate transcripts, produce "
        "the final scorecard with 8 dimension scores (1-10), a weighted composite score, "
        "a recommendation (accept/reject/waitlist), and a 2-3 sentence justification.\n\n"
        "When synthesizing, give appropriate weight to each specialist's domain expertise. "
        "The Devil's Advocate's concerns should be taken seriously but not given veto power. "
        "Cultural calibration confidence should modulate how much weight you give reference scores.\n\n"
        "Respond with a JSON object matching the requested schema."
    ),
}
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_prompts.py -v`
Expected: ALL PASS

**Step 5: Lint and commit**

```bash
uv run poe lint
git add src/agentic_admission/agents/prompts.py tests/test_prompts.py
git commit -m "feat: add system prompts for 5-agent deliberation panel"
```

---

## Task 4: Create Specialist Evaluator Functions

Each of the 4 specialist agents is an async function that takes dossier content and returns an `AgentScorecard`.

**Files:**
- Create: `src/agentic_admission/agents/evaluators.py`
- Test: `tests/test_evaluators.py`

**Step 1: Write the failing test**

Create `tests/test_evaluators.py`:

```python
"""Tests for specialist evaluator agent functions."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from agentic_admission.agents.evaluators import (
    evaluate_academic,
    evaluate_devils_advocate,
    evaluate_motivation,
    evaluate_reference,
)
from agentic_admission.models.evaluation import AgentRole, AgentScorecard

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


@pytest.fixture
def _mock_llm(mocker: MockerFixture):
    """Patch ``complete`` to return a valid AgentScorecard without hitting an LLM."""
    scorecard = AgentScorecard(
        role=AgentRole.ACADEMIC,
        scores={"academic_strength": 7, "institution_quality": 6},
        justifications={
            "academic_strength": "Solid GPA.",
            "institution_quality": "Mid-tier institution.",
        },
    )

    async def fake_complete(*, messages, response_model, model, base_url, **kwargs):
        return response_model.model_validate(scorecard.model_dump())

    mocker.patch("agentic_admission.agents.evaluators.complete", side_effect=fake_complete)


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateAcademic:
    async def test_returns_scorecard(self):
        result = await evaluate_academic(
            transcript_text="GPA: 3.8/4.0, BS Computer Science",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)
        assert result.role == AgentRole.ACADEMIC

    async def test_scorecard_has_required_dimensions(self):
        result = await evaluate_academic(
            transcript_text="GPA: 3.8/4.0",
            model="test",
            base_url="http://test",
        )
        assert "academic_strength" in result.scores
        assert "institution_quality" in result.scores


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateReference:
    async def test_returns_scorecard(self):
        result = await evaluate_reference(
            letters_text="Dear committee, this student is exceptional...",
            calibration_context="US university avg sentiment: 0.85",
            historical_letters="[Letter 1] ...",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateMotivation:
    async def test_returns_scorecard(self):
        result = await evaluate_motivation(
            motivation_text="I want to join MTE because...",
            cv_text="Experience: 2 years at Google...",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)


@pytest.mark.usefixtures("_mock_llm")
class TestEvaluateDevilsAdvocate:
    async def test_returns_scorecard(self):
        result = await evaluate_devils_advocate(
            full_dossier_text="[Transcript] ... [Letters] ... [CV] ...",
            model="test",
            base_url="http://test",
        )
        assert isinstance(result, AgentScorecard)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_evaluators.py -v`
Expected: FAIL — module does not exist.

**Step 3: Write the implementation**

Create `src/agentic_admission/agents/evaluators.py`:

```python
"""Specialist evaluator agent functions for the deliberation panel."""

from __future__ import annotations

from agentic_admission.agents.llm_client import ChatMessage, complete
from agentic_admission.agents.prompts import AGENT_PROMPTS
from agentic_admission.models.evaluation import AgentRole, AgentScorecard


async def evaluate_academic(
    *,
    transcript_text: str,
    model: str,
    base_url: str,
) -> AgentScorecard:
    """Run the Academic Evaluator agent.

    Parameters
    ----------
    transcript_text
        Markdown text of transcripts, GPA info, and GRE scores.
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.

    Returns
    -------
    AgentScorecard
        Scorecard with ``academic_strength`` and ``institution_quality``.
    """
    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.ACADEMIC]),
        ChatMessage(role="user", content=f"Evaluate this candidate:\n\n{transcript_text}"),
    ]
    scorecard = await complete(
        messages=messages, response_model=AgentScorecard, model=model, base_url=base_url,
    )
    return AgentScorecard(
        role=AgentRole.ACADEMIC,
        scores=scorecard.scores,
        justifications=scorecard.justifications,
    )


async def evaluate_reference(
    *,
    letters_text: str,
    calibration_context: str,
    historical_letters: str,
    model: str,
    base_url: str,
) -> AgentScorecard:
    """Run the Reference Letter Specialist agent.

    Parameters
    ----------
    letters_text
        Markdown text of all recommendation letters.
    calibration_context
        Calibration profile for the candidate's region/institution.
    historical_letters
        3-5 retrieved historical letters with outcomes.
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.

    Returns
    -------
    AgentScorecard
        Scorecard with ``reference_quality`` and ``calibration_confidence``.
    """
    user_content = (
        f"## Candidate's Reference Letters\n\n{letters_text}\n\n"
        f"## Calibration Profile\n\n{calibration_context}\n\n"
        f"## Historical Letters for Comparison\n\n{historical_letters}"
    )
    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.REFERENCE]),
        ChatMessage(role="user", content=user_content),
    ]
    scorecard = await complete(
        messages=messages, response_model=AgentScorecard, model=model, base_url=base_url,
    )
    return AgentScorecard(
        role=AgentRole.REFERENCE,
        scores=scorecard.scores,
        justifications=scorecard.justifications,
    )


async def evaluate_motivation(
    *,
    motivation_text: str,
    cv_text: str,
    model: str,
    base_url: str,
) -> AgentScorecard:
    """Run the Motivation & Fit Evaluator agent.

    Parameters
    ----------
    motivation_text
        Markdown text of the motivation letter.
    cv_text
        Markdown text of the CV.
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.

    Returns
    -------
    AgentScorecard
        Scorecard with ``motivation_clarity`` and ``program_fit``.
    """
    user_content = f"## Motivation Letter\n\n{motivation_text}\n\n## CV\n\n{cv_text}"
    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.MOTIVATION]),
        ChatMessage(role="user", content=user_content),
    ]
    scorecard = await complete(
        messages=messages, response_model=AgentScorecard, model=model, base_url=base_url,
    )
    return AgentScorecard(
        role=AgentRole.MOTIVATION,
        scores=scorecard.scores,
        justifications=scorecard.justifications,
    )


async def evaluate_devils_advocate(
    *,
    full_dossier_text: str,
    model: str,
    base_url: str,
) -> AgentScorecard:
    """Run the Devil's Advocate agent.

    Parameters
    ----------
    full_dossier_text
        Markdown text of the entire dossier (all documents concatenated).
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.

    Returns
    -------
    AgentScorecard
        Scorecard with ``risk_flags`` and ``consistency``.
    """
    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.DEVILS_ADVOCATE]),
        ChatMessage(role="user", content=f"Review this complete dossier:\n\n{full_dossier_text}"),
    ]
    scorecard = await complete(
        messages=messages, response_model=AgentScorecard, model=model, base_url=base_url,
    )
    return AgentScorecard(
        role=AgentRole.DEVILS_ADVOCATE,
        scores=scorecard.scores,
        justifications=scorecard.justifications,
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_evaluators.py -v`
Expected: ALL PASS

**Step 5: Lint and commit**

```bash
uv run poe lint
git add src/agentic_admission/agents/evaluators.py tests/test_evaluators.py
git commit -m "feat: add 4 specialist evaluator agent functions"
```

---

## Task 5: Create the Chair Agent

The Chair has three jobs: detect disagreements, moderate debates, and synthesize the final verdict.

**Files:**
- Create: `src/agentic_admission/agents/chair.py`
- Test: `tests/test_chair.py`

**Step 1: Write the failing test**

Create `tests/test_chair.py`:

```python
"""Tests for the Chair agent functions."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from agentic_admission.agents.chair import detect_disagreements, moderate_debate, synthesize
from agentic_admission.models.evaluation import (
    AgentRole,
    AgentScorecard,
    Conflict,
    DebateEntry,
    DebateTranscript,
    Decision,
    PanelVerdict,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture


def _make_scorecard(role: AgentRole, scores: dict[str, int]) -> AgentScorecard:
    return AgentScorecard(
        role=role,
        scores=scores,
        justifications={k: "test justification" for k in scores},
    )


SAMPLE_SCORECARDS = (
    _make_scorecard(AgentRole.ACADEMIC, {"academic_strength": 8, "institution_quality": 7}),
    _make_scorecard(AgentRole.REFERENCE, {"reference_quality": 7, "calibration_confidence": 6}),
    _make_scorecard(AgentRole.MOTIVATION, {"motivation_clarity": 8, "program_fit": 7}),
    _make_scorecard(AgentRole.DEVILS_ADVOCATE, {"risk_flags": 9, "consistency": 8}),
)


class TestDetectDisagreements:
    @pytest.fixture
    def _mock_llm_conflicts(self, mocker: MockerFixture):
        conflict = Conflict(
            dimension="reference_quality",
            agents_involved=(AgentRole.REFERENCE, AgentRole.DEVILS_ADVOCATE),
            nature="Conflicting interpretation of letter quality.",
            debate_question="Is this letter genuinely strong?",
        )

        async def fake_complete(*, messages, response_model, model, base_url, **kwargs):
            # Chair returns a wrapper with conflicts list
            from agentic_admission.agents.chair import DisagreementReport
            return DisagreementReport(conflicts=(conflict,))

        mocker.patch("agentic_admission.agents.chair.complete", side_effect=fake_complete)

    @pytest.mark.usefixtures("_mock_llm_conflicts")
    async def test_returns_conflict_list(self):
        conflicts = await detect_disagreements(
            scorecards=SAMPLE_SCORECARDS,
            model="test",
            base_url="http://test",
        )
        assert len(conflicts) == 1
        assert conflicts[0].dimension == "reference_quality"


class TestModerateDebate:
    @pytest.fixture
    def _mock_llm_debate(self, mocker: MockerFixture):
        entry = DebateEntry(
            role=AgentRole.REFERENCE, round_number=1, argument="The letter is strong.",
        )

        async def fake_complete(*, messages, response_model, model, base_url, **kwargs):
            return AgentScorecard(
                role=AgentRole.REFERENCE,
                scores={"reference_quality": 7},
                justifications={"reference_quality": "After debate, I maintain my position."},
            )

        mocker.patch("agentic_admission.agents.chair.complete", side_effect=fake_complete)

    @pytest.mark.usefixtures("_mock_llm_debate")
    async def test_returns_debate_transcript(self):
        conflict = Conflict(
            dimension="reference_quality",
            agents_involved=(AgentRole.REFERENCE, AgentRole.DEVILS_ADVOCATE),
            nature="test conflict",
            debate_question="Is this letter strong?",
        )
        transcript = await moderate_debate(
            conflict=conflict,
            scorecards=SAMPLE_SCORECARDS,
            model="test",
            base_url="http://test",
        )
        assert isinstance(transcript, DebateTranscript)
        assert transcript.conflict_dimension == "reference_quality"


class TestSynthesize:
    @pytest.fixture
    def _mock_llm_verdict(self, mocker: MockerFixture):
        verdict = PanelVerdict(
            candidate_id="test_candidate",
            scorecards=(),
            debates=(),
            final_scores={
                "academic_strength": 8,
                "institution_quality": 7,
                "reference_quality": 7,
                "calibration_confidence": 6,
                "motivation_clarity": 8,
                "program_fit": 7,
                "risk_flags": 9,
                "consistency": 8,
            },
            composite_score=7.5,
            decision=Decision.ACCEPT,
            justification="Strong candidate overall.",
        )

        async def fake_complete(*, messages, response_model, model, base_url, **kwargs):
            return verdict

        mocker.patch("agentic_admission.agents.chair.complete", side_effect=fake_complete)

    @pytest.mark.usefixtures("_mock_llm_verdict")
    async def test_returns_panel_verdict(self):
        verdict = await synthesize(
            candidate_id="test_candidate",
            scorecards=SAMPLE_SCORECARDS,
            debates=(),
            model="test",
            base_url="http://test",
        )
        assert isinstance(verdict, PanelVerdict)
        assert verdict.decision == Decision.ACCEPT
        assert len(verdict.final_scores) == 8
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_chair.py -v`
Expected: FAIL — module does not exist.

**Step 3: Write the implementation**

Create `src/agentic_admission/agents/chair.py`:

```python
"""Chair agent: disagreement detection, debate moderation, and final synthesis."""

from __future__ import annotations

import json

from loguru import logger
from pydantic import BaseModel

from agentic_admission.agents.llm_client import ChatMessage, complete
from agentic_admission.agents.prompts import AGENT_PROMPTS
from agentic_admission.models.evaluation import (
    AgentRole,
    AgentScorecard,
    Conflict,
    DebateEntry,
    DebateTranscript,
    Decision,
    PanelVerdict,
)

_MAX_DEBATE_ROUNDS = 2


class DisagreementReport(BaseModel, frozen=True):
    """Chair's assessment of conflicts across scorecards.

    Attributes
    ----------
    conflicts
        Detected semantic conflicts (empty tuple if none).
    """

    conflicts: tuple[Conflict, ...]


def _format_scorecards(scorecards: tuple[AgentScorecard, ...]) -> str:
    """Render scorecards as readable text for the Chair's context."""
    sections = []
    for card in scorecards:
        lines = [f"### {card.role.value.upper()}"]
        for dim, score in card.scores.items():
            justification = card.justifications.get(dim, "")
            lines.append(f"- {dim}: {score}/10 — {justification}")
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


async def detect_disagreements(
    *,
    scorecards: tuple[AgentScorecard, ...],
    model: str,
    base_url: str,
) -> tuple[Conflict, ...]:
    """Have the Chair identify semantic conflicts across specialist scorecards.

    Parameters
    ----------
    scorecards
        The 4 specialist scorecards.
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.

    Returns
    -------
    tuple[Conflict, ...]
        Detected conflicts, empty if agents agree.
    """
    formatted = _format_scorecards(scorecards)
    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.CHAIR]),
        ChatMessage(
            role="user",
            content=(
                "Review these 4 specialist scorecards and identify any meaningful "
                "semantic disagreements. Return a DisagreementReport.\n\n"
                f"{formatted}"
            ),
        ),
    ]
    report = await complete(
        messages=messages, response_model=DisagreementReport, model=model, base_url=base_url,
    )
    logger.info("Chair detected {} conflict(s)", len(report.conflicts))
    return report.conflicts


async def moderate_debate(
    *,
    conflict: Conflict,
    scorecards: tuple[AgentScorecard, ...],
    model: str,
    base_url: str,
) -> DebateTranscript:
    """Run a 2-round targeted debate between disagreeing agents.

    Parameters
    ----------
    conflict
        The specific disagreement to debate.
    scorecards
        All specialist scorecards (for context).
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.

    Returns
    -------
    DebateTranscript
        Full transcript of the debate.
    """
    entries: list[DebateEntry] = []
    context = _format_scorecards(scorecards)

    for round_num in range(1, _MAX_DEBATE_ROUNDS + 1):
        for role in conflict.agents_involved:
            prior_args = "\n".join(
                f"[{e.role.value}, Round {e.round_number}]: {e.argument}" for e in entries
            )
            messages = [
                ChatMessage(
                    role="system",
                    content=AGENT_PROMPTS[role],
                ),
                ChatMessage(
                    role="user",
                    content=(
                        f"DEBATE — Round {round_num}\n\n"
                        f"Question: {conflict.debate_question}\n\n"
                        f"Context:\n{context}\n\n"
                        f"Prior arguments:\n{prior_args or '(none yet)'}\n\n"
                        "Defend or adjust your position. Respond with an AgentScorecard."
                    ),
                ),
            ]
            response = await complete(
                messages=messages,
                response_model=AgentScorecard,
                model=model,
                base_url=base_url,
            )
            justification = response.justifications.get(
                conflict.dimension, next(iter(response.justifications.values()), ""),
            )
            entries.append(
                DebateEntry(role=role, round_number=round_num, argument=justification),
            )

    logger.info(
        "Debate on '{}' completed: {} entries", conflict.dimension, len(entries),
    )
    return DebateTranscript(
        conflict_dimension=conflict.dimension, entries=tuple(entries),
    )


async def synthesize(
    *,
    candidate_id: str,
    scorecards: tuple[AgentScorecard, ...],
    debates: tuple[DebateTranscript, ...],
    model: str,
    base_url: str,
) -> PanelVerdict:
    """Produce the final panel verdict.

    Parameters
    ----------
    candidate_id
        Unique candidate identifier.
    scorecards
        All specialist scorecards.
    debates
        All debate transcripts (empty if no conflicts).
    model
        LLM model identifier.
    base_url
        vLLM endpoint base URL.

    Returns
    -------
    PanelVerdict
        The final scorecard, recommendation, and justification.
    """
    formatted_cards = _format_scorecards(scorecards)
    debate_text = ""
    if debates:
        sections = []
        for transcript in debates:
            lines = [f"### Debate: {transcript.conflict_dimension}"]
            for entry in transcript.entries:
                lines.append(
                    f"[{entry.role.value}, Round {entry.round_number}]: {entry.argument}",
                )
            sections.append("\n".join(lines))
        debate_text = "\n\n".join(sections)

    messages = [
        ChatMessage(role="system", content=AGENT_PROMPTS[AgentRole.CHAIR]),
        ChatMessage(
            role="user",
            content=(
                "Produce the FINAL VERDICT for this candidate. Return a PanelVerdict with "
                "all 8 dimension scores, composite_score, decision, and justification.\n\n"
                f"## Specialist Scorecards\n\n{formatted_cards}\n\n"
                f"## Debate Transcripts\n\n{debate_text or '(no debates needed)'}"
            ),
        ),
    ]
    verdict = await complete(
        messages=messages, response_model=PanelVerdict, model=model, base_url=base_url,
    )
    return PanelVerdict(
        candidate_id=candidate_id,
        scorecards=scorecards,
        debates=debates,
        final_scores=verdict.final_scores,
        composite_score=verdict.composite_score,
        decision=verdict.decision,
        justification=verdict.justification,
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_chair.py -v`
Expected: ALL PASS

**Step 5: Lint and commit**

```bash
uv run poe lint
git add src/agentic_admission/agents/chair.py tests/test_chair.py
git commit -m "feat: add Chair agent with disagreement detection, debate, and synthesis"
```

---

## Task 6: Create the Orchestrator

The orchestrator runs the full 4-phase protocol for a single candidate.

**Files:**
- Create: `src/agentic_admission/agents/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Step 1: Write the failing test**

Create `tests/test_orchestrator.py`:

```python
"""Tests for the deliberation orchestrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from agentic_admission.agents.orchestrator import evaluate_candidate
from agentic_admission.models.evaluation import Decision, PanelVerdict

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

from agentic_admission.models.evaluation import AgentRole, AgentScorecard, Conflict, DebateTranscript


def _make_scorecard(role: AgentRole) -> AgentScorecard:
    scores = {
        AgentRole.ACADEMIC: {"academic_strength": 8, "institution_quality": 7},
        AgentRole.REFERENCE: {"reference_quality": 7, "calibration_confidence": 6},
        AgentRole.MOTIVATION: {"motivation_clarity": 8, "program_fit": 7},
        AgentRole.DEVILS_ADVOCATE: {"risk_flags": 9, "consistency": 8},
    }
    return AgentScorecard(
        role=role,
        scores=scores[role],
        justifications={k: "test" for k in scores[role]},
    )


@pytest.fixture
def _mock_agents(mocker: MockerFixture):
    """Patch all agent functions to return predictable results."""
    for fn_name in ("evaluate_academic", "evaluate_reference", "evaluate_motivation", "evaluate_devils_advocate"):
        role = {
            "evaluate_academic": AgentRole.ACADEMIC,
            "evaluate_reference": AgentRole.REFERENCE,
            "evaluate_motivation": AgentRole.MOTIVATION,
            "evaluate_devils_advocate": AgentRole.DEVILS_ADVOCATE,
        }[fn_name]

        async def _fake(*, role=role, **kwargs):
            return _make_scorecard(role)

        mocker.patch(f"agentic_admission.agents.orchestrator.{fn_name}", side_effect=_fake)

    # No disagreements
    async def _fake_detect(**kwargs):
        return ()

    mocker.patch("agentic_admission.agents.orchestrator.detect_disagreements", side_effect=_fake_detect)

    # Simple synthesis
    async def _fake_synthesize(*, candidate_id, scorecards, debates, model, base_url):
        return PanelVerdict(
            candidate_id=candidate_id,
            scorecards=scorecards,
            debates=debates,
            final_scores={
                "academic_strength": 8, "institution_quality": 7,
                "reference_quality": 7, "calibration_confidence": 6,
                "motivation_clarity": 8, "program_fit": 7,
                "risk_flags": 9, "consistency": 8,
            },
            composite_score=7.5,
            decision=Decision.ACCEPT,
            justification="Strong candidate.",
        )

    mocker.patch("agentic_admission.agents.orchestrator.synthesize", side_effect=_fake_synthesize)


@pytest.mark.usefixtures("_mock_agents")
class TestEvaluateCandidate:
    async def test_returns_panel_verdict(self):
        verdict = await evaluate_candidate(
            candidate_id="2024-25_round1_42",
            transcript_text="GPA: 3.8/4.0",
            letters_text="Dear committee...",
            calibration_context="US avg: 0.85",
            historical_letters="[Letter 1]...",
            motivation_text="I want to join MTE...",
            cv_text="Experience: Google...",
            full_dossier_text="[All documents]...",
            model="test",
            base_url="http://test",
        )
        assert isinstance(verdict, PanelVerdict)
        assert verdict.candidate_id == "2024-25_round1_42"
        assert verdict.decision == Decision.ACCEPT

    async def test_all_four_scorecards_present(self):
        verdict = await evaluate_candidate(
            candidate_id="test",
            transcript_text="t",
            letters_text="l",
            calibration_context="c",
            historical_letters="h",
            motivation_text="m",
            cv_text="cv",
            full_dossier_text="f",
            model="test",
            base_url="http://test",
        )
        roles = {card.role for card in verdict.scorecards}
        assert roles == {AgentRole.ACADEMIC, AgentRole.REFERENCE, AgentRole.MOTIVATION, AgentRole.DEVILS_ADVOCATE}
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: FAIL — module does not exist.

**Step 3: Write the implementation**

Create `src/agentic_admission/agents/orchestrator.py`:

```python
"""Orchestrator: runs the 4-phase deliberation protocol for one candidate."""

from __future__ import annotations

import asyncio

from loguru import logger

from agentic_admission.agents.chair import detect_disagreements, moderate_debate, synthesize
from agentic_admission.agents.evaluators import (
    evaluate_academic,
    evaluate_devils_advocate,
    evaluate_motivation,
    evaluate_reference,
)
from agentic_admission.models.evaluation import DebateTranscript, PanelVerdict


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
) -> PanelVerdict:
    """Run the full 4-phase deliberation protocol for a single candidate.

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

    Returns
    -------
    PanelVerdict
        The final scorecard, recommendation, and justification.
    """
    logger.info("Phase 1: Independent evaluation for {}", candidate_id)

    academic_task = evaluate_academic(
        transcript_text=transcript_text, model=model, base_url=base_url,
    )
    reference_task = evaluate_reference(
        letters_text=letters_text,
        calibration_context=calibration_context,
        historical_letters=historical_letters,
        model=model,
        base_url=base_url,
    )
    motivation_task = evaluate_motivation(
        motivation_text=motivation_text, cv_text=cv_text, model=model, base_url=base_url,
    )
    devils_task = evaluate_devils_advocate(
        full_dossier_text=full_dossier_text, model=model, base_url=base_url,
    )

    scorecards = tuple(await asyncio.gather(
        academic_task, reference_task, motivation_task, devils_task,
    ))

    logger.info("Phase 2: Disagreement detection for {}", candidate_id)

    conflicts = await detect_disagreements(
        scorecards=scorecards, model=model, base_url=base_url,
    )

    debates: tuple[DebateTranscript, ...] = ()
    if conflicts:
        logger.info(
            "Phase 3: Targeted debate on {} conflict(s) for {}", len(conflicts), candidate_id,
        )
        debate_results = await asyncio.gather(*(
            moderate_debate(
                conflict=conflict, scorecards=scorecards, model=model, base_url=base_url,
            )
            for conflict in conflicts
        ))
        debates = tuple(debate_results)
    else:
        logger.info("Phase 3: No disagreements, skipping debate for {}", candidate_id)

    logger.info("Phase 4: Final synthesis for {}", candidate_id)

    return await synthesize(
        candidate_id=candidate_id,
        scorecards=scorecards,
        debates=debates,
        model=model,
        base_url=base_url,
    )
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_orchestrator.py -v`
Expected: ALL PASS

**Step 5: Lint and commit**

```bash
uv run poe lint
git add src/agentic_admission/agents/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add deliberation orchestrator with 4-phase protocol"
```

---

## Task 7: Update `agents/__init__.py` and Wire Into Main

Export the public API and update `main.py` to support running evaluations.

**Files:**
- Modify: `src/agentic_admission/agents/__init__.py`
- Modify: `src/agentic_admission/main.py`

**Step 1: Update agents __init__**

```python
"""Multi-agent orchestration for admission evaluation."""

from agentic_admission.agents.orchestrator import evaluate_candidate

__all__ = ["evaluate_candidate"]
```

**Step 2: Update main.py**

```python
"""Entry point for the agentic-admission system."""

from __future__ import annotations

import sys

from loguru import logger

from agentic_admission.config import settings


def run() -> None:
    """Launch the admission agent pipeline."""
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level)
    logger.info("agentic-admission starting (model={})", settings.model_name)
    logger.info("Agent deliberation system ready. Use evaluate_candidate() to evaluate dossiers.")


if __name__ == "__main__":
    run()
```

**Step 3: Run full test suite**

```bash
uv run poe lint
uv run pytest -v -m "not slow"
```
Expected: ALL PASS

**Step 4: Commit**

```bash
git add src/agentic_admission/agents/__init__.py src/agentic_admission/main.py
git commit -m "feat: wire agent orchestrator into package public API"
```

---

## Task 8 (Future): Calibration Pipeline

> This task is deferred. It requires the zero-entropy chunking + embedding infrastructure.
> Implement after Tasks 1-7 are complete and validated.

**Scope:**
- Create `src/agentic_admission/calibration/chunker.py` — zero-entropy chunking of reference letters
- Create `src/agentic_admission/calibration/embedder.py` — embed chunks with sentence-transformer
- Create `src/agentic_admission/calibration/retriever.py` — vector DB storage + reranked retrieval
- Create `src/agentic_admission/calibration/profiler.py` — generate calibration profiles by region
- Dependencies: `lancedb`, `sentence-transformers`

This will feed into `evaluate_reference()` by providing the `calibration_context` and `historical_letters` parameters.
