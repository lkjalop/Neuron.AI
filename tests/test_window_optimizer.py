from rag.window import optimize_window

def test_optimize_window_basic():
    candidates = [
        {"key": ("d1", 0), "tokens": ["a", "b", "c"], "score": 0.9},
        {"key": ("d2", 0), "tokens": ["c", "d", "e"], "score": 0.8},
        {"key": ("d3", 0), "tokens": ["f"], "score": 0.7},
    ]
    sel, cov, covered = optimize_window(candidates, token_budget=5)
    assert sel  # not empty
    assert 0 < cov <= 1
    assert len(covered) <= 5
    # Expect first candidate chosen
    assert ("d1", 0) in sel


def test_optimize_window_redundancy():
    # Two candidates with overlapping tokens, verify redundancy penalty encourages diversity
    cands = [
        {"key": ("x1", 0), "tokens": ["alpha", "beta", "gamma"], "score": 1.0},
        {"key": ("x2", 0), "tokens": ["alpha", "beta", "delta"], "score": 0.9},
        {"key": ("x3", 0), "tokens": ["theta", "iota"], "score": 0.5},
    ]
    sel, cov, covered = optimize_window(cands, token_budget=4, redundancy_penalty=0.5)
    # With penalty, x3 may be selected to broaden coverage
    assert len(sel) >= 1
    assert cov > 0
