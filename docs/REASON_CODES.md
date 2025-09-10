# Detector & Fusion Reason Codes (Canonical Taxonomy)

| Code | Layer | Meaning | Typical Trigger | Analyst Note |
|------|-------|---------|-----------------|-------------|
| baseline_zscore | Baseline | Rolling z-score exceeded threshold | Value dev > N std dev | Check variance spike |
| baseline_abs_delta | Baseline | Absolute delta from mean threshold | Sudden jump post stability | Investigate deployment/burst |
| baseline_mad | Baseline | MAD fallback anomaly | Low variance robust deviation | Consider window size |
| zero_variance_fallback | Baseline | Zero variance fallback anomaly | All identical then spike | Adjust threshold or warmup |
| snn_spike_threshold | SNN | Spike density/activity beyond threshold | High spiking ratio | Compare baseline presence |
| resource_guard_trip | Governance | SNN disabled due to guard | Latency/memory threshold | Capacity planning |
| temporal_periodicity | Temporal | Periodic pattern break | Expected cycle broken | Validate schedule changes |
| graph_connectivity_ratio | Graph | Abnormal connectivity ratio | Node/edge pattern shift | Lateral spread suspicion |
| consensus_suppression | Fusion | Unique anomaly suppressed | Only one detector fired | Evaluate detector drift |
| fallback_strategy_transition | Fusion | Auto fallback triggered | Suppression rate high | Fusion tuning needed |
| drift_psi_high | Drift | PSI above high threshold | Distribution shift | Recalibrate / retrain |
| calibration_bucket_misfit | Calibration | Large bin error in ECE | Poor prob mapping | Refit calibrator |
| agent_annotation_context | Agent | Context enrichment added | Pattern match heuristic | Cross-reference incidents |

Change Policy: Amendments require audit entry + canonical doc hash update.
