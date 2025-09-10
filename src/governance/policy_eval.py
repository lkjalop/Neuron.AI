"""Governance Policy Evaluation Loop.

Periodically evaluates loaded policy compliance using policy.compliance.compute_score.
Emits metrics and writes signed snapshot (if enabled via runtime params).
"""
from __future__ import annotations
import asyncio, json, time, logging, pathlib, os
from typing import Optional, Dict, Any

log = logging.getLogger("neuron.governance.policy")

try:
    from policy import compliance  # type: ignore
except Exception:  # pragma: no cover
    compliance = None  # type: ignore

try:
    from config import runtime_params  # type: ignore
except Exception:  # pragma: no cover
    runtime_params = None  # type: ignore

try:
    from core import metrics  # type: ignore
except Exception:  # pragma: no cover
    metrics = None  # type: ignore

_POLICY_FILE = pathlib.Path("config/policy.json")
_LAST_SCORE: Dict[str, Any] | None = None
_TASK: asyncio.Task | None = None

async def _loop():  # pragma: no cover (timing dependent)
    global _LAST_SCORE
    while True:
        try:
            if not runtime_params or not bool(int(runtime_params.get_param("governance.policy.eval.enabled") or 0)):
                await asyncio.sleep(5)
                continue
            interval = int(runtime_params.get_param("governance.policy.eval.interval_s") or 600)
            policy = _load_policy()
            if policy and compliance:
                start = time.time()
                score = compliance.compute_score(policy)
                _LAST_SCORE = score
                _emit_metrics(score)
                _maybe_snapshot(score)
                dur = time.time() - start
                log.debug("policy_eval score=%s dur=%.4fs", score.get("score"), dur)
            else:
                log.debug("policy_eval skipped: no policy or compliance module")
                if metrics and hasattr(metrics, 'GOVERNANCE_POLICY_EVAL_TOTAL'):
                    try: metrics.GOVERNANCE_POLICY_EVAL_TOTAL.labels(outcome="error").inc()  # type: ignore
                    except Exception: pass
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        except Exception as e:  # noqa: BLE001
            log.exception("policy_eval_loop_error: %s", e)
            if metrics and hasattr(metrics, 'GOVERNANCE_POLICY_EVAL_TOTAL'):
                try: metrics.GOVERNANCE_POLICY_EVAL_TOTAL.labels(outcome="error").inc()  # type: ignore
                except Exception: pass
            await asyncio.sleep(10)


def _emit_metrics(score: Dict[str, Any]) -> None:
    if not metrics:
        return
    try:
        if hasattr(metrics, 'GOVERNANCE_POLICY_EVAL_TOTAL'):
            metrics.GOVERNANCE_POLICY_EVAL_TOTAL.labels(outcome="success").inc()  # type: ignore
        if hasattr(metrics, 'GOVERNANCE_POLICY_SCORE'):
            metrics.GOVERNANCE_POLICY_SCORE.labels(policy_id=str(score.get("policy_id"))).set(float(score.get("score", 0.0)))  # type: ignore
        comps = score.get("components", {}) or {}
        if hasattr(metrics, 'GOVERNANCE_POLICY_COMPONENT'):
            for k, v in comps.items():
                try:
                    metrics.GOVERNANCE_POLICY_COMPONENT.labels(policy_id=str(score.get("policy_id")), component=k).set(float(v))  # type: ignore
                except Exception:
                    pass
    except Exception:  # pragma: no cover
        pass


def _maybe_snapshot(score: Dict[str, Any]) -> None:
    try:
        if not runtime_params:
            return
        if not bool(int(runtime_params.get_param("governance.policy.eval.sign") or 0)):
            return
        if not compliance:
            return
        signed = compliance.sign_snapshot(score)
        compliance.write_snapshot(signed)
    except Exception:  # pragma: no cover
        log.debug("policy_snapshot_error", exc_info=True)


def _load_policy() -> Optional[Dict[str, Any]]:
    try:
        if _POLICY_FILE.exists():
            return json.loads(_POLICY_FILE.read_text(encoding="utf-8"))
    except Exception:
        log.warning("policy_load_error", exc_info=True)
    return None


def last_score() -> Dict[str, Any] | None:
    return _LAST_SCORE


def start(loop: asyncio.AbstractEventLoop) -> None:
    global _TASK
    if _TASK is None:
        _TASK = loop.create_task(_loop())
        log.info("governance policy evaluation loop started")


def stop() -> None:
    global _TASK
    if _TASK:
        _TASK.cancel()
        _TASK = None
        log.info("governance policy evaluation loop stopped")

__all__ = ["start", "stop", "last_score"]
