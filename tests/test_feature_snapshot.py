import pytest, time
from features.asset_features import compute_asset_features
from storage import postgres


@pytest.mark.asyncio
async def test_feature_snapshot_exposure_ordering():
    # Skip gracefully if tables not present
    try:
        await postgres.fetch('SELECT 1 FROM findings LIMIT 1')
    except Exception:
        pytest.skip('findings table missing')

    now = time.time()
    # Seed three assets with varying severity mix
    async def ins(fid, cve, asset, sev, risk_score):
        await postgres.execute(
            """INSERT INTO findings (id,cve_id,asset_id,component_id,first_seen,last_seen,state,detection_source,risk_score,risk_severity,asset_metadata,sla_due_ts,risk_factors,treatment_state,accepted_risk,remediation_target_ts)
            VALUES ($1,$2,$3,$4,$5,$5,'open','test', $6, $7, '{}', NULL, '{}', NULL, NULL, NULL)
            ON CONFLICT (id) DO NOTHING""",
            fid, cve, asset, None, now, risk_score, sev
        )

    # asset A: 2 critical
    await ins('fa1','CVE-A1','asset-A','CRITICAL',0.95)
    await ins('fa2','CVE-A2','asset-A','CRITICAL',0.97)
    # asset B: 1 high 1 medium
    await ins('fb1','CVE-B1','asset-B','HIGH',0.70)
    await ins('fb2','CVE-B2','asset-B','MEDIUM',0.45)
    # asset C: 3 low
    await ins('fc1','CVE-C1','asset-C','LOW',0.10)
    await ins('fc2','CVE-C2','asset-C','LOW',0.12)
    await ins('fc3','CVE-C3','asset-C','LOW',0.08)

    feats = await compute_asset_features(now=now)
    assert 'asset-A' in feats and 'asset-B' in feats and 'asset-C' in feats
    # Exposure score should rank A > B > C
    ordering = sorted(feats.items(), key=lambda kv: kv[1]['exposure_score'], reverse=True)
    ranked_assets = [a for a,_ in ordering]
    assert ranked_assets[:3] == ['asset-A','asset-B','asset-C'], f"Unexpected ordering {ranked_assets[:3]}"
    # Variance: ensure not all exposure scores identical
    scores = {a: f['exposure_score'] for a,f in feats.items()}
    assert len(set(scores.values())) > 1
