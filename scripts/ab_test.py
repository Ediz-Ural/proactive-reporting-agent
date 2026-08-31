"""
Comprehensive A/B Test -- Prompting Strategy Comparison

Runs pipeline multiple times across multiple periods for each strategy.
Produces statistical summaries with mean, std, min, max.

Usage:
    python scripts/ab_test.py
    python scripts/ab_test.py --runs 3 --company-id 1
"""

import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from pathlib import Path

STRATEGIES = ["zero_shot", "few_shot", "cot"]

TEST_PERIODS = [
    ("2017-03-01", "2017-03-31", "Mar 2017"),
    ("2017-06-01", "2017-06-30", "Jun 2017"),
    ("2017-09-01", "2017-09-30", "Sep 2017"),
]


def run_single(strategy, company_id, start_date, end_date):
    """Run pipeline once with given strategy. Returns metrics dict."""
    from config.settings import settings
    from src.graph.workflow import run_pipeline

    settings.WRITER_STRATEGY = strategy

    t0 = time.time()
    try:
        state = run_pipeline(
            start_date=start_date,
            end_date=end_date,
            report_type="monthly",
            recipients=[],
            company_id=company_id,
        )
    except Exception as e:
        return {"error": str(e), "strategy": strategy, "total_time": time.time() - t0}

    total_time = time.time() - t0
    ev = state.get("evaluation", {})
    report = state.get("draft_report", "") or ""

    return {
        "strategy": strategy,
        "period": f"{start_date}/{end_date}",
        "total_time": round(total_time, 2),
        "overall_score": ev.get("overall_score", 0),
        "numerical_accuracy": ev.get("numerical_accuracy", 0),
        "completeness": ev.get("completeness", 0),
        "readability": ev.get("readability", 0),
        "actionability": ev.get("actionability", 0),
        "hallucination_free": ev.get("hallucination_free", 0),
        "approved": ev.get("approved", False),
        "iterations": state.get("evaluator_iteration", 1),
        "word_count": len(report.split()),
        "char_count": len(report),
        "section_count": report.count("###"),
        "report_text": report,
    }


def compute_stats(values):
    """Compute mean, std, min, max for a list of numbers."""
    if not values:
        return {"mean": 0, "std": 0, "min": 0, "max": 0}
    return {
        "mean": round(statistics.mean(values), 3),
        "std": round(statistics.stdev(values), 3) if len(values) > 1 else 0,
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--company-id", type=int, default=1)
    parser.add_argument("--runs", type=int, default=5, help="Runs per strategy per period")
    parser.add_argument("--output", type=str, default="data/ab_test")
    args = parser.parse_args()

    total_runs = len(STRATEGIES) * len(TEST_PERIODS) * args.runs
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("COMPREHENSIVE A/B TEST")
    print(f"Strategies: {STRATEGIES}")
    print(f"Periods: {[p[2] for p in TEST_PERIODS]}")
    print(f"Runs per combination: {args.runs}")
    print(f"Total pipeline executions: {total_runs}")
    print(f"Company ID: {args.company_id}")
    print("=" * 70)

    all_results = []
    run_counter = 0

    for strategy in STRATEGIES:
        for start, end, label in TEST_PERIODS:
            for run_num in range(1, args.runs + 1):
                run_counter += 1
                print(f"\n[{run_counter}/{total_runs}] {strategy} | {label} | run {run_num}")

                result = run_single(strategy, args.company_id, start, end)
                result["run_num"] = run_num
                result["period_label"] = label

                if "error" in result:
                    print(f"  ERROR: {result['error']}")
                else:
                    print(f"  Score: {result['overall_score']:.2f} | "
                          f"Time: {result['total_time']:.1f}s | "
                          f"Words: {result['word_count']} | "
                          f"Iter: {result['iterations']}")

                all_results.append(result)

    # -- Save raw results ------------------------------------------------------
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # Save without report text
    slim = [{k: v for k, v in r.items() if k != "report_text"} for r in all_results]
    raw_file = output_dir / f"ab_raw_{ts}.json"
    with open(raw_file, "w") as f:
        json.dump(slim, f, indent=2, default=str)

    # Save individual reports
    for r in all_results:
        if r.get("report_text"):
            fname = f"report_{r['strategy']}_{r['period_label'].replace(' ', '_')}_run{r['run_num']}_{ts}.md"
            with open(output_dir / fname, "w") as f:
                f.write(r["report_text"])

    # -- Compute statistics per strategy ---------------------------------------
    print("\n" + "=" * 90)
    print("STATISTICAL SUMMARY (aggregated across all periods and runs)")
    print("=" * 90)

    metrics_keys = [
        "overall_score", "numerical_accuracy", "completeness",
        "readability", "actionability", "hallucination_free",
        "total_time", "word_count", "iterations",
    ]

    strategy_stats = {}
    for strategy in STRATEGIES:
        runs = [r for r in all_results if r["strategy"] == strategy and "error" not in r]
        stats = {}
        for key in metrics_keys:
            values = [r[key] for r in runs]
            stats[key] = compute_stats(values)
        stats["n_runs"] = len(runs)
        stats["n_errors"] = len([r for r in all_results if r["strategy"] == strategy and "error" in r])
        stats["approval_rate"] = round(sum(1 for r in runs if r["approved"]) / len(runs) * 100, 1) if runs else 0
        strategy_stats[strategy] = stats

    # Print comparison
    print(f"\n{'Metric':<25} {'Zero-Shot':>20} {'Few-Shot':>20} {'CoT':>20}")
    print("-" * 90)

    display_metrics = [
        ("Overall Score", "overall_score"),
        ("Num. Accuracy", "numerical_accuracy"),
        ("Completeness", "completeness"),
        ("Readability", "readability"),
        ("Actionability", "actionability"),
        ("Hallucination-Free", "hallucination_free"),
        ("Time (seconds)", "total_time"),
        ("Word Count", "word_count"),
        ("Eval. Iterations", "iterations"),
    ]

    for display_name, key in display_metrics:
        vals = []
        for s in STRATEGIES:
            st = strategy_stats[s][key]
            vals.append(f"{st['mean']:.2f} ± {st['std']:.2f}")
        print(f"{display_name:<25} {vals[0]:>20} {vals[1]:>20} {vals[2]:>20}")

    print("-" * 90)
    for s in STRATEGIES:
        st = strategy_stats[s]
        print(f"{s}: {st['n_runs']} successful runs, {st['n_errors']} errors, {st['approval_rate']}% approval rate")

    # -- Per-period breakdown --------------------------------------------------
    print("\n" + "=" * 90)
    print("PER-PERIOD BREAKDOWN (Overall Score)")
    print("=" * 90)
    print(f"{'Period':<15} {'Zero-Shot':>20} {'Few-Shot':>20} {'CoT':>20}")
    print("-" * 80)

    for start, end, label in TEST_PERIODS:
        vals = []
        for s in STRATEGIES:
            runs = [r for r in all_results
                    if r["strategy"] == s and r.get("period_label") == label and "error" not in r]
            scores = [r["overall_score"] for r in runs]
            if scores:
                vals.append(f"{statistics.mean(scores):.2f} ± {statistics.stdev(scores):.2f}" if len(scores) > 1 else f"{scores[0]:.2f}")
            else:
                vals.append("N/A")
        print(f"{label:<15} {vals[0]:>20} {vals[1]:>20} {vals[2]:>20}")

    # -- Save summary ----------------------------------------------------------
    summary = {
        "test_config": {
            "strategies": STRATEGIES,
            "periods": [p[2] for p in TEST_PERIODS],
            "runs_per_combo": args.runs,
            "total_runs": total_runs,
            "company_id": args.company_id,
            "timestamp": ts,
        },
        "strategy_stats": strategy_stats,
    }

    summary_file = output_dir / f"ab_summary_{ts}.json"
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\nRaw results: {raw_file}")
    print(f"Summary: {summary_file}")
    print(f"Reports: {output_dir}/report_*.md")
    print(f"\nTotal runs: {run_counter} | Successful: {sum(1 for r in all_results if 'error' not in r)}")


if __name__ == "__main__":
    main()
