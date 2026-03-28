"""
Evaluator Agent — Full implementation (Week 4).

Evaluates the quality of the generated report against source data
and produces a structured score with specific feedback.

This implements the Evaluator-Optimizer pattern:
- If approved=True → report moves to Delivery
- If approved=False → report returns to Writer with feedback
- Max iterations controlled by settings.MAX_EVALUATOR_ITERATIONS
"""

from __future__ import annotations

import json
import logging
import re

from src.graph.state import AgentState

logger = logging.getLogger(__name__)


EVALUATOR_SYSTEM_PROMPT = """Sen bir rapor kalite denetçisisin.
Verilen raporu aşağıdaki 5 kritere göre 0.0-1.0 arası puanla.

KRİTERLER:
1. numerical_accuracy (0.0-1.0): Rapordaki rakamlar kaynak veriyle uyuşuyor mu?
   - 1.0: Tüm rakamlar doğru
   - 0.5: Bazı rakamlar yanlış veya eksik
   - 0.0: Büyük sayısal hatalar var

2. completeness (0.0-1.0): Tüm önemli bulgular rapora dahil edilmiş mi?
   - Trend, anomali, tahmin, kategori performansı, aksiyon önerileri
   - 1.0: Tüm bölümler dolu ve yeterli
   - 0.5: Bazı bölümler eksik
   - 0.0: Kritik bulgular atlanmış

3. readability (0.0-1.0): Rapor teknik bilgisi olmayan biri için anlaşılır mı?
   - 1.0: Çok net ve okunabilir
   - 0.5: Bazı kısımlar karmaşık
   - 0.0: Anlaşılması zor

4. actionability (0.0-1.0): Öneriler spesifik ve uygulanabilir mi?
   - 1.0: Her öneri bir bulguya dayanıyor ve somut
   - 0.5: Öneriler genel
   - 0.0: Öneri yok veya anlamsız

5. hallucination_free (0.0-1.0): Raporda kaynak veride olmayan uydurma bilgi var mı?
   - 1.0: Hallucination yok
   - 0.5: Küçük yorumlama hataları
   - 0.0: Ciddi uydurma bilgi var

YANIT FORMATI (sadece JSON, başka bir şey yazma):
{
    "numerical_accuracy": 0.8,
    "completeness": 0.9,
    "readability": 0.85,
    "actionability": 0.7,
    "hallucination_free": 0.95,
    "overall_score": 0.84,
    "approved": true,
    "feedback": "Rapor genel olarak iyi. Öneriler biraz daha spesifik olabilir."
}

NOT: overall_score = (numerical_accuracy + completeness + readability + actionability + hallucination_free) / 5
NOT: approved = overall_score >= 0.7
"""

SCORE_KEYS = frozenset({
    "numerical_accuracy",
    "completeness",
    "readability",
    "actionability",
    "hallucination_free",
})


class EvaluatorAgent:
    """
    Scores report quality across 5 dimensions and decides approve/revise.

    Evaluation criteria:
    1. Numerical accuracy — do numbers in the report match source data?
    2. Completeness — are all important findings covered?
    3. Readability — is the report clear and well-structured?
    4. Actionability — are recommendations specific and actionable?
    5. Hallucination check — does the report contain fabricated info?

    Approval threshold: overall_score >= 0.7
    """

    APPROVAL_THRESHOLD: float = 0.7

    def evaluate(self, state: AgentState) -> dict:
        """
        Evaluate the draft report.

        Reads from state: draft_report, analysis_results, raw_data, evaluator_iteration
        Writes to state: evaluation, current_agent

        Returns:
            Dict of state updates.
        """
        draft_report = state.get("draft_report") or ""
        analysis_results = state.get("analysis_results") or {}
        raw_data = state.get("raw_data") or {}
        iteration = state.get("evaluator_iteration", 0)

        logger.info(
            "EvaluatorAgent: evaluating draft (iteration=%d, length=%d chars)",
            iteration, len(draft_report),
        )

        if not draft_report:
            logger.warning("EvaluatorAgent: no draft report to evaluate")
            evaluation = {
                "numerical_accuracy": 0.0,
                "completeness": 0.0,
                "readability": 0.0,
                "actionability": 0.0,
                "hallucination_free": 0.0,
                "overall_score": 0.0,
                "approved": False,
                "feedback": "Rapor boş — Writer Agent bir rapor üretmedi.",
            }
            return {"evaluation": evaluation, "current_agent": "evaluator"}

        # Try LLM-based evaluation first
        evaluation = self._llm_evaluation(draft_report, analysis_results, raw_data)

        # Fallback to rule-based if LLM unavailable or returns bad JSON
        if evaluation is None:
            logger.info("EvaluatorAgent: using rule-based fallback evaluation")
            evaluation = self._rule_based_evaluation(draft_report, analysis_results, raw_data)

        logger.info(
            "EvaluatorAgent: score=%.2f approved=%s (iteration=%d)",
            evaluation["overall_score"], evaluation["approved"], iteration,
        )

        return {"evaluation": evaluation, "current_agent": "evaluator"}

    # ── LLM-based evaluation ─────────────────────────────────────────────────

    def _llm_evaluation(self, draft_report: str, analysis_results: dict, raw_data: dict) -> dict | None:
        """Evaluate using LLM. Returns None if LLM unavailable or parse fails."""
        from src.tools.llm_tools import call_llm_with_retry

        prompt = self._build_evaluation_prompt(draft_report, analysis_results, raw_data)
        response = call_llm_with_retry(
            prompt=prompt,
            system_prompt=EVALUATOR_SYSTEM_PROMPT,
            temperature=0.0,
        )

        if response is None:
            return None

        return self._parse_llm_evaluation(response)

    def _build_evaluation_prompt(self, draft_report: str, analysis_results: dict, raw_data: dict) -> str:
        """Build the evaluation prompt with source data and report."""
        summary_json = json.dumps(
            raw_data.get("weekly_summary", {}), indent=2, default=str, ensure_ascii=False,
        )
        analysis_summary = self._summarize_analysis(analysis_results)

        return f"""KAYNAK VERİ (weekly_summary):
{summary_json}

ANALİZ SONUÇLARI (özet):
{analysis_summary}

DEĞERLENDİRİLECEK RAPOR:
{draft_report}

Değerlendirmeni JSON olarak yaz:"""

    @staticmethod
    def _summarize_analysis(analysis_results: dict) -> str:
        """Create a concise summary of analysis results for the evaluator."""
        parts = []

        trends = analysis_results.get("trends", {})
        if trends:
            parts.append(f"Trendler: {len(trends)} metrik analiz edildi")

        anomalies = analysis_results.get("anomalies", [])
        if isinstance(anomalies, list):
            parts.append(f"Anomaliler: {len(anomalies)} tespit edildi")

        forecast = analysis_results.get("forecast", {})
        if forecast:
            parts.append("Tahmin: mevcut")

        cat_perf = analysis_results.get("category_performance", [])
        if isinstance(cat_perf, list) and cat_perf:
            parts.append(f"Kategori performansı: {len(cat_perf)} kategori")

        meta = analysis_results.get("analysis_metadata", {})
        completed = meta.get("analyses_completed", [])
        if completed:
            parts.append(f"Tamamlanan analizler: {', '.join(completed)}")

        return "\n".join(parts) if parts else "Analiz sonuçları mevcut değil"

    def _parse_llm_evaluation(self, response_text: str) -> dict | None:
        """Parse LLM JSON response, handling markdown fences and edge cases."""
        # Strip markdown code fences
        text = re.sub(r"```json\s*", "", response_text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        try:
            result = json.loads(text)
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.warning("EvaluatorAgent: failed to parse LLM response as JSON")
            return None

        # Validate required keys
        if not SCORE_KEYS.issubset(result.keys()):
            logger.warning("EvaluatorAgent: LLM response missing required score keys")
            return None

        # Clamp scores to 0-1
        for key in SCORE_KEYS:
            try:
                result[key] = max(0.0, min(1.0, float(result[key])))
            except (ValueError, TypeError):
                logger.warning("EvaluatorAgent: invalid score value for %s", key)
                return None

        # Recalculate overall to ensure consistency
        result["overall_score"] = round(
            sum(result[k] for k in SCORE_KEYS) / len(SCORE_KEYS), 2
        )
        result["approved"] = result["overall_score"] >= self.APPROVAL_THRESHOLD

        # Ensure feedback is a string
        if "feedback" not in result or not isinstance(result["feedback"], str):
            result["feedback"] = "Değerlendirme tamamlandı." if result["approved"] else "Rapor iyileştirme gerektiriyor."

        return result

    # ── Rule-based fallback ──────────────────────────────────────────────────

    def _rule_based_evaluation(self, draft_report: str, analysis_results: dict, raw_data: dict) -> dict:
        """Deterministic evaluation without LLM."""
        scores: dict[str, float] = {}

        # 1. Numerical accuracy — raporda weekly_summary rakamları var mı?
        summary = raw_data.get("weekly_summary", {})
        total_revenue = str(summary.get("total_revenue", summary.get("total_sales", "")))
        if total_revenue and total_revenue in draft_report:
            scores["numerical_accuracy"] = 0.8
        elif total_revenue:
            scores["numerical_accuracy"] = 0.4
        else:
            # No summary to compare — give benefit of doubt
            scores["numerical_accuracy"] = 0.6

        # 2. Completeness — temel bölümler var mı?
        required_sections = ["özet göstergeler", "bulgular", "önerileri"]
        found = sum(1 for s in required_sections if s in draft_report.lower())
        scores["completeness"] = round(found / len(required_sections), 2)

        # 3. Readability — uzunluk kontrolü
        word_count = len(draft_report.split())
        if 100 <= word_count <= 600:
            scores["readability"] = 0.9
        elif 50 <= word_count <= 800:
            scores["readability"] = 0.7
        else:
            scores["readability"] = 0.4

        # 4. Actionability — öneriler / numaralı liste var mı?
        has_recommendations = any(
            x in draft_report.lower() for x in ["1.", "2.", "öneri", "aksiyon"]
        )
        scores["actionability"] = 0.8 if has_recommendations else 0.3

        # 5. Hallucination — basit kontrol
        scores["hallucination_free"] = 0.9 if word_count > 50 else 0.3

        overall = round(sum(scores.values()) / len(scores), 2)

        # Build feedback
        feedback_parts = []
        if scores["numerical_accuracy"] < 0.7:
            feedback_parts.append("Raporda kaynak veriden gelen rakamlar eksik veya hatalı.")
        if scores["completeness"] < 0.7:
            feedback_parts.append(
                "Bazı bölümler eksik: Özet Göstergeler, Bulgular veya Öneriler kontrol edilmeli."
            )
        if scores["actionability"] < 0.7:
            feedback_parts.append("Aksiyon önerileri daha spesifik ve numaralandırılmış olmalı.")

        return {
            **scores,
            "overall_score": overall,
            "approved": overall >= self.APPROVAL_THRESHOLD,
            "feedback": " ".join(feedback_parts) if feedback_parts else "Rapor kabul edildi.",
        }
