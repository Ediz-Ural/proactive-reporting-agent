"""
LLM utility functions for the reporting agent.
Centralised LLM calls — all agents use these helpers.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


def get_llm(temperature: float = 0.1):
    """
    Get a configured ChatOpenAI instance.

    Returns:
        ChatOpenAI instance, or None if API key is not configured.
    """
    from config.settings import settings

    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — LLM calls will be skipped")
        return None

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.OPENAI_MODEL,
        temperature=temperature,
        api_key=settings.OPENAI_API_KEY,
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
