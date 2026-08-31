"""
Tests for Writer Agent — LLM mock, fallback, prompt strategies, revision.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestWriterAgent:
    """Tests for WriterAgent.write() and prompt building."""

    def _make_state(self, **overrides):
        state = {
            "start_date": "2024-01-01",
            "end_date": "2024-01-07",
            "report_type": "weekly",
            "recipients": [],
            "raw_data": {
                "daily_sales": [
                    {"order_date": "2024-01-01", "total_sales": 5000, "total_orders": 30},
                    {"order_date": "2024-01-02", "total_sales": 6000, "total_orders": 35},
                ],
                "by_category": [],
                "weekly_summary": {
                    "total_sales": 45000,
                    "total_orders": 300,
                    "avg_order_value": 150.0,
                    "unique_customers": 200,
                },
            },
            "quality_report": {"is_valid": True},
            "analysis_results": {
                "trends": {
                    "total_sales": {
                        "direction": "increasing",
                        "growth_rate_pct": 8.5,
                    }
                },
                "anomalies": [
                    {"metric": "sales", "date": "2024-01-03", "value": 12000}
                ],
                "category_performance": [
                    {"category": "Technology", "total_sales": 22000, "sales_share_pct": 48.9}
                ],
                "forecast": {
                    "predictions": [{"date": "2024-01-08", "predicted": 6500}]
                },
            },
            "analysis_plan": ["trends", "anomalies"],
            "writer_strategy": None,
            "historical_context": "Geçmiş rapor bağlamı test.",
            "draft_report": None,
            "evaluation": None,
            "evaluator_iteration": 0,
            "final_report": None,
            "delivery_status": None,
            "feedback_metrics": None,
            "errors": [],
            "current_agent": "rag",
            "run_id": "test-run",
        }
        state.update(overrides)
        return state

    # ── LLM mock tests ──────────────────────────────────────────────────────

    def test_write_with_llm_mock(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent(strategy="few_shot")
        state = self._make_state()

        with patch("src.agents.writer.WriterAgent._call_llm") as mock_llm:
            mock_llm.return_value = "## Haftalık Rapor\nTest rapor içeriği."
            result = agent.write(state)

        assert result["current_agent"] == "writer"
        assert result["draft_report"] == "## Haftalık Rapor\nTest rapor içeriği."
        assert result["evaluator_iteration"] == 1

    def test_write_fallback_when_llm_unavailable(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent(strategy="few_shot")
        state = self._make_state()

        with patch("src.agents.writer.WriterAgent._call_llm") as mock_llm:
            mock_llm.return_value = None
            result = agent.write(state)

        assert result["draft_report"] is not None
        assert len(result["draft_report"]) > 0
        assert "Tedarikçi Performans Raporu" in result["draft_report"]
        assert "45000" in result["draft_report"]

    def test_fallback_report_has_sections(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent(strategy="zero_shot")
        state = self._make_state()

        with patch("src.agents.writer.WriterAgent._call_llm", return_value=None):
            result = agent.write(state)

        report = result["draft_report"]
        assert "### Özet Göstergeler" in report
        assert "### Önemli Bulgular" in report
        assert "[TREND]" in report
        assert "### Aksiyon Önerileri" in report

    def test_fallback_includes_historical_context(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent()
        state = self._make_state(historical_context="Geçen hafta Technology %12 büyüdü.")

        with patch("src.agents.writer.WriterAgent._call_llm", return_value=None):
            result = agent.write(state)

        assert "Geçmiş Karşılaştırma" in result["draft_report"]

    def test_fallback_skips_history_when_empty(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent()
        state = self._make_state(historical_context="")

        with patch("src.agents.writer.WriterAgent._call_llm", return_value=None):
            result = agent.write(state)

        assert "Geçmiş Karşılaştırma" not in result["draft_report"]

    # ── Prompt strategy tests ────────────────────────────────────────────────

    def test_zero_shot_prompt(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent(strategy="zero_shot")
        prompt = agent._build_prompt(
            analysis_results={"trends": {}},
            historical_context="",
            start_date="2024-01-01",
            end_date="2024-01-07",
            report_type="weekly",
            raw_data={},
            evaluation=None,
        )
        assert "Analiz Sonuçları:" in prompt
        assert "ÖRNEK RAPOR" not in prompt
        assert "Adım adım" not in prompt

    def test_few_shot_prompt_contains_examples(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent(strategy="few_shot")
        prompt = agent._build_prompt(
            analysis_results={"trends": {}},
            historical_context="",
            start_date="2024-01-01",
            end_date="2024-01-07",
            report_type="weekly",
            raw_data={},
            evaluation=None,
        )
        assert "ÖRNEK RAPOR 1:" in prompt
        assert "ÖRNEK RAPOR 2:" in prompt

    def test_cot_prompt_has_steps(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent(strategy="cot")
        prompt = agent._build_prompt(
            analysis_results={"trends": {}},
            historical_context="",
            start_date="2024-01-01",
            end_date="2024-01-07",
            report_type="weekly",
            raw_data={},
            evaluation=None,
        )
        assert "Adım adım düşün:" in prompt
        assert "1." in prompt

    # ── Revision / evaluation feedback tests ─────────────────────────────────

    def test_revision_includes_feedback(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent(strategy="zero_shot")
        evaluation = {
            "approved": False,
            "overall_score": 3.5,
            "feedback": "Aksiyon önerileri daha spesifik olmalı.",
        }
        prompt = agent._build_prompt(
            analysis_results={},
            historical_context="",
            start_date="2024-01-01",
            end_date="2024-01-07",
            report_type="weekly",
            raw_data={},
            evaluation=evaluation,
        )
        assert "ÖNCEKİ RAPOR DEĞERLENDİRMESİ:" in prompt
        assert "3.5" in prompt
        assert "Aksiyon önerileri daha spesifik olmalı" in prompt

    def test_revision_not_included_when_approved(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent(strategy="zero_shot")
        evaluation = {"approved": True, "overall_score": 8.0}
        prompt = agent._build_prompt(
            analysis_results={},
            historical_context="",
            start_date="2024-01-01",
            end_date="2024-01-07",
            report_type="weekly",
            raw_data={},
            evaluation=evaluation,
        )
        assert "ÖNCEKİ RAPOR DEĞERLENDİRMESİ:" not in prompt

    # ── evaluator_iteration tests ────────────────────────────────────────────

    def test_evaluator_iteration_increments(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent()
        state = self._make_state(evaluator_iteration=2)

        with patch("src.agents.writer.WriterAgent._call_llm", return_value=None):
            result = agent.write(state)

        assert result["evaluator_iteration"] == 3

    def test_evaluator_iteration_starts_at_zero(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent()
        state = self._make_state(evaluator_iteration=0)

        with patch("src.agents.writer.WriterAgent._call_llm", return_value=None):
            result = agent.write(state)

        assert result["evaluator_iteration"] == 1

    # ── Strategy validation ──────────────────────────────────────────────────

    def test_invalid_strategy_falls_back(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent(strategy="invalid_strategy")
        assert agent.strategy == "few_shot"

    # ── Summary block tests ─────────────────────────────────────────────────

    def test_summary_block_included_in_prompt(self):
        from src.agents.writer import WriterAgent

        agent = WriterAgent(strategy="few_shot")
        raw_data = {
            "weekly_summary": {
                "total_revenue": 20301.12,
                "total_profit": 1613.88,
                "total_orders": 53,
                "avg_order_value": 383.04,
                "unique_customers": 53,
                "profit_margin_pct": 7.95,
            }
        }
        prompt = agent._build_prompt(
            analysis_results={"trends": {}},
            historical_context="",
            start_date="2017-02-01",
            end_date="2017-02-28",
            report_type="monthly",
            raw_data=raw_data,
            evaluation=None,
        )
        assert "KAYNAK VERİ" in prompt
        assert "20301.12" in prompt
        assert "53" in prompt

    def test_summary_block_empty_when_no_summary(self):
        from src.agents.writer import WriterAgent

        block = WriterAgent._build_summary_block({})
        assert block == ""

    def test_summary_block_all_fields(self):
        from src.agents.writer import WriterAgent

        raw_data = {
            "weekly_summary": {
                "total_revenue": 99999.99,
                "total_profit": 5000.0,
                "total_orders": 100,
                "avg_order_value": 999.99,
                "unique_customers": 77,
                "profit_margin_pct": 5.0,
            }
        }
        block = WriterAgent._build_summary_block(raw_data)
        assert "99999.99" in block
        assert "5000.0" in block
        assert "100" in block
        assert "999.99" in block
        assert "77" in block
        assert "%5.0" in block

    def test_summary_block_in_all_strategies(self):
        from src.agents.writer import WriterAgent

        raw_data = {
            "weekly_summary": {
                "total_revenue": 12345.0,
                "total_profit": 1000.0,
                "total_orders": 50,
                "avg_order_value": 246.9,
                "unique_customers": 40,
                "profit_margin_pct": 8.1,
            }
        }
        for strategy in ("zero_shot", "few_shot", "cot"):
            agent = WriterAgent(strategy=strategy)
            prompt = agent._build_prompt(
                analysis_results={},
                historical_context="",
                start_date="2024-01-01",
                end_date="2024-01-31",
                report_type="monthly",
                raw_data=raw_data,
                evaluation=None,
            )
            assert "KAYNAK VERİ" in prompt, f"Missing in {strategy}"
            assert "12345.0" in prompt, f"Revenue missing in {strategy}"

    # ── Truncation ───────────────────────────────────────────────────────────

    def test_truncate_analysis(self):
        from src.agents.writer import WriterAgent

        big = {"key": "x" * 10000}
        result = WriterAgent._truncate_analysis(big, max_chars=500)
        assert len(result) <= 520  # 500 + "... (kırpıldı)"
        assert "kırpıldı" in result
