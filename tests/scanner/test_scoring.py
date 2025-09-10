from scanner.scoring.exploitability import blend_score

def test_blend_score_basic():
    params = {
        "scanner.score.base_weight": 1.0,
        "scanner.score.neuromorphic_weight": 0.2,
        "scanner.score.scale": 1.0,
        "_neu_signal": 0.5,
    }
    s = blend_score(0.4, "HIGH", params)
    # HIGH => sev_w=1.5 => 0.4*1.5*1.0 + 0.5*0.2 = 0.6 + 0.1 = 0.7
    assert s == 0.7

def test_blend_score_scale_and_unknown_sev():
    params = {
        "scanner.score.base_weight": 2.0,
        "scanner.score.neuromorphic_weight": 0.0,
        "scanner.score.scale": 2.0,
        "_neu_signal": 0.0,
    }
    s = blend_score(0.5, "weird", params)  # sev_w defaults to 1.0
    # 0.5 * 1.0 * 2.0 * scale 2.0 => raw=1.0 => scaled=2.0
    assert s == 2.0
