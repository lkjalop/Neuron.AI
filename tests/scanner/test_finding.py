from scanner.model.finding import Finding

def test_fingerprint_deterministic():
    f1 = Finding.from_raw(
        id="x1", plugin="dummy", title="Test", severity="HIGH", exploitability=0.7,
        score=1.0, resources=["r1"], evidence={"value": 123, "noise": [1,2,3]}, tags=["t1"]
    )
    f2 = Finding.from_raw(
        id="x1", plugin="dummy", title="Test", severity="HIGH", exploitability=0.7,
        score=1.0, resources=["r1"], evidence={"noise": [9,8], "value": 123}, tags=["t1"]
    )
    assert f1.fingerprint == f2.fingerprint, "Fingerprint should ignore non-stable evidence differences"

def test_to_dict_order_fields():
    f = Finding.from_raw(
        id="x2", plugin="dummy", title="X", severity="LOW", exploitability=0.1,
        score=0.05, resources=[], evidence={}, tags=[]
    )
    data = f.to_dict()
    keys = list(data.keys())
    assert keys == ["id","plugin","title","severity","exploitability","score","resources","evidence","tags","fingerprint"]
