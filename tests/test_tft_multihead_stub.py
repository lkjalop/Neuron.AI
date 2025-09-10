from core.temporal.models.tft_multihead import TFTMultiHeadStub

def test_tft_multihead_forward_shape():
    model = TFTMultiHeadStub(window=8, feature_dim=5, heads=3, seed=7)
    window = [[float(i+j) for j in range(5)] for i in range(8)]
    pred, residual = model.forward(window)
    assert len(pred) == 5 and len(residual) == 5
    # Deterministic test: stable first element
    pred2, residual2 = model.forward(window)
    assert pred[0] == pred2[0] and residual[0] == residual2[0]
