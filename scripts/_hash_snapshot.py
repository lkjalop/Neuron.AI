import hashlib, json, pathlib
files=['src/core/detect/snn.py','src/core/metrics.py','src/core/main.py','docs/SNN_ENCODING.md','tests/test_snn_detector.py']
out={}
for f in files:
    p=pathlib.Path(f)
    if p.exists():
        out[f]=hashlib.sha256(p.read_bytes()).hexdigest()
print(json.dumps(out, indent=2))
