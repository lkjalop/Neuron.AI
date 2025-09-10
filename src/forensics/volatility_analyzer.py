"""Volatility3 analyzer wrapper (behind runtime flag).

Provides a lightweight interface to execute selected Volatility3 plugins
against a provided memory dump and parse tabular outputs into structured
artifacts, with basic severity tagging heuristics.

Design goals:
- Best-effort: gracefully handle missing volatility3 installation or
  plugin/imagery errors and return an informative result.
- Conservative defaults: Windows-centric plugins; no symbol downloads.
- Time-bounded execution using subprocess with a soft timeout.

Expected runtime params (read by caller):
- forensics.volatility.enabled -> bool
- forensics.volatility.plugins -> list[str] or comma-separated str
- forensics.volatility.max_runtime_s -> int/float
"""
from __future__ import annotations

from typing import List, Dict, Any, Tuple
import json, subprocess, sys, shlex, os


def _severity_for_plugin_row(plugin: str, row: Dict[str, Any]) -> str:
    """Heuristic severity tags per plugin.

    - windows.pslist: flag known LOLBINs as medium.
    - windows.netscan: listening on high ports (>= 49152) as medium; known C2 ports high.
    - windows.dlllist: unsigned modules low.
    - handles: default low for interesting object types.
    """
    p = plugin.lower()
    try:
        if "pslist" in p:
            name = str(row.get("Name") or row.get("ImageFileName") or "").lower()
            if name in {"powershell.exe", "cmd.exe", "wscript.exe", "mshta.exe", "rundll32.exe"}:
                return "medium"
            return "low"
        if "netscan" in p:
            lport = int(row.get("LocalPort") or row.get("LPort") or 0)
            state = str(row.get("State") or "").upper()
            fport = int(row.get("ForeignPort") or row.get("FPort") or 0)
            # Known suspicious remote ports
            if fport in {4444, 1337, 9001} and state == "ESTABLISHED":
                return "high"
            if state == "LISTENING" and lport >= 49152:
                return "medium"
            return "low"
        if "dlllist" in p:
            signer = str(row.get("Signer") or row.get("Signature") or "").lower()
            if signer in {"", "n/a", "unsigned"}:
                return "low"
            return "low"
        if "handles" in p:
            typ = str(row.get("Type") or "").lower()
            if typ in {"process", "thread", "mutant"}:
                return "low"
            return "low"
    except Exception:
        return "low"
    return "low"


class VolatilityAnalyzer:
    """Wrapper to invoke volatility3 via its CLI renderer and parse JSON.

    Uses subprocess to call `python -m volatility3` with `-r json` and a
    conservative plugin list. This avoids deep framework API coupling.
    """

    def __init__(self, python_exe: str | None = None):
        self.python_exe = python_exe or sys.executable

    def _find_vol_command(self) -> List[str]:
        # Prefer `python -m volatility3` to ensure we use the same interpreter.
        return [self.python_exe, "-m", "volatility3"]

    def _run_plugin(self, dump_path: str, plugin: str, timeout_s: float) -> Tuple[str, str, int]:
        cmd = self._find_vol_command() + ["-f", dump_path, plugin, "-r", "json"]
        # Some environments expose `volatility3.cli` entrypoint instead.
        env = os.environ.copy()
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=max(1.0, timeout_s),
                check=False,
                text=True,
            )
            return proc.stdout, proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as e:
            return "", f"timeout:{e}", 124
        except Exception as e:
            return "", f"error:{e}", 1

    def _parse_json_rows(self, raw: str) -> List[Dict[str, Any]]:
        # Volatility3 JSON renderer typically outputs a JSON document; be permissive.
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except Exception:
            # Attempt to locate the last JSON object in a mixed stream
            try:
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(raw[start:end])
                else:
                    return []
            except Exception:
                return []
        # The structure varies; attempt common patterns: {"rows":[...]}, or list
        if isinstance(data, dict):
            rows = data.get("rows") or data.get("data") or data.get("result")
            if isinstance(rows, list):
                return [r for r in rows if isinstance(r, dict)]
            # Some renderers put columns + rows
            if "columns" in data and "rows" in data and isinstance(data["rows"], list):
                return [r for r in data["rows"] if isinstance(r, dict)]
        elif isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        return []

    def analyze(self, dump_path: str, plugins: List[str], max_runtime_s: float = 60.0) -> Dict[str, Any]:
        artifacts: List[Dict[str, Any]] = []
        errors: Dict[str, str] = {}
        ran: List[str] = []
        per_plugin_timeout = max(1.0, float(max_runtime_s) / max(1, len(plugins)))
        for plugin in plugins:
            out, err, code = self._run_plugin(dump_path, plugin, timeout_s=per_plugin_timeout)
            if code != 0:
                errors[plugin] = (err or f"exit:{code}")[:500]
                continue
            rows = self._parse_json_rows(out)
            for row in rows:
                artifacts.append({
                    "type": plugin,
                    "data": row,
                    "severity": _severity_for_plugin_row(plugin, row),
                    "source": "volatility3",
                })
            ran.append(plugin)
        summary = {
            "plugins_ran": ran,
            "plugins_requested": plugins,
            "artifact_count": len(artifacts),
            "errors": errors,
        }
        return {"artifacts": artifacts, "summary": summary}


__all__ = ["VolatilityAnalyzer"]
