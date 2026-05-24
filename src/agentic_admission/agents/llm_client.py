"""Async LLM client for OpenAI-compatible chat completion endpoints."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

import httpx
from loguru import logger
from pydantic import BaseModel, ValidationError
from tenacity import RetryError, retry, retry_if_exception, stop_after_attempt, wait_exponential

from agentic_admission.config import settings

_HTTP_PAYMENT_REQUIRED: int = 402
_BILLING_ERROR_MESSAGE: str = (
    "OpenRouter credits exhausted. Add more at https://openrouter.ai/settings/credits"
)
_MAX_LLM_ATTEMPTS: int = 3


class LLMError(Exception):
    """Base exception for LLM client errors."""


class LLMResponseError(LLMError):
    """LLM returned unparseable or invalid response."""


class LLMConnectionError(LLMError):
    """Transient connection/HTTP error after retries exhausted."""


class LLMBillingError(LLMError):
    """API returned 402 — credits exhausted, no point retrying."""


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
    return isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.ReadError))


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


def _extract_json(text: str) -> dict | None:
    """Try multiple strategies to extract a JSON object from LLM output.

    Handles: raw JSON, markdown-fenced JSON, JSON embedded after thinking text.
    """
    cleaned = text.strip()

    # Strategy 1: direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Strategy 2: strip markdown fences
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        inner = cleaned[first_newline + 1 :]
        if inner.rstrip().endswith("```"):
            inner = inner.rstrip()[:-3].rstrip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            pass

    # Strategy 3: find the first { and last } — extract JSON from mixed text
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidate = cleaned[first_brace : last_brace + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Strategy 4: find JSON in markdown code block within text
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", cleaned, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    return None


async def complete[T: BaseModel](
    *,
    messages: list[ChatMessage],
    response_model: type[T],
    model: str,
    base_url: str,
    client: httpx.AsyncClient | None = None,
    temperature: float = 0.1,
    max_tokens: int = 16384,
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
    payload = _build_payload(
        messages=messages,
        response_model=response_model,
        model=model,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    for attempt in range(1, _MAX_LLM_ATTEMPTS + 1):
        logger.debug(
            "LLM request to {}: model={} (attempt {}/{})",
            base_url,
            model,
            attempt,
            _MAX_LLM_ATTEMPTS,
        )

        body = await _send_request(base_url=base_url, payload=payload, client=client)
        raw_content = _extract_raw_content(body, attempt=attempt)
        if raw_content is None:
            continue  # empty content, retry

        logger.debug("LLM raw response: {}", raw_content[:500])
        parsed = _extract_json(raw_content)
        if parsed is None:
            if attempt < _MAX_LLM_ATTEMPTS:
                logger.warning(
                    "LLM returned unparseable JSON (attempt {}/{}), retrying ...",
                    attempt,
                    _MAX_LLM_ATTEMPTS,
                )
                continue
            msg = f"LLM returned unparseable JSON: {raw_content[:200]}"
            raise LLMResponseError(msg)

        try:
            return response_model.model_validate(parsed)
        except ValidationError as exc:
            if attempt < _MAX_LLM_ATTEMPTS:
                logger.warning(
                    "LLM response failed validation (attempt {}/{}), retrying ...",
                    attempt,
                    _MAX_LLM_ATTEMPTS,
                )
                continue
            msg = f"LLM response failed {response_model.__name__} validation"
            raise LLMResponseError(msg) from exc

    msg = "LLM request failed: exhausted all attempts"
    raise LLMResponseError(msg)


def _build_payload(
    *,
    messages: list[ChatMessage],
    response_model: type[BaseModel],
    model: str,
    base_url: str,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """Build the OpenAI-style chat completion payload with JSON-schema injection."""
    schema_json = json.dumps(response_model.model_json_schema(), indent=2)
    schema_instruction = (
        "\n\n# CRITICAL OUTPUT FORMAT REQUIREMENT\n"
        "You MUST respond with ONLY a valid JSON object. "
        "No thinking, no explanation, no markdown fences, no text before or after. "
        "Your entire response must be parseable by json.loads().\n\n"
        f"Required JSON schema:\n{schema_json}"
    )
    formatted_messages = [
        {
            "role": m.role,
            "content": m.content + schema_instruction if m.role == "system" else m.content,
        }
        for m in messages
    ]

    payload: dict[str, Any] = {
        "model": model,
        "messages": formatted_messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if "openrouter" in base_url and settings.openrouter_provider:
        payload["provider"] = {"order": [settings.openrouter_provider]}
    return payload


async def _send_request(
    *, base_url: str, payload: dict[str, Any], client: httpx.AsyncClient | None
) -> dict[str, Any]:
    """Dispatch a single LLM request and translate transport errors."""
    try:
        response = await _post_with_retry(base_url=base_url, payload=payload, client=client)
    except RetryError as exc:
        cause = exc.last_attempt.exception()
        msg = f"LLM request failed after retries: {cause}"
        raise LLMConnectionError(msg) from cause
    except httpx.HTTPStatusError as exc:
        _handle_http_error(exc)
    except (httpx.ConnectError, httpx.ReadTimeout) as exc:
        msg = f"LLM request failed: {exc}"
        raise LLMConnectionError(msg) from exc

    body = response.json()
    if "error" in body:
        err = body["error"]
        err_msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        msg = f"LLM returned error in response body: {err_msg}"
        raise LLMResponseError(msg)
    return body


def _handle_http_error(exc: httpx.HTTPStatusError) -> None:
    """Map an HTTPStatusError to the right ``LLMError`` subclass."""
    try:
        error_body = exc.response.text[:500]
    except Exception:
        error_body = "(unreadable)"
    logger.warning("LLM HTTP {}: {}", exc.response.status_code, error_body)
    if exc.response.status_code == _HTTP_PAYMENT_REQUIRED:
        raise LLMBillingError(_BILLING_ERROR_MESSAGE) from exc
    msg = f"LLM request failed: {exc}"
    raise LLMConnectionError(msg) from exc


def _extract_raw_content(body: dict[str, Any], *, attempt: int) -> str | None:
    """Pull ``choices[0].message.content`` from the LLM response body.

    Returns ``None`` when the content is empty and a retry is still
    available; raises ``LLMResponseError`` on terminal failure or malformed
    structure.
    """
    try:
        raw_content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        msg = f"LLM response missing expected structure: {str(body)[:200]}"
        raise LLMResponseError(msg) from exc

    if raw_content:
        return raw_content
    if attempt < _MAX_LLM_ATTEMPTS:
        logger.warning(
            "LLM returned empty content (attempt {}/{}), retrying ...", attempt, _MAX_LLM_ATTEMPTS
        )
        return None
    msg = f"LLM returned empty content after {_MAX_LLM_ATTEMPTS} attempts: {str(body)[:200]}"
    raise LLMResponseError(msg)
