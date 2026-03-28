"""
Tests for the EvaluatorAgent — LLM-based and rule-based evaluation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.evaluator import EvaluatorAgent, SCORE_KEYS


class TestEvaluatorAgent:
    """Test suite for EvaluatorAgent."""

    def _make_state(self, **overrides):
        """Create a minimal AgentState for testing."""
        state = {
            "start_date": "2024-01-01",
            "end_date": "2024-01-31",
            "report_type": "weekly",
            "recipients": [],
            "raw_data": {
                "weekly_summary": {
                    "total_sales": 52340.75,
                    "total_orders": 378,
                    "avg_order_value": 138.47,
                    "unique_customers": 245,
                },
                "daily_sales": [],
            },
            "quality_report": {"is_valid": True},
            "analysis_results": {
                "trends": {"total_sales": {"direction": "increasing", "growth_rate_pct": 15.2}},
                "anomalies": [{"date": "2024-01-15", "value": 1200}],
                "forecast": {"predictions": [{"predicted": 55000}]},
                "category_performance": [{"category": "Tech", "total_sales": 20000}],
                "analysis_metadata": {
                    "analyses_completed": ["trends", "anomalies", "forecast"],
                    "analyses_failed": [],
                },
            },
            "historical_context": "",
            "draft_report": (
                "## Haftalık Satış Raporu — 2024-01-01 / 2024-01-31\n\n"
                "### Özet Göstergeler\n"
                "- Toplam gelir: 52340.75 TL\n"
                "- Sipariş sayısı: 378\n\n"
                "### Önemli Bulgular\n"
                "- [TREND] Satışlar yükseliş trendinde\n"
                "- [ANOMALİ] 1 anomali tespit edildi\n\n"
                "### Aksiyon Önerileri\n"
                "1. Stok planlamasını gözden geçirin.\n"
                "2. Kampanya stratejisini güncelleyin.\n"
                "3. Müşteri segmentasyonunu iyileştirin.\n"
            ),
            "evaluation": None,
            "evaluator_iteration": 1,
            "final_report": None,
            "delivery_status": None,
            "feedback_metrics": None,
            "analysis_plan": ["trends", "anomalies"],
            "writer_strategy": "few_shot",
            "errors": [],
            "current_agent": "writer",
            "run_id": "test-run-001",
        }
        state.update(overrides)
        return state

    # ── LLM-based evaluation (mocked) ────────────────────────────────────────

    def test_llm_evaluation_approved(self):
        """LLM returns high scores → approved=True."""
        llm_response = json.dumps({
            "numerical_accuracy": 0.9,
            "completeness": 0.85,
            "readability": 0.9,
            "actionability": 0.8,
            "hallucination_free": 0.95,
            "overall_score": 0.88,
            "approved": True,
            "feedback": "Rapor genel olarak iyi.",
        })

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=llm_response):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        ev = result["evaluation"]
        assert ev["approved"] is True
        assert ev["overall_score"] >= 0.7
        assert all(k in ev for k in SCORE_KEYS)

    def test_llm_evaluation_rejected(self):
        """LLM returns low scores → approved=False."""
        llm_response = json.dumps({
            "numerical_accuracy": 0.3,
            "completeness": 0.4,
            "readability": 0.5,
            "actionability": 0.2,
            "hallucination_free": 0.6,
            "overall_score": 0.4,
            "approved": False,
            "feedback": "Rapor çok eksik.",
        })

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=llm_response):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        ev = result["evaluation"]
        assert ev["approved"] is False
        assert ev["overall_score"] < 0.7

    def test_llm_response_with_markdown_fences(self):
        """LLM wraps JSON in ```json ... ``` → still parses correctly."""
        inner = json.dumps({
            "numerical_accuracy": 0.9,
            "completeness": 0.85,
            "readability": 0.9,
            "actionability": 0.8,
            "hallucination_free": 0.95,
            "feedback": "İyi rapor.",
        })
        llm_response = f"```json\n{inner}\n```"

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=llm_response):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        ev = result["evaluation"]
        assert ev["approved"] is True
        assert all(k in ev for k in SCORE_KEYS)

    def test_llm_returns_invalid_json_falls_back(self):
        """LLM returns non-JSON text → falls back to rule-based."""
        with patch("src.tools.llm_tools.call_llm_with_retry", return_value="This is not JSON at all"):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        ev = result["evaluation"]
        assert "overall_score" in ev
        assert "approved" in ev
        # Should still work via rule-based fallback

    def test_llm_returns_missing_keys_falls_back(self):
        """LLM returns JSON but missing required keys → falls back."""
        partial = json.dumps({"numerical_accuracy": 0.9, "completeness": 0.8})

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=partial):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        ev = result["evaluation"]
        assert "overall_score" in ev
        # Fell back to rule-based

    # ── Score clamping ───────────────────────────────────────────────────────

    def test_scores_clamped_to_0_1(self):
        """Scores outside 0-1 are clamped."""
        llm_response = json.dumps({
            "numerical_accuracy": 1.5,
            "completeness": -0.3,
            "readability": 0.9,
            "actionability": 2.0,
            "hallucination_free": 0.95,
            "feedback": "Test clamping.",
        })

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=llm_response):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        ev = result["evaluation"]
        assert ev["numerical_accuracy"] == 1.0
        assert ev["completeness"] == 0.0
        assert ev["actionability"] == 1.0

    # ── Overall score recalculation ──────────────────────────────────────────

    def test_overall_score_recalculated(self):
        """Overall score is recalculated from individual scores, not trusted from LLM."""
        llm_response = json.dumps({
            "numerical_accuracy": 0.8,
            "completeness": 0.8,
            "readability": 0.8,
            "actionability": 0.8,
            "hallucination_free": 0.8,
            "overall_score": 0.99,  # wrong — should be 0.8
            "approved": True,
            "feedback": "ok",
        })

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=llm_response):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        assert result["evaluation"]["overall_score"] == 0.8  # recalculated

    # ── Rule-based fallback ──────────────────────────────────────────────────

    def test_rule_based_fallback_when_no_llm(self):
        """When LLM is unavailable, rule-based evaluation runs."""
        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=None):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        ev = result["evaluation"]
        assert "overall_score" in ev
        assert "approved" in ev
        assert "feedback" in ev
        assert all(k in ev for k in SCORE_KEYS)

    def test_rule_based_approves_good_report(self):
        """Rule-based evaluation approves a well-structured report."""
        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=None):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        ev = result["evaluation"]
        # The default _make_state has a good report with all sections
        assert ev["approved"] is True
        assert ev["overall_score"] >= 0.7

    def test_rule_based_rejects_short_report(self):
        """Rule-based evaluation rejects a very short report."""
        state = self._make_state(draft_report="Kısa rapor.")

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=None):
            agent = EvaluatorAgent()
            result = agent.evaluate(state)

        ev = result["evaluation"]
        assert ev["approved"] is False
        assert ev["overall_score"] < 0.7

    def test_rule_based_checks_numerical_accuracy(self):
        """Rule-based gives high accuracy score when revenue appears in report."""
        state = self._make_state()
        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=None):
            agent = EvaluatorAgent()
            result = agent.evaluate(state)

        # The default report contains "52340.75" which matches weekly_summary
        assert result["evaluation"]["numerical_accuracy"] >= 0.7

    def test_rule_based_low_accuracy_when_no_numbers(self):
        """Rule-based gives low accuracy when revenue is missing from report."""
        state = self._make_state(
            draft_report=(
                "## Haftalık Satış Raporu\n\n"
                "### Özet Göstergeler\n- Veri yok\n\n"
                "### Önemli Bulgular\n- Yok\n\n"
                "### Aksiyon Önerileri\n1. Veri toplama gerekli.\n2. İyileştirme yapılmalı.\n"
            )
        )
        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=None):
            agent = EvaluatorAgent()
            result = agent.evaluate(state)

        assert result["evaluation"]["numerical_accuracy"] <= 0.5

    # ── Empty report ─────────────────────────────────────────────────────────

    def test_empty_report_gives_zero_scores(self):
        """Empty draft_report → all zero scores, not approved."""
        state = self._make_state(draft_report="")
        agent = EvaluatorAgent()
        result = agent.evaluate(state)

        ev = result["evaluation"]
        assert ev["approved"] is False
        assert ev["overall_score"] == 0.0

    # ── current_agent field ──────────────────────────────────────────────────

    def test_sets_current_agent(self):
        """Evaluator sets current_agent to 'evaluator'."""
        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=None):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        assert result["current_agent"] == "evaluator"

    # ── Approval threshold ───────────────────────────────────────────────────

    def test_approval_threshold_exactly_0_7(self):
        """Score exactly 0.7 → approved=True."""
        llm_response = json.dumps({
            "numerical_accuracy": 0.7,
            "completeness": 0.7,
            "readability": 0.7,
            "actionability": 0.7,
            "hallucination_free": 0.7,
            "feedback": "Eşik değer.",
        })

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=llm_response):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        assert result["evaluation"]["approved"] is True
        assert result["evaluation"]["overall_score"] == 0.7

    def test_approval_threshold_just_below(self):
        """Score just below 0.7 → approved=False."""
        llm_response = json.dumps({
            "numerical_accuracy": 0.69,
            "completeness": 0.69,
            "readability": 0.69,
            "actionability": 0.69,
            "hallucination_free": 0.69,
            "feedback": "Yetersiz.",
        })

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=llm_response):
            agent = EvaluatorAgent()
            result = agent.evaluate(self._make_state())

        assert result["evaluation"]["approved"] is False


class TestEvaluatorParsing:
    """Test JSON parsing edge cases."""

    def test_parse_valid_json(self):
        agent = EvaluatorAgent()
        response = json.dumps({
            "numerical_accuracy": 0.9,
            "completeness": 0.8,
            "readability": 0.85,
            "actionability": 0.75,
            "hallucination_free": 0.9,
            "feedback": "Good.",
        })
        result = agent._parse_llm_evaluation(response)
        assert result is not None
        assert result["overall_score"] == 0.84

    def test_parse_json_with_extra_text(self):
        """JSON with surrounding text → parse fails (returns None)."""
        agent = EvaluatorAgent()
        result = agent._parse_llm_evaluation("Here is my evaluation: {bad json}")
        assert result is None

    def test_parse_json_with_code_fences(self):
        agent = EvaluatorAgent()
        inner = json.dumps({
            "numerical_accuracy": 0.9,
            "completeness": 0.8,
            "readability": 0.85,
            "actionability": 0.75,
            "hallucination_free": 0.9,
            "feedback": "Good.",
        })
        result = agent._parse_llm_evaluation(f"```json\n{inner}\n```")
        assert result is not None
        assert "overall_score" in result

    def test_parse_missing_required_fields(self):
        agent = EvaluatorAgent()
        result = agent._parse_llm_evaluation('{"numerical_accuracy": 0.9}')
        assert result is None

    def test_parse_non_numeric_score(self):
        """Non-numeric score values → parse fails."""
        agent = EvaluatorAgent()
        data = {
            "numerical_accuracy": "high",
            "completeness": 0.8,
            "readability": 0.85,
            "actionability": 0.75,
            "hallucination_free": 0.9,
        }
        result = agent._parse_llm_evaluation(json.dumps(data))
        assert result is None
