"""Rule-based NLP query translator (Phase 1 IR implementation).

Produces an intermediate representation (IR) aligned with docs/NLP_QUERY_SCHEMA.md.

IR Shape:
{
  'domain': 'vulnerabilities' | 'findings',
  'clauses': [ { 'type': str, ... } ],
  'meta': {
      'confidence': float,
      'fallback_used': bool,
      'tokens': [ { raw, normalized, tag } ],
      'unparsed_tokens': [str]
  }
}

Parsing Strategy (heuristic, deterministic):
 1. Tokenize on whitespace & punctuation.
 2. Identify severity words (allow multiple) -> severity IN clause.
 3. Detect exploit status tokens (exploit, exploited, exploitable) -> exploit_status clause.
 4. Age patterns:  "older than N days" | ">N days" | "age > N" -> age clause (operator '>').
 5. Limit patterns:  "top N" | "first N" | "limit N" -> limit clause.
 6. Sort hints: "sort by X" or phrases like "highest severity" -> sort clause.
 7. Domain inference: mention of "finding" / "findings" selects findings domain; default vulnerabilities.
Confidence Heuristic: (# recognized semantic tokens) / (total tokens) ^ 0.65 (mild smoothing), bounded [0,1].

Future Upgrades: boolean logic, asset filters, date ranges.
"""
from __future__ import annotations

import re, math
from typing import Dict, Any, List

SEVERITY_WORDS = {
    'critical': 'CRITICAL',
    'high': 'HIGH',
    'medium': 'MEDIUM',
    'low': 'LOW'
}

SORT_FIELD_ALIASES = {
    'severity': 'severity',
    'risk': 'risk_score',
    'risk_score': 'risk_score',
    'score': 'risk_score',
    'age': 'age_days',
    'age_days': 'age_days'
}

TOKEN_SPLIT_RE = re.compile(r"[\s,;]+")
INT_RE = re.compile(r"^\d{1,5}$")
CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)
ASSET_PREFIX_RE = re.compile(r"^(asset:|host:)([A-Za-z0-9_.\-]+)$", re.IGNORECASE)


def _tokenize(q: str) -> List[str]:
    raw_tokens = [t for t in TOKEN_SPLIT_RE.split(q.strip()) if t]
    return raw_tokens


def translate(query: str) -> Dict[str, Any]:  # noqa: C901 (complexity acceptable for deterministic rules)
    ql = query.lower().strip()
    tokens = _tokenize(ql)
    recognized: List[dict] = []
    unparsed: List[str] = []
    clauses: List[dict] = []
    domain = 'vulnerabilities'

    # Domain detection
    if any(t.startswith('finding') for t in tokens):
        domain = 'findings'
        recognized.append({'raw': 'findings', 'normalized': 'findings', 'tag': 'domain'})

    # Severity (allow multi). Collect unique order-of-appearance.
    severities = []
    for i, t in enumerate(tokens):
        sev = SEVERITY_WORDS.get(t)
        if sev and sev not in severities:
            severities.append(sev)
            recognized.append({'raw': t, 'normalized': sev, 'tag': 'severity'})
    if severities:
        op = 'in' if len(severities) > 1 else 'equals'
        clauses.append({'type': 'severity', 'operator': op, 'values' if op == 'in' else 'value': severities if op == 'in' else severities[0]})  # type: ignore[arg-type]

    # Exploit status
    if any(t.startswith('exploit') or t in {'exploited', 'exploitable'} for t in tokens):
        clauses.append({'type': 'exploit_status', 'operator': 'equals', 'value': True})
        recognized.append({'raw': 'exploit', 'normalized': 'exploit_status', 'tag': 'exploit_status'})

    # Age patterns
    age_val = None
    # older than N days
    m = re.search(r"older than (\d{1,4}) days", ql)
    if m:
        age_val = int(m.group(1))
    if age_val is None:
        # >N days or age > N
        m2 = re.search(r">\s?(\d{1,4})\s?days", ql) or re.search(r"age\s*>\s*(\d{1,4})", ql)
        if m2:
            age_val = int(m2.group(1))
    if age_val is not None:
        clauses.append({'type': 'age', 'operator': '>', 'value': age_val})
        recognized.append({'raw': str(age_val), 'normalized': str(age_val), 'tag': 'age_threshold'})

    # Limit
    limit_val = None
    m = re.search(r"\b(top|first|limit) (\d{1,4})\b", ql)
    if m:
        limit_val = int(m.group(2))
    if limit_val is not None:
        clauses.append({'type': 'limit', 'value': limit_val})
        recognized.append({'raw': str(limit_val), 'normalized': str(limit_val), 'tag': 'limit'})

    # Sort
    sort_field = None
    # explicit phrase sort by X
    m = re.search(r"sort by (\w+)", ql)
    if m:
        cand = m.group(1)
        if cand in SORT_FIELD_ALIASES:
            sort_field = SORT_FIELD_ALIASES[cand]
            recognized.append({'raw': cand, 'normalized': sort_field, 'tag': 'sort_field'})
    # heuristics
    if not sort_field:
        if 'highest severity' in ql or 'highest risk' in ql:
            sort_field = 'severity'
            recognized.append({'raw': 'highest', 'normalized': 'severity', 'tag': 'sort_field'})
        elif 'oldest' in tokens:
            sort_field = 'age_days'
            recognized.append({'raw': 'oldest', 'normalized': 'age_days', 'tag': 'sort_field'})
    if sort_field:
        clauses.append({'type': 'sort', 'field': sort_field, 'direction': 'desc'})

    # CVE extraction
    cves = []
    for m in CVE_RE.finditer(query):
        cve_norm = m.group(0).upper()
        if cve_norm not in cves:
            cves.append(cve_norm)
            recognized.append({'raw': m.group(0), 'normalized': cve_norm, 'tag': 'cve'})
    if cves:
        op = 'in' if len(cves) > 1 else 'equals'
        clauses.append({'type': 'cve_id', 'operator': op, 'values' if op == 'in' else 'value': cves if op == 'in' else cves[0]})  # type: ignore[arg-type]

    # Asset / host filters via prefixed tokens asset:ID or host:NAME
    assets = []
    for t in tokens:
        am = ASSET_PREFIX_RE.match(t)
        if am:
            ident = am.group(2)
            ident_norm = ident.lower()
            if ident_norm not in assets:
                assets.append(ident_norm)
                recognized.append({'raw': t, 'normalized': ident_norm, 'tag': 'asset'})
    if assets:
        op = 'in' if len(assets) > 1 else 'equals'
        clauses.append({'type': 'asset', 'operator': op, 'values' if op == 'in' else 'value': assets if op == 'in' else assets[0]})  # type: ignore[arg-type]

    # Compute confidence
    recognized_raws = {t['raw'] for t in recognized}
    for t in tokens:
        if t not in recognized_raws and t not in {'and', 'or', 'than', 'days', 'older', 'the'} and not INT_RE.match(t):
            unparsed.append(t)
    # smoothing exponent to reduce penalty for longer queries
    if tokens:
        base_score = len(recognized) / len(tokens)
        confidence = min(1.0, round(math.pow(base_score, 0.65), 4))
    else:
        confidence = 0.0

    ir = {
        'domain': domain,
        'clauses': clauses,
        'meta': {
            'confidence': confidence,
            'fallback_used': False,
            'tokens': recognized,
            'unparsed_tokens': unparsed,
        }
    }
    return ir

__all__ = ['translate']
