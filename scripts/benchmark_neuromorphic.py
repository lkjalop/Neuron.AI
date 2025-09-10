"""Neuromorphic benchmark harness.

Compares baseline vs SNN (proto or LIF) on synthetic temporal anomaly patterns.
Outputs JSON artifact with detection counts and simple energy proxy metrics.

Usage (example):
  python scripts/benchmark_neuromorphic.py --events 500 --patterns drift,burst,periodic --snn-mode lif
"""
from __future__ import annotations
import argparse, json, random, time, math, hashlib, os
from dataclasses import dataclass
from typing import List, Dict

# Minimal local imports (avoid full app startup)
from config import runtime_params  # type: ignore
from core.detect.baseline import BaselineDetector  # type: ignore
from core.detect.snn import SNNDetector  # type: ignore
from core.event import Event  # type: ignore

# Patterns definitions -------------------------------------------------------

def gen_event(seq_idx: int, base_mean: float, pattern: str) -> float:
    """Generate event value for a named synthetic pattern.

    Added patterns:
      - periodic_shift: periodic sinusoidal baseline + occasional stepped shift window (enables residual forecast testing)
      - noise: very low variance region used to approximate false positive propensity
    """
    # Baseline Gaussian noise
    if pattern == "noise":
        # Tight normal distribution low variance
        return random.gauss(base_mean, 0.05)
    val = random.gauss(base_mean, 1.0)
    if pattern == "drift" and seq_idx > 150:
        val += (seq_idx - 150) * 0.02  # gradual upward drift
    elif pattern == "burst" and 200 < seq_idx < 230:
        val += random.uniform(6, 9)  # burst anomaly window
    elif pattern == "periodic" and seq_idx % 50 == 0:
        val += 8  # periodic spike
    elif pattern == "periodic_shift":
        # Sinusoidal baseline
        val += math.sin(seq_idx / 15.0) * 2.5
        # Introduce stepped shift every 120..140 window
        if 300 < seq_idx % 500 < 360:
            val += 4.5
    return val

@dataclass
class DetectorStats:
    anomalies: int = 0
    spike_energy: int = 0

# Main benchmark ------------------------------------------------------------

def run_benchmark(events: int, patterns: List[str], snn_mode: str, encoder: str) -> Dict:
    try:
        runtime_params.update_param("detection.enable_snn", True, reason="benchmark_enable_snn")
    except Exception:
        pass
    try:
        runtime_params.update_param("snn.mode", snn_mode, reason="benchmark_set_mode")
    except Exception:
        pass
    try:
        runtime_params.update_param("snn.encoder", encoder, reason="benchmark_set_encoder")
    except Exception:
        pass
    baseline = BaselineDetector()
    snn = SNNDetector()
    stats: Dict[str, DetectorStats] = {"baseline": DetectorStats(), "snn": DetectorStats()}

    start = time.time()
    noise_windows = 0
    noise_anoms = {"baseline": 0, "snn": 0}
    for i in range(events):
        pattern = patterns[i % len(patterns)]
        val = gen_event(i, 0.0, pattern)
        ev = Event(event_id=f"e{i}", timestamp=time.time(), event_type="bench", tenant_id="t0", features={"value": val}, trace_id=f"tr{i}")
        # Attach synthetic pattern metadata for precision proxy instrumentation downstream
        try:
            md = getattr(ev, 'metadata', None)
            if md is None:
                ev.metadata = {"synthetic_pattern": pattern}  # type: ignore[attr-defined]
            else:
                md["synthetic_pattern"] = pattern
        except Exception:
            pass
        b_res = baseline.process(ev)
        s_res = snn.process(ev)
        if b_res:
            stats["baseline"].anomalies += len(b_res)
        if s_res:
            stats["snn"].anomalies += len(s_res)
            # energy proxy: spike_count from first result if present
            spike_count = s_res[0].get("spike_count", 0)
            stats["snn"].spike_energy += int(spike_count)
        # Precision proxy accounting for noise windows
        if pattern == "noise":
            noise_windows += 1
            if b_res:
                noise_anoms["baseline"] += len(b_res)
            if s_res:
                noise_anoms["snn"] += len(s_res)
    elapsed = time.time() - start

    # Basic uplift metrics
    result = {
        "events": events,
        "patterns": patterns,
    "snn_mode": snn_mode,
    "snn_encoder": encoder,
        "elapsed_s": elapsed,
        "baseline_anomalies": stats["baseline"].anomalies,
        "snn_anomalies": stats["snn"].anomalies,
        "snn_spike_energy": stats["snn"].spike_energy,
        "uplift_raw": stats["snn"].anomalies - stats["baseline"].anomalies,
        "uplift_ratio": (stats["snn"].anomalies + 1) / (stats["baseline"].anomalies + 1),
        "noise_windows": noise_windows,
        "noise_false_positive_baseline": noise_anoms["baseline"],
        "noise_false_positive_snn": noise_anoms["snn"],
    }
    result["hash"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()[:16]
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--events", type=int, default=500)
    ap.add_argument("--patterns", type=str, default="drift,burst,periodic")
    ap.add_argument("--snn-mode", type=str, default="proto", choices=["proto", "lif", "all"], help="Single mode or 'all' to iterate both")
    ap.add_argument("--encoder", type=str, default="rate_v2", choices=["rate_v1", "rate_v2", "all"], help="Single encoder or 'all'")
    ap.add_argument("--out", type=str, default="artifacts/perf/neuromorphic_benchmark.json")
    ap.add_argument("--markdown", type=str, default="artifacts/perf/neuromorphic_benchmark.md")
    args = ap.parse_args()
    pats = [p.strip() for p in args.patterns.split(',') if p.strip()]
    modes = [args.snn_mode] if args.snn_mode != "all" else ["proto", "lif"]
    encoders = [args.encoder] if args.encoder != "all" else ["rate_v1", "rate_v2"]
    results = []
    for m in modes:
        for e in encoders:
            try:
                r = run_benchmark(args.events, pats, m, e)
            except Exception as ex:  # noqa: BLE001
                r = {"error": str(ex), "snn_mode": m, "snn_encoder": e}
            results.append(r)
    summary = {
        "events": args.events,
        "patterns": pats,
        "combinations": results,
        "generated_at": time.time(),
    }
    # Compute comparative uplift stats per encoder aggregated over modes
    agg: Dict[str, Dict[str, float]] = {}
    for r in results:
        if "error" in r:
            continue
        enc = r.get("snn_encoder")
        a = agg.setdefault(enc, {"baseline_anomalies": 0, "snn_anomalies": 0})
        a["baseline_anomalies"] += r.get("baseline_anomalies", 0)
        a["snn_anomalies"] += r.get("snn_anomalies", 0)
    agg_out = []
    for enc, v in agg.items():
        ratio = (v["snn_anomalies"] + 1) / (v["baseline_anomalies"] + 1)
        agg_out.append({"encoder": enc, "aggregate_uplift_ratio": ratio, **v})
    summary["encoder_aggregate"] = agg_out
    out_path = args.out
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(json.dumps(summary, indent=2))
    # Markdown summary
    md_lines = ["# Neuromorphic Benchmark Summary", "", f"Events: {args.events}", f"Patterns: {', '.join(pats)}", "", "## Per Combination", ""]
    for r in results:
        if "error" in r:
            md_lines.append(f"- Mode={r['snn_mode']} Encoder={r['snn_encoder']} ERROR: {r['error']}")
            continue
        md_lines.append(
            f"- Mode={r['snn_mode']} Encoder={r['snn_encoder']} Baseline={r['baseline_anomalies']} SNN={r['snn_anomalies']} UpliftRatio={r['uplift_ratio']:.2f}" )
    md_lines.append("\n## Encoder Aggregate Uplift")
    for a in agg_out:
        md_lines.append(f"- Encoder={a['encoder']} AggregateUpliftRatio={a['aggregate_uplift_ratio']:.2f} (SNN={a['snn_anomalies']} Base={a['baseline_anomalies']})")
    with open(args.markdown, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

if __name__ == "__main__":
    main()
