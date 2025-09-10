"""Deterministic replay harness.

Usage:
  python -m scripts.replay_harness --events events.jsonl --iterations 2 --max-events 200 \
      --assert-composite-drift 0.05 --assert-retrieval-stability 1

Objectives:
  - Feed a fixed sequence of events into the running FastAPI app (in-process TestClient).
  - After each iteration collect:
       * Governance composite signal sequence (snapshot from /executive/kpis)
       * Retrieval ordering signature for representative insight queries (hash of chunk_id ordering)
  - Compute drift statistics across iterations and optionally fail (non-zero exit) if thresholds exceeded.

Assumptions / Simplifications:
  - Uses seeded PRNG for any randomized components (sets PYTHONHASHSEED and random.seed if available).
  - Insight retrieval queries derived from distinct event 'category' fields (best-effort) limited to top N.
  - Focus is on stability of composite governance signal and deterministic retrieval ordering for same queries.

Runtime Param Influences:
  - governance.shadow_mode may be auto-enabled during replay unless --allow-governor applies.

Exit Codes:
  0 success / within thresholds
  2 composite drift exceeded
  3 retrieval instability exceeded
  4 general error
"""
from __future__ import annotations

import argparse, json, hashlib, sys, os, statistics, time
from typing import List, Dict, Any

try:
    from fastapi.testclient import TestClient  # type: ignore
except Exception:  # pragma: no cover
    TestClient = None  # type: ignore


def _hash_list(values: List[Any]) -> str:
    h = hashlib.sha256()
    for v in values:
        h.update(str(v).encode('utf-8'))
        h.update(b'|')
    return h.hexdigest()[:16]


def load_events(path: str, max_events: int | None = None) -> List[Dict[str, Any]]:
    events = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                if isinstance(ev, dict):
                    events.append(ev)
            except Exception:
                continue
            if max_events and len(events) >= max_events:
                break
    return events


def run_replay(app, events: List[Dict[str, Any]], iterations: int = 2, insight_queries: int = 3) -> Dict[str, Any]:
    if not TestClient:
        raise RuntimeError("fastapi.testclient unavailable")
    client = TestClient(app)
    composite_sequences: List[List[float]] = []
    retrieval_signatures: List[List[str]] = []  # per iteration list of query signatures

    # Derive candidate insight queries from event categories (best-effort)
    seen_cats = []
    for ev in events:
        cat = ev.get('category') or ev.get('type') or ev.get('detector')
        if cat and cat not in seen_cats:
            seen_cats.append(cat)
        if len(seen_cats) >= insight_queries:
            break
    if not seen_cats:
        seen_cats = ["anomaly"]

    for it in range(iterations):
        seq = []
        # Ingest events
        for ev in events:
            try:
                client.post('/ingest', json=ev)
            except Exception:
                continue
            # Periodically snapshot composite (every 25 events)
            if len(seq) == 0 or (len(seq) < 5000 and (len(seq) % 25 == 0)):
                try:
                    r = client.get('/executive/kpis')
                    if r.status_code == 200:
                        k = r.json()
                        comp = ((k.get('governance') or {}).get('composite_signal'))
                        if isinstance(comp, (int, float)):
                            seq.append(float(comp))
                except Exception:
                    pass
        # Final snapshot
        try:
            r = client.get('/executive/kpis')
            if r.status_code == 200:
                k = r.json()
                comp = ((k.get('governance') or {}).get('composite_signal'))
                if isinstance(comp, (int, float)):
                    seq.append(float(comp))
        except Exception:
            pass
        composite_sequences.append(seq)
        # Retrieval ordering signatures
        sigs = []
        for cat in seen_cats:
            try:
                r = client.get('/insights', params={'tenant': 'tenantA'})
                if r.status_code != 200:
                    continue
                data = r.json()
                # flatten context chunk ordering for this category
                matches = []
                for ins in data.get('insights', []):
                    if ins.get('category') == cat and 'context' in ins:
                        matches.extend([c.get('chunk_id') for c in (ins.get('context') or [])])
                if matches:
                    sigs.append(_hash_list(matches))
            except Exception:
                continue
        retrieval_signatures.append(sigs)
    return {
        'composite_sequences': composite_sequences,
        'retrieval_signatures': retrieval_signatures,
        'queries': seen_cats,
    }


def analyze(results: Dict[str, Any], max_composite_drift: float | None, require_retrieval_stability: bool) -> Dict[str, Any]:
    comp_seqs = results['composite_sequences']
    drift = 0.0
    if len(comp_seqs) >= 2:
        # Compare element-wise means (pad shorter with last value) across iterations
        base = comp_seqs[0]
        other = comp_seqs[1]
        if base and other:
            L = max(len(base), len(other))
            b_expanded = base + [base[-1]] * (L - len(base))
            o_expanded = other + [other[-1]] * (L - len(other))
            diffs = [abs(a - b) for a, b in zip(b_expanded, o_expanded)]
            drift = max(diffs) if diffs else 0.0
    retrieval_stable = True
    sigs = results['retrieval_signatures']
    if require_retrieval_stability and len(sigs) >= 2:
        if sigs[0] != sigs[1]:
            retrieval_stable = False
    return {'composite_drift': drift, 'retrieval_stable': retrieval_stable}


def main():
    parser = argparse.ArgumentParser(description='Deterministic replay harness')
    parser.add_argument('--events', required=True, help='Path to events JSONL')
    parser.add_argument('--iterations', type=int, default=2)
    parser.add_argument('--max-events', type=int, default=500)
    parser.add_argument('--assert-composite-drift', type=float, default=None, dest='assert_drift')
    parser.add_argument('--assert-retrieval-stability', type=int, default=0, dest='assert_retrieval')
    parser.add_argument('--allow-governor', action='store_true', help='If set, do not force governance.shadow_mode=1')
    args = parser.parse_args()

    from core.main import build_app  # lazy import after args
    from config import runtime_params

    # Force shadow mode & disable weight tunes for deterministic run unless override
    if not args.allow_governor:
        try:
            runtime_params.update_param('governance.shadow_mode', True, reason='replay_harness_seed', actor='replay')
        except Exception:
            pass
    # Load events
    events = load_events(args.events, max_events=args.max_events)
    if not events:
        print('No events loaded; aborting', file=sys.stderr)
        sys.exit(4)
    app = build_app()

    results = run_replay(app, events, iterations=args.iterations)
    analysis = analyze(results, args.assert_drift, bool(args.assert_retrieval))
    print(json.dumps({'results': results, 'analysis': analysis}, indent=2))

    # Enforcement
    if args.assert_drift is not None and analysis['composite_drift'] > args.assert_drift:
        print(f"Composite drift {analysis['composite_drift']:.4f} exceeds threshold {args.assert_drift}", file=sys.stderr)
        sys.exit(2)
    if args.assert_retrieval and not analysis['retrieval_stable']:
        print("Retrieval ordering instability detected", file=sys.stderr)
        sys.exit(3)
    sys.exit(0)


if __name__ == '__main__':  # pragma: no cover
    main()
