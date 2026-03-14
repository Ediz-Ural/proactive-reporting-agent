"""
LLM utility functions for the reporting agent.
Centralised LLM calls — all agents use these helpers.
"""

from __future__ import annotations

import json
import logging
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
