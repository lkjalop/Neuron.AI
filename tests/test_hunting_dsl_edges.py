"""Edge case tests for hunting DSL parser & matcher.

Validates:
  * Empty / whitespace query returns no predicates.
  * Unsupported operator raises ValueError.
  * Mixed AND spacing & case-insensitivity of tokens.
  * Regex operator '~' compiles and filters appropriately.
  * Inequality '!=' works when value mismatched.
"""
from __future__ import annotations

import pytest

try:
    from hunting import dsl
except Exception:  # pragma: no cover - module path fallback
    pytest.skip("hunting.dsl module not present", allow_module_level=True)


def test_empty_query():
    preds = dsl.parse_query("")
    assert preds == []


def test_whitespace_query():
    preds = dsl.parse_query("   \n  \t  ")
    assert preds == []


def test_unsupported_operator():
    with pytest.raises(ValueError):
        dsl.parse_query("field > 10")  # '>' not supported


def test_case_insensitive_and_and_spacing():
    preds = dsl.parse_query("severity=HIGH   AnD   type=ANOMALY")
    assert len(preds) == 2
    rec = {"severity": "HIGH", "type": "ANOMALY"}
    assert all(p(rec) for p in preds)


def test_regex_operator_matches():
    preds = dsl.parse_query("message~err(or)?")
    assert len(preds) == 1
    rec_ok = {"message": "critical error occurred"}
    rec_bad = {"message": "all fine"}
    assert preds[0](rec_ok)
    assert not preds[0](rec_bad)


def test_not_equals_operator():
    preds = dsl.parse_query("status!=closed AND status!=resolved")
    rec = {"status": "open"}
    assert len(preds) == 2
    assert all(p(rec) for p in preds)
    rec2 = {"status": "closed"}
    assert not all(p(rec2) for p in preds)
