from nlp.translator import translate

def test_negative_multi_severity():
    out = translate('show high and medium vulnerabilities')
    # Current rule: first matched token wins (high)
    assert out.get('severity') == 'HIGH'

def test_negative_ambiguous_no_severity():
    out = translate('list vulns')
    assert 'severity' not in out

def test_exploit_phrase_variations():
    out = translate('list exploitable vulns')
    assert out.get('exploit_only') is True
