"""
LLM utility functions for the reporting agent.
Centralised LLM calls — all agents use these helpers.
"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

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


def interpret_analysis(analysis_results: dict[str, Any]) -> str | None:
    """
    Ask LLM to produce a 3-5 bullet point summary of the analysis results.

    This is a PREVIEW — the full Writer Agent will do this properly in Week 3.

    Args:
        analysis_results: Dict of analysis outputs from AnalystAgent.

    Returns:
        LLM-generated summary string, or None if LLM is unavailable.
    """
    llm = get_llm()
    if llm is None:
        logger.info("Skipping LLM interpretation — no API key configured")
        return None

    prompt = (
        "Sen bir is analisti asistanisin. Asagidaki analiz sonuclarini "
        "kisa ve oz 3-5 madde ile yorumla. Her madde bir insight olsun.\n"
        "Turkce yaz.\n\n"
        f"Analiz Sonuclari:\n{json.dumps(analysis_results, indent=2, default=str)}"
    )

    try:
        response = llm.invoke(prompt)
        return response.content
    except Exception as exc:
        logger.error("LLM interpretation failed: %s", exc)
        return None


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


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """
    Estimate token count for the given text.

    Tries tiktoken if available, otherwise uses a simple heuristic.

    Args:
        text: Input text.
        model: Model name for tiktoken encoding.

    Returns:
        Estimated token count.
    """
    try:
        import tiktoken

        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    except (ImportError, KeyError):
        # Simple heuristic: ~4 chars per token for English/Turkish
        return len(text) // 4
