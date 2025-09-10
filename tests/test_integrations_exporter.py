import os, json, time

def test_export_all_disabled(monkeypatch):
    # Import after monkeypatch to avoid early enable
    from core.integrations import base
    called = {}
    # Ensure splunk exporter is registered (import side-effect). It should be disabled by default (param false)
    import core.integrations.splunk  # noqa: F401
    results = base.export_all([{"id":1, "msg":"x"}])
    # At least one exporter (splunk) should report disabled
    assert any(r[1]["outcome"] == "disabled" for r in results)


def test_export_all_empty_batch(monkeypatch):
    from core.integrations import base

    class DummyExp:
        name = "dummy"
        def enabled(self):
            return True
        def export(self, records):
            if not list(records):
                return {"outcome": "skipped", "count":0, "latency_s":0.0}
            return {"outcome":"success", "count": len(list(records)), "latency_s":0.0}
    base.register(DummyExp())
    results = base.export_all([])
    # Expect dummy exporter outcome skipped
    assert any(name=="dummy" and res["outcome"]=="skipped" for name,res in results)
