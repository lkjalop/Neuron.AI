"""Runtime parameter registry with validation and audit logging.

Provides governed mutation of tunable detection & system parameters prior to
Phase 3 (SNN) so we can adjust sensitivity without redeploy.
"""
from __future__ import annotations

import json, threading, time, pathlib, typing as t
import datetime, hashlib, os
try:
    from core import metrics  # type: ignore
except Exception:  # pragma: no cover
    metrics = None  # type: ignore

_LOCK = threading.Lock()
_SCHEMA: dict[str, tuple[type, object, object, object]] = {
    # key: (type, default, min, max)
    "baseline.window_size": (int, 50, 5, 10_000),
    "baseline.stddev_threshold": (float, 3.0, 0.5, 12.0),
    "baseline.warmup_min": (int, 10, 1, 2_000),
    "baseline.mad_factor": (float, 3.5, 0.5, 30.0),
    "flood.threshold": (float, 0.2, 0.01, 1.0),
    "baseline.use_hybrid": (bool, False, False, True),  # hybrid z+MAD decision mode
    # --- Phase 3 SNN parameters (scaffold) ---
    # Master feature flag to enable SNN detector registration (disabled by default until A12 gate)
    "detection.enable_snn": (bool, False, False, True),
    # Number of time steps for rate / temporal encoding window.
    "snn.encoding_window": (int, 20, 1, 5_000),
    # Global multiplier applied after feature normalization to derive spike rates.
    "snn.rate_scale": (float, 1.0, 0.0001, 100.0),
    # Membrane decay factor for LIF neurons (close to 1.0 retains memory longer).
    "snn.lif_decay": (float, 0.95, 0.5, 0.9999),
    # Firing threshold for readout / anomaly scoring layer.
    # Threshold empirically selected ~3.0; cap lowered from 10.0 to 6.0 to reduce risk of silent disablement of SNN (too high threshold -> zero anomalies)
    "snn.threshold": (float, 1.0, 0.1, 6.0),
    # Mode selection for SNN implementation: proto (accumulator) or lif (snntorch-backed)
    "snn.mode": (str, "proto", "proto", "lif"),
    # Hidden size for LIF torch implementation
    "snn.lif.hidden_size": (int, 32, 1, 8192),
    # Exponential smoothing alpha for predicted activity gauge (0..1)
    "snn.prediction.alpha": (float, 0.7, 0.0, 1.0),
    # Resource guard parameters
    # Max acceptable p95 inference latency (seconds) before triggering degrade / cooldown
    "snn.guard.max_latency_s": (float, 0.25, 0.01, 5.0),
    # Max acceptable spike density (fraction of active spikes) averaged over window
    "snn.guard.max_spike_density": (float, 0.8, 0.01, 1.0),
    # Cooldown period in seconds after guard triggers before re-enabling SNN
    "snn.guard.cooldown_s": (float, 30.0, 1.0, 3600.0),
    # --- Phase 4 Fusion parameters ---
    # Strategy controlling arbitrator behavior: pass_through | baseline_priority | snn_priority (future) | consensus_only (future)
    "detection.fusion.strategy": (str, "pass_through", "pass_through", "consensus_only"),
    # Rolling window size for fusion precision proxy ratio (SNN unique / union)
    "fusion.precision_window": (int, 200, 10, 10_000),
    # Alert threshold for sustained suppression rate (0..1). If rolling suppression rate exceeds this, increment alert counter.
    "fusion.suppression_alert_rate": (float, 0.85, 0.0, 1.0),
    # Weights for weighted_sum fusion strategy (Phase 4 experimental) w_b * baseline_indicator + w_s * snn_norm
    "fusion.weight.baseline": (float, 0.6, 0.0, 5.0),
    "fusion.weight.snn": (float, 0.4, 0.0, 5.0),
    # Memory signal weighting seed & uplift gating threshold (Phase4/5 adaptive fusion)
    "fusion.memory.signal.seed": (float, 0.1, 0.0, 1.0),
    "fusion.memory.uplift.threshold": (float, 0.05, 0.0, 1.0),
    # Isolation Forest detector fusion weight
    "fusion.weight.iforest": (float, 0.0, 0.0, 5.0),
    # Weighted sum suppression threshold: drop SNN-only anomalies if composite score below this (0 disables suppression)
    "fusion.weighted_sum.suppress_threshold": (float, 0.0, 0.0, 5.0),
    # --- Encoder V2 & Calibration additions ---
    # Select encoder: rate_v1 | rate_v2 (adds adaptive scaling & burst emphasis)
    "snn.encoder": (str, "rate_v1", "rate_v1", "rate_v2"),
    # Target SNN anomaly rate as fraction of baseline anomaly count (used when auto-cal enabled)
    "snn.auto_cal.target_ratio": (float, 2.0, 0.1, 20.0),
    # Minimum events between auto-calibration passes
    "snn.auto_cal.interval": (int, 500, 50, 100_000),
    # Enable auto threshold calibration (true/false)
    "snn.auto_cal.enabled": (bool, False, False, True),
    # Max step size for threshold adjustment per calibration pass (fractional delta)
    "snn.auto_cal.max_step": (float, 0.2, 0.01, 1.0),
    # Global shrink factor for rate_v2 encoder to cap uplift; applied multiplicatively to per-feature rates
    "snn.encoder.rate_v2.global_shrink": (float, 0.1, 0.01, 1.0),
    # Minimum floor applied after shrink to keep v2 from fully silencing (0 disables floor)
    "snn.encoder.rate_v2.min_floor": (float, 0.04, 0.0, 0.2),
    # Debug flag to emit encoder v2 rate vectors (stdout best-effort)
    "snn.encoder.rate_v2.debug": (bool, False, False, True),
    # Debug flag to bypass density cap (diagnostics only)
    "snn.encoder.rate_v2.debug_no_cap": (bool, False, False, True),
    # Enable simple sequence forecaster residual feature injection
    "seq.forecaster.enable": (bool, False, False, True),
        # Experimental temporal transformer (TFT) enable flag (no-op scaffold)
        "detection.temporal.enable_transformer": (bool, False, False, True),
    # Temporal guard: max acceptable processing latency (seconds) placeholder
    "temporal.guard.max_latency_s": (float, 0.2, 0.01, 5.0),
    # Temporal guard: max sequence window memory (approx vector count * features) before backoff
    "temporal.guard.max_window": (int, 2000, 10, 100_000),
    # Adaptive fusion weight for temporal detector contribution (0 disables influence in future fusion logic)
    "detection.temporal.weight": (float, 0.0, 0.0, 5.0),
    # Enable temporal residual variance based micro-anomaly contribution in baseline & SNN hybrid paths
    "temporal.residual.enable": (bool, False, False, True),
    # Simple temporal variance model flags
    "detection.temporal.simple_model": (bool, False, False, True),
    "detection.temporal.var_threshold": (float, 0.18, 0.01, 1.0),
    "detection.temporal.encoder": (str, "variance", "variance", "attn"),
    "detection.temporal.attn_threshold": (float, 0.22, 0.01, 1.0),
    # Max acceptable precision proxy (false positive) rate for temporal contribution to participate in fusion (future when temporal participates in proxy windows). 1.0 disables gating.
    "fusion.temporal.precision_max_rate": (float, 1.0, 0.0, 1.0),
    # Calibration persistence controls
    "temporal.calibration.save_interval_updates": (int, 200, 10, 100_000),
    "temporal.calibration.save_interval_s": (float, 120.0, 5.0, 10_000.0),
    "temporal.calibration.max_age_s": (float, 7200.0, 60.0, 172800.0),
    # Temporal guard v2 thresholds
    "temporal.guard.max_calibration_stale_s": (float, 900.0, 30.0, 86400.0),
    "temporal.guard.max_residual_var": (float, 5.0, 0.01, 10_000.0),
    # --- Adaptive Temporal Weight Tuner Parameters ---
    # Master enable flag for adaptive tuning of detection.temporal.weight
    "fusion.temporal.tuner.enabled": (bool, False, False, True),
    # Target uplift ratio: temporal_applied / baseline_anomalies (>=1 means match baseline volume)
    "fusion.temporal.tuner.target_uplift": (float, 0.8, 0.0, 10.0),
    # Maximum proportional step (fraction of current weight) per tuning cycle (absolute clamp also applied)
    "fusion.temporal.tuner.max_step": (float, 0.25, 0.01, 1.0),
    # Absolute maximum delta (hard cap) per cycle if proportional exceeds
    "fusion.temporal.tuner.max_abs_delta": (float, 0.3, 0.01, 5.0),
    # Cooldown between tuner adjustments (seconds)
    "fusion.temporal.tuner.cooldown_s": (float, 30.0, 1.0, 3600.0),
    # Allowed relative error band (± tolerance * target) before adjusting
    "fusion.temporal.tuner.tolerance": (float, 0.1, 0.0, 1.0),
    # Minimum number of baseline anomalies in window to consider adjusting
    "fusion.temporal.tuner.min_baseline": (int, 3, 1, 10_000),
    # Weight bounds for tuner (safety override narrower than global param bounds if desired)
    "fusion.temporal.tuner.min_weight": (float, 0.0, 0.0, 5.0),
    "fusion.temporal.tuner.max_weight": (float, 2.0, 0.0, 10.0),
    # Seed weight to jump-start from 0 when uplift requires increase
    "fusion.temporal.tuner.seed_weight": (float, 0.05, 0.0, 1.0),
    # --- Governance / Shadow Mode Parameters (Batch 5) ---
    # Enable shadow recommendations (no automatic param mutation; emits audit_agent_decision records with suggestions)
    "governance.shadow.enabled": (bool, False, False, True),
    # Persist shadow recommendations to JSONL (best-effort) when enabled
    "governance.shadow.persist": (bool, False, False, True),
    # Force drift guard trigger after N precision proxy windows (testing / diagnostics). 0 disables.
    "governance.drift_guard.force_after_windows": (int, 0, 0, 1_000_000),
    # Force immediate drift guard trigger (test/diagnostics). Resets automatically not handled (caller must disable).
    "governance.drift_guard.force_immediate": (bool, False, False, True),
    # Enable persistence of drift guard trace ring buffer to JSONL (added Batch 4 observability). Disabled by default to avoid IO overhead.
    "governance.drift_guard.trace.persist": (bool, False, False, True),
    # Action mode ordering for drift guard when triggered: disable_then_raise | raise_first | disable_only | raise_only
    # Determines which mitigation is attempted first (disable SNN vs raise suppression threshold). New in Batch 6.
    "governance.drift_guard.action_mode": (str, "disable_then_raise", "disable_then_raise", "raise_first"),
    # Maximum suppression autotune adjustments allowed per hour per tenant (rate limit governance). 0 disables limiting.
    "governance.autotune.max_per_hour": (int, 12, 0, 10_000),
    # Enable governance diagnostics endpoint (/governance/diagnostics). Disable for hardened deployments.
    "governance.diagnostics.enabled": (bool, True, False, True),
    # Maximum governance actions log file size in bytes before rotation (0 disables rotation)
    "governance.diagnostics.max_log_bytes": (int, 500_000, 0, 100_000_000),
    # Number of rotated history files to retain
    "governance.diagnostics.max_history_files": (int, 5, 1, 100),
    # --- Isolation Forest Detector Parameters ---
    "iforest.enable": (bool, False, False, True),
    "iforest.buffer_size": (int, 512, 16, 100_000),
    "iforest.retrain_interval_events": (int, 128, 1, 1_000_000),
    "iforest.retrain_interval_s": (float, 30.0, 0.0, 86_400.0),
    # Allow very large sentinel values in tests to effectively disable training without range errors
    "iforest.min_train": (int, 32, 8, 10_000_000),
    "iforest.max_samples": (int, 256, 8, 10_000),
    "iforest.n_estimators": (int, 100, 10, 2_000),
    "iforest.contamination": (float, 0.1, 0.0001, 0.5),  # if set to special string 'auto' validation bypass not handled; treat float path
    "iforest.random_seed": (int, 42, 0, 10_000_000),
    # Extreme value heuristic threshold for single-dimensional vectors (magnitude > threshold -> anomaly)
    "iforest.extreme_value_threshold": (float, 6.0, 1.0, 10_000.0),
    # --- Phase 6.1 Ticketing ---
    # Default SLA target (seconds) for ticket acknowledgement / action before breach flagged
    "ticket.sla.seconds": (int, 3600, 60, 604800),
    # --- Retrieval / RAG Parameters (A17) ---
    # Character chunk size for document ingestion
    "retrieval.chunk_size": (int, 800, 100, 10_000),
    # Character overlap between consecutive chunks
    "retrieval.chunk_overlap": (int, 80, 0, 1_000),
    # Safety cap on total chunks retained in active in-memory index (older overflow truncated)
    "retrieval.max_chunks": (int, 5000, 10, 100_000),
    # Enable explanation fields in retrieval output (if disabled, explanations omitted regardless of flag)
    "retrieval.enable_explanations": (bool, False, False, True),
    # Scoring mode: keyword | hybrid (hybrid incorporates simple term frequency embedding similarity)
    "retrieval.scoring.mode": (str, "keyword", "keyword", "hybrid"),
    # Weight for embedding component when hybrid scoring mode active (0..1)
    "retrieval.hybrid.embedding_weight": (float, 0.3, 0.0, 1.0),
    # --- Feedback & Insight Enrichment Parameters (A18) ---
    # Maximum analyst note length accepted by feedback ingestion (chars)
    "feedback.max_note_length": (int, 2000, 0, 20_000),
    # Minimum severity for adding retrieval context to insights
    "insight.context.min_severity": (float, 0.6, 0.0, 1.0),
    # Top-K context chunks to attach when enrichment enabled
    "insight.context.top_k": (int, 3, 0, 50),
    # --- Reliability (A11 completion) ---
    # Enable inline detection fast path (separate from header; header still required for actual activation but this param gates availability)
    "ingest.inline_detection.enabled": (bool, True, False, True),
    # Jitter: additional random events to skip anomaly decisions during warm-up (0 disables)
    "baseline.warmup_jitter_events": (int, 0, 0, 10_000),
    # Max seconds jitter delay (sleep) applied once at process start for baseline stabilization (0 disables)
    "baseline.warmup_jitter_max_s": (float, 0.0, 0.0, 30.0),
    # Drift monitoring compute interval (events between recompute cycles)
    "drift.compute_interval": (int, 200, 10, 500_000),
    # --- Anomaly Sink Runtime Controls (new) ---
    "anomalies.batch.size": (int, 50, 1, 500),
    "anomalies.batch.interval_s": (float, 2.0, 0.1, 30.0),
    "anomalies.ttl_days": (int, 7, 1, 365),
    # Agent scheduling loop interval
    "agents.loop.interval_s": (float, 5.0, 0.5, 3600.0),
    # Forecasting & temporal enhancements
    "forecast.ewma.alpha": (float, 0.3, 0.01, 0.99),
    "forecast.holt.beta": (float, 0.1, 0.0, 1.0),
    "forecast.holt.gamma": (float, 0.0, 0.0, 1.0),
    "forecast.enable_holt_winters": (bool, False, False, True),
    # Temporal transformer fusion weight
    "fusion.weight.transformer": (float, 0.0, 0.0, 5.0),
    # Enable/disable temporal and transformer contributions in fusion
    "detection.temporal.enabled": (bool, False, False, True),
    "detection.transformer.enabled": (bool, False, False, True),
    # Base detector fusion weights
    "fusion.weight.baseline": (float, 0.6, 0.0, 5.0),
    "fusion.weight.snn": (float, 0.4, 0.0, 5.0),
    "fusion.weight.iforest": (float, 0.0, 0.0, 5.0),
    # Telemetry enable flag
    "telemetry.kernel.enable": (bool, False, False, True),
    # LLM provider & cost controls
    "llm.provider": (str, "noop", "noop", "remote"),
    "llm.cost.max_usd_per_hour": (float, 1.0, 0.0, 1000.0),
    "llm.local.command": (str, "", "", "~"),
    # SNN deeper config
    "snn.lif.layers": (int, 2, 1, 16),
    # --- Vulnerability Scanning & Risk (A14) ---
    "vuln.scan.enabled": (bool, False, False, True),
    "vuln.scan.interval_seconds": (int, 900, 60, 86_400),
    "vuln.enrichment.interval_seconds": (int, 1800, 60, 86_400),
    # Retrieval pipeline enable flag (503 when disabled)
    "retrieval.pipeline.enabled": (int, 1, 0, 1),
    # --- Alerting & Notification (Batch 6) ---
    # Master enable for alert dispatching
    "alerts.enabled": (bool, True, False, True),
    # Webhook channel enable
    "alerts.webhook.enabled": (bool, False, False, True),
    # Webhook URL (HTTP/HTTPS) to POST alert JSON payloads
    "alerts.webhook.url": (str, "", "", "~"),
    # Webhook timeout seconds
    "alerts.webhook.timeout_s": (float, 3.0, 0.5, 60.0),
    # Risk weight vector (sum not required to be 1; normalized implicitly in scoring logic if needed)
    "vuln.risk.weights.cvss": (float, 0.30, 0.0, 1.0),
    "vuln.risk.weights.exploit": (float, 0.20, 0.0, 1.0),
    "vuln.risk.weights.exposure": (float, 0.15, 0.0, 1.0),
    "vuln.risk.weights.age": (float, 0.10, 0.0, 1.0),
    "vuln.risk.weights.churn": (float, 0.05, 0.0, 1.0),
    "vuln.risk.weights.anomaly": (float, 0.10, 0.0, 1.0),
    "vuln.risk.exploit_bonus_max": (float, 0.10, 0.0, 1.0),
    # --- Threat Feeds (Batch 6) ---
    "threat.feeds.enabled": (bool, True, False, True),
    # Per-feed enables (example demo feed)
    "threat.feed.demo.enabled": (bool, True, False, True),
    # URL sample feed config
    "threat.feed.url_sample.enabled": (bool, False, False, True),
    "threat.feed.url_sample.url": (str, "http://127.0.0.1:8000/threat-feeds/sample.json", "", "~"),
    "threat.feed.url_sample.keys.value": (str, "value", "value", "~"),
    "threat.feed.url_sample.keys.type": (str, "type", "type", "~"),
    "threat.feed.url_sample.keys.tags": (str, "tags", "tags", "~"),
    "threat.feed.url_sample.ttl_s": (float, 120.0, 5.0, 3600.0),
    # SLA days per severity band
    "vuln.sla.days.critical": (int, 7, 1, 365),
    "vuln.sla.days.high": (int, 14, 1, 365),
    "vuln.sla.days.medium": (int, 30, 1, 365),
    "vuln.sla.days.low": (int, 60, 1, 365),
    # --- Vulnerability Enrichment & Correlation (Batch 7+8 additions) ---
    # Enable EPSS/KEV enrichment application in risk scoring path (allows test isolation when disabled)
    "vuln.enrichment.apply": (bool, True, False, True),
    # Weight applied to EPSS factor (scales epss probability directly) when enrichment enabled
    "vuln.risk.weights.epss": (float, 0.15, 0.0, 2.0),
    # Weight applied when KEV listed (additive constant)
    "vuln.risk.weights.kev": (float, 0.10, 0.0, 2.0),
    # Threshold for EPSS probability to contribute
    "vuln.risk.epss_threshold": (float, 0.5, 0.0, 1.0),
    # Half-life (days) for temporal decay of vulnerability aging
    "vuln.risk.aging_half_life_days": (float, 365.0, 1.0, 5000.0),
    # Correlation weight multiplier for anomaly-linked components
    "vuln.risk.weights.anomaly_correlation": (float, 0.12, 0.0, 2.0),
    # SLA countdown gauge enable (allows disabling if high cardinality)
    "vuln.sla.countdown.enable": (bool, True, False, True),
    # --- Reporting & Governance Enhancements (post Batch 17) ---
    # Enable periodic unified report bundle generation
    "report.bundle.enable": (bool, False, False, True),
    # Interval seconds between report bundle builds
    "report.bundle.interval_seconds": (int, 1800, 60, 86_400),
    # Enable adaptive weight governance loop (applies regulator proposals)
    "governance.weight.enable": (bool, False, False, True),
    # Interval seconds between weight governance evaluation cycles
    "governance.weight.interval_s": (int, 120, 10, 10_000),
    # --- Governance Composite Adaptive Controls (Batch 21) ---
    # Shadow mode for governance-driven adjustments (log only, no mutation)
    "governance.shadow_mode": (bool, True, False, True),
    # Maximum allowed adjustments per hour applied by weight governor (policy guard)
    "governance.weight.max_adjust_per_hour": (int, 20, 1, 10_000),
    # Composite signal upper threshold above which temporal weight is decreased (0..1)
    "governance.composite.high_threshold": (float, 0.75, 0.0, 1.0),
    # Composite signal lower threshold below which temporal weight can be increased (0..1)
    "governance.composite.low_threshold": (float, 0.35, 0.0, 1.0),
    # Maximum proportional step (fraction of current weight) for governance composite adjustments
    "governance.composite.max_step_frac": (float, 0.15, 0.01, 1.0),
    # Absolute maximum delta applied per governance composite adjustment
    "governance.composite.max_abs_delta": (float, 0.15, 0.001, 5.0),
    # Cooldown seconds between governance composite driven adjustments
    "governance.composite.cooldown_s": (float, 90.0, 5.0, 10_000.0),
    # Minimum temporal weight bound enforced for governance composite adjustments (safety lower)
    "governance.composite.min_weight": (float, 0.0, 0.0, 5.0),
    # Maximum temporal weight bound enforced for governance composite adjustments (safety upper)
    "governance.composite.max_weight": (float, 1.5, 0.0, 10.0),
    # Hysteresis margin added around thresholds to reduce oscillation (applied proportionally)
    "governance.composite.hysteresis": (float, 0.03, 0.0, 0.5),
    # --- Governance Policy Evaluation (Automation Refinements) ---
    # Enable periodic policy compliance evaluation loop
    "governance.policy.eval.enabled": (bool, True, False, True),
    # Interval seconds between automatic policy evaluations
    "governance.policy.eval.interval_s": (int, 600, 30, 86_400),
    # Sign snapshots (HMAC) when writing chain
    "governance.policy.eval.sign": (bool, True, False, True),
    # Per-signal weights for composite computation (will be normalized to sum<=1)
    # suppression: weight for sustained suppression rate average
    "governance.composite.weights.suppression": (float, 0.50, 0.0, 1.0),
    # novelty: weight for SNN unique ratio average
    "governance.composite.weights.novelty": (float, 0.30, 0.0, 1.0),
    # overlap: weight applied to (1 - overlap_avg) term
    "governance.composite.weights.overlap": (float, 0.20, 0.0, 1.0),
    # --- Batch 7 Temporal Calibration & Stability Additions ---
    # Maximum residual samples retained per tenant for temporal calibration cache
    "temporal.calibration.max_samples": (int, 500, 50, 50_000),
    # Minimum samples required before temporal residual normalization applied
    "temporal.calibration.min_samples": (int, 50, 10, 100_000),
    # Hysteresis margin (additional) around temporal tuner tolerance (fraction of target)
    "fusion.temporal.tuner.hysteresis": (float, 0.05, 0.0, 0.5),
    # Minimum aggregate baseline anomalies before tuner can adjust (stability guard)
    "fusion.temporal.tuner.min_anomalies": (int, 10, 1, 100_000),
    # Latency guard p99 threshold seconds for temporal path (adaptive degrade)
    "temporal.guard.latency_p99_s": (float, 0.15, 0.01, 10.0),
    # Cooldown seconds after temporal latency guard triggers before re-enable
    "temporal.guard.cooldown_s": (float, 60.0, 5.0, 10_000.0),
    # Enable temporal pause on guard vs just weight reduction
    "temporal.guard.pause_on_trigger": (bool, True, False, True),
    # SNN normalization enable flag (percentile / mapping layer)
    "snn.norm.enable": (bool, False, False, True),
    # SNN normalization rolling window size for percentile mapping
    "snn.norm.window": (int, 400, 50, 100_000),
    # Minimum samples before applying SNN normalization mapping
    "snn.norm.min_samples": (int, 80, 10, 100_000),
    # Maximum age seconds since last SNN norm update before considered stale (for metrics/alerting)
    "snn.norm.max_stale_s": (float, 1800.0, 60.0, 172800.0),
    # --- Integrations (Exporters) ---
    "integration.splunk.enabled": (bool, False, False, True),
    # Splunk HEC URL (validation: any non-empty string accepted)
    "integration.splunk.hec_url": (str, "", "", "~"),
    # Splunk HEC Token (masked; stored as plain string here; secret management externalized later)
    "integration.splunk.token": (str, "", "", "~"),
    "integration.splunk.source": (str, "neuron", "neuron", "~"),
    "integration.splunk.sourcetype": (str, "neuron:event", "neuron:event", "~"),
    "integration.splunk.index": (str, "", "", "~"),
    # --- Phase 2 Forensics / Memory Trigger (Selective Acquisition) ---
    # Confidence threshold below which an anomaly is considered low-confidence and may trigger memory acquisition (0..1)
    "memory.trigger.confidence_threshold": (float, 0.7, 0.0, 1.0),
    # Risk score threshold (0..100 scaled) above which asset risk is deemed high enough to justify acquisition
    "memory.trigger.risk_threshold": (float, 60.0, 0.0, 100.0),
    # Maximum concurrent active memory acquisition jobs (soft gate). 0 disables triggering.
    "memory.jobs.active": (int, 2, 0, 10_000),
    # --- Diagnostics / Introspection Gating (new) ---
    # If true, /diagnostics/config requires header x-diagnostics-key matching diagnostics.auth.key
    "diagnostics.auth.required": (bool, False, False, True),
    # Shared secret key value required when diagnostics.auth.required=true (empty string means unset)
    "diagnostics.auth.key": (str, "", "", "~"),
    # --- Phase 5 Response / Automation Parameters ---
    # Master enable flag for recommendation endpoint (soft disable without removing code paths)
    "response.recommend.enable": (bool, True, False, True),
    # Master enable for automated escalation loop
    "response.auto.escalate.enabled": (bool, False, False, True),
    # Minimum case last_confidence required to consider escalation
    "response.auto.escalate.min_confidence": (float, 0.65, 0.0, 1.0),
    # Require promotion state? (if true, only promoted cases eligible)
    "response.auto.escalate.require_promoted": (bool, True, False, True),
    # Minimum age seconds beyond SLA overdue to escalate (0 = escalate immediately when overdue)
    "response.auto.escalate.min_overdue_s": (int, 300, 0, 604800),
    # Governance composite lower bound required (block if composite < this)
    "response.auto.escalate.gov_low": (float, 0.25, 0.0, 1.0),
    # Governance composite upper bound clamp: if composite > this, treat as unstable & block destructive actions
    "response.auto.escalate.gov_high": (float, 0.9, 0.0, 1.0),
    # Max escalations per hour (rate limit)
    "response.auto.escalate.max_per_hour": (int, 10, 0, 10_000),
    # Playbook dry-run only (true keeps preview mode; future false executes actions)
    "response.playbook.dry_run_only": (bool, True, False, True),
    # Default action set weighting factors for recommendation scoring (confidence, overdue_age_factor, promotion)
    "response.weight.confidence": (float, 0.5, 0.0, 5.0),
    "response.weight.overdue_age": (float, 0.3, 0.0, 5.0),
    "response.weight.promotion": (float, 0.2, 0.0, 5.0),
    # Memory artifact acquisition gating: minimum memory_artifacts before skipping acquisition recommendation
    "response.memory.min_artifacts_for_skip": (int, 2, 0, 1000),
    # Quarantine recommendation minimum confidence threshold
    "response.quarantine.min_confidence": (float, 0.8, 0.0, 1.0),
    # Ticket escalation minimum confidence threshold
    "response.ticket.min_confidence": (float, 0.6, 0.0, 1.0),
    # --- Phase 5 Execution Enhancements (new) ---
    # Enable manual execution endpoint /response/execute/{case_id}
    "response.execution.enable": (bool, False, False, True),
    # Cooldown seconds between identical action executions per case (0 disables)
    "response.action.cooldown_s": (int, 60, 0, 86_400),
    # Maximum executions per case/action per hour (0 blocks all execution attempts)
    "response.action.max_per_case_per_hour": (int, 5, 0, 10_000),
    # --- Phase 6 Executive Dashboard ---
    # Cache TTL seconds for /executive/dashboard snapshot (min 1s)
    "executive.dashboard.cache_ttl_s": (int, 15, 1, 3600),
    # --- Phase 1 Optional Enhancements (IOC / Hunt / Ingest) ---
    # IOC retention time-to-live seconds (0 disables expiry)
    "ioc.ttl.seconds": (int, 0, 0, 31_536_000),
    # Maximum retained IOC records (prune oldest beyond)
    "ioc.max_retained": (int, 10000, 100, 1_000_000),
    # IOC hit de-duplication suppression window seconds (0 disables)
    "ioc.hit.dedupe_window_s": (int, 0, 0, 86400),
    # Hunt query cache size (0 disables cache)
    "hunt.query.cache.size": (int, 0, 0, 10_000),
    # Hunt query cache TTL seconds (ignored if size=0)
    "hunt.query.cache.ttl_s": (int, 120, 1, 86_400),
    # Enable normalization validation endpoint (/ingest/validate)
    "ingest.validation.enable": (bool, True, False, True),
    # Per-tenant ingest rate limit (events per minute); 0 disables
    "ingest.rate.per_tenant_per_min": (int, 0, 0, 1_000_000),
    # Hunt high-activity multiplier for tenant buffer share
    "hunt.buffer.tier.high_activity_multiplier": (float, 2.0, 1.0, 20.0),
    # Activity evaluation window seconds for tiering
    "hunt.buffer.activity.window_s": (int, 600, 30, 86_400),
    # --- Phase 5 Execution Enhancements ---
    # Enable actual response action execution endpoint (beyond preview / automation dry run)
    "response.execution.enable": (bool, False, False, True),
    # Cooldown seconds between identical action executions per case (0 disables cooldown)
    "response.action.cooldown_s": (int, 120, 0, 86_400),
    # Maximum executions per case per hour (0 disables further executions)
    "response.action.max_per_case_per_hour": (int, 20, 0, 10_000),
    # Executive dashboard cache TTL seconds (applies to /executive/dashboard)
    "executive.dashboard.cache_ttl_s": (int, 15, 1, 300),
    # --- Forensics: Volatility3 Integration (optional) ---
    # Master enable flag for running volatility3 against memory dumps
    "forensics.volatility.enabled": (bool, False, False, True),
    # Comma-separated plugin list or JSON array (windows.pslist, windows.netscan, windows.dlllist, handles)
    "forensics.volatility.plugins": (str, "windows.pslist,windows.netscan", "windows.pslist,windows.netscan", "~"),
    # Max total runtime seconds budget per job (split across plugins)
    "forensics.volatility.max_runtime_s": (int, 60, 5, 1800),
    # --- Forensics: YARA scanning (optional) ---
    # Master enable flag for YARA scanning
    "forensics.yara.enabled": (bool, False, False, True),
    # Directory containing .yar/.yara rules (recursively scanned)
    "forensics.yara.rules_dir": (str, "", "", "~"),
    # Max total runtime seconds budget for YARA scanning
    "forensics.yara.max_runtime_s": (int, 20, 1, 600),
    # --- Batch 1B / Batch 2 Persistence & Cache Controls ---
    # Maximum story content size in bytes (applied to /story create); hard cap 1MB via validator path
    "story.max_content_bytes": (int, 20000, 100, 1_000_000),
    # Story TTL seconds (0 disables expiry)
    "story.ttl_seconds": (int, 43200, 0, 7 * 24 * 3600),  # default 12h, upper bound 7 days
    # Maximum report content size in bytes (applies to commit & diff apply)
    "report.max_content_bytes": (int, 200000, 1000, 2_000_000),
    # ELI5 cache maximum entries (0 disables caching)
    "eli5.cache.max_entries": (int, 100, 0, 10_000),
    # ELI5 cache TTL seconds per entry (0 disables TTL eviction)
    "eli5.cache.ttl_seconds": (int, 1800, 0, 86_400),
}

# --- Metrics Export Allowlist (Batch 3 Observability) ---
# Only these keys are exported via the RUNTIME_PARAM_VALUE gauge to avoid
# high-cardinality explosion. Extend cautiously.
_METRIC_EXPORT_PARAM_KEYS: set[str] = {
    "story.max_content_bytes",
    "story.ttl_seconds",
    "report.max_content_bytes",
    "eli5.cache.max_entries",
    "eli5.cache.ttl_seconds",
}

_PARAMS: dict[str, t.Any] = {}
_DEFAULTS_FILE = pathlib.Path("config/runtime_params.defaults.json")
_AUDIT_FILE = pathlib.Path("audit/param_changes.log")
_AUDIT_LOG_MD = pathlib.Path("audit/AUDIT_LOG.md")
_AUDIT_HEAD = pathlib.Path("audit/param_changes.head")

# Rotation settings
_AUDIT_MAX_BYTES = 64 * 1024  # 64KB threshold for rotation (tunable)

def _sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def _load_defaults() -> None:
    data = {}
    if _DEFAULTS_FILE.exists():
        try:
            data = json.loads(_DEFAULTS_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    for k, (typ, default, _min, _max) in _SCHEMA.items():
        raw = data.get(k, default)
        try:
            _PARAMS[k] = typ(raw)
        except Exception:
            _PARAMS[k] = default


def list_params() -> dict[str, t.Any]:
    with _LOCK:
        return dict(_PARAMS)


def get_param(key: str, default: t.Any = None) -> t.Any:
    """Return current value for param key.

    Backwards compatibility: original signature had only (key); tests may call
    get_param(key, default). If default provided and key missing, return that
    default instead of None. This does not perform validation.
    """
    with _LOCK:
        if default is not None:
            return _PARAMS.get(key, default)
        return _PARAMS.get(key)

def get_param_default(key: str, default: t.Any) -> t.Any:
    """Return param or provided default if missing (non-validating).

    Useful for integration modules where absence should not raise.
    """
    with _LOCK:
        return _PARAMS.get(key, default)


def _validate(key: str, value: t.Any) -> t.Any:
    if key not in _SCHEMA:
        raise ValueError(f"Unknown parameter {key}")
    typ, _default, lo, hi = _SCHEMA[key]
    try:
        if typ is bool:
            if isinstance(value, bool):
                casted = value
            elif isinstance(value, (int, float)):
                casted = bool(value)
            elif isinstance(value, str):
                casted = value.strip().lower() in {"1", "true", "yes", "on"}
            else:
                raise ValueError("Invalid bool value")
        else:
            casted = typ(value)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Invalid type for {key}: expected {typ.__name__}") from e
    # Range check only meaningful for numeric types
    if isinstance(casted, (int, float)) and not isinstance(casted, bool):
        if casted < lo or casted > hi:  # type: ignore[operator]
            raise ValueError(f"Value {casted} out of range [{lo}, {hi}] for {key}")
    # Enumeration guard for selected string params
    if isinstance(casted, str):
        if key == "snn.encoder" and casted not in {"rate_v1", "rate_v2"}:
            raise ValueError(f"Invalid value {casted} for {key}; allowed: rate_v1, rate_v2")
        if key == "detection.fusion.strategy" and casted not in {"pass_through", "baseline_priority", "consensus_only", "weighted_sum"}:
            raise ValueError(f"Invalid value {casted} for {key}; allowed: pass_through, baseline_priority, consensus_only, weighted_sum")
    return casted


def update_param(key: str, value: t.Any, reason: str, actor: str = "system") -> t.Any:
    new_val = _validate(key, value)
    with _LOCK:
        old = _PARAMS.get(key)
        _PARAMS[key] = new_val
    _audit_change(key, old, new_val, reason, actor)
    try:
        if metrics and hasattr(metrics, 'PARAM_CHANGES_TOTAL'):
            metrics.PARAM_CHANGES_TOTAL.labels(key=key, actor=actor).inc()  # type: ignore[attr-defined]
    except Exception:
        pass
    # Export selected runtime param values as gauges (best-effort)
    try:
        if key in _METRIC_EXPORT_PARAM_KEYS and metrics and hasattr(metrics, 'RUNTIME_PARAM_VALUE'):
            try:
                metrics.RUNTIME_PARAM_VALUE.labels(key=key).set(float(new_val))  # type: ignore[attr-defined]
            except Exception:
                pass
    except Exception:
        pass
    # Fusion architecture hash hook: when any fusion.weight.* param changes hash FUSION_ARCHITECTURE.md
    try:
        if key.startswith("fusion.weight."):
            from pathlib import Path as _P
            import hashlib as _h
            arch_path = _P("docs") / "FUSION_ARCHITECTURE.md"
            if arch_path.exists():
                blob = arch_path.read_bytes()
                digest = _h.sha256(blob).hexdigest()
                # Record synthetic audit entry linking weight change to architecture hash for traceability
                _audit_change("fusion.arch.hash", None, {"file": str(arch_path), "sha256": digest, "trigger_param": key}, reason="weight_change_hash", actor="system")
                # Best-effort: update chain manifest file if present by appending lightweight JSON line (non-breaking)
                try:
                    chain = _P("audit") / "FUSION_ARCH_HASH_CHAIN.jsonl"
                    chain.parent.mkdir(parents=True, exist_ok=True)
                    import json as _json, time as _t
                    chain_rec = {"ts": _t.time(), "param": key, "hash": digest}
                    with chain.open("a", encoding="utf-8") as cf:
                        cf.write(_json.dumps(chain_rec) + "\n")
                except Exception:
                    pass
    except Exception:
        pass
    # Suppression threshold watcher: update gauge for all tenants (or unknown) when threshold changes
    if key == "fusion.weighted_sum.suppress_threshold":  # lightweight, best-effort
        try:
            from core import metrics as _m  # type: ignore
            tenants: list[str] = []
            try:
                from core.main import pipeline as _pl  # type: ignore
                if _pl and getattr(_pl, 'tenants', None):  # type: ignore
                    tenants = list(_pl.tenants)  # type: ignore
            except Exception:
                tenants = []
            if not tenants:
                tenants = ["unknown"]
            for _t in tenants:
                try:
                    _m.FUSION_SUPPRESS_THRESHOLD.labels(tenant=_t).set(float(new_val))  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception:
            pass
    return new_val


def save_defaults() -> None:
    """Persist current parameter values to defaults file.

    This allows threshold sweeps or tuning sessions to checkpoint selected
    values so future restarts retain the audited configuration without
    manual file edits (which would bypass audit trail).
    """
    with _LOCK:
        data = dict(_PARAMS)
    _DEFAULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _DEFAULTS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(_DEFAULTS_FILE)


def _audit_change(key: str, old: t.Any, new: t.Any, reason: str, actor: str):
    _AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "ts": time.time(),
        "key": key,
        "old": old,
        "new": new,
        "reason": reason,
        "actor": actor,
    }
    # Hash chain: prev hash stored in head file (or zeros if none)
    prev_hash = "0" * 64
    if _AUDIT_HEAD.exists():
        try:
            prev_hash = _AUDIT_HEAD.read_text(encoding="utf-8").strip() or prev_hash
        except Exception:
            pass
    payload = json.dumps(rec, separators=(",", ":"))
    chained = {"prev": prev_hash, "rec": rec}
    line = json.dumps(chained)
    curr_hash = _sha256_str(line)
    # Write entry
    with _AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    # Update head
    try:
        _AUDIT_HEAD.write_text(curr_hash, encoding="utf-8")
    except Exception:
        pass
    # Rotation check
    try:
        if _AUDIT_FILE.stat().st_size > _AUDIT_MAX_BYTES:
            ts = int(time.time())
            rotated = _AUDIT_FILE.with_suffix(f".log.{ts}")
            _AUDIT_FILE.rename(rotated)
            _AUDIT_FILE.write_text("", encoding="utf-8")
    except Exception:
        pass
    # Markdown append
    try:
        ts_iso = datetime.datetime.utcfromtimestamp(rec["ts"]).isoformat() + "Z"
        line_md = f"- {ts_iso} PARAM_CHANGE key={key} old={old} new={new} reason={reason} actor={actor}\n"
        with _AUDIT_LOG_MD.open("a", encoding="utf-8") as md:
            md.write(line_md)
    except Exception:
        pass


def audit_agent_decision(agent: str, action: str, detail: dict[str, t.Any]):
    synthetic_key = f"agent.{agent}.decision"
    _audit_change(synthetic_key, None, {"action": action, "detail": detail}, reason="agent_decision", actor=agent)


_load_defaults()

# Seed exported param gauges once at import (best-effort).
try:  # pragma: no cover
    if metrics and hasattr(metrics, 'RUNTIME_PARAM_VALUE'):
        for _k in _METRIC_EXPORT_PARAM_KEYS:
            if _k in _PARAMS:
                try:
                    metrics.RUNTIME_PARAM_VALUE.labels(key=_k).set(float(_PARAMS[_k]))  # type: ignore[attr-defined]
                except Exception:
                    pass
except Exception:
    pass

__all__ = [
    "list_params",
    "get_param",
    "update_param",
    "save_defaults",
    # Backwards compatibility accessor for legacy import style
    # Provided dynamically below if not already defined.
]

# Backwards-compatible callable accessor expected by some legacy modules/tests
def runtime_params() -> dict[str, t.Any]:  # pragma: no cover - thin wrapper
    """Return a shallow copy snapshot of current runtime params.

    Historically some code imported `runtime_params` symbol directly:
        from config.runtime_params import runtime_params
    This accessor preserves that pattern while internal usage prefers
    `get_param` / `list_params` for specific access patterns.
    """
    return list_params()

__all__.append("runtime_params")
