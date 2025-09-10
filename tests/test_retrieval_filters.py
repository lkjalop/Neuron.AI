from core.retrieval.corpus import corpus


def test_retrieval_filter_temporal_band():
    c = corpus()
    # Simulate rebuild (would normally pull from traces; here we manually inject entries)
    c._entries.clear()  # type: ignore[attr-defined]
    c._entries.append({  # type: ignore[attr-defined]
        'event_id': 'e1',
        'embedding': [0.7, 0.7, 0.0],
        'meta': {
            'fused_count': 1,
            'detectors': 1,
            'temporal_residual_norm': 0.3,
            'temporal_confidence_band': 'HIGH',
            'temporal_mean_vec': [0.12],
        },
    })
    c._entries.append({  # type: ignore[attr-defined]
        'event_id': 'e2',
        'embedding': [0.5, 0.5, 0.7],
        'meta': {
            'fused_count': 2,
            'detectors': 1,
            'temporal_residual_norm': 0.0,
            'temporal_confidence_band': None,
            'temporal_mean_vec': None,
        },
    })
    res = c.query(None, top_k=5, filter={'detector': 'temporal', 'confidence_band': 'HIGH'})
    assert len(res) == 1
    assert res[0]['event_id'] == 'e1'


def test_retrieval_filter_detector_only():
    c = corpus()
    c._entries.clear()  # type: ignore[attr-defined]
    c._entries.append({  # temporal present
        'event_id': 'e1',
        'embedding': [0.1, 0.2, 0.3],
        'meta': {
            'fused_count': 1,
            'detectors': 1,
            'temporal_residual_norm': 0.2,
            'temporal_confidence_band': 'MEDIUM',
            'temporal_mean_vec': [0.05],
        },
    })
    c._entries.append({  # temporal absent
        'event_id': 'e2',
        'embedding': [0.2, 0.3, 0.4],
        'meta': {
            'fused_count': 1,
            'detectors': 1,
            'temporal_residual_norm': 0.0,
            'temporal_confidence_band': None,
            'temporal_mean_vec': None,
        },
    })
    res = c.query(None, top_k=5, filter={'detector': 'temporal'})
    assert len(res) == 1
    assert res[0]['event_id'] == 'e1'