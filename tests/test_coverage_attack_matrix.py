"""Tests for coverage.attack_matrix coverage_summary function.

Ensures returned structure has expected keys and technique counts align
with provided mapping.
"""
from __future__ import annotations

import pytest

try:
    from coverage import attack_matrix
except Exception:  # pragma: no cover
    pytest.skip("coverage.attack_matrix module not present", allow_module_level=True)


def test_coverage_summary_shape():
    summary = attack_matrix.coverage_summary()
    assert isinstance(summary, dict)
    assert {"total_techniques", "covered", "coverage_ratio", "by_tactic"}.issubset(summary.keys())
    assert isinstance(summary["by_tactic"], dict)
    # Validate ratio range
    assert 0.0 <= summary["coverage_ratio"] <= 1.0
    # Covered cannot exceed total
    assert summary["covered"] <= summary["total_techniques"]


def test_coverage_summary_tactic_internal_consistency():
    summary = attack_matrix.coverage_summary()
    total_from_tactics = 0
    covered_from_tactics = 0
    for tactic, data in summary["by_tactic"].items():
        assert {"techniques", "covered", "coverage_ratio"}.issubset(data.keys())
        techs = data["techniques"]
        covered = data["covered"]
        ratio = data["coverage_ratio"]
        assert covered <= len(techs)
        if len(techs) > 0:
            # ratio approximate (floating) but should be in range
            assert 0.0 <= ratio <= 1.0
        total_from_tactics += len(techs)
        covered_from_tactics += covered
    # Totals aggregated should match top-level counts
    assert total_from_tactics == summary["total_techniques"]
    assert covered_from_tactics == summary["covered"]
