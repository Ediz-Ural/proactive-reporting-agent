"""
Tests for the Evaluator-Optimizer loop — the most critical test file.

Verifies that:
1. Evaluator rejection triggers Writer revision
2. evaluator_iteration increments correctly
3. Max iterations forces delivery
4. Writer receives evaluator feedback in revision prompt
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.evaluator import EvaluatorAgent
from src.agents.writer import WriterAgent
from src.graph.workflow import route_after_evaluator


class TestEvaluatorOptimizerLoop:
    """Integration tests for the Evaluator-Optimizer pattern."""

    def _make_state(self, **overrides):
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
            "draft_report": None,
            "evaluation": None,
            "evaluator_iteration": 0,
            "final_report": None,
            "delivery_status": None,
            "feedback_metrics": None,
            "analysis_plan": ["trends", "anomalies"],
            "writer_strategy": "few_shot",
            "errors": [],
            "current_agent": "rag",
            "run_id": "test-loop-001",
        }
        state.update(overrides)
        return state

    # ── route_after_evaluator logic ──────────────────────────────────────────

    def test_route_approved_goes_to_delivery(self):
        """Approved report routes to delivery."""
        state = self._make_state(
            evaluation={"approved": True, "overall_score": 0.85},
            evaluator_iteration=1,
        )
        assert route_after_evaluator(state) == "delivery"

    def test_route_rejected_goes_to_writer(self):
        """Rejected report routes back to writer."""
        state = self._make_state(
            evaluation={"approved": False, "overall_score": 0.5},
            evaluator_iteration=1,
        )
        assert route_after_evaluator(state) == "writer"

    def test_route_max_iterations_forces_delivery(self):
        """Even if not approved, max iterations routes to delivery."""
        state = self._make_state(
            evaluation={"approved": False, "overall_score": 0.4},
            evaluator_iteration=3,  # equals MAX_EVALUATOR_ITERATIONS
        )
        assert route_after_evaluator(state) == "delivery"

    def test_route_above_max_iterations_forces_delivery(self):
        """Iteration count exceeding max still routes to delivery."""
        state = self._make_state(
            evaluation={"approved": False, "overall_score": 0.3},
            evaluator_iteration=5,
        )
        assert route_after_evaluator(state) == "delivery"

    def test_route_missing_evaluation_defaults_to_delivery(self):
        """Missing evaluation (approved defaults True) → delivery."""
        state = self._make_state(evaluation=None, evaluator_iteration=1)
        assert route_after_evaluator(state) == "delivery"

    # ── Writer receives feedback on revision ─────────────────────────────────

    def test_writer_includes_feedback_in_revision(self):
        """Writer includes evaluator feedback when evaluation.approved=False."""
        state = self._make_state(
            evaluation={
                "approved": False,
                "overall_score": 0.5,
                "feedback": "Öneriler eksik, rakamlar hatalı.",
            },
            evaluator_iteration=1,
        )

        writer = WriterAgent(strategy="zero_shot")
        prompt = writer._build_prompt(
            analysis_results=state["analysis_results"],
            historical_context=state["historical_context"],
            start_date=state["start_date"],
            end_date=state["end_date"],
            report_type=state["report_type"],
            raw_data=state["raw_data"],
            evaluation=state["evaluation"],
        )

        assert "ÖNCEKİ RAPOR DEĞERLENDİRMESİ" in prompt
        assert "Öneriler eksik" in prompt
        assert "0.5" in prompt

    def test_writer_no_feedback_on_first_draft(self):
        """Writer does NOT include revision note on first draft (no evaluation)."""
        state = self._make_state(evaluation=None, evaluator_iteration=0)

        writer = WriterAgent(strategy="zero_shot")
        prompt = writer._build_prompt(
            analysis_results=state["analysis_results"],
            historical_context=state["historical_context"],
            start_date=state["start_date"],
            end_date=state["end_date"],
            report_type=state["report_type"],
            raw_data=state["raw_data"],
            evaluation=state["evaluation"],
        )

        assert "ÖNCEKİ RAPOR DEĞERLENDİRMESİ" not in prompt

    def test_writer_no_feedback_when_approved(self):
        """Writer does NOT include revision note when evaluation.approved=True."""
        state = self._make_state(
            evaluation={"approved": True, "overall_score": 0.9, "feedback": "OK"},
            evaluator_iteration=1,
        )

        writer = WriterAgent(strategy="zero_shot")
        prompt = writer._build_prompt(
            analysis_results=state["analysis_results"],
            historical_context=state["historical_context"],
            start_date=state["start_date"],
            end_date=state["end_date"],
            report_type=state["report_type"],
            raw_data=state["raw_data"],
            evaluation=state["evaluation"],
        )

        assert "ÖNCEKİ RAPOR DEĞERLENDİRMESİ" not in prompt

    # ── evaluator_iteration counter ──────────────────────────────────────────

    def test_writer_increments_iteration(self):
        """Writer increments evaluator_iteration on each call."""
        state = self._make_state(evaluator_iteration=0)

        with patch("src.agents.writer.WriterAgent._call_llm", return_value=None):
            writer = WriterAgent()
            result = writer.write(state)

        assert result["evaluator_iteration"] == 1

    def test_writer_increments_on_revision(self):
        """Writer increments iteration on revision too."""
        state = self._make_state(
            evaluator_iteration=2,
            evaluation={"approved": False, "overall_score": 0.5, "feedback": "Fix it"},
        )

        with patch("src.agents.writer.WriterAgent._call_llm", return_value=None):
            writer = WriterAgent()
            result = writer.write(state)

        assert result["evaluator_iteration"] == 3

    # ── Full loop simulation (Writer → Evaluator → Writer → Evaluator) ─────

    def test_evaluator_rejects_and_writer_revises(self):
        """
        Simulate: Writer produces draft → Evaluator rejects (score=0.5)
        → Writer rewrites → Evaluator approves (score=0.8)
        """
        state = self._make_state()

        # Iteration 1: Writer produces first draft
        with patch("src.agents.writer.WriterAgent._call_llm", return_value=None):
            writer = WriterAgent()
            writer_result_1 = writer.write(state)

        state.update(writer_result_1)
        assert state["evaluator_iteration"] == 1
        assert state["draft_report"] is not None

        # Iteration 1: Evaluator rejects
        reject_response = json.dumps({
            "numerical_accuracy": 0.4,
            "completeness": 0.5,
            "readability": 0.6,
            "actionability": 0.3,
            "hallucination_free": 0.7,
            "feedback": "Öneriler daha spesifik olmalı. Rakamlar kaynak veriyle uyuşmuyor.",
        })

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=reject_response):
            evaluator = EvaluatorAgent()
            eval_result_1 = evaluator.evaluate(state)

        state.update(eval_result_1)
        assert state["evaluation"]["approved"] is False
        assert state["evaluation"]["overall_score"] < 0.7

        # Routing check: should go back to writer
        assert route_after_evaluator(state) == "writer"

        # Iteration 2: Writer rewrites with feedback
        with patch("src.agents.writer.WriterAgent._call_llm", return_value=None):
            writer = WriterAgent()
            writer_result_2 = writer.write(state)

        state.update(writer_result_2)
        assert state["evaluator_iteration"] == 2

        # Iteration 2: Evaluator approves
        approve_response = json.dumps({
            "numerical_accuracy": 0.85,
            "completeness": 0.8,
            "readability": 0.9,
            "actionability": 0.75,
            "hallucination_free": 0.9,
            "feedback": "Rapor artık kabul edilebilir düzeyde.",
        })

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=approve_response):
            evaluator = EvaluatorAgent()
            eval_result_2 = evaluator.evaluate(state)

        state.update(eval_result_2)
        assert state["evaluation"]["approved"] is True
        assert state["evaluation"]["overall_score"] >= 0.7

        # Routing check: should go to delivery
        assert route_after_evaluator(state) == "delivery"

    def test_max_iterations_forces_approval(self):
        """
        Evaluator keeps rejecting → after MAX_EVALUATOR_ITERATIONS, pipeline
        forces delivery regardless of approval status.
        """
        state = self._make_state()

        reject_response = json.dumps({
            "numerical_accuracy": 0.3,
            "completeness": 0.4,
            "readability": 0.5,
            "actionability": 0.2,
            "hallucination_free": 0.5,
            "feedback": "Rapor hâlâ yetersiz.",
        })

        for i in range(3):
            # Writer produces draft
            with patch("src.agents.writer.WriterAgent._call_llm", return_value=None):
                writer = WriterAgent()
                writer_result = writer.write(state)
            state.update(writer_result)

            # Evaluator rejects
            with patch("src.tools.llm_tools.call_llm_with_retry", return_value=reject_response):
                evaluator = EvaluatorAgent()
                eval_result = evaluator.evaluate(state)
            state.update(eval_result)

            assert state["evaluation"]["approved"] is False

        # After 3 iterations (max), routing should force delivery
        assert state["evaluator_iteration"] == 3
        assert route_after_evaluator(state) == "delivery"

    def test_approved_on_first_try(self):
        """Report approved on first try — no loop needed."""
        state = self._make_state()

        # Writer produces draft
        with patch("src.agents.writer.WriterAgent._call_llm", return_value=None):
            writer = WriterAgent()
            writer_result = writer.write(state)
        state.update(writer_result)

        # Evaluator approves immediately
        approve_response = json.dumps({
            "numerical_accuracy": 0.9,
            "completeness": 0.85,
            "readability": 0.9,
            "actionability": 0.8,
            "hallucination_free": 0.95,
            "feedback": "Mükemmel rapor.",
        })

        with patch("src.tools.llm_tools.call_llm_with_retry", return_value=approve_response):
            evaluator = EvaluatorAgent()
            eval_result = evaluator.evaluate(state)
        state.update(eval_result)

        assert state["evaluator_iteration"] == 1
        assert state["evaluation"]["approved"] is True
        assert route_after_evaluator(state) == "delivery"

    # ── Rule-based loop simulation ───────────────────────────────────────────

    def test_rule_based_loop_without_llm(self):
        """Full loop works even without LLM (rule-based evaluation)."""
        state = self._make_state()

        with patch("src.agents.writer.WriterAgent._call_llm", return_value=None), \
             patch("src.tools.llm_tools.call_llm_with_retry", return_value=None):

            # Writer → Evaluator (rule-based)
            writer = WriterAgent()
            writer_result = writer.write(state)
            state.update(writer_result)

            evaluator = EvaluatorAgent()
            eval_result = evaluator.evaluate(state)
            state.update(eval_result)

        # Rule-based should produce valid evaluation
        assert "approved" in state["evaluation"]
        assert "overall_score" in state["evaluation"]
        assert isinstance(state["evaluation"]["overall_score"], float)
        assert 0.0 <= state["evaluation"]["overall_score"] <= 1.0
