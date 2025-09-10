"""LLM Provider Abstraction.

Provides a pluggable interface for reasoning / summarization without hard dependency.

Modes:
 - noop: returns template or empty string
 - local: invokes a local model command (llama.cpp / gpt4all) via subprocess (stream disabled)
 - remote: placeholder (future OpenAI / Anthropic) behind budget guard
"""
from __future__ import annotations

from dataclasses import dataclass
import time, subprocess, json, shlex, threading
from typing import Optional, Dict, Any
from config import runtime_params

# Runtime params (will add later to schema if needed): llm.provider, llm.max_tokens, llm.enable
# For now rely on env flags to activate remote/local.

@dataclass
class LLMResult:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = "noop"
    latency_s: float = 0.0
    cached: bool = False

class LLMProvider:
    def generate(self, prompt: str, **kwargs) -> LLMResult:  # noqa: D401
        raise NotImplementedError

class NoOpProvider(LLMProvider):
    def generate(self, prompt: str, **kwargs) -> LLMResult:
        return LLMResult(text="", tokens_in=len(prompt.split()), tokens_out=0, model="noop", latency_s=0.0)

class LocalCommandProvider(LLMProvider):
    """Invokes a local model runner CLI.

    Environment variables:
      LLM_LOCAL_CMD e.g.: "llama.cpp -m ./models/phi3.bin -p '{prompt}' --n-predict 128"

    Placeholders:
      {prompt} substituted with shell-escaped prompt.
    """
    def __init__(self, max_tokens: int = 256, timeout_s: float = 15.0):
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s

    def generate(self, prompt: str, **kwargs) -> LLMResult:
        cmd_tpl = runtime_params.get_param("llm.local.command") or None
        if not cmd_tpl:
            return LLMResult(text="", model="local-missing-cmd")
        safe_prompt = prompt.replace("'", " ")[:4000]
        cmd = cmd_tpl.format(prompt=safe_prompt, max_tokens=self.max_tokens)
        start = time.time()
        try:
            proc = subprocess.run(shlex.split(cmd), capture_output=True, timeout=self.timeout_s, text=True)
            text = proc.stdout.strip().splitlines()[-1] if proc.stdout else ""
            return LLMResult(text=text, tokens_in=len(prompt.split()), tokens_out=len(text.split()), model="local", latency_s=time.time()-start)
        except Exception as e:  # noqa: BLE001
            return LLMResult(text=f"error: {e}", model="local-error")

class RemoteProvider(LLMProvider):
    """Placeholder remote provider (future OpenAI / Anthropic) respecting budget guard."""
    def __init__(self):
        self._spent_usd = 0.0
        self._lock = threading.Lock()
        self._max_hourly = float(runtime_params.get_param("llm.cost.max_usd_per_hour") or 1.0)
        self._window_start = time.time()

    def _allow(self) -> bool:
        with self._lock:
            now = time.time()
            if now - self._window_start > 3600:
                self._window_start = now
                self._spent_usd = 0.0
            return self._spent_usd < self._max_hourly

    def _record(self, est_cost: float):
        with self._lock:
            self._spent_usd += est_cost

    def generate(self, prompt: str, **kwargs) -> LLMResult:
        if not self._allow():
            return LLMResult(text="budget_exhausted", model="remote-blocked")
        # Stub: remote disabled until implemented
        return LLMResult(text="remote_not_configured", model="remote-stub")

# Provider factory
_CACHE: Dict[str, LLMProvider] = {}

def get_provider() -> LLMProvider:
    mode = runtime_params.get_param("llm.provider") or "noop"
    if mode in _CACHE:
        return _CACHE[mode]
    if mode == "local":
        prov = LocalCommandProvider()
    elif mode == "remote":
        prov = RemoteProvider()
    else:
        prov = NoOpProvider()
    _CACHE[mode] = prov
    return prov

__all__ = ["LLMProvider", "LLMResult", "get_provider", "NoOpProvider", "LocalCommandProvider", "RemoteProvider"]
