"""Tests for the A/B test script."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_ab_script_imports():
    """Verify ab_test script can be imported without errors."""
    import scripts.ab_test as ab

    assert hasattr(ab, "run_single")
    assert hasattr(ab, "compute_stats")
    assert hasattr(ab, "STRATEGIES")
    assert len(ab.STRATEGIES) == 3


def test_compute_stats():
    """Verify compute_stats returns correct statistics."""
    import scripts.ab_test as ab

    result = ab.compute_stats([1.0, 2.0, 3.0, 4.0, 5.0])
    assert result["mean"] == 3.0
    assert result["min"] == 1.0
    assert result["max"] == 5.0
    assert result["std"] > 0


def test_compute_stats_empty():
    """Verify compute_stats handles empty list."""
    import scripts.ab_test as ab

    result = ab.compute_stats([])
    assert result["mean"] == 0
    assert result["std"] == 0


def test_compute_stats_single():
    """Verify compute_stats handles single value (std=0)."""
    import scripts.ab_test as ab

    result = ab.compute_stats([42.0])
    assert result["mean"] == 42.0
    assert result["std"] == 0
    assert result["min"] == 42.0
    assert result["max"] == 42.0


def test_strategies_list():
    """Verify all expected strategies are present."""
    import scripts.ab_test as ab

    assert "zero_shot" in ab.STRATEGIES
    assert "few_shot" in ab.STRATEGIES
    assert "cot" in ab.STRATEGIES


def test_test_periods():
    """Verify test periods are defined correctly."""
    import scripts.ab_test as ab

    assert len(ab.TEST_PERIODS) == 3
    for start, end, label in ab.TEST_PERIODS:
        assert len(start) == 10
        assert len(end) == 10
        assert len(label) > 0
