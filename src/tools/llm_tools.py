"""
LLM utility functions for the reporting agent.
Centralised LLM calls — all agents use these helpers.
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar

logger = logging.getLogger(__name__)

# Per-run credentials supplied by the caller (an API request carrying the user's
# own key). Never persisted — the value lives only for the duration of the run.
_credentials: ContextVar[tuple[str, str] | None] = ContextVar("llm_credentials", default=None)


@contextmanager
def llm_credentials(api_key: str | None = None, model: str | None = None):
    """
    Bind an API key and/or model for every LLM call made inside the block.

    Falls back to the values in settings for anything not supplied, so a run
    without caller credentials behaves exactly as before.
    """
    if not api_key and not model:
        yield
        return

    token = _credentials.set((api_key or "", model or ""))
    try:
        yield
    finally:
        _credentials.reset(token)


def resolve_credentials() -> tuple[str, str]:
    """Return the (api_key, model) in effect: caller-supplied first, then settings."""
    from config.settings import settings

    api_key, model = _credentials.get() or ("", "")
    return api_key or settings.OPENAI_API_KEY, model or settings.OPENAI_MODEL


def get_llm(temperature: float = 0.1):
    """
    Get a configured ChatOpenAI instance.

    Uses the credentials bound by `llm_credentials` when present, otherwise the
    ones from settings.

    Returns:
        ChatOpenAI instance, or None if no API key is available.
    """
    api_key, model = resolve_credentials()

    if not api_key:
        logger.warning("No OpenAI API key available — LLM calls will be skipped")
        return None

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key,
    )


def call_llm_with_retry(
    prompt: str,
    system_prompt: str = "",
    temperature: float = 0.1,
    max_retries: int = 2,
) -> str | None:
    """
    Call the LLM with retry mechanism.

    Args:
        prompt: User prompt.
        system_prompt: System prompt (optional).
        temperature: LLM temperature.
        max_retries: Max number of retries.

    Returns:
        LLM response string, or None if failed / unavailable.
    """
    llm = get_llm(temperature=temperature)
    if llm is None:
        return None

    from langchain_core.messages import HumanMessage, SystemMessage

    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    for attempt in range(max_retries + 1):
        try:
            response = llm.invoke(messages)
            return response.content
        except Exception as exc:
            logger.warning("LLM call attempt %d failed: %s", attempt + 1, exc)
            if attempt < max_retries:
                time.sleep(1 * (attempt + 1))
            else:
                logger.error("LLM call failed after %d attempts", max_retries + 1)
                return None

    return None
