import os, json, time
from core.temporal.calibration import calibrator, QuantileCalibrator


def test_calibration_save_and_load(tmp_path, monkeypatch):
    # Force calibration path into temp dir
    calib_file = tmp_path / 'temporal_calibration.json'
    monkeypatch.setattr('core.temporal.calibration._CALIBRATION_PATH', str(calib_file), raising=False)
    monkeypatch.setattr('core.temporal.calibration._CALIBRATION_DIR', str(tmp_path), raising=False)
    cal = QuantileCalibrator(max_samples=10)
    for v in [0.5, 0.7, 1.2, 0.3, 2.0]:
        cal.add('t0', v)
    cal.save()
    assert calib_file.exists()
    data = json.loads(calib_file.read_text())
    assert 't0' in data
    # New calibrator loads persisted state
    cal2 = QuantileCalibrator(max_samples=10)
    monkeypatch.setattr(cal2, '_loaded', False, raising=False)
    cal2.load(max_age_s=3600.0)
    p50, p90, p99 = cal2.quantiles('t0')
    assert p50 > 0 and p99 >= p90 >= p50
