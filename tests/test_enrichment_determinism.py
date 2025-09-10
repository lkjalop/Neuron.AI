from __future__ import annotations
from scanner.enrichment import get_epss_scores, get_kev_set

def test_enrichment_determinism():
    cve_ids = [f"CVE-2025-000{i}" for i in range(10)]
    epss1 = get_epss_scores(cve_ids)
    epss2 = get_epss_scores(cve_ids)
    kev1 = get_kev_set(cve_ids)
    kev2 = get_kev_set(cve_ids)
    # Determinism: repeated calls yield same results
    assert epss1 == epss2
    assert kev1 == kev2
    # EPSS values are in [0,1]
    for v in epss1.values():
        assert 0.0 <= v <= 1.0
    # KEV set is subset of input
    for k in kev1:
        assert k in cve_ids
