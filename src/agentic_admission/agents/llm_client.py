"""Async LLM client for OpenAI-compatible chat completion endpoints."""

from __future__ import annotations

import json
from typing import Literal

import httpx
from loguru import logger
from pydantic import BaseModel, ValidationError
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMResponseError(LLMError):
    """LLM returned unparseable or invalid response."""


class LLMConnectionError(LLMError):
    """Transient connection/HTTP error after retries exhausted."""


class ChatMessage(BaseModel, frozen=True):
    """A single message in a chat conversation.

    Attributes
    ----------
    role
        One of ``"system"``, ``"user"``, ``"assistant"``.
    content
        The message text.
    """

    role: Literal["system", "user", "assistant"]
    content: str


_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({429, 502, 503, 504})


def _is_retryable(exc: BaseException) -> bool:
    """Return True for transient errors that warrant a retry.

    Parameters
    ----------
    exc
        The exception to inspect.

    Returns
    -------
    bool
        Whether the exception is retryable.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _RETRYABLE_STATUS_CODES
    return isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout))


@retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=30),
    reraise=False,
)
async def _post_with_retry(
    *, base_url: str, payload: dict, client: httpx.AsyncClient | None = None
) -> httpx.Response:
    """Send a POST request to the LLM endpoint with automatic retries.

    Parameters
    ----------
    base_url
        Base URL of the vLLM endpoint.
    payload
        JSON payload to send.
    client
        Optional shared ``httpx.AsyncClient``.  When provided the caller owns
        the client lifetime and no new client is created.

    Returns
    -------
    httpx.Response
        The HTTP response from the server.

    Raises
    ------
    LLMConnectionError
        When all retry attempts are exhausted.
    """
    if client is not None:
        response = await client.post(f"{base_url}/chat/completions", json=payload)
        response.raise_for_status()
        return response
    async with httpx.AsyncClient(timeout=120.0) as new_client:
        response = await new_client.post(f"{base_url}/chat/completions", json=payload)
        response.raise_for_status()
    return response


async def complete[T: BaseModel](
    *,
    messages: list[ChatMessage],
    response_model: type[T],
    model: str,
    base_url: str,
    client: httpx.AsyncClient | None = None,
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
    client
        Optional shared ``httpx.AsyncClient``.  When provided the caller owns
        the client lifetime and no new client is created per request.
    temperature
        Sampling temperature.
    max_tokens
        Maximum tokens in the response.

    Returns
    -------
    T
        Parsed Pydantic model instance.

    Raises
    ------
    LLMConnectionError
        When the server is unreachable or returns transient errors after retries.
    LLMResponseError
        When the response cannot be parsed as JSON or fails Pydantic validation.
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

    try:
        response = await _post_with_retry(base_url=base_url, payload=payload, client=client)
    except RetryError as exc:
        cause = exc.last_attempt.exception()
        msg = f"LLM request failed after retries: {cause}"
        raise LLMConnectionError(msg) from cause
    except (httpx.HTTPStatusError, httpx.ConnectError, httpx.ReadTimeout) as exc:
        msg = f"LLM request failed: {exc}"
        raise LLMConnectionError(msg) from exc

    body = response.json()
    raw_content = body["choices"][0]["message"]["content"]

    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        msg = f"LLM returned unparseable JSON: {raw_content[:200]}"
        raise LLMResponseError(msg) from exc

    try:
        return response_model.model_validate(parsed)
    except ValidationError as exc:
        msg = f"LLM response failed {response_model.__name__} validation"
        raise LLMResponseError(msg) from exc
