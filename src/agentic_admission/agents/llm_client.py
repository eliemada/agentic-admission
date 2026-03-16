"""Async LLM client for OpenAI-compatible chat completion endpoints."""

from __future__ import annotations

import json

import httpx
from loguru import logger
from pydantic import BaseModel


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


async def complete[T: BaseModel](
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
