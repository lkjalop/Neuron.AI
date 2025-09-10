from core.temporal.calibration import QuantileCalibrator

class MockPostgresModule:
    def __init__(self):
        self.executed = []
    async def execute(self, sql, *args):  # type: ignore
        self.executed.append((sql, args))
        return 'OK'

def test_calibration_persistence(monkeypatch):
    monkeypatch.setenv('NEON_DATABASE_URL', 'postgres://example')
    mock_pg = MockPostgresModule()
    monkeypatch.setitem(__import__('sys').modules, 'storage.postgres', mock_pg)
    c = QuantileCalibrator()
    for v in [0.1,0.2,0.3,0.4,0.5]:
        c.add('tenantC', v)
    c.save()
    # Create table + upsert attempted
    stmts = ' '.join(s for s,_ in mock_pg.executed)
    assert 'CREATE TABLE IF NOT EXISTS calibration_quantiles' in stmts
    assert 'INSERT INTO calibration_quantiles' in stmts
