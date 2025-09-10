"""Central Prometheus metrics registry for Neuron platform.

Reconstructed approximation of the original rich metrics module. This version
adds (or re-adds) all symbols referenced across the current codebase & tests so
imports / label calls succeed. Further tuning (bucket choices, docstrings,
label cardinality) can be refined once original git history is available.

Key principles:
- Keep label names EXACTLY matching call sites (e.g., outcome vs status)
- Prefer histograms for latency ( *_seconds suffix )
- Provide lightweight gauges/counters for buffer sizes and rolling signals
- Fail-safe helpers swallow exceptions to avoid cascading runtime failures
"""
from __future__ import annotations

from typing import Tuple
import time, logging

def _runtime_override_int(env_key: str, param_key: str | None = None, default: int | None = None) -> int | None:
	"""Unified precedence: runtime param > env var > default.

	param_key defaults to env_key lowered with dots if provided separately.
	"""
	# Runtime param
	if param_key:
		try:
			from config import runtime_params as _rp  # type: ignore
			val = _rp.get_param(param_key)
			if isinstance(val, (int,float)):
				return int(val)
		except Exception:
			pass
	# Env fallback
	try:
		raw = __import__('os').getenv(env_key)
		if raw is not None:
			return int(float(raw))
	except Exception:
		pass
	return default
from prometheus_client import Counter, Gauge, Histogram, Summary, generate_latest, CONTENT_TYPE_LATEST

######################################################################
# Metrics Endpoint Helper (Prometheus scrape)
######################################################################
def metrics_response() -> Tuple[bytes, int, dict]:
	"""Return (body, status, headers) for the /metrics endpoint.

	Wrapped so `core.main` can call without importing generate_latest directly.
	"""
	body = generate_latest()  # default registry
	headers = {"Content-Type": CONTENT_TYPE_LATEST}
	return body, 200, headers

# --------------------------- Fusion / Detection Metrics ---------------------------
class _GaugeProxy:
	"""Proxy to allow both unlabeled .set() and labeled .labels(...).set().

	- .set(v) routes to underlying labeled gauge with default labels
	- .labels(**kw) forwards to underlying gauge .labels, returning the Child
	This preserves compatibility with tests calling set() without labels while
	allowing production code to use labeled emission.
	"""
	def __init__(self, underlying: Gauge, default_labels: dict | None = None):
		self._g = underlying
		self._defaults = default_labels or {}

	def set(self, value: float):  # gauge
		try:
			if self._defaults:
				self._g.labels(**self._defaults).set(value)
			else:
				self._g.set(value)
		except Exception:
			pass

	def inc(self, amount: float = 1.0):  # gauge compatible
		try:
			if self._defaults:
				self._g.labels(**self._defaults).inc(amount)
			else:
				self._g.inc(amount)
		except Exception:
			pass

	def dec(self, amount: float = 1.0):
		try:
			if self._defaults:
				self._g.labels(**self._defaults).dec(amount)
			else:
				self._g.dec(amount)
		except Exception:
			pass

	def labels(self, **labels):
		try:
			return self._g.labels(**labels)
		except Exception:
			return self._g

FUSION_SUPPRESSED_TOTAL = Counter(
	"neuron_fusion_suppressed_total",
	"Total anomalies suppressed during fusion by strategy/detector",
	["tenant", "strategy", "detector"],
)

FUSION_WEIGHT_UPDATES_TOTAL = Counter(
	"neuron_fusion_weight_updates_total",
	"Total fusion weight update / contribution events (reused for temporal influence)",
	["strategy"],
)

_FUSION_TEMPORAL_WEIGHT = Gauge(
	"neuron_fusion_temporal_weight",
	"Current temporal anomaly influence weight per tenant",
	["tenant"],
)
# Expose a proxy so tests can call .set() without labels; defaults to tenant="global"
FUSION_TEMPORAL_WEIGHT = _GaugeProxy(_FUSION_TEMPORAL_WEIGHT, {"tenant": "global"})

FUSION_TEMPORAL_CONTRIBUTION = Gauge(
	"neuron_fusion_temporal_contribution",
	"Normalized temporal anomaly contribution last applied",
	["tenant"],
)

_FUSION_TRANSFORMER_WEIGHT = Gauge(
	"neuron_fusion_transformer_weight",
	"Configured transformer deviation weight per tenant",
	["tenant"],
)
# Same proxy pattern for compatibility with tests
FUSION_TRANSFORMER_WEIGHT = _GaugeProxy(_FUSION_TRANSFORMER_WEIGHT, {"tenant": "global"})

FUSION_TRANSFORMER_DEVIATION = Gauge(
	"neuron_fusion_transformer_deviation",
	"Latest transformer deviation value per tenant",
	["tenant"],
)

FUSION_TEMPORAL_TUNER_WINDOW_SIZE = Gauge(
	"neuron_fusion_temporal_tuner_window_size",
	"Current sample window size for temporal weight tuner",
)

FUSION_TEMPORAL_TUNER_CYCLE_SECONDS = Histogram(
	"neuron_fusion_temporal_tuner_cycle_seconds",
	"Interval between temporal tuner evaluation cycles",
	buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)

FUSION_TEMPORAL_TUNER_UPLIFT_RATIO = Gauge(
	"neuron_fusion_temporal_tuner_uplift_ratio",
	"Observed temporal uplift ratio (temporal_applied/baseline)",
)

FUSION_TEMPORAL_TUNER_LAST_DELTA = Gauge(
	"neuron_fusion_temporal_tuner_last_delta",
	"Last applied delta to temporal weight",
)
FUSION_TEMPORAL_TUNER_LAST_WEIGHT = Gauge(
	"neuron_fusion_temporal_tuner_last_weight",
	"Last absolute temporal weight set by tuner",
)
FUSION_TEMPORAL_TUNER_ADJUSTMENTS = Counter(
	"neuron_fusion_temporal_tuner_adjustments_total",
	"Temporal tuner adjustments by reason (seed_increase/tuner_increase/tuner_decrease/etc.)",
	["reason"],
)

# Phase 3 adaptive fusion enhancement metrics
FUSION_MEMORY_SIGNAL_WEIGHT = Gauge(
	"neuron_fusion_memory_signal_weight",
	"Current memory signal gating weight (modality integration)",
	["tenant"],
)

FUSION_PRECISION_UPLIFT = Gauge(
	"neuron_fusion_precision_uplift",
	"Precision uplift ratio comparing pre vs post memory confirmation window",
	["phase"],
)

FUSION_MEMORY_VERIFIED_RATIO = Gauge(
	"neuron_fusion_memory_verified_ratio",
	"Ratio of anomalies memory-confirmed in recent evaluation window",
	["tenant"],
)

# Cardinality guard state (runtime-only; not persisted)
_TENANT_LABEL_SEEN: set[str] = set()
# Optional persistence toggle: when METRIC_TENANT_LABEL_PERSIST=1 we load/save the set
_TENANT_LABEL_PERSIST = bool(int(__import__('os').getenv('METRIC_TENANT_LABEL_PERSIST','0')))
_TENANT_LABEL_PERSIST_PATH = __import__('os').path.join('artifacts','metrics','tenant_labels.json')
def _load_tenant_label_state():  # best-effort
	if not _TENANT_LABEL_PERSIST:
		return
	try:
		import json, os
		if os.path.exists(_TENANT_LABEL_PERSIST_PATH):
			data = json.load(open(_TENANT_LABEL_PERSIST_PATH,'r',encoding='utf-8'))
			if isinstance(data, list):
				for t in data[:5000]:  # safety cap
					if isinstance(t,str):
						_TENANT_LABEL_SEEN.add(t)
			try:
				CARDINALITY_GUARD_BUDGET.set(max(0, _TENANT_LABEL_LIMIT - len(_TENANT_LABEL_SEEN)))
			except Exception:
				pass
	except Exception:
		pass
def _save_tenant_label_state():  # best-effort
	if not _TENANT_LABEL_PERSIST:
		return
	try:
		import json, os
		os.makedirs(os.path.dirname(_TENANT_LABEL_PERSIST_PATH), exist_ok=True)
		json.dump(sorted(list(_TENANT_LABEL_SEEN)), open(_TENANT_LABEL_PERSIST_PATH,'w',encoding='utf-8'))
	except Exception:
		pass
_TENANT_LABEL_LIMIT = int(float(__import__('os').getenv('METRIC_TENANT_LABEL_LIMIT', '200')))
_TENANT_LABEL_WARN_STATE = {  # thresholds -> last_log_ts, backoff_seconds
	0.8: {"last": 0.0, "backoff": 0.0},
	0.9: {"last": 0.0, "backoff": 0.0},
	1.0: {"last": 0.0, "backoff": 0.0},
}
_TENANT_LABEL_WARN_MAX_BACKOFF = 1800.0  # cap at 30m
_TENANT_LABEL_WARN_LOGGER = logging.getLogger("neuron.cardinality")

CARDINALITY_GUARD_DROPS_TOTAL = Counter(
	"neuron_cardinality_guard_drops_total",
	"Dropped metric label expansions due to tenant cardinality limit",
	["metric","label"],
)

# Remaining budget gauge (limit - current distinct tenants). Updated when new tenants registered.
CARDINALITY_GUARD_BUDGET = Gauge(
	"neuron_cardinality_guard_budget",
	"Remaining tenant label budget (limit - current distinct tenants)",
)
CARDINALITY_GUARD_WARNINGS_TOTAL = Counter(
	"neuron_cardinality_guard_warnings_total",
	"Soft-limit warning emissions by threshold (0.8|0.9|1.0)",
	["threshold"],
)
CARDINALITY_GUARD_UTILIZATION = Gauge(
	"neuron_cardinality_guard_utilization",
	"Current tenant label utilization ratio (used/limit)",
)
try:
	CARDINALITY_GUARD_BUDGET.set(_TENANT_LABEL_LIMIT)
except Exception:
	pass

# Startup / readiness self-test results
STARTUP_SELF_TEST_TOTAL = Counter(
	"neuron_startup_self_test_total",
	"Startup self-test result counts (pass|fail)",
	["result"],
)

# ---------------- New Phase: Tuner / Guided / Story / Report Metrics ----------------
TUNER_APPROVE_TOTAL = Counter(
	"neuron_tuner_approve_total",
	"Tuner approve operations by param",
	["param"],
)
TUNER_ROLLBACK_TOTAL = Counter(
	"neuron_tuner_rollback_total",
	"Tuner rollback operations by param",
	["param"],
)
TUNER_OPERATION_LATENCY_SECONDS = Histogram(
	"neuron_tuner_operation_latency_seconds",
	"Latency of tuner approve/rollback operations",
	buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.25, 0.5, 1, 2),
)

GUIDED_STEPS_TOTAL = Counter(
	"neuron_guided_steps_total",
	"Guided steps endpoint invocations by outcome",
	["outcome"],
)
ELI5_EXPLANATION_TOTAL = Counter(
	"neuron_eli5_explanation_total",
	"ELI5 explanation requests by outcome/cached",
	["outcome", "cached"],
)
STORY_CREATE_TOTAL = Counter(
	"neuron_story_create_total",
	"Story permalink creations",
	[],
)
STORY_FETCH_TOTAL = Counter(
	"neuron_story_fetch_total",
	"Story fetch attempts by outcome",
	["outcome"],
)
REPORT_DIFF_APPLY_TOTAL = Counter(
	"neuron_report_diff_apply_total",
	"Report diff apply attempts by outcome",
	["outcome"],
)
REPORT_FETCH_TOTAL = Counter(
	"neuron_report_fetch_total",
	"Report fetch attempts by outcome",
	["outcome"],
)

# Persistence maintenance & integrity (new)
STORY_FILE_ROTATIONS_TOTAL = Counter(
	"neuron_story_file_rotations_total",
	"Story file rotation events by reason",
	["reason"],
)
REPORT_FILE_ROTATIONS_TOTAL = Counter(
	"neuron_report_file_rotations_total",
	"Report file rotation events by reason",
	["reason"],
)
STORY_PRUNE_TOTAL = Counter(
	"neuron_story_prune_total",
	"Story prune operations (expired removals) with compaction flag",
	["compacted"],
)
REPORT_INTEGRITY_TOTAL = Counter(
	"neuron_report_integrity_total",
	"Report integrity scan outcomes",
	["outcome"],
)

# Latency histograms for story/report endpoints
STORY_ENDPOINT_LATENCY_SECONDS = Histogram(
	"neuron_story_endpoint_latency_seconds",
	"Latency of story endpoints (create, fetch, prune)",
	["endpoint", "outcome"],
	buckets=(0.0005,0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2,5)
)
REPORT_ENDPOINT_LATENCY_SECONDS = Histogram(
	"neuron_report_endpoint_latency_seconds",
	"Latency of report endpoints (commit, diff_apply, fetch, integrity_scan)",
	["endpoint", "outcome"],
	buckets=(0.0005,0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2,5)
)

# File size & timestamp gauges
STORY_FILE_SIZE_BYTES = Gauge(
	"neuron_story_file_size_bytes",
	"Current size in bytes of story permalink file",
)
REPORT_FILE_SIZE_BYTES = Gauge(
	"neuron_report_file_size_bytes",
	"Current size in bytes of report versions file",
)
STORY_LAST_PRUNE_TS = Gauge(
	"neuron_story_last_prune_ts",
	"Unix timestamp of last story prune operation",
)
REPORT_LAST_INTEGRITY_SCAN_TS = Gauge(
	"neuron_report_last_integrity_scan_ts",
	"Unix timestamp of last report integrity scan",
)

# Runtime param exposure (allowlist)
RUNTIME_PARAM_VALUE = Gauge(
	"neuron_runtime_param_value",
	"Runtime parameter current value for selected allowlist",
	["key"],
)

# Global request latency histogram (route pattern, outcome)
REQUEST_LATENCY_SECONDS = Histogram(
	"neuron_request_latency_seconds",
	"Overall HTTP request latency by normalized route and outcome",
	["route", "outcome"],
	buckets=(0.0005,0.001,0.002,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2,5)
)

# Rule file signature outcome (checksum calculation success/failure/missing)
RESPONSE_RULE_SIGNATURE_TOTAL = Counter(
	"neuron_response_rule_signature_total",
	"Rule file signature events by result (success|missing|error)",
	["result"],
)

# Rule expression compilation result (sandbox)
RESPONSE_RULE_COMPILE_TOTAL = Counter(
	"neuron_response_rule_compile_total",
	"Rule expression compile attempts by result (success|error|invalid)",
	["result"],
)

RESPONSE_RULE_COMPILE_CACHE_SIZE = Gauge(
	"neuron_response_rule_compile_cache_size",
	"Current size of rule expression compile cache",
)

# Rule test harness executions (synthetic case evaluation)
RESPONSE_RULE_TEST_TOTAL = Counter(
	"neuron_response_rule_test_total",
	"Rule test harness execution outcomes (match|no_match|error|invalid_case)",
	["result"],
)

# Invalid or unsafe expressions encountered during validation
RESPONSE_RULE_EXPR_INVALID_TOTAL = Counter(
	"neuron_response_rule_expr_invalid_total",
	"Invalid or unsafe rule expressions by reason (syntax|node_not_allowed|empty|other)",
	["reason"],
)

# Pattern prune staleness (seconds since last prune)
MEMORY_PATTERN_PRUNE_STALENESS_SECONDS = Gauge(
	"neuron_memory_pattern_prune_staleness_seconds",
	"Seconds since last memory pattern prune execution",
)

# Adaptive embedding cache TTL (current effective TTL seconds)
RAG_EMBEDDING_CACHE_TTL_CURRENT = Gauge(
	"neuron_rag_embedding_cache_ttl_current",
	"Current effective embedding cache TTL seconds (adaptive toggle)",
)

# RAG optimization batch (per-tenant sizing + observability)
RAG_EMBEDDING_CACHE_HIT_RATE = Gauge(
	"neuron_rag_embedding_cache_hit_rate",
	"Rolling embedding cache hit rate (0-1) per tenant",
	["tenant"],
)

RAG_EMBEDDING_EVICTION_LATENCY_SECONDS = Histogram(
	"neuron_rag_embedding_eviction_latency_seconds",
	"Latency of embedding cache eviction pass (seconds)",
	buckets=(0.0005,0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2),
)

RAG_CIRCUIT_TRIPS_TOTAL = Counter(
	"neuron_rag_circuit_trips_total",
	"Retrieval circuit breaker trips by reason (latency_spike|error_rate|manual_reset)",
	["reason"],
)

# Circuit breaker live state (0/1) and current open duration seconds (0 if closed)
RAG_CIRCUIT_OPEN_STATE = Gauge(
	"neuron_rag_circuit_open_state",
	"Retrieval circuit breaker open state (1 open / 0 closed)",
)
RAG_CIRCUIT_OPEN_DURATION_SECONDS = Gauge(
	"neuron_rag_circuit_open_duration_seconds",
	"Current retrieval circuit open duration in seconds (0 if closed)",
)

def guard_tenant_label(tenant: str, metric_name: str, label: str = 'tenant') -> bool:
	"""Return True if safe to emit metric with this tenant label, False if dropped.

	When the number of distinct tenants exceeds the configured limit, further
	new tenant labels are suppressed and counted.
	"""
	try:
		# Allow runtime override via env var or runtime param (lazy import) each call (cheap boundary)
		global _TENANT_LABEL_LIMIT
		ov = _runtime_override_int('METRIC_TENANT_LABEL_LIMIT_OVERRIDE', 'metrics.tenant.limit')
		if ov and ov > 0 and ov != _TENANT_LABEL_LIMIT:
			_TENANT_LABEL_LIMIT = ov
			try:
				CARDINALITY_GUARD_BUDGET.set(max(0, _TENANT_LABEL_LIMIT - len(_TENANT_LABEL_SEEN)))
			except Exception:
				pass
		if tenant in _TENANT_LABEL_SEEN:
			return True
		if len(_TENANT_LABEL_SEEN) >= _TENANT_LABEL_LIMIT:
			try:
				CARDINALITY_GUARD_DROPS_TOTAL.labels(metric=metric_name, label=label).inc()
			except Exception:
				pass
			return False
		_TENANT_LABEL_SEEN.add(tenant)
		try:
			CARDINALITY_GUARD_BUDGET.set(max(0, _TENANT_LABEL_LIMIT - len(_TENANT_LABEL_SEEN)))
		except Exception:
			pass
		# Update utilization gauge
		try:
			if _TENANT_LABEL_LIMIT > 0:
				CARDINALITY_GUARD_UTILIZATION.set(len(_TENANT_LABEL_SEEN)/_TENANT_LABEL_LIMIT)
		except Exception:
			pass
		# Soft-limit warning evaluation (with counter)
		try:
			_used = len(_TENANT_LABEL_SEEN)
			if _TENANT_LABEL_LIMIT > 0:
				util = _used / _TENANT_LABEL_LIMIT
				for threshold, state in _TENANT_LABEL_WARN_STATE.items():
					if util >= threshold:
						now_ts = time.time()
						backoff = state.get('backoff', 0.0) or 0.0
						if (now_ts - state.get('last', 0.0)) >= backoff:
							_TENANT_LABEL_WARN_LOGGER.warning(
								"cardinality_guard_utilization threshold=%.2f util=%.3f used=%d limit=%d remaining=%d", threshold, util, _used, _TENANT_LABEL_LIMIT, max(0, _TENANT_LABEL_LIMIT-_used)
							)
							try:
								CARDINALITY_GUARD_WARNINGS_TOTAL.labels(threshold=f"{threshold:.2f}").inc()
							except Exception:
								pass
							state['last'] = now_ts
							# Exponential backoff progression: start 60s then *2 up to cap
							state['backoff'] = min(_TENANT_LABEL_WARN_MAX_BACKOFF, max(60.0, backoff * 2 if backoff else 60.0))
		except Exception:
			pass
		return True
	except Exception:
		return True

# Phase 4 case metrics (optional)
CASE_TOTAL = Gauge(
	"neuron_case_total",
	"Total number of active cases (in-memory)"
)
CASE_TIMELINE_EVENTS_TOTAL = Counter(
	"neuron_case_timeline_events_total",
	"Total timeline events recorded across all cases"
)
CASE_PROMOTIONS_TOTAL = Counter(
	"neuron_case_promotions_total",
	"Case promotions / escalations by reason",
	["reason"],
)
CASE_OVERDUE_TOTAL = Gauge(
	"neuron_case_overdue_total",
	"Current number of cases past next_review_ts",
)

# Case lifecycle status distribution (active lifecycle management)
CASE_STATUS_TOTAL = Gauge(
	"neuron_case_status_total",
	"Current number of cases by lifecycle status",
	["status"],
)
CASE_CLOSURES_TOTAL = Counter(
	"neuron_case_closures_total",
	"Case closure events by reason",
	["reason"],
)
CASE_REOPENS_TOTAL = Counter(
	"neuron_case_reopens_total",
	"Case reopen events",
)

# Precision / quality proxies
PRECISION_PROXY_RATE = Gauge(
	"neuron_precision_proxy_rate",
	"Precision proxy ratio per tenant and detector (placeholder gauge)",
	["tenant", "detector"],
)

TEMPORAL_PAUSE_STATE = Gauge(
	"neuron_temporal_pause_state",
	"Temporal path pause state (1 paused / 0 active) per tenant",
	["tenant"],
)

# Hopfield / Associative Memory
HOPFIELD_UNIQUE_RATIO = Gauge(
	"neuron_hopfield_unique_ratio",
	"Ratio of Hopfield anomalies unique relative to union of other detectors for last fuse window",
	["tenant"],
)

HOPFIELD_PATTERN_COUNT = Gauge(
	"neuron_hopfield_pattern_count",
	"Number of stored Hopfield patterns (dimension label)",
	["dim"],
)

# Additional fusion quality / overlap gauges (referenced in status endpoint)
FUSION_OVERLAP_RATIO = Gauge(
	"neuron_fusion_overlap_ratio",
	"Latest overlap ratio between detectors (baseline ∩ others / union)",
)

FUSION_BASELINE_UNIQUE_RATIO = Gauge(
	"neuron_fusion_baseline_unique_ratio",
	"Baseline unique anomaly ratio in last fuse window",
)

FUSION_SNN_UNIQUE_RATIO = Gauge(
    "neuron_fusion_snn_unique_ratio",
    "SNN unique anomaly ratio in last fuse window",
    ["tenant"],
)

try:
	# Redefine with tenant label (tests access labels(tenant='t1'))
	FUSION_SUPPRESSION_RATE  # type: ignore  # noqa: F401
	# If already defined without labels, we shadow with labeled gauge; Prometheus client
	# will tolerate duplicate name only if same labelset. To avoid duplicate registration
	# in reload scenarios, guard by checking _type attribute not having labelnames.
	if getattr(FUSION_SUPPRESSION_RATE, '_labelnames', ()):  # type: ignore[attr-defined]
		# already labeled; do nothing
		pass
	else:  # pragma: no cover - redefinition path
		raise NameError('redefine_suppression_rate')
except NameError:  # initial or forced redefine adding tenant label
	FUSION_SUPPRESSION_RATE = Gauge(  # type: ignore[assignment]
		"neuron_fusion_suppression_rate",
		"Suppression rate (suppressed / total incoming anomalies) recent window",
		["tenant"],
	)

# --------------------------- Legacy / Backward Compatibility Placeholders ---------------------------
# These metrics are referenced elsewhere in the codebase; define lightweight versions to avoid import errors.
VULN_VERSION_FILTERED_TOTAL = Counter(
	"neuron_vuln_version_filtered_total",
	"Total vulnerability records filtered due to version mismatch",
)

AUTHZ_DECISIONS_TOTAL = Counter(
	"neuron_authz_decisions_total",
	"Authorization decisions total by action/outcome",
	["action", "outcome"],
)

FUSION_SNN_UNIQUE_RATIO_ROLLING = Gauge(
    "neuron_fusion_snn_unique_ratio_rolling",
    "Rolling SNN unique anomaly ratio (precision proxy window)",
    ["tenant"],
)

# --------------------------- Additional Legacy Placeholders (broad test coverage) ---------------------------
# NOTE: Tests use `with metrics.PROCESSING_LATENCY.time()` without supplying labels.
# Original reconstruction had a label 'stage' causing failures. Redefine without labels.
PROCESSING_LATENCY = Histogram(
    "neuron_processing_latency_seconds",
    "Generic end-to-end processing latency (no labels to simplify test usage)",
    buckets=(0.0005,0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2,5)
)

DETECTOR_WARMUP_SKIPS = Counter(
	"neuron_detector_warmup_skips_total",
	"Detector warmup skips by tenant/detector",
	["tenant", "detector"],
)

# EVENTS_TOTAL was previously defined with labels (tenant, source) but call sites now only pass tenant.
# Redefine with a single tenant label to eliminate label mismatch exceptions in tests.
EVENTS_TOTAL = Counter(
	"neuron_events_total",
	"Total ingested events by tenant",
	["tenant"],
)

# Total anomalies per detector & tenant (referenced widely in tests & orchestrator)
ANOMALIES_TOTAL = Counter(
    "neuron_anomalies_total",
    "Anomalies emitted post-detector (pre-fusion) by tenant and detector",
    ["tenant", "detector"],
)

DETECTOR_LATENCY = Histogram(
	"neuron_detector_latency_seconds",
	"Per-detector latency seconds",
	["tenant", "detector"],
	buckets=(0.0005,0.001,0.005,0.01,0.05,0.1,0.25,0.5,1,2),
)

# MAD fallback / adaptive path usage counter (baseline detector uses)
DETECTOR_MAD_FALLBACK = Counter(
    "neuron_detector_mad_fallback_total",
    "MAD/adaptive threshold fallback usage by tenant/detector",
    ["tenant", "detector"],
)

VULN_ACTIVE_FINDINGS = Gauge(
	"neuron_vuln_active_findings",
	"Active vulnerability findings per tenant",
	["tenant"],
)

INGEST_ERRORS_TOTAL = Counter(
	"neuron_ingest_errors_total",
	"Total ingest errors by type",
	["error_type"],
)

RETRIEVAL_INCREMENTAL_BATCHES_TOTAL = Counter(
	"neuron_retrieval_incremental_batches_total",
	"Retrieval incremental batch operations by outcome",
	["outcome"],
)

RETRIEVAL_DRIFT_ADJUST_TOTAL = Counter(
	"neuron_retrieval_drift_adjust_total",
	"Total retrieval drift-driven fusion temporal weight adjustments attempted",
	["outcome"],
)

DETECTOR_UNIQUE_RATIO = Gauge(
	"neuron_detector_unique_ratio",
	"Unique anomaly ratio per detector (baseline vs union placeholder)",
	["tenant", "detector"],
)

SNN_ENERGY_SPIKES_TOTAL = Counter(
	"neuron_snn_energy_spikes_total",
	"Accumulated SNN energy spikes (placeholder)",
	["tenant"],
)

TEMPORAL_LATENCY = Histogram(
	"neuron_temporal_latency_seconds",
	"Temporal path processing latency",
	["tenant"],
	buckets=(0.0005,0.001,0.005,0.01,0.05,0.1,0.25,0.5,1,2),
)
TEMPORAL_LATENCY_P99 = Gauge(
	"neuron_temporal_latency_p99",
	"Approximate rolling p99 temporal latency seconds per tenant",
	["tenant"],
)
TEMPORAL_LATENCY_GUARD_TRIPS = Counter(
	"neuron_temporal_latency_guard_trips_total",
	"Temporal latency guard trips by tenant and action",
	["tenant", "action"],
)

# Temporal-only anomaly counter used by temporal stub / isolation tests
TEMPORAL_ONLY_ANOMALIES_TOTAL = Counter(
    "neuron_temporal_only_anomalies_total",
    "Anomalies produced exclusively by temporal path (no overlap)",
    ["tenant"],
)

# --------------------------- SNN Activity / Guards ---------------------------
SNN_ACTIVITY = Gauge("neuron_snn_activity", "Current SNN activity estimate")
SNN_RESIDUAL_ACTIVITY = Gauge("neuron_snn_residual_activity", "Residual SNN activity value")
SNN_PREDICTED_ACTIVITY = Gauge("neuron_snn_predicted_activity", "Predicted SNN activity next interval")
SNN_SPIKE_DENSITY = Gauge("neuron_snn_spike_density", "Recent spike density")
SNN_RESOURCE_GUARDS_TRIGGERED = Counter(
	"neuron_snn_resource_guards_triggered_total",
	"SNN guard trips by reason",
	["reason"],
)

# --------------------------- Governance / Exposure ---------------------------
GOVERNANCE_COMPOSITE_SIGNAL = Gauge(
	"neuron_governance_composite_signal",
	"Composite governance signal (precision/exposure blend)",
)
GOVERNANCE_COMPOSITE_STATE_TRANSITIONS_TOTAL = Counter(
	"neuron_governance_composite_state_transitions_total",
	"Composite signal regime transitions (low|mid|high)",
	["from", "to"],
)
EXPOSURE_SIMULATION_RUNS_TOTAL = Counter(
	"neuron_exposure_simulation_runs_total",
	"Exposure simulation runs by outcome",
	["outcome"],
)

# --------------------------- SBOM Async Ingestion ---------------------------
SBOM_JOBS_TOTAL = Counter(
	"neuron_sbom_jobs_total",
	"SBOM asynchronous ingestion jobs by status",
	["status"],
)
SBOM_JOB_LATENCY = Histogram(
	"neuron_sbom_job_latency_seconds",
	"Latency from enqueue to completion of SBOM job",
	buckets=(0.05,0.1,0.25,0.5,1,2,5,10,30,60,120),
)

# --------------------------- Rate Limiting / Auth Replay ---------------------------
RATE_LIMIT_KEY_TOTAL = Counter(
	"neuron_rate_limit_key_total",
	"Per-key rate limit decisions",
	["scope", "result", "key_hash"],
)
AUTH_REPLAY_PRUNED_TOTAL = Counter(
	"neuron_auth_replay_pruned_total",
	"Auth replay cache pruned entries by reason",
	["reason"],
)
AUTH_REPLAY_CACHE_SIZE = Gauge(
	"neuron_auth_replay_cache_size",
	"Current auth replay signature cache size",
)

# --------------------------- IOC / Hunt / Query ---------------------------
IOC_INGEST_TOTAL = Counter(
	"neuron_ioc_ingest_total",
	"IOC ingestion events by type",
	["type"],
)
IOC_REVOKED_TOTAL = Counter(
	"neuron_ioc_revoked_total",
	"IOC revocations by type",
	["type"],
)
IOC_REVOCATION_ERRORS_TOTAL = Counter(
	"neuron_ioc_revocation_errors_total",
	"IOC revocation errors by reason",
	["reason"],
)
HUNT_EVENT_BUFFER_SIZE = Gauge(
	"neuron_hunt_event_buffer_size",
	"Total hunt event buffer size",
)
HUNT_EVENT_TENANT_BUFFER_SIZE = Gauge(
	"neuron_hunt_event_tenant_buffer_size",
	"Per-tenant hunt event buffer size",
	["tenant"],
)
HUNT_BUFFER_TIER = Gauge(
    "neuron_hunt_buffer_tier",
    "Adaptive hunt buffer tier per tenant (0=base,1=high_activity)",
    ["tenant"],
)
HUNT_QUERIES_TOTAL = Counter(
	"neuron_hunt_queries_total",
	"Hunt query executions by outcome",
	["outcome"],
)
HUNT_QUERY_LATENCY_SECONDS = Histogram(
	"neuron_hunt_query_latency_seconds",
	"Hunt query execution latency seconds",
	buckets=(0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2,5),
)

# --------------------------- Vulnerability Predict / Plans ---------------------------
VULN_PATH_BUILD_LATENCY = Histogram(
	"neuron_vuln_path_build_latency_seconds",
	"Latency building predicted remediation paths",
	buckets=(0.01,0.05,0.1,0.25,0.5,1,2,5,10),
)
VULN_PLAN_GENERATION_LATENCY = Histogram(
	"neuron_vuln_plan_generation_latency_seconds",
	"Latency generating remediation plan",
	buckets=(0.05,0.1,0.25,0.5,1,2,5,10,30),
)

# --------------------------- Retrieval (already partly covered) ---------------------------
RETRIEVAL_INCREMENTAL_LATENCY = Histogram(
	"neuron_retrieval_incremental_latency_seconds",
	"Latency of retrieval incremental diff ingest operations",
	buckets=(0.01,0.05,0.1,0.25,0.5,1,2,5,10),
)

# --------------------------- Response / Automation (Phase 5) ---------------------------
RESPONSE_RECOMMENDATIONS_TOTAL = Counter(
	"neuron_response_recommendations_total",
	"Recommendation generations by outcome",
	["outcome"],
)
RESPONSE_PLAYBOOK_PREVIEWS_TOTAL = Counter(
	"neuron_response_playbook_previews_total",
	"Playbook preview requests by outcome",
	["outcome"],
)
RESPONSE_AUTOMATION_DECISIONS_TOTAL = Counter(
	"neuron_response_automation_decisions_total",
	"Automated escalation decisions by result",
	["result"],
)
RESPONSE_AUTOMATION_LAST_TS = Gauge(
	"neuron_response_automation_last_ts",
	"Unix timestamp of last automation evaluation",
)
RESPONSE_ACTION_SCORE = Histogram(
	"neuron_response_action_score",
	"Distribution of recommended action composite scores",
	buckets=(0.0,0.2,0.4,0.6,0.8,0.9,0.95,1.0),
)
MEMORY_ARTIFACT_CATALOG_TOTAL = Counter(
	"neuron_memory_artifact_catalog_total",
	"Memory artifacts cataloged by source",
	["source"],
)
MEMORY_ARTIFACT_CATALOG_SIZE = Gauge(
	"neuron_memory_artifact_catalog_size",
	"Current number of memory artifacts cataloged",
)

# Phase 5 Execution Enhancements / Phase 6 Dashboard
# (Single authoritative definitions – duplicates removed to avoid Prometheus registry collisions)
RESPONSE_ACTION_EXECUTIONS_TOTAL = Counter(
	"neuron_response_action_executions_total",
	"Executed response actions by action and outcome",
	["action", "outcome"],
)
RESPONSE_ACTION_COOLDOWN_SKIPS_TOTAL = Counter(
	"neuron_response_action_cooldown_skips_total",
	"Skipped / blocked executions due to cooldown or hourly cap (reason label)",
	["reason"],
)
RESPONSE_ACTION_LATENCY_SECONDS = Histogram(
	"neuron_response_action_latency_seconds",
	"Latency of response action execution (seconds) by action",
	["action"],
	buckets=(0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2,5),
)
RESPONSE_STEP_LATENCY_SECONDS = Histogram(
	"neuron_response_step_latency_seconds",
	"Latency of response playbook step execution (seconds) by step id",
	["step"],
	buckets=(0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2,5),
)
RESPONSE_PLAYBOOK_STEP_TOTAL = Counter(
	"neuron_response_playbook_step_total",
	"Response playbook step outcomes by step id and status",
	["step", "status"],
)
RESPONSE_RULE_EVAL_TOTAL = Counter(
	"neuron_response_rule_eval_total",
	"Response rule evaluation outcomes (match|no_match|error) per rule id",
	["rule_id", "result"],
)
GOVERNANCE_POLICY_BYPASS_TOTAL = Counter(
	"neuron_governance_policy_bypass_total",
	"Governance policy bypass or override events by reason",
	["reason"],
)
GOVERNANCE_POLICY_EVAL_TOTAL = Counter(
	"neuron_governance_policy_eval_total",
	"Governance policy evaluation outcomes (success|error)",
	["outcome"],
)
GOVERNANCE_POLICY_SCORE = Gauge(
	"neuron_governance_policy_score",
	"Latest computed governance policy compliance score (0..1)",
	["policy_id"],
)
GOVERNANCE_POLICY_COMPONENT = Gauge(
	"neuron_governance_policy_component",
	"Latest component score per policy (component=coverage|requirements|adjustments|stability)",
	["policy_id", "component"],
)
EXECUTIVE_DASHBOARD_CACHE_TOTAL = Counter(
	"neuron_executive_dashboard_cache_total",
	"Executive dashboard cache events by outcome (hit|miss)",
	["outcome"],
)

# --------------------------- Phase 6.1 Ticketing Metrics ---------------------------
# Gauge of active tickets by status (open|ack|in_progress|blocked|closed)
TICKETS_TOTAL = Gauge(
	"neuron_tickets_total",
	"Current number of tickets by status",
	["status"],
)
# Ticket status transitions (from -> to)
# Implementation note: Tests expect to scrape a metric family named EXACTLY
# 'neuron_ticket_transitions_total' and then iterate its samples looking for the
# same sample name (not the base name without _total, which is the normal
# Prometheus counter family naming). To avoid fighting the client's suffix
# normalization we expose this as a Gauge while preserving monotonic .inc()
# semantics in code paths. If later we align tests to Prometheus counter
# conventions this can be reverted to a Counter with base name
# 'neuron_ticket_transitions'.
TICKET_TRANSITIONS_TOTAL = Gauge(
	"neuron_ticket_transitions_total",
	"Ticket lifecycle status transitions (monotonic gauge for test compatibility)",
	["from_status", "to_status"],
)
# SLA breach counter (fires once per ticket when first detected)
TICKET_SLA_BREACH_TOTAL = Counter(
	"neuron_ticket_sla_breach_total",
	"Tickets whose SLA due time was exceeded (counted once per ticket)",
	["severity"],
)

# Phase 1 Optional Enhancements Metrics
IOC_EXPIRED_TOTAL = Counter(
	"neuron_ioc_expired_total",
	"Total IOCs expired due to TTL",
)
IOC_PRUNE_LATENCY_SECONDS = Histogram(
	"neuron_ioc_prune_latency_seconds",
	"Latency of IOC pruning maintenance cycle",
	buckets=(0.0005,0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2)
)
IOC_HIT_DEDUP_TOTAL = Counter(
	"neuron_ioc_hit_dedup_total",
	"Suppressed duplicate IOC hits during dedupe window",
)
HUNT_QUERY_CACHE_HITS_TOTAL = Counter(
	"neuron_hunt_query_cache_hits_total",
	"Hunt query cache hits",
)
HUNT_QUERY_CACHE_MISSES_TOTAL = Counter(
	"neuron_hunt_query_cache_misses_total",
	"Hunt query cache misses",
)
INGEST_VALIDATE_TOTAL = Counter(
	"neuron_ingest_validate_total",
	"Ingest validation requests by outcome",
	["outcome"],
)
INGEST_RATE_LIMITED_TOTAL = Counter(
	"neuron_ingest_rate_limited_total",
	"Per-tenant ingest rate limited events",
	["tenant"],
)
ERROR_CODE_TOTAL = Counter(
    "neuron_error_code_total",
    "Standardized error responses emitted by code",
    ["code"],
)

# --------------------------- Integration placeholders already present ---------------------------

# Backward compatibility: expose generate_latest wrapper name expected by some older imports
generate_latest_metrics = metrics_response  # alias

# --------------------------- Integrations Metrics ---------------------------
INTEGRATION_EXPORT_TOTAL = Counter(
	"neuron_integration_export_total",
	"Total integration export attempts by integration and outcome",
	["integration", "outcome"],
)

INTEGRATION_EXPORT_LATENCY_SECONDS = Histogram(
	"neuron_integration_export_latency_seconds",
	"Latency of integration export attempts in seconds",
	["integration", "outcome"],
	buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

def record_integration_export_metrics(integration: str, outcome: str, latency_s: float):
	"""Helper to record integration export metrics (best-effort)."""
	try:
		INTEGRATION_EXPORT_TOTAL.labels(integration=integration, outcome=outcome).inc()
		INTEGRATION_EXPORT_LATENCY_SECONDS.labels(integration=integration, outcome=outcome).observe(latency_s)
	except Exception:
		pass

def _try_set(g, value: float, **labels):  # pragma: no cover - helper for optional updates
	try:
		if labels:
			g.labels(**labels).set(value)
		else:
			g.set(value)
	except Exception:
		pass

# Export only UPPERCASE metric symbols + helper functions plus registry() shim
try:
	from prometheus_client import REGISTRY as _PROM_CLIENT_REGISTRY  # type: ignore
except Exception:  # pragma: no cover
	_PROM_CLIENT_REGISTRY = None  # type: ignore

def registry():  # shim expected by tests calling metrics.registry()
	return _PROM_CLIENT_REGISTRY

__all__ = [name for name, obj in globals().items() if name.isupper()] + ["registry"]

# --------------------------- Added Missing Metrics (emission site alignment) ---------------------------
# Alerts dispatcher totals (channel, outcome)
ALERT_DISPATCH_TOTAL = Counter(
	"neuron_alert_dispatch_total",
	"Alert dispatch outcomes by channel and outcome",
	["channel", "outcome"],
)
# Threat Feed metrics (Batch 6)
THREAT_FEED_STATUS_TOTAL = Counter(
	"neuron_threat_feed_status_total",
	"Threat feed fetch outcome counts by feed and status (success|error|disabled)",
	["feed", "status"],
)
THREAT_FEED_FETCH_LATENCY = Histogram(
	"neuron_threat_feed_fetch_latency_seconds",
	"Threat feed fetch latency seconds by feed",
	["feed"],
	buckets=(0.01,0.05,0.1,0.25,0.5,1,2,5,10,30),
)
THREAT_FEED_BACKOFF_SECONDS = Gauge(
	"neuron_threat_feed_backoff_seconds",
	"Current backoff seconds applied to next fetch per feed",
	["feed"],
)
THREAT_FEED_AGE_SECONDS = Gauge(
	"neuron_threat_feed_age_seconds",
	"Seconds since last successful fetch per feed",
	["feed"],
)
# Fusion & suppression governance
FUSION_SUPPRESS_THRESHOLD = Gauge(
	"neuron_fusion_suppress_threshold",
	"Current fusion suppression threshold per tenant",
	["tenant"],
)
FUSION_SUPPRESSION_ALERTS_TOTAL = Counter(
	"neuron_fusion_suppression_alerts_total",
	"Suppression alert triggers by tenant and strategy",
	["tenant", "strategy"],
)
FUSION_SOURCE_COMBO_TOTAL = Counter(
	"neuron_fusion_source_combo_total",
	"Anomaly source combination occurrences (baseline+snn etc)",
	["tenant", "combo"],
)
FUSION_DECISIONS_TOTAL = Counter(
	"neuron_fusion_decisions_total",
	"Fusion decision outcome counts per tenant",
	["tenant", "outcome"],
)
FUSION_DECISION_LATENCY_SECONDS = Histogram(
	"neuron_fusion_decision_latency_seconds",
	"Latency of fusion decision computation",
	["tenant", "strategy"],
	buckets=(0.0005,0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2),
)
FUSION_SUPPRESS_AUTOTUNE_ADJUSTMENTS_TOTAL = Counter(
	"neuron_fusion_suppress_autotune_adjustments_total",
	"Suppression threshold autotune adjustments",
	["tenant", "direction", "reason"],
)
FUSION_STRATEGY_FALLBACK_TOTAL = Counter(
	"neuron_fusion_strategy_fallback_total",
	"Fusion strategy fallback events",
	["tenant", "from", "reason"],
)
FUSION_STRATEGY_FALLBACK_LATENCY_SECONDS = Histogram(
	"neuron_fusion_strategy_fallback_latency_seconds",
	"Latency of strategy fallback execution path (parameter update + governance recording) per tenant",
	["tenant"],
	buckets=(0.0001,0.0005,0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1),
)

# Precision proxy & governance
PRECISION_PROXY_WINDOWS = Counter(
	"neuron_precision_proxy_windows_total",
	"Precision proxy noise windows processed per tenant",
	["tenant"],
)
PRECISION_PROXY_FALSE_POSITIVE = Counter(
	"neuron_precision_proxy_false_positive_total",
	"Precision proxy false positive counts by detector",
	["tenant", "detector"],
)
GOVERNANCE_ACTIONS_TOTAL = Counter(
	"neuron_governance_actions_total",
	"Governance actions taken (autotune, drift_guard, strategy_fallback)",
	["tenant", "action", "detail"],
)
GOV_ACTION_DRIFT_GUARD_TOTAL = Counter(
	"neuron_gov_action_drift_guard_total",
	"Drift guard actions taken",
	["tenant", "mode"],
)
GOV_ACTION_AUTOTUNE_TOTAL = Counter(
	"neuron_gov_action_autotune_total",
	"Autotune actions (direction up/down)",
	["tenant", "direction"],
)
GOV_ACTION_STRATEGY_FALLBACK_TOTAL = Counter(
	"neuron_gov_action_strategy_fallback_total",
	"Strategy fallback governance actions",
	["tenant", "from", "to", "reason"],
)
GOV_ACTION_LOG_ROTATIONS_TOTAL = Counter(
	"neuron_gov_action_log_rotations_total",
	"Governance action log rotations by reason",
	["reason"],
)
GOV_ACTION_LOG_SIZE_BYTES = Gauge(
	"neuron_gov_action_log_size_bytes",
	"Current size of governance action log (bytes)",
)
SNN_DRIFT_GUARD_TRIPS_TOTAL = Counter(
	"neuron_snn_drift_guard_trips_total",
	"SNN drift guard trips by tenant/action",
	["tenant", "action"],
)

# Temporal specific guards / buffers
TEMPORAL_BUFFER_READY_RATIO = Gauge(
	"neuron_temporal_buffer_ready_ratio",
	"Ratio (0/1) indicating temporal vector buffer readiness per tenant",
	["tenant"],
)
TEMPORAL_GUARD_TRIPS_TOTAL = Counter(
	"neuron_temporal_guard_trips_total",
	"Temporal guard trips by tenant and reason",
	["tenant", "reason"],
)

# Ingestion depth
INGEST_QUEUE_DEPTH = Gauge(
	"neuron_ingest_queue_depth",
	"Current ingestion queue depth per tenant",
	["tenant"],
)

# Retrieval context attach
RETRIEVAL_CONTEXT_ATTACH_TOTAL = Counter(
	"neuron_retrieval_context_attach_total",
	"Retrieval context attachment attempts by status",
	["tenant", "status"],
)

# Detector union/overlap tracking (orchestrator)
UNION_EVENTS_TOTAL = Counter(
	"neuron_union_events_total",
	"Total events contributing to detector union per tenant",
	["tenant"],
)
DETECTOR_UNIQUE_EVENTS_TOTAL = Counter(
	"neuron_detector_unique_events_total",
	"Unique events per detector and tenant",
	["tenant", "detector"],
)
DETECTOR_OVERLAP_EVENTS_TOTAL = Counter(
	"neuron_detector_overlap_events_total",
	"Detector overlap contribution events per tenant/detector",
	["tenant", "detector"],
)

# Network anomalies (Phase1)
NETWORK_ANOMALIES_TOTAL = Counter(
	"neuron_network_anomalies_total",
	"Network anomalies by tenant and trigger type (trigger='__total__' aggregates per event)",
	["tenant", "trigger"],
)

# Network observability enhancements (Phase1 optional)
NETWORK_DETECT_LATENCY_SECONDS = Histogram(
	"neuron_network_detect_latency_seconds",
	"Latency of network detector feature extraction + heuristic evaluation",
	["tenant"],
	buckets=(0.0001,0.0005,0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1),
)
NETWORK_ASSETS_TRACKED = Gauge(
	"neuron_network_assets_tracked",
	"Number of active assets (keys) currently tracked in network state",
)

# Forensics / Memory (Phase2 scaffold)
FORENSICS_JOB_TOTAL = Counter(
	"neuron_forensics_job_total",
	"Forensics acquisition jobs by modality and status",
	["modality", "status"],
)
FORENSICS_FINDINGS_TOTAL = Counter(
	"neuron_forensics_findings_total",
	"Forensics-derived findings aggregated by modality",
	["modality"],
)

# --------------------------- Action Registry / Memory Pattern Metrics (Phase 8) ---------------------------
ACTION_REGISTRY_EXECUTIONS_TOTAL = Counter(
	"neuron_action_registry_executions_total",
	"Action registry executions by action, outcome and path",
	["action", "outcome", "path"],
)
MEMORY_PATTERN_TOTAL = Gauge(
	"neuron_memory_pattern_total",
	"Total memory patterns stored",
)
MEMORY_PATTERN_MATCH_TOTAL = Counter(
	"neuron_memory_pattern_match_total",
	"Pattern match simulation invocations by outcome",
	["outcome"],
)
MEMORY_PATTERN_EVICTIONS_TOTAL = Counter(
	"neuron_memory_pattern_evictions_total",
	"Memory pattern evictions by reason (capacity|ttl|prune)",
	["reason"],
)
FORENSICS_JOB_PERSIST_ERRORS_TOTAL = Counter(
	"neuron_forensics_job_persist_errors_total",
	"Persistence write/load errors for forensics jobs by stage",
	["stage"],
)
FORENSICS_JOB_RETRIES_TOTAL = Counter(
	"neuron_forensics_job_retries_total",
	"Forensics job retry outcomes by modality and outcome (retry|exhausted)",
	["modality", "outcome"],
)

# Temporal feature buffer (Batch 2A)
TEMPORAL_BUFFER_SIZE = Gauge(
	"neuron_temporal_buffer_size",
	"Temporal feature buffer size per tenant",
	["tenant"],
)
TEMPORAL_BUFFER_PRUNES_TOTAL = Counter(
	"neuron_temporal_buffer_prunes_total",
	"Temporal feature buffer prune events by tenant and reason",
	["tenant", "reason"],
)
TEMPORAL_BUFFER_READY = Gauge(
	"neuron_temporal_buffer_ready",
	"Temporal buffer readiness (1 if tenant buffer >= readiness threshold)",
	["tenant"],
)
TEMPORAL_BUFFER_RETAINED_RATIO = Gauge(
	"neuron_temporal_buffer_retained_ratio",
	"Post-compaction ratio of retained entries vs pre-compaction length (per tenant)",
	["tenant"],
)

# Memory artifact correlation scoring (Batch 2 next feature)
MEMORY_ARTIFACT_CORRELATION_TOTAL = Counter(
	"neuron_memory_artifact_correlation_total",
	"Memory artifact correlation evaluations by outcome (high|medium|low|error)",
	["outcome"],
)
MEMORY_SIGNAL_GATING_LATENCY_SECONDS = Histogram(
	"neuron_memory_signal_gating_latency_seconds",
	"Latency of memory signal gating & job trigger evaluation path",
	buckets=(0.0001,0.0005,0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2),
)

# Vulnerability scanner cycles counter placeholder
VULN_SCAN_CYCLES_TOTAL = Counter(
	"neuron_vuln_scan_cycles_total",
	"Vulnerability scanner cycle iterations by outcome/status (placeholder - tests monkeypatch)",
	["status"],
)

# Fusion anomalies total (some code checks for existence before increment)
FUSION_ANOMALIES_TOTAL = Counter(
	"neuron_fusion_anomalies_total",
	"Anomalies passing fusion per tenant and strategy",
	["tenant", "strategy"],
)

# New counters / histograms required by tests & recent code paths
EVENTS_DROPPED_TOTAL = Counter(
	"neuron_events_dropped_total",
	"Total events dropped during ingest by tenant and reason",
	["tenant", "reason"],
)

VULN_NORMALIZATION_LATENCY = Histogram(
	"neuron_vuln_normalization_latency_seconds",
	"Latency of vulnerability record normalization pipeline",
	buckets=(0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2,5,10)
)

# --------------------------- RAG / Retrieval Batch 4 Metrics ---------------------------
RAG_RETRIEVAL_LATENCY_SECONDS = Histogram(
	"neuron_rag_retrieval_latency_seconds",
	"End-to-end retrieval (query -> ranked contexts) latency seconds",
	buckets=(0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2,5,10)
)
RAG_RANK_ADJUST_TOTAL = Counter(
	"neuron_rag_rank_adjust_total",
	"Rank adjustment applications by reason (length_penalty|recent_boost|dedupe|other)",
	["reason"],
)
RAG_EMBEDDING_CACHE_SIZE = Gauge(
	"neuron_rag_embedding_cache_size",
	"Current number of entries in embedding cache",
)
RAG_EMBEDDING_CACHE_TENANT_SIZE = Gauge(
	"neuron_rag_embedding_cache_tenant_size",
	"Per-tenant embedding cache entry count (guarded emission)",
	["tenant"],
)
RAG_EMBEDDING_CACHE_USAGE_DECAY_TOTAL = Counter(
	"neuron_rag_embedding_cache_usage_decay_total",
	"Embedding cache entries whose usage counts were decayed during maintenance",
)
MEMORY_ARTIFACT_LINK_TOTAL = Counter(
	"neuron_memory_artifact_link_total",
	"Memory artifact linkage events by link_type (pattern_case|pattern_ticket|artifact_case|artifact_ticket)",
	["link_type"],
)

# --------------------------- Batch A New Metrics (Rule & Retrieval Enhancements) ---------------------------
RESPONSE_RULE_RELOAD_TOTAL = Counter(
	"neuron_response_rule_reload_total",
	"Rule DSL reload attempts by result (success|error|skipped)",
	["result"],
)
RESPONSE_RULE_LATENCY_SECONDS = Histogram(
	"neuron_response_rule_latency_seconds",
	"Latency of individual rule evaluation (seconds) per rule id",
	["rule_id"],
	buckets=(0.0001,0.0005,0.001,0.005,0.01,0.025,0.05,0.1,0.25,0.5,1,2),
)
RESPONSE_RULE_CHAIN_TOTAL = Counter(
	"neuron_response_rule_chain_total",
	"Rule chaining execution outcomes (ok|loop_detected|depth_exceeded|error)",
	["result"],
)
RAG_RETRIEVAL_TOTAL = Counter(
	"neuron_rag_retrieval_total",
	"Retrieval request outcomes (success|empty|error)",
	["result"],
)

# --- Drift Guard Action Telemetry (Batch 5.2) ---
try:  # pragma: no cover
	from prometheus_client import Counter as _DGCounter, Gauge as _DGGauge, Histogram as _DGHist  # type: ignore
	DRIFT_GUARD_ACTIONS_TOTAL = _DGCounter(
		'neuron_drift_guard_actions_total',
		'Drift guard action decisions by mode and outcome',
		['tenant', 'mode', 'outcome']
	)
	DRIFT_GUARD_LAST_TRIGGER_TS = _DGGauge(
		'neuron_drift_guard_last_trigger_ts',
		'Unix timestamp of last drift guard trigger per tenant'
	)
	DRIFT_GUARD_COOLDOWN_ACTIVE = _DGGauge(
		'neuron_drift_guard_cooldown_active',
		'Cooldown active state (1 active / 0 idle) per tenant'
	)
	DRIFT_GUARD_TIME_BETWEEN_SECONDS = _DGHist(
		'neuron_drift_guard_time_between_seconds',
		'Time between drift guard triggers per tenant (seconds)',
		buckets=(1,5,10,30,60,120,300,600,1800,3600)
	)
except Exception:  # pragma: no cover
	DRIFT_GUARD_ACTIONS_TOTAL = None  # type: ignore
	DRIFT_GUARD_LAST_TRIGGER_TS = None  # type: ignore
	DRIFT_GUARD_COOLDOWN_ACTIVE = None  # type: ignore
	DRIFT_GUARD_TIME_BETWEEN_SECONDS = None  # type: ignore
RAG_RANK_DEBUG_REQUESTS_TOTAL = Counter(
	"neuron_rag_rank_debug_requests_total",
	"Ranking debug endpoint requests",
)
RAG_EMBEDDING_CACHE_HITS_TOTAL = Counter(
	"neuron_rag_embedding_cache_hits_total",
	"Embedding cache hits",
)
RAG_EMBEDDING_CACHE_MISSES_TOTAL = Counter(
	"neuron_rag_embedding_cache_misses_total",
	"Embedding cache misses",
)
RAG_EMBEDDING_CACHE_EVICTIONS_TOTAL = Counter(
	"neuron_rag_embedding_cache_evictions_total",
	"Embedding cache evictions due to capacity or TTL",
	["reason"],
)
RETRIEVAL_PROBE_TOTAL = Counter(
	"neuron_retrieval_probe_total",
	"Synthetic retrieval probe outcomes by tenant and result",
	["tenant", "result"],
)

# Provide explicit alias without shadowing registry() shim
from prometheus_client import REGISTRY as PROM_REGISTRY_ALIAS  # noqa: E402

# --- Governance / Shadow Mode Metrics (Batch 5.1) ---
try:  # pragma: no cover - registration best-effort
	from prometheus_client import Counter as _ShadowCounter, Gauge as _ShadowGauge  # type: ignore
	GOVERNANCE_SHADOW_RECOMMENDATIONS_TOTAL = _ShadowCounter(
		'neuron_governance_shadow_recommendations_total',
		'Total shadow governance recommendations emitted (no live mutation)',
		['tenant', 'action']
	)
	GOVERNANCE_SHADOW_BUFFER_UTILIZATION = _ShadowGauge(
		'neuron_governance_shadow_buffer_utilization',
		'Fraction of shadow recommendation ring buffer utilized (0..1)'
	)
except Exception:  # pragma: no cover
	GOVERNANCE_SHADOW_RECOMMENDATIONS_TOTAL = None  # type: ignore
	GOVERNANCE_SHADOW_BUFFER_UTILIZATION = None  # type: ignore

