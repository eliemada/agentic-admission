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
