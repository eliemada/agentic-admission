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
        response_json = {"choices": [{"message": {"content": body}}]}
        mock_response = mocker.Mock()
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
