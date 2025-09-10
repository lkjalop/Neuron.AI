from config import runtime_params
import os
import time

AUDIT_LOG = os.path.join('audit', 'AUDIT_LOG.md')

def read_audit_tail():
    try:
        with open(AUDIT_LOG, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        return lines[-20:]
    except FileNotFoundError:
        return []


def test_audit_log_records_fusion_weight_updates(tmp_path):
    # Apply two param changes and ensure audit log reflects keys
    runtime_params.update_param('fusion.weight.baseline', 0.55, reason='test_audit')
    runtime_params.update_param('fusion.weight.snn', 0.45, reason='test_audit')
    # Give a brief moment if async flush (though implementation likely synchronous)
    time.sleep(0.05)
    tail = ''.join(read_audit_tail())
    assert 'fusion.weight.baseline' in tail
    assert 'fusion.weight.snn' in tail
