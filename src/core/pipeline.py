"""Processing pipeline orchestrating ingestion and detectors."""
from __future__ import annotations

import asyncio
import time
import logging
import contextlib
from typing import Optional, Sequence

from core.ingest.manager import IngestionManager
from core.detect.baseline import register_default
from core.detect.interface import registry
from core.detect.fusion import arbitrator
from config import runtime_params
from core import metrics
from core.drift.monitor import drift_monitor
from core.trace_store import traces
from core.features.registry import feature_order, to_vector
from core.sequence.buffer import buffers as vector_buffers
import os, json
from detect.network.detector import register_network  # type: ignore  # network detector (Phase1)

log = logging.getLogger("neuron.pipeline")


class Pipeline:
    def __init__(self, tenants: Sequence[str]):
        self.tenants = tenants
        self.ingestion = IngestionManager(tenants)
        # Register baseline detector (other detectors can be added later)
        register_default()
        # Attempt SNN detector registration if feature flag set (graceful fallback)
        self._maybe_register_snn()
        # Attempt temporal transformer stub registration if flag enabled
        self._maybe_register_temporal()
        # Register network flow detector (fast win) if flag enabled
        self._maybe_register_network()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        # Rolling window storage for precision drift proxy per tenant
        self._rolling_window_size = 200  # default; may be overridden by runtime param
        # Map tenant -> list of (snn_unique (0/1), union (0/1)) per event (bounded)
        self._fusion_history: dict[str, list[tuple[int, int]]] = {}
        # Suppression tracking: tenant -> list of (suppressed, passed)
        self._suppression_history: dict[str, list[tuple[int, int]]] = {}
        # Drift monitoring counters
        self._events_seen = 0
        self._drift_compute_interval = 200  # default; may be overridden by runtime param
        # Precision proxy tallies (tenant -> {windows, fp_baseline, fp_snn, fp_temporal})
        self._precision_proxy: dict[str, dict[str, int]] = {}
        # Track drift guard trigger indices per tenant
        self._drift_guard_triggered: dict[str, int] = {}
        # Governance action history (deque-like list capped) per tenant for diagnostics endpoint
        self._gov_actions: dict[str, list[dict]] = {}
        # Governance shadow recommendation ring buffer per tenant (for surfacing via API)
        self._gov_recommendations: dict[str, list[dict]] = {}
        # Drift guard evaluation trace ring buffer per tenant (for new tracing endpoint)
        self._drift_guard_traces: dict[str, list[dict]] = {}
        # Autotune adjustment timestamps per tenant (for rate limit)
        self._autotune_ts: dict[str, list[float]] = {}
        # Last autotune timestamp per tenant (cooldown tracking)
        if not hasattr(self, "_last_autotune"):
            self._last_autotune: dict[str, float] = {}
        # Initial suppression threshold gauge sync (per tenant)
        try:
            cur_thr = float(runtime_params.get_param("fusion.weighted_sum.suppress_threshold") or 0.0)
            for t in tenants:
                try:
                    metrics.FUSION_SUPPRESS_THRESHOLD.labels(tenant=t).set(cur_thr)  # type: ignore[attr-defined]
                except Exception:
                    pass
                # --- Shadow governance evaluation (Batch 5.1) ---
                try:
                    # Shadow governance evaluation occurs during event processing; no-op on init
                    pass
                except Exception:
                    pass
        except Exception:
            pass
        # Ensure governance artifacts directory exists for action persistence
        try:
            os.makedirs("artifacts/governance", exist_ok=True)
        except Exception:
            pass

        # Optional: seed temporal transformer with a tiny synthetic stream to keep deviation responsive in demos
        try:
            if bool(runtime_params.get_param("detection.transformer.enabled")):
                from core.temporal.transformer import instance as tt_instance  # type: ignore
                import random
                tt = tt_instance()
                for _ in range(8):
                    tt.ingest([random.random() for _ in range(4)])
        except Exception:
            pass

    # --- Adaptive Governance Helpers (extracted for test determinism) ---
    def list_drift_guard_traces(self, tenant: str | None = None, limit: int = 100):
        try:
            limit = max(1, min(500, int(limit)))
        except Exception:
            limit = 100
        try:
            if tenant:
                buf = self._drift_guard_traces.get(tenant, [])
                return list(reversed(buf))[:limit]
            # flatten
            all_recs: list[dict] = []
            for t, buf in self._drift_guard_traces.items():
                all_recs.extend(buf[-limit:])
            # newest first
            all_recs.sort(key=lambda r: r.get('ts',0), reverse=True)
            return all_recs[:limit]
        except Exception:
            return []

    # --- Test helper methods (non-production usage) ---
    def _test_trigger_strategy_fallback(self, tenant: str = "tenant_test"):
        """Force a strategy fallback to observe latency metric (tests only)."""
        try:
            from config import runtime_params as _rp
            # Ensure starting strategy
            _rp.update_param("detection.fusion.strategy", "weighted_sum", reason="test_helper", actor="test")
            # Simulate precision proxy tallies meeting thresholds
            self._precision_proxy.setdefault(tenant, {"windows": 100, "fp_snn": 60, "fp_baseline": 10})
            # Simulate suppression history to produce high suppression rate
            self._suppression_history.setdefault(tenant, [(1,0)] * 95 + [(0,1)] * 5)
            # Invoke internal logic path similarly to main loop – reuse fallback snippet by calling drift guard & autotune chain indirectly via fabricated rate
            # Directly call _maybe_drift_guard to populate traces (not strictly required for fallback metric)
            self._maybe_drift_guard(tenant, suppression_rate=0.95, force=False)
            # Manually re-run fallback condition block (isolated) replicating key logic
            import time as _t_fb
            start = _t_fb.perf_counter()
            try:
                _rp.update_param("detection.fusion.strategy", "baseline_priority", reason="strategy_fallback", actor="test_helper")
            except Exception:
                pass
            elapsed = _t_fb.perf_counter() - start
            try:
                metrics.FUSION_STRATEGY_FALLBACK_LATENCY_SECONDS.labels(tenant=tenant).observe(elapsed)  # type: ignore[attr-defined]
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _test_trigger_memory_gating(self, tenant: str = "tenant_test"):
        """Invoke memory gating path with a synthetic anomaly to emit gating latency metric."""
        try:
            anomaly = {"fusion_decision_score": 0.2, "risk_score": 90, "asset_id": "assetX", "triggers": ["test"]}
            import time as _t_mem
            start = _t_mem.perf_counter()
            self._maybe_memory_trigger([anomaly])
            elapsed = _t_mem.perf_counter() - start
            try:
                metrics.MEMORY_SIGNAL_GATING_LATENCY_SECONDS.observe(elapsed)  # type: ignore[attr-defined]
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _maybe_drift_guard(self, tenant: str, suppression_rate: float | None = None, force: bool = False):
        """Evaluate drift guard conditions and take action.

        Parameters:
            tenant: tenant id
            suppression_rate: recent suppression rate (optional; if None treat as 0)
            force: bypass history / thresholds (used in tests)
        """
        try:  # defensive: never raise
            import time as _t
            hist = self._fusion_history.get(tenant) or []
            rate = suppression_rate or 0.0
            # Read runtime force flags
            force_immediate = False
            force_after = 0
            try:
                force_immediate = bool(runtime_params.get_param("governance.drift_guard.force_immediate"))
            except Exception:  # noqa: BLE001
                pass
            try:
                force_after = int(runtime_params.get_param("governance.drift_guard.force_after_windows") or 0)
            except Exception:  # noqa: BLE001
                pass
            trigger = False
            if force or force_immediate:
                trigger = True
            elif force_after and len(hist) >= force_after:
                trigger = True
            elif len(hist) >= 30:
                try:
                    total_union = sum(u for _, u in hist) or 1
                    total_snn_unique = sum(s for s, _ in hist)
                    rolling_ratio = total_snn_unique / total_union
                except Exception:
                    rolling_ratio = 0.0
                if rolling_ratio > 0.85 and rate > 0.8:
                    trigger = True
            # Record evaluation trace (best-effort)
            try:
                trace_buf = self._drift_guard_traces.setdefault(tenant, [])
                trace_rec = {
                    "ts": _t.time(),
                    "tenant": tenant,
                    "suppression_rate": rate,
                    "rolling_snn_unique_ratio": rolling_ratio if 'rolling_ratio' in locals() else None,
                    "force_flags": {"force": force, "force_immediate": force_immediate, "force_after": force_after},
                    "trigger": False,
                    "actions": [],
                }
            except Exception:
                trace_rec = None
            if not trigger:
                if trace_rec is not None:
                    try:
                        trace_buf.append(trace_rec)
                        if len(trace_buf) > 200:
                            del trace_buf[:-200]
                    except Exception:
                        pass
                return False
            # single trigger gating
            last_trig = self._drift_guard_triggered.get(tenant, -1)
            if len(hist) <= last_trig and not (force or force_immediate):
                if trace_rec is not None:
                    try:
                        trace_buf.append(trace_rec)
                        if len(trace_buf) > 200:
                            del trace_buf[:-200]
                    except Exception:
                        pass
                return False
            prev_index = self._drift_guard_triggered.get(tenant)
            self._drift_guard_triggered[tenant] = len(hist)
            # Telemetry: trigger timestamps & interval histogram
            try:
                import time as _t2
                now_ts = _t2.time()
                if getattr(metrics, 'DRIFT_GUARD_LAST_TRIGGER_TS', None):
                    metrics.DRIFT_GUARD_LAST_TRIGGER_TS.labels(tenant=tenant).set(now_ts)  # type: ignore[attr-defined]
                if prev_index is not None and getattr(metrics, 'DRIFT_GUARD_TIME_BETWEEN_SECONDS', None):
                    last_map = getattr(self, '_drift_guard_last_ts', {}) if hasattr(self, '_drift_guard_last_ts') else {}
                    last_ts = last_map.get(tenant)
                    if last_ts:
                        metrics.DRIFT_GUARD_TIME_BETWEEN_SECONDS.labels(tenant=tenant).observe(max(0.0, now_ts - last_ts))  # type: ignore[attr-defined]
                    if not hasattr(self, '_drift_guard_last_ts'):
                        self._drift_guard_last_ts = {}
                    self._drift_guard_last_ts[tenant] = now_ts
            except Exception:
                pass
            # Action: disable SNN else raise threshold
            try:
                snn_enabled = bool(runtime_params.get_param("detection.enable_snn"))
            except Exception:
                snn_enabled = False
            # Determine action ordering via runtime param
            try:
                mode = runtime_params.get_param("governance.drift_guard.action_mode") or "disable_then_raise"
            except Exception:
                mode = "disable_then_raise"
            actions_order: list[str]
            if mode == "raise_first":
                actions_order = ["raise", "disable"]
            elif mode == "disable_only":
                actions_order = ["disable"]
            elif mode == "raise_only":
                actions_order = ["raise"]
            else:
                actions_order = ["disable", "raise"]
            performed = False
            outcomes: list[str] = []
            for act in actions_order:
                if act == "disable" and snn_enabled:
                    try:
                        runtime_params.update_param("detection.enable_snn", False, reason="drift_guard", actor="governance")
                        metrics.SNN_DRIFT_GUARD_TRIPS_TOTAL.labels(tenant=tenant, action="disable_snn").inc()  # type: ignore[attr-defined]
                        metrics.GOVERNANCE_ACTIONS_TOTAL.labels(tenant=tenant, action="drift_guard", detail="disable_snn").inc()  # type: ignore[attr-defined]
                        self._record_gov_action(tenant, {
                            "ts": _t.time(),
                            "action": "drift_guard",
                            "detail": "disable_snn"
                        })
                        if trace_rec is not None:
                            trace_rec.setdefault("actions", []).append("disable_snn")
                        performed = True
                        outcomes.append("disable_snn")
                        try:
                            if getattr(metrics, 'DRIFT_GUARD_ACTIONS_TOTAL', None):
                                metrics.DRIFT_GUARD_ACTIONS_TOTAL.labels(tenant=tenant, mode=str(mode), outcome="disable_snn").inc()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    except Exception:
                        pass
                if act == "raise":
                    try:
                        thr_key = "fusion.weighted_sum.suppress_threshold"
                        current_thr = float(runtime_params.get_param(thr_key) or 0.5)
                        new_thr = min(current_thr + 0.02, 0.95)
                        if new_thr - current_thr >= 0.01:
                            runtime_params.update_param(thr_key, round(new_thr, 4), reason="drift_guard", actor="governance")
                            metrics.SNN_DRIFT_GUARD_TRIPS_TOTAL.labels(tenant=tenant, action="raise_threshold").inc()  # type: ignore[attr-defined]
                            metrics.GOVERNANCE_ACTIONS_TOTAL.labels(tenant=tenant, action="drift_guard", detail="raise_threshold").inc()  # type: ignore[attr-defined]
                            try:
                                metrics.GOV_ACTION_DRIFT_GUARD_TOTAL.labels(tenant=tenant, mode="raise_threshold").inc()  # type: ignore[attr-defined]
                            except Exception:
                                pass
                            self._record_gov_action(tenant, {
                                "ts": _t.time(),
                                "action": "drift_guard",
                                "detail": "raise_threshold",
                                "new_threshold": new_thr
                            })
                            if trace_rec is not None:
                                trace_rec.setdefault("actions", []).append("raise_threshold")
                            performed = True
                            outcomes.append("raise_threshold")
                            try:
                                if getattr(metrics, 'DRIFT_GUARD_ACTIONS_TOTAL', None):
                                    metrics.DRIFT_GUARD_ACTIONS_TOTAL.labels(tenant=tenant, mode=str(mode), outcome="raise_threshold").inc()  # type: ignore[attr-defined]
                            except Exception:
                                pass
                    except Exception:
                        pass
                if performed:
                    break
            # No action outcome telemetry
            if not outcomes:
                try:
                    if getattr(metrics, 'DRIFT_GUARD_ACTIONS_TOTAL', None):
                        metrics.DRIFT_GUARD_ACTIONS_TOTAL.labels(tenant=tenant, mode=str(mode), outcome="no_action").inc()  # type: ignore[attr-defined]
                except Exception:
                    pass
            if trace_rec is not None:
                trace_rec["trigger"] = performed
                try:
                    trace_buf.append(trace_rec)
                    if len(trace_buf) > 200:
                        del trace_buf[:-200]
                    # Optional persistence
                    try:
                        persist_enabled = False
                        try:
                            persist_enabled = bool(runtime_params.get_param("governance.drift_guard.trace.persist"))
                        except Exception:
                            persist_enabled = False
                        if persist_enabled:
                            os.makedirs("artifacts/governance", exist_ok=True)
                            path = "artifacts/governance/drift_guard_traces.jsonl"
                            rec_out = dict(trace_rec)
                            rec_out["tenant"] = tenant
                            with open(path, "a", encoding="utf-8") as f:
                                f.write(json.dumps(rec_out) + "\n")
                    except Exception:
                        pass
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _record_gov_action(self, tenant: str, rec: dict):
        try:
            hist = self._gov_actions.setdefault(tenant, [])
            hist.append(rec)
            if len(hist) > 200:
                del hist[: len(hist) - 200]
            # Persist append-only JSONL (best-effort)
            try:
                rec2 = dict(rec)
                rec2["tenant"] = tenant
                path = "artifacts/governance/governance_actions.jsonl"
                max_bytes = 0
                max_hist = 0
                try:
                    max_bytes = int(runtime_params.get_param("governance.diagnostics.max_log_bytes") or 0)
                    max_hist = int(runtime_params.get_param("governance.diagnostics.max_history_files") or 5)
                except Exception:
                    max_bytes = 0
                    max_hist = 5
                rotate = False
                if max_bytes > 0 and os.path.exists(path):
                    try:
                        if os.path.getsize(path) >= max_bytes:
                            rotate = True
                    except Exception:
                        rotate = False
                if rotate:
                    # Rotate: move current file to .1, increment suffix, prune beyond retention
                    try:
                        try:
                            metrics.GOV_ACTION_LOG_ROTATIONS_TOTAL.labels(reason="size").inc()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        for i in range(max_hist, 0, -1):
                            old = f"{path}.{i}"
                            if os.path.exists(old):
                                if i == max_hist:
                                    os.remove(old)
                                else:
                                    os.replace(old, f"{path}.{i+1}")
                        os.replace(path, f"{path}.1")
                    except Exception:
                        pass
                with open(path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(rec2) + "\n")
                # Update size gauge
                try:
                    if os.path.exists(path):
                        metrics.GOV_ACTION_LOG_SIZE_BYTES.set(os.path.getsize(path))  # type: ignore[attr-defined]
                except Exception:
                    pass
            except Exception:
                pass
        except Exception:
            pass

    # --- Test Hook: Autotune suppression helper (non-loop) ---
    def _autotune_test_hook(self, tenant: str, snn_fp_rate: float, base_fp_rate: float, now_ts: float | None = None):
        """Invoke suppression autotune logic once for tests.

        Returns (changed: bool, new_threshold: float)
        """
        try:
            if now_ts is None:
                now_ts = time.time()
            strat = runtime_params.get_param("detection.fusion.strategy")
            if strat != "weighted_sum":
                return False, float(runtime_params.get_param("fusion.weighted_sum.suppress_threshold") or 0.0)
            try:
                thr_key = "fusion.weighted_sum.suppress_threshold"
                current_thr = float(runtime_params.get_param(thr_key) or 0.5)
            except Exception:
                current_thr = 0.5
            diff = snn_fp_rate - base_fp_rate
            adjust = 0.0
            tol = 0.05
            if diff > tol:
                adjust = +0.01
            elif diff < -tol:
                adjust = -0.01
            if adjust == 0.0:
                # Even if no threshold change, in shadow mode emit a recommendation audit when FP diff suggests it
                try:
                    if bool(runtime_params.get_param("governance.shadow.enabled")) and abs(diff) > 0.05:
                        suggestion = {"action": "raise_threshold" if diff > 0 else "lower_threshold", "delta": 0.01 if diff > 0 else -0.01, "reason": "shadow_fp_rate_diff", "diff": round(diff,4)}
                        try:
                            runtime_params.audit_agent_decision("governance_shadow", "recommend", {"tenant": tenant, "suggestion": suggestion})  # type: ignore[attr-defined]
                        except Exception:
                            pass
                except Exception:
                    pass
                return False, current_thr
            new_thr = current_thr + adjust
            if new_thr < 0.05:
                new_thr = 0.05
            if new_thr > 0.95:
                new_thr = 0.95
            last_adj = self._last_autotune.get(tenant, 0.0)
            if (now_ts - last_adj) < 30:
                return False, current_thr
            allow = True
            max_per_hour = 0
            try:
                max_per_hour = int(runtime_params.get_param("governance.autotune.max_per_hour") or 0)
            except Exception:
                max_per_hour = 0
            if max_per_hour > 0:
                ts_list = self._autotune_ts.setdefault(tenant, [])
                cutoff = now_ts - 3600
                ts_list[:] = [t for t in ts_list if t >= cutoff]
                if len(ts_list) >= max_per_hour:
                    allow = False
            if not allow:
                return False, current_thr
            if abs(new_thr - current_thr) < 0.005:
                return False, current_thr
            runtime_params.update_param(thr_key, round(new_thr, 4), reason="autotune_suppression", actor="governance")
            try:
                metrics.FUSION_SUPPRESS_AUTOTUNE_ADJUSTMENTS_TOTAL.labels(tenant=tenant, direction="up" if adjust > 0 else "down", reason="fp_rate_diff").inc()  # type: ignore[attr-defined]
                metrics.GOVERNANCE_ACTIONS_TOTAL.labels(tenant=tenant, action="autotune_suppression", detail="up" if adjust > 0 else "down").inc()  # type: ignore[attr-defined]
                metrics.FUSION_SUPPRESS_THRESHOLD.labels(tenant=tenant).set(new_thr)  # type: ignore[attr-defined]
            except Exception:
                pass
            self._last_autotune[tenant] = now_ts
            if max_per_hour > 0:
                self._autotune_ts.setdefault(tenant, []).append(now_ts)
            self._record_gov_action(tenant, {
                "ts": now_ts,
                "action": "autotune_suppression",
                "direction": "up" if adjust > 0 else "down",
                "old": current_thr,
                "new": new_thr,
                "snn_fp_rate": snn_fp_rate,
                "baseline_fp_rate": base_fp_rate
            })
            # Also emit a shadow recommendation audit alongside if enabled
            try:
                if bool(runtime_params.get_param("governance.shadow.enabled")):
                    suggestion = {"action": "raise_threshold" if adjust > 0 else "lower_threshold", "delta": 0.01 if adjust > 0 else -0.01, "reason": "shadow_fp_rate_diff"}
                    try:
                        runtime_params.audit_agent_decision("governance_shadow", "recommend", {"tenant": tenant, "suggestion": suggestion})  # type: ignore[attr-defined]
                    except Exception:
                        pass
            except Exception:
                pass
            return True, new_thr
        except Exception:
            return False, float(runtime_params.get_param("fusion.weighted_sum.suppress_threshold") or 0.0)

    def _maybe_register_snn(self):
        """Best-effort registration of the SNN detector when feature flag enabled.

        This stays lightweight and defensive: if dependencies (torch, snntorch) or the
        implementation module are unavailable the pipeline proceeds without SNN.
        """
        try:
            enabled = bool(runtime_params.get_param("detection.enable_snn"))
        except Exception:
            enabled = False
        if not enabled:
            log.debug("SNN detector flag disabled; skipping registration")
            return
        # Test optimization: allow skipping heavy imports for focussed API contract tests
        if os.getenv("TEST_FAST_NO_TORCH") == "1":  # pragma: no cover - test speed path
            log.debug("TEST_FAST_NO_TORCH=1 set; skipping torch/snntorch import for speed")
            try:
                from core.detect.snn import register_snn  # type: ignore
                register_snn()
                log.info("SNN detector registered (fast path without torch validation)")
            except Exception as e:  # noqa: BLE001
                log.debug("Fast-path SNN registration skipped (%s)", e)
            return
        try:  # noqa: BLE001
            # Optional dependencies (we only log if missing)
            try:
                import torch  # type: ignore  # noqa: F401
            except Exception as e:  # noqa: BLE001
                log.debug("torch unavailable (%s); advanced SNN features will be skipped", e)
            try:
                import snntorch  # type: ignore  # noqa: F401
            except Exception as e:  # noqa: BLE001
                log.debug("snntorch unavailable (%s); using prototype LIF only", e)
            from core.detect.snn import register_snn  # type: ignore
        except ImportError as e:  # pragma: no cover
            log.warning("SNN detector dependencies/module missing (%s); continuing without SNN", e)
            return
        try:
            register_snn()
            log.info("SNN detector registered (experimental)")
        except Exception as e:  # noqa: BLE001
            log.error("Failed to initialize SNN detector: %s", e, exc_info=True)

    def _maybe_register_temporal(self):
        try:
            enabled = bool(runtime_params.get_param("detection.temporal.enable_transformer"))
        except Exception:
            enabled = False
        if not enabled:
            return
        try:
            from core.detect.temporal import register_temporal  # type: ignore
            register_temporal()
            log.info("Temporal detector stub registered (flag enabled)")
        except Exception as e:  # noqa: BLE001
            log.warning("Temporal detector stub registration failed: %s", e)

    def _maybe_register_network(self):
        try:
            enabled = bool(runtime_params.get_param("detection.enable_network"))
        except Exception:
            enabled = True  # default ON for Phase 1
        if not enabled:
            return
        try:
            register_network()
        except Exception:
            pass

    async def start(self):
        if self._running:
            return
        self._running = True
        await self.ingestion.start()
        self._task = asyncio.create_task(self._loop())
        log.info("Pipeline started for tenants=%s", self.tenants)

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:  # expected during shutdown
                pass
            except Exception:  # noqa: BLE001
                pass

    async def _loop(self):
        while True:
            ev = await self.ingestion.get()
            # Record for drift prior to mutation/processing
            try:
                drift_monitor().record(ev)
                self._events_seen += 1
                # Refresh interval from runtime param best-effort
                try:
                    desired = runtime_params.get_param("drift.compute_interval") or self._drift_compute_interval
                    if isinstance(desired, int) and 50 <= desired <= 50_000:
                        self._drift_compute_interval = desired
                except Exception:
                    pass
                if self._events_seen % self._drift_compute_interval == 0:
                    drift_monitor().compute()
            except Exception:
                pass
            with metrics.PROCESSING_LATENCY.time():  # type: ignore
                # Collect per-detector anomaly results
                detector_results = {}
                # Pre-populate temporal vector buffer (best-effort)
                try:
                    if bool(runtime_params.get_param("detection.temporal.enable_transformer")):
                        order = feature_order()
                        vec = to_vector({k: v for k, v in ev.features.items() if isinstance(v, (int, float))})
                        # configurable window length reuse snn.encoding_window for now or default 20
                        try:
                            win = int(runtime_params.get_param("snn.encoding_window") or 20)
                        except Exception:
                            win = 20
                        mgr = vector_buffers(window=win, feature_order=order)
                        buf = mgr.get(ev.tenant_id)
                        # adapt to VectorSequenceBuffer API
                        try:
                            buf.add_vector(vec)
                        except Exception:
                            pass
                        try:
                            ratio = 1.0 if buf.ready() else 0.0
                            metrics.TEMPORAL_BUFFER_READY_RATIO.labels(tenant=ev.tenant_id).set(ratio)  # type: ignore[attr-defined]
                        except Exception:
                            pass
                except Exception:
                    pass
                for det in registry.detectors():
                    try:
                        start_det = time.perf_counter()
                        res = det.process(ev) or []
                        elapsed = time.perf_counter() - start_det
                        # Temporal guard enforcement (latency only for now)
                        if det.name == "temporal":
                            try:
                                metrics.TEMPORAL_LATENCY.labels(tenant=ev.tenant_id).observe(elapsed)  # type: ignore[attr-defined]
                                max_lat = float(runtime_params.get_param("temporal.guard.max_latency_s") or 0.2)
                                if elapsed > max_lat:
                                    metrics.TEMPORAL_GUARD_TRIPS_TOTAL.labels(tenant=ev.tenant_id, reason="latency").inc()  # type: ignore[attr-defined]
                                    # Feed latency sample to fusion arbitrator for p99 guard logic
                                    try:
                                        from core.detect.fusion import arbitrator as _arb  # type: ignore
                                        _arb().record_temporal_latency(ev.tenant_id, elapsed)
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                        try:
                            metrics.DETECTOR_LATENCY.labels(tenant=ev.tenant_id, detector=det.name).observe(elapsed)  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    except Exception:  # noqa: BLE001
                        res = []
                    detector_results[det.name] = res
                # SNN normalization (async loop path) before fusion
                try:
                    from core.detect.snn_norm import normalizer as _snn_norm  # type: ignore
                    snn_list = detector_results.get("snn") or []
                    if snn_list:
                        for _rec in snn_list:
                            sc = _rec.get("score")
                            if sc is not None:
                                norm = _snn_norm().normalize(sc, ev.tenant_id)
                                _rec["normalized_score"] = norm
                except Exception:
                    pass
                # Fuse (currently pass-through unless strategy changes)
                try:
                    import time as _t
                    start_fuse = _t.perf_counter()
                    fused_results, meta = arbitrator().fuse(detector_results)
                    fuse_elapsed = _t.perf_counter() - start_fuse
                    # Export latency histogram
                    try:
                        metrics.FUSION_DECISION_LATENCY_SECONDS.labels(tenant=ev.tenant_id, strategy=meta.get("strategy", "?" )).observe(fuse_elapsed)  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    suppressed = int(meta.get("suppressed", 0)) if isinstance(meta, dict) else 0
                    # Passed count approximated as fused results length
                    passed = len(fused_results)
                    # Early drift guard force (test/diagnostic) independent of history
                    try:
                        if bool(runtime_params.get_param("governance.drift_guard.force_immediate")):
                            try:
                                snn_enabled = bool(runtime_params.get_param("detection.enable_snn"))
                            except Exception:
                                snn_enabled = False
                            if snn_enabled:
                                try:
                                    runtime_params.update_param("detection.enable_snn", False, reason="drift_guard", actor="governance")
                                    metrics.SNN_DRIFT_GUARD_TRIPS_TOTAL.labels(tenant=ev.tenant_id, action="disable_snn").inc()  # type: ignore[attr-defined]
                                except Exception:
                                    pass
                    except Exception:
                        pass
                    # Populate fusion decisions ring buffer (best-effort)
                    try:
                        from core.main import _FUSION_DECISIONS, _FUSION_DECISIONS_MAX  # type: ignore
                        outcome = None
                        baseline_anoms = detector_results.get("baseline") or []
                        snn_anoms = detector_results.get("snn") or []
                        temporal_anoms = detector_results.get("temporal") or []
                        has_baseline = bool(baseline_anoms)
                        has_snn = bool(snn_anoms)
                        has_temporal = bool(temporal_anoms)
                        if has_baseline and has_snn:
                            outcome = "overlap"
                        elif has_baseline:
                            outcome = "baseline_only"
                        elif has_snn:
                            outcome = "snn_only"
                        else:
                            outcome = "none"
                        score = None
                        comp_sample = None
                        if fused_results:
                            first = fused_results[0]
                            score = first.get("fusion_decision_score")
                            comp_sample = first.get("fusion_components")
                        rec = {
                            "ts": _t.time(),
                            "tenant_id": getattr(ev, 'tenant_id', None),
                            "event_id": getattr(ev, 'event_id', None),
                            "outcome": outcome,
                            "decision_score": score,
                            "strategy": meta.get("strategy"),
                            "baseline_present": has_baseline,
                            "snn_present": has_snn,
                            "temporal_present": has_temporal,
                            "suppressed_count": suppressed,
                            "fused_count": passed,
                            "latency_ms": round(fuse_elapsed * 1000, 3),
                            "components_sample": comp_sample,
                        }
                        _FUSION_DECISIONS.append(rec)
                        if len(_FUSION_DECISIONS) > _FUSION_DECISIONS_MAX:
                            del _FUSION_DECISIONS[:-_FUSION_DECISIONS_MAX]
                    except Exception:
                        pass
                    # Semantic enrichment attach (context snippets) if enabled
                    try:
                        attach_enabled = bool(runtime_params.get_param("retrieval.context.attach.enabled"))
                    except Exception:
                        attach_enabled = False
                    if attach_enabled and fused_results:
                        try:
                            top_k_ctx = int(runtime_params.get_param("retrieval.context.attach.top_k") or 3)
                        except Exception:
                            top_k_ctx = 3
                        try:
                            from core.retrieval.interface import retrieve_context as _retrieve_context  # type: ignore
                        except Exception:
                            _retrieve_context = None  # type: ignore
                        for _rec in fused_results:
                            if not _retrieve_context:
                                try:
                                    metrics.RETRIEVAL_CONTEXT_ATTACH_TOTAL.labels(tenant=ev.tenant_id, status="skipped").inc()  # type: ignore[attr-defined]
                                except Exception:
                                    pass
                                continue
                            try:
                                cat = _rec.get("category") or _rec.get("type") or ""
                                chunks = _retrieve_context(cat, k=top_k_ctx) if cat is not None else []  # type: ignore
                                _rec["context"] = [
                                    {k2: c.get(k2) for k2 in ("doc", "chunk_id", "score", "explanation") if isinstance(c, dict)}
                                    for c in (chunks or [])
                                ]
                                metrics.RETRIEVAL_CONTEXT_ATTACH_TOTAL.labels(tenant=ev.tenant_id, status="attached").inc()  # type: ignore[attr-defined]
                            except Exception:
                                try:
                                    metrics.RETRIEVAL_CONTEXT_ATTACH_TOTAL.labels(tenant=ev.tenant_id, status="skipped").inc()  # type: ignore[attr-defined]
                                except Exception:
                                    pass
                    elif fused_results:
                        for _rec in fused_results:
                            try:
                                metrics.RETRIEVAL_CONTEXT_ATTACH_TOTAL.labels(tenant=ev.tenant_id, status="skipped").inc()  # type: ignore[attr-defined]
                            except Exception:
                                pass
                    # Async risk overlay enrichment (network anomalies or others lacking risk_score)
                    try:
                        await self._apply_risk_overlay(fused_results)
                    except Exception:
                        pass
                    # Case enrichment: attach case_id and seed confidence if needed
                    try:
                        from core.main import _CASE_ID_INDEX, _CASES, _update_case_confidence, _persist_case  # type: ignore
                        for rec in fused_results:
                            aid = rec.get("event_id") or rec.get("id")
                            if not aid:
                                continue
                            cid = _CASE_ID_INDEX.get(aid)
                            if cid:
                                rec["case_id"] = cid
                                case = _CASES.get(cid)
                                if case and case.get("last_confidence", 0.0) == 0.0:
                                    score = float(rec.get("fusion_decision_score") or 0.0)
                                    norm_conf = max(0.0, min(1.0, score))
                                    _update_case_confidence(cid, norm_conf)
                                    _persist_case(case)
                    except Exception:
                        pass
                    # Enqueue anomalies for sink (batched persistence + TTL pruning)
                    try:
                        from storage.anomaly_sink import sink  # type: ignore
                        s = sink()
                        if s.started():
                            for rec in fused_results[:200]:  # cap per-event
                                rec2 = dict(rec)
                                rec2.setdefault('tenant', getattr(ev, 'tenant_id', None))
                                rec2.setdefault('event_time', getattr(ev, 'timestamp', None))
                                s.enqueue(rec2)
                    except Exception:
                        pass
                    # --- Phase2 Memory Trigger (selective) ---
                    try:
                        import time as _t_mem
                        _mem_start = _t_mem.perf_counter()
                        self._maybe_memory_trigger(fused_results)
                        try:
                            _mem_elapsed = _t_mem.perf_counter() - _mem_start
                            metrics.MEMORY_SIGNAL_GATING_LATENCY_SECONDS.observe(_mem_elapsed)  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    except Exception:
                        pass
                    hist_s = self._suppression_history.setdefault(ev.tenant_id, [])
                    hist_s.append((suppressed, passed))
                    # enforce window similar to precision window (reuse _rolling_window_size)
                    if len(hist_s) > self._rolling_window_size:
                        hist_s.pop(0)
                    total_sup = sum(s for s, _ in hist_s)
                    total_pass = sum(p for _, p in hist_s)
                    denom = total_sup + total_pass
                    if denom > 0:
                        rate = total_sup / denom
                        metrics.FUSION_SUPPRESSION_RATE.labels(tenant=ev.tenant_id).set(rate)  # type: ignore[attr-defined]
                        try:
                            alert_thr = runtime_params.get_param("fusion.suppression_alert_rate") or 0.85
                        except Exception:
                            alert_thr = 0.85
                        if rate >= float(alert_thr):
                            metrics.FUSION_SUPPRESSION_ALERTS_TOTAL.labels(tenant=ev.tenant_id, strategy=meta.get("strategy", "?")).inc()  # type: ignore[attr-defined]
                            # Record alert in executive aggregator (best-effort)
                            try:
                                agg = _exec_agg()
                                if agg:
                                    agg.record_alert()
                            except Exception:
                                pass
                        # --- Adaptive suppression autotune (Batch 5) ---
                        try:
                            # Guard: only attempt if strategy is weighted_sum
                            strat = runtime_params.get_param("detection.fusion.strategy")
                            if strat == "weighted_sum":
                                # Read precision proxy tallies for tenant
                                pp = self._precision_proxy.get(ev.tenant_id) or {}
                                windows = pp.get("windows", 0) or 0
                                fp_snn = pp.get("fp_snn", 0) or 0
                                fp_baseline = pp.get("fp_baseline", 0) or 0
                                if windows >= 20:  # need enough samples
                                    snn_fp_rate = fp_snn / windows if windows else 0.0
                                    base_fp_rate = fp_baseline / windows if windows else 0.0
                                    # Retrieve current threshold and bounds
                                    try:
                                        thr_key = "fusion.weighted_sum.suppress_threshold"
                                        current_thr = float(runtime_params.get_param(thr_key) or 0.5)
                                    except Exception:
                                        current_thr = 0.5
                                    # Desired direction: if SNN FP rate >> baseline FP rate raise threshold slightly; if SNN FP rate << baseline lower threshold to recover recall
                                    # Compute delta with dampening + clamp
                                    diff = snn_fp_rate - base_fp_rate
                                    adjust = 0.0
                                    # tolerance band to avoid churn
                                    tol = 0.05
                                    if diff > tol:
                                        adjust = +0.01  # raise threshold (more suppression)
                                    elif diff < -tol:
                                        adjust = -0.01  # lower threshold (less suppression)
                                    if adjust != 0.0:
                                        # Global guard rails
                                        new_thr = current_thr + adjust
                                        # Hard clamps (configurable future params)
                                        if new_thr < 0.05:
                                            new_thr = 0.05
                                        if new_thr > 0.95:
                                            new_thr = 0.95
                                        # Only update if change is meaningful and won't oscillate too fast
                                        last_adj_meta = getattr(self, "_last_autotune", {})
                                        last_tenant_adj = last_adj_meta.get(ev.tenant_id, 0)
                                        now_ts = time.time()
                                        # rate limit: at most 1 adjustment per 50 windows (~) or 30s
                                        allow = True
                                        if isinstance(last_tenant_adj, (int, float)) and (now_ts - last_tenant_adj) < 30:
                                            allow = False
                                        # Enforce governance.autotune.max_per_hour rate limit
                                        max_per_hour = 0
                                        try:
                                            max_per_hour = int(runtime_params.get_param("governance.autotune.max_per_hour") or 0)
                                        except Exception:
                                            max_per_hour = 0
                                        if max_per_hour > 0:
                                            ts_list = self._autotune_ts.setdefault(ev.tenant_id, [])
                                            now_cut = now_ts - 3600
                                            ts_list[:] = [t for t in ts_list if t >= now_cut]
                                            if len(ts_list) >= max_per_hour:
                                                allow = False
                                        if allow and abs(new_thr - current_thr) >= 0.005:
                                            try:
                                                runtime_params.update_param(thr_key, round(new_thr, 4), reason="autotune_suppression", actor="governance")
                                                metrics.FUSION_SUPPRESS_AUTOTUNE_ADJUSTMENTS_TOTAL.labels(tenant=ev.tenant_id, direction="up" if adjust > 0 else "down", reason="fp_rate_diff").inc()  # type: ignore[attr-defined]
                                                metrics.GOVERNANCE_ACTIONS_TOTAL.labels(tenant=ev.tenant_id, action="autotune_suppression", detail="up" if adjust > 0 else "down").inc()  # type: ignore[attr-defined]
                                                try:
                                                    metrics.GOV_ACTION_AUTOTUNE_TOTAL.labels(tenant=ev.tenant_id, direction="up" if adjust > 0 else "down").inc()  # type: ignore[attr-defined]
                                                except Exception:
                                                    pass
                                                # Track timestamp
                                                if not hasattr(self, "_last_autotune"):
                                                    self._last_autotune = {}
                                                self._last_autotune[ev.tenant_id] = now_ts
                                                if max_per_hour > 0:
                                                    ts_list = self._autotune_ts.setdefault(ev.tenant_id, [])
                                                    ts_list.append(now_ts)
                                                # Update gauge with latest threshold
                                                try:
                                                    metrics.FUSION_SUPPRESS_THRESHOLD.labels(tenant=ev.tenant_id).set(new_thr)  # type: ignore[attr-defined]
                                                except Exception:
                                                    pass
                                                self._record_gov_action(ev.tenant_id, {
                                                    "ts": now_ts,
                                                    "action": "autotune_suppression",
                                                    "direction": "up" if adjust > 0 else "down",
                                                    "old": current_thr,
                                                    "new": new_thr,
                                                    "snn_fp_rate": snn_fp_rate,
                                                    "baseline_fp_rate": base_fp_rate
                                                })
                                            except Exception:
                                                pass
                        except Exception:
                            pass
                        # --- Strategy fallback logic (Batch 5) ---
                        try:
                            # Conditions: high sustained suppression rate + elevated SNN FP rate relative to baseline OR absolute high SNN FP rate
                            strat = runtime_params.get_param("detection.fusion.strategy")
                            if strat == "weighted_sum":  # only fallback from weighted_sum for now
                                pp = self._precision_proxy.get(ev.tenant_id) or {}
                                windows = pp.get("windows", 0) or 0
                                if windows >= 40:  # need more evidence
                                    fp_snn = pp.get("fp_snn", 0) or 0
                                    fp_base = pp.get("fp_baseline", 0) or 0
                                    snn_rate = fp_snn / windows if windows else 0.0
                                    base_rate = fp_base / windows if windows else 0.0
                                    # Thresholds (could later become params)
                                    high_sup = rate >= 0.9
                                    snn_excess = (snn_rate - base_rate) >= 0.10  # 10pp higher
                                    high_abs_snn = snn_rate >= 0.5  # absolute poor precision proxy
                                    if high_sup and (snn_excess or high_abs_snn):
                                        import time as _t_fb
                                        _fb_start = _t_fb.perf_counter()
                                        # Fallback to baseline_priority
                                        try:
                                            runtime_params.update_param("detection.fusion.strategy", "baseline_priority", reason="strategy_fallback", actor="governance")
                                            metrics.FUSION_STRATEGY_FALLBACK_TOTAL.labels(tenant=ev.tenant_id, **{"from": "weighted_sum", "reason": "high_suppression_fp_snn"}).inc()  # type: ignore[attr-defined]
                                            metrics.GOVERNANCE_ACTIONS_TOTAL.labels(tenant=ev.tenant_id, action="strategy_fallback", detail="weighted_sum->baseline_priority").inc()  # type: ignore[attr-defined]
                                            try:
                                                # Reserved keywords 'from' and 'to' cannot be passed directly as kwargs; use dict expansion
                                                metrics.GOV_ACTION_STRATEGY_FALLBACK_TOTAL.labels(tenant=ev.tenant_id, **{"from": "weighted_sum", "to": "baseline_priority", "reason": "high_suppression_fp_snn"}).inc()  # type: ignore[attr-defined]
                                            except Exception:
                                                pass
                                            self._record_gov_action(ev.tenant_id, {
                                                "ts": time.time(),
                                                "action": "strategy_fallback",
                                                "from": "weighted_sum",
                                                "to": "baseline_priority",
                                                "reason": "high_suppression_fp_snn",
                                                "suppression_rate": rate,
                                                "snn_fp_rate": snn_rate,
                                                "baseline_fp_rate": base_rate
                                            })
                                            try:
                                                _fb_elapsed = _t_fb.perf_counter() - _fb_start
                                                metrics.FUSION_STRATEGY_FALLBACK_LATENCY_SECONDS.labels(tenant=ev.tenant_id).observe(_fb_elapsed)  # type: ignore[attr-defined]
                                            except Exception:
                                                pass
                                        except Exception:
                                            pass
                        except Exception:
                            pass
                        # --- Drift guard gating SNN (Batch 5) ---
                        self._maybe_drift_guard(ev.tenant_id, suppression_rate=rate)
                        # --- Governance shadow recommendations (helper) ---
                        try:
                            self._maybe_shadow_recommendation(ev.tenant_id)
                        except Exception:
                            pass
                except Exception:
                    pass
                # Add trace record (best-effort)
                try:
                    trace_det = []
                    for name, results in detector_results.items():
                        trace_det.append({
                            "name": name,
                            "fired": bool(results),
                            "anomalies": results[:5],  # cap details per detector
                        })
                    traces().add({
                        "event_id": getattr(ev, 'event_id', None),
                        "tenant": getattr(ev, 'tenant_id', None),
                        "timestamp": getattr(ev, 'timestamp', None),
                        "detectors": trace_det,
                        "fusion": {
                            "strategy": meta.get("strategy") if isinstance(meta, dict) else None,
                            "suppressed": suppressed,
                            "fused_count": len(fused_results),
                        },
                    })
                except Exception:
                    pass
                # Basic overlap/unique fusion metrics
                try:
                    baseline_anoms = detector_results.get("baseline") or []
                    snn_anoms = detector_results.get("snn") or []
                    has_baseline = bool(baseline_anoms)
                    has_snn = bool(snn_anoms)
                    union = 1 if (has_baseline or has_snn) else 0
                    overlap = 1 if (has_baseline and has_snn) else 0
                    outcome = "none"
                    if overlap:
                        outcome = "overlap"
                    elif has_baseline and not has_snn:
                        outcome = "baseline_only"
                    elif has_snn and not has_baseline:
                        outcome = "snn_only"
                    metrics.FUSION_DECISIONS_TOTAL.labels(tenant=ev.tenant_id, outcome=outcome).inc()  # type: ignore[attr-defined]
                    # Precision proxy update
                    try:
                        meta_ev = getattr(ev, 'metadata', {}) or {}
                        pattern_label = meta_ev.get('synthetic_pattern') or meta_ev.get('syntheticPattern')
                        if pattern_label == 'noise':
                            state = self._precision_proxy.setdefault(ev.tenant_id, {"windows": 0, "fp_baseline": 0, "fp_snn": 0, "fp_temporal": 0})
                            state["windows"] += 1
                            metrics.PRECISION_PROXY_WINDOWS.labels(tenant=ev.tenant_id).inc()  # type: ignore[attr-defined]
                            if has_baseline:
                                state["fp_baseline"] += 1
                                metrics.PRECISION_PROXY_FALSE_POSITIVE.labels(tenant=ev.tenant_id, detector='baseline').inc()  # type: ignore[attr-defined]
                            if has_snn:
                                state["fp_snn"] += 1
                                metrics.PRECISION_PROXY_FALSE_POSITIVE.labels(tenant=ev.tenant_id, detector='snn').inc()  # type: ignore[attr-defined]
                            temporal_anoms = detector_results.get("temporal") or []
                            if temporal_anoms:
                                state["fp_temporal"] += 1
                                metrics.PRECISION_PROXY_FALSE_POSITIVE.labels(tenant=ev.tenant_id, detector='temporal').inc()  # type: ignore[attr-defined]
                            windows_pp = state["windows"] or 0
                            if windows_pp:
                                metrics.PRECISION_PROXY_RATE.labels(tenant=ev.tenant_id, detector='baseline').set(state["fp_baseline"] / windows_pp)  # type: ignore[attr-defined]
                                metrics.PRECISION_PROXY_RATE.labels(tenant=ev.tenant_id, detector='snn').set(state["fp_snn"] / windows_pp)  # type: ignore[attr-defined]
                                metrics.PRECISION_PROXY_RATE.labels(tenant=ev.tenant_id, detector='temporal').set(state["fp_temporal"] / windows_pp)  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    if union:
                        ratio = overlap / union if union else 0.0
                        metrics.FUSION_OVERLAP_RATIO.labels(tenant=ev.tenant_id).set(ratio)  # type: ignore[attr-defined]
                        baseline_unique = 1 if (has_baseline and not has_snn) else 0
                        snn_unique = 1 if (has_snn and not has_baseline) else 0
                        safe_union = union if union else 1
                        metrics.FUSION_BASELINE_UNIQUE_RATIO.labels(tenant=ev.tenant_id).set(baseline_unique / safe_union)  # type: ignore[attr-defined]
                        metrics.FUSION_SNN_UNIQUE_RATIO.labels(tenant=ev.tenant_id).set(snn_unique / safe_union)  # type: ignore[attr-defined]
                        combo_label = []
                        if has_baseline:
                            combo_label.append("baseline")
                        if has_snn:
                            combo_label.append("snn")
                        if combo_label:
                            metrics.FUSION_SOURCE_COMBO_TOTAL.labels(tenant=ev.tenant_id, combo="+".join(combo_label)).inc()  # type: ignore[attr-defined]
                        hist = self._fusion_history.setdefault(ev.tenant_id, [])
                        try:
                            desired = runtime_params.get_param("fusion.precision_window") or self._rolling_window_size
                            if isinstance(desired, int) and 10 <= desired <= 10_000:
                                self._rolling_window_size = desired
                        except Exception:
                            pass
                        hist.append((snn_unique, union))
                        if len(hist) > self._rolling_window_size:
                            hist.pop(0)
                        total_union = sum(u for _, u in hist) or 1
                        total_snn_unique = sum(s for s, _ in hist)
                        rolling_ratio = total_snn_unique / total_union
                        metrics.FUSION_SNN_UNIQUE_RATIO_ROLLING.labels(tenant=ev.tenant_id).set(rolling_ratio)  # type: ignore[attr-defined]
                        try:
                            suppression_latest = metrics.FUSION_SUPPRESSION_RATE.labels(tenant=ev.tenant_id)._value.get() if hasattr(metrics.FUSION_SUPPRESSION_RATE.labels(tenant=ev.tenant_id), '_value') else 0.0  # type: ignore[attr-defined]
                        except Exception:
                            suppression_latest = 0.0
                        try:
                            agg = _exec_agg()
                            if agg:
                                agg.record_fusion(overlap_ratio=ratio, snn_unique_ratio=rolling_ratio, suppression_rate=suppression_latest)
                                agg.record_anomalies(baseline=len(baseline_anoms), snn=len(snn_anoms))
                        except Exception:
                            pass
                except Exception:
                    pass
            # queue depth gauge
            try:
                try:
                    from core.main import _INGEST_BACKEND_SEL  # type: ignore
                except Exception:
                    _INGEST_BACKEND_SEL = None  # type: ignore
                if _INGEST_BACKEND_SEL is not None and _INGEST_BACKEND_SEL.backend.supports_depth:
                    depth = _INGEST_BACKEND_SEL.backend.qsize()
                else:
                    depth = self.ingestion.queue.qsize()
                metrics.INGEST_QUEUE_DEPTH.labels(tenant=ev.tenant_id).set(depth)  # type: ignore[attr-defined]
            except Exception:
                pass

    def _maybe_shadow_recommendation(self, tenant: str):
        """Emit shadow threshold adjustment recommendation (non-mutating) if heuristic conditions met."""
        try:
            shadow_enabled = False
            try:
                shadow_enabled = bool(runtime_params.get_param("governance.shadow.enabled")) if hasattr(runtime_params, 'get_param') else False
            except Exception:
                shadow_enabled = False
            if not shadow_enabled:
                return
            pp = self._precision_proxy.get(tenant) or {}
            windows = pp.get("windows", 0) or 0
            if windows < 30:
                return
            fp_snn = pp.get("fp_snn", 0) or 0
            fp_base = pp.get("fp_baseline", 0) or 0
            snn_rate = fp_snn / windows if windows else 0.0
            base_rate = fp_base / windows if windows else 0.0
            diff = snn_rate - base_rate
            if diff > 0.05:
                suggestion = {"action": "raise_threshold", "delta": 0.01, "reason": "shadow_fp_rate_diff", "diff": round(diff,4)}
            elif diff < -0.05:
                suggestion = {"action": "lower_threshold", "delta": -0.01, "reason": "shadow_fp_rate_diff", "diff": round(diff,4)}
            else:
                suggestion = None
            if suggestion:
                # Append to in-memory ring buffer for tenant (capped 200)
                try:
                    buf = self._gov_recommendations.setdefault(tenant, [])
                    rec = {"ts": time.time(), "tenant": tenant, "suggestion": suggestion}
                    buf.append(rec)
                    if len(buf) > 200:
                        del buf[: len(buf) - 200]
                except Exception:
                    pass
                try:
                    runtime_params.audit_agent_decision("governance_shadow", "recommend", {"tenant": tenant, "suggestion": suggestion})  # type: ignore[attr-defined]
                except Exception:
                    pass
        except Exception:
            pass

    # --- Accessor for recommendations (used by API endpoint) ---
    def list_governance_recommendations(self, tenant: str | None = None):
        try:
            if tenant:
                return list(self._gov_recommendations.get(tenant, []))
            # Flatten all tenants
            out: list[dict] = []
            for t, lst in self._gov_recommendations.items():
                out.extend(lst)
            # Return newest last as stored; caller can reverse
            return out
        except Exception:
            return []

    async def flush(self, max_items: int | None = None):
        """Drain remaining queued events synchronously.

        Parameters:
            max_items: optional safety cap to avoid infinite loops if queue refills.
        """
        processed = 0
        while True:
            if max_items is not None and processed >= max_items:
                break
            try:
                try:
                    from core.main import _INGEST_BACKEND_SEL  # type: ignore
                except Exception:
                    _INGEST_BACKEND_SEL = None  # type: ignore
                if _INGEST_BACKEND_SEL is not None:
                    try:
                        ev = _INGEST_BACKEND_SEL.backend.get_nowait()  # type: ignore[assignment]
                    except Exception:
                        ev = self.ingestion.queue.get_nowait()
                else:
                    ev = self.ingestion.queue.get_nowait()
            except Exception:
                break
            with metrics.PROCESSING_LATENCY.time():  # type: ignore
                detector_results = {}
                for det in registry.detectors():
                    try:
                        start_det = time.perf_counter()
                        res = det.process(ev) or []
                        elapsed = time.perf_counter() - start_det
                        try:
                            metrics.DETECTOR_LATENCY.labels(tenant=ev.tenant_id, detector=det.name).observe(elapsed)  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    except Exception:  # noqa: BLE001
                        res = []
                    detector_results[det.name] = res
                # SNN normalization (flush path) before fusion
                try:
                    from core.detect.snn_norm import normalizer as _snn_norm  # type: ignore
                    snn_list = detector_results.get("snn") or []
                    if snn_list:
                        for _rec in snn_list:
                            sc = _rec.get("score")
                            if sc is not None:
                                norm = _snn_norm().normalize(sc, ev.tenant_id)
                                _rec["normalized_score"] = norm
                except Exception:
                    pass
                try:
                    fused_results, meta = arbitrator().fuse(detector_results)
                    suppressed = int(meta.get("suppressed", 0)) if isinstance(meta, dict) else 0
                    passed = len(fused_results)
                    # Risk overlay enrichment in flush path (best-effort)
                    try:
                        await self._apply_risk_overlay(fused_results)
                    except Exception:
                        pass
                    try:
                        import time as _t_mem
                        _mem_start = _t_mem.perf_counter()
                        self._maybe_memory_trigger(fused_results)
                        try:
                            _mem_elapsed = _t_mem.perf_counter() - _mem_start
                            metrics.MEMORY_SIGNAL_GATING_LATENCY_SECONDS.observe(_mem_elapsed)  # type: ignore[attr-defined]
                        except Exception:
                            pass
                    except Exception:
                        pass
                    # Semantic enrichment attach (flush path)
                    try:
                        attach_enabled = bool(runtime_params.get_param("retrieval.context.attach.enabled"))
                    except Exception:
                        attach_enabled = False
                    if attach_enabled and fused_results:
                        try:
                            top_k_ctx = int(runtime_params.get_param("retrieval.context.attach.top_k") or 3)
                        except Exception:
                            top_k_ctx = 3
                        try:
                            from core.retrieval.interface import retrieve_context as _retrieve_context  # type: ignore
                        except Exception:
                            _retrieve_context = None  # type: ignore
                        for _rec in fused_results:
                            if not _retrieve_context:
                                try:
                                    metrics.RETRIEVAL_CONTEXT_ATTACH_TOTAL.labels(tenant=ev.tenant_id, status="skipped").inc()  # type: ignore[attr-defined]
                                except Exception:
                                    pass
                                continue
                            try:
                                cat = _rec.get("category") or _rec.get("type") or ""
                                chunks = _retrieve_context(cat, k=top_k_ctx) if cat is not None else []  # type: ignore
                                _rec["context"] = [
                                    {k2: c.get(k2) for k2 in ("doc", "chunk_id", "score", "explanation") if isinstance(c, dict)}
                                    for c in (chunks or [])
                                ]
                                metrics.RETRIEVAL_CONTEXT_ATTACH_TOTAL.labels(tenant=ev.tenant_id, status="attached").inc()  # type: ignore[attr-defined]
                            except Exception:
                                try:
                                    metrics.RETRIEVAL_CONTEXT_ATTACH_TOTAL.labels(tenant=ev.tenant_id, status="skipped").inc()  # type: ignore[attr-defined]
                                except Exception:
                                    pass
                    elif fused_results:
                        for _rec in fused_results:
                            try:
                                metrics.RETRIEVAL_CONTEXT_ATTACH_TOTAL.labels(tenant=ev.tenant_id, status="skipped").inc()  # type: ignore[attr-defined]
                            except Exception:
                                pass
                    hist_s = self._suppression_history.setdefault(ev.tenant_id, [])
                    hist_s.append((suppressed, passed))
                    if len(hist_s) > self._rolling_window_size:
                        hist_s.pop(0)
                    total_sup = sum(s for s, _ in hist_s)
                    total_pass = sum(p for _, p in hist_s)
                    denom = total_sup + total_pass
                    if denom > 0:
                        rate = total_sup / denom
                        metrics.FUSION_SUPPRESSION_RATE.labels(tenant=ev.tenant_id).set(rate)  # type: ignore[attr-defined]
                        try:
                            alert_thr = runtime_params.get_param("fusion.suppression_alert_rate") or 0.85
                        except Exception:
                            alert_thr = 0.85
                        if rate >= float(alert_thr):
                            metrics.FUSION_SUPPRESSION_ALERTS_TOTAL.labels(tenant=ev.tenant_id, strategy=meta.get("strategy", "?")).inc()  # type: ignore[attr-defined]
                            try:
                                agg = _exec_agg()
                                if agg:
                                    agg.record_alert()
                            except Exception:
                                pass
                        try:
                            agg = _exec_agg()
                            if agg:
                                agg.record_fusion(overlap_ratio=0.0, snn_unique_ratio=0.0, suppression_rate=rate)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    trace_det = []
                    for name, results in detector_results.items():
                        trace_det.append({
                            "name": name,
                            "fired": bool(results),
                            "anomalies": results[:5],
                        })
                    traces().add({
                        "event_id": getattr(ev, 'event_id', None),
                        "tenant": getattr(ev, 'tenant_id', None),
                        "timestamp": getattr(ev, 'timestamp', None),
                        "detectors": trace_det,
                        "fusion": {
                            "strategy": meta.get("strategy") if isinstance(meta, dict) else None,
                            "suppressed": suppressed,
                            "fused_count": len(fused_results),
                        },
                    })
                except Exception:
                    pass
                try:
                    baseline_anoms = detector_results.get("baseline") or []
                    snn_anoms = detector_results.get("snn") or []
                    has_baseline = bool(baseline_anoms)
                    has_snn = bool(snn_anoms)
                    union = 1 if (has_baseline or has_snn) else 0
                    overlap = 1 if (has_baseline and has_snn) else 0
                    outcome = "none"
                    if overlap:
                        outcome = "overlap"
                    elif has_baseline and not has_snn:
                        outcome = "baseline_only"
                    elif has_snn and not has_baseline:
                        outcome = "snn_only"
                    metrics.FUSION_DECISIONS_TOTAL.labels(tenant=ev.tenant_id, outcome=outcome).inc()  # type: ignore[attr-defined]
                    try:
                        meta = getattr(ev, 'metadata', {}) or {}
                        pattern_label = meta.get('synthetic_pattern') or meta.get('syntheticPattern')
                        if pattern_label == 'noise':
                            state = self._precision_proxy.setdefault(ev.tenant_id, {"windows": 0, "fp_baseline": 0, "fp_snn": 0})
                            state["windows"] += 1
                            metrics.PRECISION_PROXY_WINDOWS.labels(tenant=ev.tenant_id).inc()  # type: ignore[attr-defined]
                            if has_baseline:
                                state["fp_baseline"] += 1
                                metrics.PRECISION_PROXY_FALSE_POSITIVE.labels(tenant=ev.tenant_id, detector='baseline').inc()  # type: ignore[attr-defined]
                            if has_snn:
                                state["fp_snn"] += 1
                                metrics.PRECISION_PROXY_FALSE_POSITIVE.labels(tenant=ev.tenant_id, detector='snn').inc()  # type: ignore[attr-defined]
                            windows = state["windows"] or 0
                            if windows:
                                metrics.PRECISION_PROXY_RATE.labels(tenant=ev.tenant_id, detector='baseline').set(state["fp_baseline"] / windows)  # type: ignore[attr-defined]
                                metrics.PRECISION_PROXY_RATE.labels(tenant=ev.tenant_id, detector='snn').set(state["fp_snn"] / windows)  # type: ignore[attr-defined]
                    except Exception:
                        pass
                    if union:
                        ratio = overlap / union if union else 0.0
                        metrics.FUSION_OVERLAP_RATIO.labels(tenant=ev.tenant_id).set(ratio)  # type: ignore[attr-defined]
                        baseline_unique = 1 if (has_baseline and not has_snn) else 0
                        snn_unique = 1 if (has_snn and not has_baseline) else 0
                        metrics.FUSION_BASELINE_UNIQUE_RATIO.labels(tenant=ev.tenant_id).set(baseline_unique / union)  # type: ignore[attr-defined]
                        metrics.FUSION_SNN_UNIQUE_RATIO.labels(tenant=ev.tenant_id).set(snn_unique / union)  # type: ignore[attr-defined]
                        combo_label = []
                        if has_baseline:
                            combo_label.append("baseline")
                        if has_snn:
                            combo_label.append("snn")
                        if combo_label:
                            metrics.FUSION_SOURCE_COMBO_TOTAL.labels(tenant=ev.tenant_id, combo="+".join(combo_label)).inc()  # type: ignore[attr-defined]
                        hist = self._fusion_history.setdefault(ev.tenant_id, [])
                        try:
                            desired = runtime_params.get_param("fusion.precision_window") or self._rolling_window_size
                            if isinstance(desired, int) and 10 <= desired <= 10_000:
                                self._rolling_window_size = desired
                        except Exception:
                            pass
                        hist.append((snn_unique, union))
                        if len(hist) > self._rolling_window_size:
                            hist.pop(0)
                        total_union = sum(u for _, u in hist) or 1
                        total_snn_unique = sum(s for s, _ in hist)
                        rolling_ratio = total_snn_unique / total_union
                        metrics.FUSION_SNN_UNIQUE_RATIO_ROLLING.labels(tenant=ev.tenant_id).set(rolling_ratio)  # type: ignore[attr-defined]
                        try:
                            suppression_latest = metrics.FUSION_SUPPRESSION_RATE.labels(tenant=ev.tenant_id)._value.get() if hasattr(metrics.FUSION_SUPPRESSION_RATE.labels(tenant=ev.tenant_id), '_value') else 0.0  # type: ignore[attr-defined]
                        except Exception:
                            suppression_latest = 0.0
                        try:
                            agg = _exec_agg()
                            if agg:
                                agg.record_fusion(overlap_ratio=ratio, snn_unique_ratio=rolling_ratio, suppression_rate=suppression_latest)
                        except Exception:
                            pass
                        try:
                            agg = _exec_agg()
                            if agg:
                                agg.record_anomalies(baseline=len(baseline_anoms), snn=len(snn_anoms))
                        except Exception:
                            pass
                except Exception:
                    pass
            try:
                try:
                    from core.main import _INGEST_BACKEND_SEL  # type: ignore
                except Exception:
                    _INGEST_BACKEND_SEL = None  # type: ignore
                if _INGEST_BACKEND_SEL is not None and _INGEST_BACKEND_SEL.backend.supports_depth:
                    depth = _INGEST_BACKEND_SEL.backend.qsize()
                else:
                    depth = self.ingestion.queue.qsize()
                metrics.INGEST_QUEUE_DEPTH.labels(tenant=ev.tenant_id).set(depth)  # type: ignore[attr-defined]
            except Exception:
                pass
            processed += 1
            # drift compute also during flush loop (mirrors async loop)
            try:
                drift_monitor().record(ev)
                self._events_seen += 1
                if self._events_seen % self._drift_compute_interval == 0:
                    drift_monitor().compute()
            except Exception:
                pass
        return processed

    def _memory_concurrency_limit(self) -> int:
        try:
            val = runtime_params.get_param("memory.jobs.active")
            if isinstance(val, (int,float)):
                return max(0, int(val))
        except Exception:
            pass
        return 2

    def _maybe_memory_trigger(self, anomalies):
        if not anomalies:
            return
        # Read thresholds
        try:
            conf_thr = float(runtime_params.get_param("memory.trigger.confidence_threshold") or 0.7)
            risk_thr = float(runtime_params.get_param("memory.trigger.risk_threshold") or 60.0)
        except Exception:
            conf_thr, risk_thr = 0.7, 60.0
        # Concurrency gate
        try:
            from forensics.memory import submit_memory_job  # type: ignore
            from forensics import memory as _mem  # type: ignore
        except Exception:
            return
        active = getattr(_mem, '_ACTIVE', 0)
        if active >= self._memory_concurrency_limit():
            return
        # Find candidate anomalies with low confidence (score) but high risk
        for a in anomalies:
            try:
                score = float(a.get("score") or a.get("fusion_decision_score") or 0.0)
                risk = float(a.get("risk_score") or 0.0)
                if score < conf_thr and risk >= risk_thr and a.get("asset_id"):
                    # Fire-and-forget task (async job)
                    import asyncio
                    ctx = {"score": score, "risk": risk, "triggers": a.get("triggers")}
                    # Create coroutine first so we can safely handle fallback without leaving it un-awaited
                    _coro = submit_memory_job(a.get("asset_id"), ctx)
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(_coro)
                    except RuntimeError:
                        # No running loop (common in sync test contexts). Best-effort execute immediately.
                        try:
                            asyncio.run(_coro)
                        except Exception:
                            pass
            except Exception:
                continue

    async def _apply_risk_overlay(self, anomalies):  # type: ignore[override]
        """Attach risk_score / risk_severity to anomalies lacking them.

        Looks up asset criticality & external_exposure from vuln_store (async Postgres fetch) in a batched fashion
        to reduce round trips (one multi-row query for unique asset_ids). Silent on errors.
        """
        if not anomalies:
            return
        # Collect asset ids needing enrichment
        pending: list[str] = []
        for a in anomalies:
            try:
                if a.get("asset_id") and (a.get("risk_score") is None):
                    pending.append(a.get("asset_id"))
            except Exception:
                continue
        if not pending:
            return
        # Deduplicate
        unique_ids = list({p for p in pending if isinstance(p, str)})
        if not unique_ids:
            return
        try:
            from storage import vuln_store  # type: ignore
        except Exception:
            return
        try:
            pg = getattr(vuln_store, 'postgres', None)  # type: ignore[attr-defined]
            if not pg:
                return
            # Single batched query (ANY($1)) pattern; fallback loop if unsupported
            rows = []
            try:
                rows = await pg.fetch("SELECT id, criticality, external_exposure FROM assets WHERE id = ANY($1)", unique_ids)  # type: ignore
            except Exception:
                # fallback individual fetches (still async sequential)
                rows = []
                for aid in unique_ids:
                    try:
                        r = await pg.fetch("SELECT id, criticality, external_exposure FROM assets WHERE id=$1", aid)  # type: ignore
                        if r:
                            rows.append(r[0])
                    except Exception:
                        continue
            risk_map: dict[str, tuple[float, str]] = {}
            for r in rows or []:
                try:
                    aid = r.get("id") or r.get("asset_id")
                    if not aid:
                        continue
                    crit = float(r.get("criticality") or 0.0)
                    ext = 1.0 if r.get("external_exposure") else 0.0
                    base = min(1.0, 0.7 * crit + 0.3 * ext)
                    sev = "low"
                    if base >= 0.7:
                        sev = "high"
                    elif base >= 0.4:
                        sev = "medium"
                    risk_map[str(aid)] = (round(base * 100.0, 3), sev)
                except Exception:
                    continue
            if not risk_map:
                return
            for a in anomalies:
                try:
                    aid = a.get("asset_id")
                    if aid and a.get("risk_score") is None and aid in risk_map:
                        sc, sev = risk_map[aid]
                        a["risk_score"] = sc
                        a["risk_severity"] = sev
                except Exception:
                    continue
        except Exception:
            return


def _exec_agg():  # lazy accessor to avoid circular import with core.main
    try:  # noqa: BLE001
        from core.main import executive_agg  # type: ignore
        return executive_agg
    except Exception:  # during early import or tests that only load pipeline
        return None


__all__ = ["Pipeline"]
