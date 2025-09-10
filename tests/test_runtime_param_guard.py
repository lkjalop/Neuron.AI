import pytest
from config import runtime_params


def test_invalid_encoder_value_raises():
    with pytest.raises(ValueError):
        runtime_params.update_param('snn.encoder', 'invalid_encoder_xyz', reason='test_guard')


def test_valid_encoder_values_pass():
    for val in ['rate_v1', 'rate_v2']:
        runtime_params.update_param('snn.encoder', val, reason='test_guard_valid')
        assert runtime_params.get_param('snn.encoder') == val
