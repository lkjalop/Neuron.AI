import pytest
from nlp.translator import translate


def test_translate_severity():
    out = translate("show critical exploitable vulns older than 30 days")
    # Check IR structure
    assert out['domain'] == 'vulnerabilities'
    
    # Find severity clause
    severity_clause = next((c for c in out['clauses'] if c['type'] == 'severity'), None)
    assert severity_clause is not None
    assert severity_clause['value'] == 'CRITICAL'
    
    # Find exploit status clause
    exploit_clause = next((c for c in out['clauses'] if c['type'] == 'exploit_status'), None)
    assert exploit_clause is not None
    assert exploit_clause['value'] is True
    
    # Find age clause
    age_clause = next((c for c in out['clauses'] if c['type'] == 'age'), None)
    assert age_clause is not None
    assert age_clause['value'] == 30


def test_translate_findings_target():
    out = translate("open findings high severity")
    # Check IR structure
    assert out['domain'] == 'findings'
    
    # Find severity clause
    severity_clause = next((c for c in out['clauses'] if c['type'] == 'severity'), None)
    assert severity_clause is not None
    assert severity_clause['value'] == 'HIGH'
