"""
Pattern Comparison — Prompt Chaining (baseline) vs Multi-Agent (mine)

Runs both patterns across the same periods with multiple runs each,
scores each output with the EvaluatorAgent, then writes raw and
aggregated results to data/pattern_comparison/.

Usage:
    python scripts/pattern_comparison.py
    python scripts/pattern_comparison.py --company-id 1 --runs 5
"""

import argparse
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


PATTERNS = ["baseline", "multiagent"]

TEST_PERIODS = [
    ("2017-03-01", "2017-03-31", "Mar 2017"),
    ("2017-06-01", "2017-06-30", "Jun 2017"),
    ("2017-09-01", "2017-09-30", "Sep 2017"),
]

METRIC_KEYS = [
    "overall_score",
    "numerical_accuracy",
    "completeness",
    "readability",
    "actionability",
    "hallucination_free",
    "total_time",
    "word_count",
]


# ── Pattern A — Baseline (Prompt Chaining) ───────────────────────────────────

BASELINE_SYSTEM_PROMPT = (
    "Sen bir iş raporu yazarısın. "
    "Verilen veriden kısa bir Türkçe aylık performans raporu yaz."
)


def run_baseline(start_date: str, end_date: str, company_id: int) -> tuple[str, dict]:
    """
    Prompt-chaining baseline: SQL → SQL → single LLM call.

    Returns:
        (report_text, raw_data_dict) — raw_data is reused by the evaluator.
    """
    from src.tools.llm_tools import call_llm_with_retry
    from src.tools.sql_tools import get_sales_by_category, get_weekly_summary

    weekly_summary = get_weekly_summary(start_date, end_date, company_id=company_id)
    by_category = get_sales_by_category(start_date, end_date, company_id=company_id)

    by_category_payload = (
        by_category.to_dict(orient="records")
        if hasattr(by_category, "to_dict")
        else by_category
    )

    prompt = (
        "Aşağıdaki veriden bir aylık performans raporu yaz.\n\n"
        f"DÖNEM: {start_date} → {end_date}\n\n"
        "HAFTALIK ÖZET (weekly_summary):\n"
        f"{json.dumps(weekly_summary, ensure_ascii=False, indent=2, default=str)}\n\n"
        "KATEGORİ BAZINDA SATIŞLAR (by_category):\n"
        f"{json.dumps(by_category_payload, ensure_ascii=False, indent=2, default=str)}\n\n"
        "Bu veriden bir aylık rapor yaz."
    )

    response = call_llm_with_retry(
        prompt=prompt,
        system_prompt=BASELINE_SYSTEM_PROMPT,
        temperature=0.1,
    )

    report = response or ""
    raw_data = {
        "weekly_summary": weekly_summary,
        "by_category": by_category_payload,
    }
    return report, raw_data


# ── Pattern B — Multi-Agent (existing pipeline) ──────────────────────────────

def run_multiagent(start_date: str, end_date: str, company_id: int) -> tuple[str, dict, dict]:
    """
    Multi-agent pipeline: Orchestrator + Workers + RAG + Evaluator loop.

    Returns:
        (report_text, raw_data, analysis_results)
    """
    from src.graph.workflow import run_pipeline

    state = run_pipeline(
        start_date=start_date,
        end_date=end_date,
        report_type="monthly",
        recipients=[],
        company_id=company_id,
    )
    return (
        state.get("draft_report") or "",
        state.get("raw_data") or {},
        state.get("analysis_results") or {},
    )


# ── Evaluator helper ─────────────────────────────────────────────────────────

def evaluate_report(report: str, raw_data: dict, analysis_results: dict) -> dict:
    """Score a report using EvaluatorAgent."""
    from src.agents.evaluator import EvaluatorAgent

    agent = EvaluatorAgent()
    state = {
        "draft_report": report,
        "raw_data": raw_data,
        "analysis_results": analysis_results,
        "evaluator_iteration": 0,
    }
    result = agent.evaluate(state)
    return result.get("evaluation", {})


# ── Single-run wrappers ──────────────────────────────────────────────────────

def run_single(pattern: str, company_id: int, start: str, end: str) -> dict:
    """Run one pattern once, score it, return metrics dict."""
    t0 = time.perf_counter()
    try:
        if pattern == "baseline":
            report, raw_data = run_baseline(start, end, company_id)
            analysis_results: dict = {}
        elif pattern == "multiagent":
            report, raw_data, analysis_results = run_multiagent(start, end, company_id)
        else:
            raise ValueError(f"Unknown pattern: {pattern}")

        total_time = time.perf_counter() - t0

        evaluation = evaluate_report(report, raw_data, analysis_results)

        return {
            "pattern": pattern,
            "period": f"{start}/{end}",
            "total_time": round(total_time, 2),
            "overall_score": evaluation.get("overall_score", 0),
            "numerical_accuracy": evaluation.get("numerical_accuracy", 0),
            "completeness": evaluation.get("completeness", 0),
            "readability": evaluation.get("readability", 0),
            "actionability": evaluation.get("actionability", 0),
            "hallucination_free": evaluation.get("hallucination_free", 0),
            "approved": bool(evaluation.get("approved", False)),
            "word_count": len(report.split()),
            "char_count": len(report),
            "report_text": report,
        }
    except Exception as exc:
        return {
            "pattern": pattern,
            "period": f"{start}/{end}",
            "total_time": round(time.perf_counter() - t0, 2),
            "error": str(exc),
        }


# ── Stats helpers ────────────────────────────────────────────────────────────

def compute_stats(values: list[float]) -> dict:
    """mean/std/min/max for a list of numbers."""
    if not values:
        return {"mean": 0, "std": 0, "min": 0, "max": 0}
    return {
        "mean": round(statistics.mean(values), 3),
        "std": round(statistics.stdev(values), 3) if len(values) > 1 else 0,
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def aggregate_per_pattern(results: list[dict]) -> dict:
    """Per-pattern aggregate stats."""
    stats_by_pattern: dict = {}
    for pattern in PATTERNS:
        runs = [r for r in results if r["pattern"] == pattern and "error" not in r]
        errors = [r for r in results if r["pattern"] == pattern and "error" in r]

        pattern_stats: dict = {}
        for key in METRIC_KEYS:
            pattern_stats[key] = compute_stats([r[key] for r in runs])

        pattern_stats["n_runs"] = len(runs)
        pattern_stats["n_errors"] = len(errors)
        pattern_stats["approval_rate"] = (
            round(sum(1 for r in runs if r["approved"]) / len(runs) * 100, 1)
            if runs
            else 0
        )
        stats_by_pattern[pattern] = pattern_stats
    return stats_by_pattern


# ── Main comparison driver ───────────────────────────────────────────────────

def compare_patterns(company_id: int, periods: list[tuple], n_runs: int) -> dict:
    """Run all (pattern × period × run) combinations, return aggregated results."""
    total_runs = len(PATTERNS) * len(periods) * n_runs

    print("=" * 70)
    print("PATTERN COMPARISON — Baseline vs Multi-Agent")
    print(f"Patterns: {PATTERNS}")
    print(f"Periods: {[p[2] for p in periods]}")
    print(f"Runs per combination: {n_runs}")
    print(f"Total executions: {total_runs}")
    print(f"Company ID: {company_id}")
    print("=" * 70)

    all_results: list[dict] = []
    counter = 0

    for pattern in PATTERNS:
        for start, end, label in periods:
            for run_idx in range(1, n_runs + 1):
                counter += 1
                print(f"\n[{counter}/{total_runs}] {pattern} | {label} | run {run_idx}")

                result = run_single(pattern, company_id, start, end)
                result["run_idx"] = run_idx
                result["period_label"] = label

                if "error" in result:
                    print(f"  ERROR: {result['error']}")
                else:
                    print(
                        f"  Score: {result['overall_score']:.2f} | "
                        f"Time: {result['total_time']:.1f}s | "
                        f"Words: {result['word_count']}"
                    )

                all_results.append(result)

    pattern_stats = aggregate_per_pattern(all_results)
    return {"all_results": all_results, "pattern_stats": pattern_stats}


# ── Output ───────────────────────────────────────────────────────────────────

def print_summary_table(pattern_stats: dict) -> None:
    """Print compact comparison table to console."""
    print("\n" + "=" * 80)
    print("SUMMARY (mean across all periods and runs)")
    print("=" * 80)

    header = f"{'Pattern':<22} | {'Overall':>8} | {'Num.Acc':>8} | {'Hallucin':>8} | {'Time(s)':>8}"
    print(header)
    print("-" * len(header))

    labels = {"baseline": "Baseline (chain)", "multiagent": "Multi-Agent (mine)"}
    for pattern in PATTERNS:
        st = pattern_stats[pattern]
        print(
            f"{labels[pattern]:<22} | "
            f"{st['overall_score']['mean']:>8.2f} | "
            f"{st['numerical_accuracy']['mean']:>8.2f} | "
            f"{st['hallucination_free']['mean']:>8.2f} | "
            f"{st['total_time']['mean']:>8.1f}"
        )

    print("-" * len(header))
    for pattern in PATTERNS:
        st = pattern_stats[pattern]
        print(
            f"{labels[pattern]}: {st['n_runs']} successful, "
            f"{st['n_errors']} errors, {st['approval_rate']}% approval rate"
        )


def save_results(
    all_results: list[dict],
    pattern_stats: dict,
    output_dir: Path,
    timestamp: str,
    company_id: int,
    n_runs: int,
) -> tuple[Path, Path]:
    """Write raw + summary JSON files."""
    raw_file = output_dir / f"raw_{timestamp}.json"
    summary_file = output_dir / f"summary_{timestamp}.json"

    with open(raw_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2, default=str)

    summary = {
        "test_config": {
            "patterns": PATTERNS,
            "periods": [p[2] for p in TEST_PERIODS],
            "runs_per_combo": n_runs,
            "total_runs": len(PATTERNS) * len(TEST_PERIODS) * n_runs,
            "company_id": company_id,
            "timestamp": timestamp,
        },
        "pattern_stats": pattern_stats,
    }
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    return raw_file, summary_file


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Compare prompt-chaining baseline vs multi-agent pipeline.")
    parser.add_argument("--company-id", type=int, default=1)
    parser.add_argument("--runs", type=int, default=5, help="Runs per pattern per period")
    parser.add_argument("--output", type=str, default="data/pattern_comparison")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    comparison = compare_patterns(
        company_id=args.company_id,
        periods=TEST_PERIODS,
        n_runs=args.runs,
    )

    print_summary_table(comparison["pattern_stats"])

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    raw_file, summary_file = save_results(
        all_results=comparison["all_results"],
        pattern_stats=comparison["pattern_stats"],
        output_dir=output_dir,
        timestamp=timestamp,
        company_id=args.company_id,
        n_runs=args.runs,
    )

    print(f"\nRaw results: {raw_file}")
    print(f"Summary:     {summary_file}")
    n_ok = sum(1 for r in comparison["all_results"] if "error" not in r)
    print(f"Total: {len(comparison['all_results'])} runs | Successful: {n_ok}")


if __name__ == "__main__":
    main()
