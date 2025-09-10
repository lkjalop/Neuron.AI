import asyncio
from core.pipeline import Pipeline
from core.event import Event
from config import runtime_params

# We'll simulate precision proxy data by sending synthetic noise events that increment windows and FP counters


def _make_noise_event(i: int, tenant: str = "tshadow"):
    ev = Event(event_id=f"e{i}", timestamp=0.0, event_type="test", tenant_id=tenant, features={"v": 0.01}, trace_id=f"tr{i}")
    # Mark as noise so precision proxy tallies consider it
    ev.metadata = {"synthetic_pattern": "noise"}  # type: ignore[attr-defined]
    return ev


def test_shadow_recommendation_emits_audit_record():
    runtime_params.update_param("detection.enable_snn", True, reason="shadow_setup", actor="test")
    runtime_params.update_param("governance.shadow.enabled", True, reason="shadow_setup", actor="test")
    p = Pipeline(["tshadow"])
    # Pre-load internal precision proxy state to exceed window threshold quickly
    # We'll craft scenario where SNN FP rate > baseline FP rate to trigger raise_threshold suggestion
    # To do that we need baseline anomalies fewer than SNN anomalies; simplest is to fake internal structure directly
    pp = p._precision_proxy.setdefault("tshadow", {"windows": 31, "fp_baseline": 5, "fp_snn": 9})  # type: ignore[attr-defined]
    # Call shadow helper explicitly
    p._maybe_shadow_recommendation("tshadow")  # type: ignore[attr-defined]
    # Since helper logs via runtime_params.audit_agent_decision, we check audit file tail
    import pathlib, json
    audit_log = pathlib.Path("audit/param_changes.log")
    assert audit_log.exists(), "Audit log should exist after recommendation"
    tail = audit_log.read_text(encoding="utf-8").strip().splitlines()[-5:]
    # Look for agent.governance_shadow.decision record
    found = False
    for line in reversed(tail):
        try:
            data = json.loads(line)
            rec = data.get("rec", {})
            if rec.get("key") == "agent.governance_shadow.decision":
                detail = rec.get("new", {}).get("detail", {})
                if detail.get("suggestion", {}).get("action") in {"raise_threshold", "lower_threshold"}:
                    found = True
                    break
        except Exception:
            continue
    assert found, "Expected a shadow recommendation audit record"

