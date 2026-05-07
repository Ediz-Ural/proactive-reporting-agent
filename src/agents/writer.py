"""
Writer Agent — Full implementation (Week 3).

Generates executive summary reports using LLM, combining:
- Analysis results from the Analyst Agent
- Historical context from the RAG Agent
- Report template structure

Supports multiple context engineering strategies for experimental comparison.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from src.graph.state import AgentState

logger = logging.getLogger(__name__)

REPORT_TYPE_LABELS = {
    "weekly": "Haftalık",
    "monthly": "Aylık",
    "quarterly": "Çeyreklik",
}

# ── System prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sen bir kıdemli iş analisti ve rapor yazarısın.
Görevin: Verilen analiz sonuçlarını ve geçmiş rapor bağlamını kullanarak
kısa, öz ve aksiyon odaklı bir executive summary yazmak.

RAPOR FORMATI:
## {report_type_label} Satış Raporu — {start_date} / {end_date}

### Özet Göstergeler
- Toplam gelir, sipariş sayısı, ortalama sipariş değeri, benzersiz müşteri
- Her metrik için önceki döneme göre % değişim

### Önemli Bulgular
- [TREND] Tespit edilen trendler ve yorumları
- [ANOMALİ] Tespit edilen anomaliler, olası nedenler
- [TAHMİN] Gelecek dönem projeksiyonu (varsa)

### Geçmiş Karşılaştırma
- Geçmiş raporlarda benzer durumlar varsa referans ver
- Dönemler arası karşılaştırma

### Aksiyon Önerileri
1. Spesifik, ölçülebilir, uygulanabilir öneriler
2. Her öneri bir bulguya dayalı olmalı
3. Öncelik sırası belirtilmeli

GEÇMİŞ RAPOR BAĞLAMI KULLANIMI:
- Geçmiş raporlarda benzer dönem veya benzer anomali varsa, bunu açıkça referans ver
- "Geçen ay da benzer bir düşüş yaşanmıştı" gibi karşılaştırma yap
- Geçmiş raporlardaki aksiyon önerilerinin sonuçlarını değerlendir
- Eğer geçmiş bağlam boşsa veya ilgisizse, zorla referans verme — sadece mevcut veriyi kullan
- Geçmiş bağlamı RAW olarak kopyalama, kendi cümlelerinle özetle

KURALLAR:
- Türkçe yaz
- Rakamları kesin ver (yuvarlama yapma)
- Hallucination yapma — sadece verilen verileri kullan
- Maksimum 500 kelime
- Eğer geçmiş bağlam boşsa, geçmiş karşılaştırma bölümünü atla
- Özet göstergelerdeki TÜM rakamlar (gelir, sipariş, müşteri, kâr) SADECE KAYNAK VERİ bloğundan alınmalıdır
- customer_metrics listesindeki segment bazlı unique_customers değerlerini TOPLAMA — KAYNAK VERİ'deki unique_customers zaten toplam sayıdır
- Herhangi bir rakamı "yaklaşık", "civarında" gibi ifadelerle değiştirme
- Para birimi USD ($) kullan — TL değil
- KAYNAK VERİ bloğunda "karşılaştırma YAPILAMAZ" yazıyorsa: Özet göstergelerde yüzde değişim YAZMA, "önceki döneme göre" ifadesi KULLANMA, sadece mutlak rakamları yaz
- Trend verisinde "note" alanı varsa ve "yeterli veri yok" diyorsa, o analizi KULLANMA
- Seyrek verili dönemlerde (az sipariş, az gün) büyük yüzdelik değişimler YANILTICI olabilir — bunları "keskin düşüş/artış" diye sunma, veri azlığını belirt

VERİ KAYNAKLARI — KARIŞTIRMA:
- "trends_AY_ICI_GUNLUK_VERI": Ay İÇİNDEKİ günlük satış verileri. Bu veriler aynı dönem içindeki gün-gün değişimleri gösterir. Bunları ASLA "önceki dönem" ile karşılaştırma olarak KULLANMA.
- "period_comparison": DÖNEMLER ARASI karşılaştırma (bu ay vs önceki ay). Sadece bu veriyi dönem karşılaştırması için kullan.
- ASLA ay-içi günlük verilerdeki ilk gün / son gün değerlerini "dönem geliri düştü/arttı" şeklinde YORUMLAMA. Dönem toplam geliri KAYNAK VERİ bloğundadır.
"""

# ── Few-shot example reports ─────────────────────────────────────────────────

EXAMPLE_REPORT_1 = """## Haftalık Satış Raporu — 2023-12-18 / 2023-12-24

### Özet Göstergeler
- Toplam gelir: $52,340.75 (önceki haftaya göre +15.2%)
- Sipariş sayısı: 378 (önceki haftaya göre +12.8%)
- Ortalama sipariş değeri: $138.47
- Benzersiz müşteri: 245

### Önemli Bulgular
- [TREND] Yılsonu kampanyaları etkisiyle tüm kategorilerde güçlü artış. Technology %18.5 ile en yüksek büyümeyi kaydetti.
- [ANOMALİ] 22 Aralık'ta günlük satış $11,200 ile ayın zirvesine ulaştı.
- [TAHMİN] Yılbaşı haftasında %5-8 düşüş bekleniyor (tatil etkisi).

### Aksiyon Önerileri
1. Yılbaşı sonrası stok eritme kampanyası planlayın — özellikle Furniture kategorisinde fazla stok mevcut.
2. Yılın en iyi 50 müşterisine teşekkür e-postası gönderin (CRM segmentasyonu kullanın).
"""

EXAMPLE_REPORT_2 = """## Aylık Satış Raporu — 2023-12-01 / 2023-12-31

### Özet Göstergeler
- Toplam gelir: $138,920.40 (önceki aya göre -5.6%)
- Sipariş sayısı: 856 (önceki aya göre -2.3%)
- Ortalama sipariş değeri: $162.29
- Benzersiz müşteri: 465

### Önemli Bulgular
- [TREND] Beklenen yılbaşı düşüşü gerçekleşti. Tüm kategorilerde gerileme.
- [ANOMALİ] 25-26 Aralık'ta sipariş sayısı günlük 8'e düştü (tatil günleri).
- [TAHMİN] Ocak ayında toparlanma bekleniyor: $144,000-$148,000 aralığı.

### Geçmiş Karşılaştırma
- Geçen yılın aynı döneminde (Aralık 2022) benzer düşüş yaşanmıştı (-%4.2). Bu yılki düşüş biraz daha sert.

### Aksiyon Önerileri
1. 2 Ocak itibarıyla "Yeni Yıl Fırsatları" kampanyası başlatın.
2. Corporate segment için Q1 bütçe dönemi teklifi hazırlayın.
"""


class WriterAgent:
    """
    Generates executive summary reports using LLM.

    Supports multiple prompting strategies:
    - zero_shot: Task description only
    - few_shot: 2-3 example reports included
    - cot: Chain-of-Thought step-by-step reasoning
    """

    VALID_STRATEGIES = ("zero_shot", "few_shot", "cot")

    def __init__(self, strategy: str = "few_shot"):
        if strategy not in self.VALID_STRATEGIES:
            logger.warning("Unknown strategy '%s', falling back to 'few_shot'", strategy)
            strategy = "few_shot"
        self.strategy = strategy

    def write(self, state: AgentState) -> dict:
        """
        Generate the executive summary report.

        Reads from state: analysis_results, historical_context, raw_data,
                         start_date, end_date, report_type, evaluator_iteration,
                         evaluation (if revision)
        Writes to state: draft_report, current_agent, evaluator_iteration

        Returns:
            Dict of state updates.
        """
        logger.info("WriterAgent: generating report (strategy=%s)", self.strategy)

        analysis_results = state.get("analysis_results") or {}
        historical_context = state.get("historical_context") or ""
        start_date = state.get("start_date", "")
        end_date = state.get("end_date", "")
        report_type = state.get("report_type", "weekly")
        raw_data = state.get("raw_data") or {}
        evaluation = state.get("evaluation")
        iteration = state.get("evaluator_iteration", 0)

        # Build prompt based on strategy
        prompt = self._build_prompt(
            analysis_results=analysis_results,
            historical_context=historical_context,
            start_date=start_date,
            end_date=end_date,
            report_type=report_type,
            raw_data=raw_data,
            evaluation=evaluation,
        )

        # Try LLM first, fallback to template
        report_text = self._call_llm(prompt, start_date, end_date)
        if report_text is None:
            logger.info("WriterAgent: LLM unavailable — using fallback template")
            report_text = self._generate_fallback_report(
                analysis_results=analysis_results,
                historical_context=historical_context,
                start_date=start_date,
                end_date=end_date,
                report_type=report_type,
                raw_data=raw_data,
            )

        logger.info("WriterAgent: report generated (%d chars)", len(report_text))

        return {
            "draft_report": report_text,
            "current_agent": "writer",
            "evaluator_iteration": iteration + 1,
        }

    # ── Prompt builders ──────────────────────────────────────────────────────

    def _build_prompt(
        self,
        analysis_results: dict,
        historical_context: str,
        start_date: str,
        end_date: str,
        report_type: str,
        raw_data: dict,
        evaluation: dict | None,
    ) -> str:
        """Build the prompt using the configured strategy."""
        type_label = REPORT_TYPE_LABELS.get(report_type, "Periyodik")
        system = SYSTEM_PROMPT.format(
            start_date=start_date,
            end_date=end_date,
            report_type_label=type_label,
        )

        # Add revision note if evaluator rejected
        revision_note = ""
        if evaluation and not evaluation.get("approved", True):
            revision_note = f"""
ÖNCEKİ RAPOR DEĞERLENDİRMESİ:
Skor: {evaluation.get('overall_score', 'N/A')}
Geri Bildirim: {evaluation.get('feedback', 'N/A')}

Lütfen yukarıdaki geri bildirimi dikkate alarak raporu yeniden yaz.
"""

        # Extract summary block so LLM sees exact figures up front
        summary_block = self._build_summary_block(raw_data, analysis_results)

        # Sanitize analysis results so LLM can't confuse data sources
        clean_results = self._sanitize_for_llm(analysis_results)

        analysis_json = self._truncate_analysis(clean_results)
        hist = historical_context or "Geçmiş rapor verisi bulunmamaktadır."

        if self.strategy == "zero_shot":
            return self._build_zero_shot_prompt(system, analysis_json, hist, revision_note, summary_block)
        elif self.strategy == "cot":
            return self._build_cot_prompt(system, analysis_json, hist, revision_note, summary_block)
        else:
            return self._build_few_shot_prompt(system, analysis_json, hist, revision_note, summary_block)

    def _build_zero_shot_prompt(
        self, system: str, analysis_json: str, hist: str, revision_note: str,
        summary_block: str = "",
    ) -> str:
        return f"""{system}
{revision_note}
{summary_block}
Analiz Sonuçları:
{analysis_json}

Geçmiş Rapor Bağlamı:
{hist}

Raporu yaz:"""

    def _build_few_shot_prompt(
        self, system: str, analysis_json: str, hist: str, revision_note: str,
        summary_block: str = "",
    ) -> str:
        return f"""{system}

### ÖRNEK RAPOR 1:
{EXAMPLE_REPORT_1}

### ÖRNEK RAPOR 2:
{EXAMPLE_REPORT_2}

---
{revision_note}
Şimdi aşağıdaki veriler için rapor yaz:

{summary_block}
Analiz Sonuçları:
{analysis_json}

Geçmiş Rapor Bağlamı:
{hist}

Raporu yaz:"""

    def _build_cot_prompt(
        self, system: str, analysis_json: str, hist: str, revision_note: str,
        summary_block: str = "",
    ) -> str:
        return f"""{system}

Adım adım düşün:
1. Önce KAYNAK VERİ bloğundaki özet göstergeleri not al
2. Trend verilerini incele ve önemli değişimleri belirle
3. Anomalileri değerlendir ve olası nedenlerini düşün
4. Geçmiş raporlarla karşılaştırma yap
5. Tahmin verilerini yorumla
6. Tüm bulgulardan aksiyon önerileri çıkar
{revision_note}
{summary_block}
Analiz Sonuçları:
{analysis_json}

Geçmiş Rapor Bağlamı:
{hist}

Şimdi adım adım düşünerek raporu yaz:"""

    # ── Summary block ──────────────────────────────────────────────────────

    @staticmethod
    def _build_summary_block(raw_data: dict[str, Any], analysis_results: dict[str, Any] | None = None) -> str:
        """Build an explicit source-of-truth block from weekly_summary.

        Placed at the top of the prompt so the LLM uses these exact figures
        for the Özet Göstergeler section instead of deriving (and potentially
        hallucinating) numbers from the analysis JSON.
        """
        summary = raw_data.get("weekly_summary", {})
        if not summary:
            return ""

        comparison = (analysis_results or {}).get("period_comparison", {})
        has_comparison = comparison and not comparison.get("insufficient_previous_data")

        block = (
            "KAYNAK VERİ — ÖZET GÖSTERGELER (Bu rakamları AYNEN kullan):\n"
            f"- Toplam gelir: ${summary.get('total_revenue', 'N/A')}\n"
            f"- Toplam kâr: ${summary.get('total_profit', 'N/A')}\n"
            f"- Sipariş sayısı: {summary.get('total_orders', 'N/A')}\n"
            f"- Ortalama sipariş değeri: ${summary.get('avg_order_value', 'N/A')}\n"
            f"- Benzersiz müşteri: {summary.get('unique_customers', 'N/A')}\n"
            f"- Kâr marjı: %{summary.get('profit_margin_pct', 'N/A')}\n"
        )

        if has_comparison:
            pct_sales = comparison.get("total_sales_change_pct")
            pct_profit = comparison.get("total_profit_change_pct")
            pct_orders = comparison.get("total_orders_change_pct")
            if pct_sales is not None:
                block += f"\nÖNCEKİ DÖNEM KARŞILAŞTIRMASI:\n"
                block += f"- Gelir değişimi: %{pct_sales:+.1f}\n"
                if pct_profit is not None:
                    block += f"- Kâr değişimi: %{pct_profit:+.1f}\n"
                if pct_orders is not None:
                    block += f"- Sipariş değişimi: %{pct_orders:+.1f}\n"
        else:
            block += "\nÖNCEKİ DÖNEM KARŞILAŞTIRMASI: Önceki dönemde yeterli veri bulunmadığından karşılaştırma YAPILAMAZ. Özet göstergelerin yanına yüzde değişim YAZMA.\n"

        return block

    # ── LLM call ─────────────────────────────────────────────────────────────

    def _call_llm(self, prompt: str, start_date: str, end_date: str) -> str | None:
        """Call LLM with retry. Returns None if unavailable."""
        from src.tools.llm_tools import call_llm_with_retry

        system_msg = (
            f"Sen bir kıdemli iş analisti ve rapor yazarısın. "
            f"Dönem: {start_date} — {end_date}. Türkçe yaz."
        )
        return call_llm_with_retry(prompt=prompt, system_prompt=system_msg)

    # ── Fallback ─────────────────────────────────────────────────────────────

    def _generate_fallback_report(
        self,
        analysis_results: dict[str, Any],
        historical_context: str,
        start_date: str,
        end_date: str,
        report_type: str,
        raw_data: dict[str, Any],
    ) -> str:
        """Template-based report generation without LLM."""
        type_label = REPORT_TYPE_LABELS.get(report_type, "Periyodik")
        lines = [f"## {type_label} Satış Raporu — {start_date} / {end_date}", ""]

        # Özet Göstergeler from raw_data weekly_summary
        summary = raw_data.get("weekly_summary", {})
        lines.append("### Özet Göstergeler")
        if summary:
            lines.append(f"- Toplam gelir: ${summary.get('total_revenue', summary.get('total_sales', 'N/A'))}")
            lines.append(f"- Sipariş sayısı: {summary.get('total_orders', 'N/A')}")
            lines.append(f"- Ortalama sipariş değeri: ${summary.get('avg_order_value', 'N/A')}")
            lines.append(f"- Benzersiz müşteri: {summary.get('unique_customers', 'N/A')}")
        else:
            daily = raw_data.get("daily_sales", [])
            if daily:
                total_sales = sum(r.get("total_sales", 0) for r in daily)
                total_orders = sum(r.get("total_orders", 0) for r in daily)
                avg_val = round(total_sales / total_orders, 2) if total_orders else 0
                lines.append(f"- Toplam gelir: ${round(total_sales, 2)}")
                lines.append(f"- Sipariş sayısı: {total_orders}")
                lines.append(f"- Ortalama sipariş değeri: ${avg_val}")
            else:
                lines.append("- Veri mevcut değil")
        lines.append("")

        # Önemli Bulgular from analysis_results
        lines.append("### Önemli Bulgular")

        # Trends
        trends = analysis_results.get("trends", {})
        if isinstance(trends, dict):
            for metric, data in trends.items():
                if isinstance(data, dict):
                    direction = data.get("direction", "unknown")
                    growth = data.get("growth_rate_pct", 0)
                    dir_label = {
                        "up": "yükseliş",
                        "down": "düşüş",
                        "stable": "stabil",
                        "increasing": "yükseliş",
                        "decreasing": "düşüş",
                        "no trend": "stabil",
                    }.get(direction, direction)
                    lines.append(
                        f"- [TREND] {metric}: {dir_label} trendi (değişim: %{growth})"
                    )

        # Anomalies
        anomalies = analysis_results.get("anomalies", [])
        if isinstance(anomalies, list):
            n_anomalies = len(anomalies)
            if n_anomalies > 0:
                lines.append(f"- [ANOMALİ] {n_anomalies} anomali tespit edildi")
            else:
                lines.append("- [ANOMALİ] Anomali tespit edilmedi")

        # Forecast
        forecast = analysis_results.get("forecast", {})
        if isinstance(forecast, dict) and forecast:
            predictions = forecast.get("predictions", [])
            if predictions:
                last_pred = predictions[-1] if isinstance(predictions, list) else {}
                pred_val = last_pred.get("predicted", "N/A")
                lines.append(f"- [TAHMİN] Gelecek dönem tahmini: {pred_val}")
        lines.append("")

        # Category performance
        cat_perf = analysis_results.get("category_performance", [])
        if cat_perf and isinstance(cat_perf, list):
            lines.append("### Kategori Performansı")
            for cat in cat_perf[:5]:
                if isinstance(cat, dict):
                    name = cat.get("category", "N/A")
                    sales = cat.get("total_sales", "N/A")
                    share = cat.get("sales_share_pct", "N/A")
                    lines.append(f"- {name}: ${sales} (pay: %{share})")
            lines.append("")

        # Historical context
        if historical_context:
            lines.append("### Geçmiş Karşılaştırma")
            # Include a truncated version
            hist_lines = historical_context.split("\n")[:10]
            lines.extend(hist_lines)
            lines.append("")

        # Aksiyon Önerileri
        lines.append("### Aksiyon Önerileri")
        lines.append("1. Trend ve anomali bulgularına göre stok ve fiyatlandırma stratejisini gözden geçirin.")
        lines.append("2. Düşük performanslı kategorilerde kampanya planlaması yapın.")
        lines.append("3. Müşteri segmentasyonuna göre hedefli pazarlama aksiyonları belirleyin.")
        lines.append("")

        lines.append(f"*Rapor otomatik olarak oluşturulmuştur — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC*")

        return "\n".join(lines)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _sanitize_for_llm(analysis_results: dict[str, Any]) -> dict[str, Any]:
        """Restructure analysis results so the LLM cannot confuse data sources.

        Key transforms:
        - Trend: rename first_value/last_value to explicit day-level labels,
          remove raw growth_rate_pct (LLM confuses with period comparison)
        - Period comparison: strip when insufficient, remove None pcts
        """
        clean = dict(analysis_results)

        # ── Trends: rename ambiguous fields ──
        trends = clean.get("trends")
        if isinstance(trends, dict) and trends and "note" not in trends:
            renamed_trends: dict[str, Any] = {}
            for metric, data in trends.items():
                if not isinstance(data, dict):
                    renamed_trends[metric] = data
                    continue
                t: dict[str, Any] = {
                    "metric": data.get("metric", metric),
                    "ay_ici_trend_yonu": data.get("direction", "stable"),
                    "ay_ici_ortalama": data.get("mean_value"),
                    "ay_ici_min_gunluk": data.get("min_value"),
                    "ay_ici_max_gunluk": data.get("max_value"),
                }
                for k, v in data.items():
                    if k.startswith("sma_") and v is not None:
                        t[k] = v
                renamed_trends[metric] = t
            clean["trends_AY_ICI_GUNLUK_VERI"] = renamed_trends
            del clean["trends"]

        # ── Period comparison: strip misleading data ──
        pc = clean.get("period_comparison", {})
        if pc and pc.get("insufficient_previous_data"):
            clean["period_comparison"] = {
                "note": "Önceki dönemde yeterli veri yok — karşılaştırma yapılamaz."
            }
        elif pc:
            clean["period_comparison"] = {
                k: v for k, v in pc.items() if v is not None
            }

        return clean

    @staticmethod
    def _truncate_analysis(analysis_results: dict, max_chars: int = 8000) -> str:
        """Serialize analysis results to JSON, truncate if too long."""
        text = json.dumps(analysis_results, indent=2, default=str, ensure_ascii=False)
        if len(text) > max_chars:
            text = text[:max_chars] + "\n... (kırpıldı)"
        return text
