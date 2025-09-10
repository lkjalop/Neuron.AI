from core.soar import actions


def test_soar_actions_sequence():
    tid = actions.open_ticket('f-123', 'Investigate critical vuln')
    sid = actions.trigger_scan('asset-9', 'tenable')
    rid = actions.accept_risk('f-123', 'Compensating control')
    log = actions.list_actions()
    assert any(entry['id'] == tid for entry in log)
    assert any(entry['id'] == sid for entry in log)
    assert any(entry['id'] == rid for entry in log)
    types = {e['type'] for e in log}
    assert {'ticket','scan','risk_accept'}.issubset(types)
