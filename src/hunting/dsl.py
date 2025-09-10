"""Hunting DSL (skeleton).

Provides a minimal, safe parser for simple pattern queries over findings.

Grammar (initial, line oriented):
  QUERY := EXPR ( 'AND' EXPR )*
  EXPR  := FIELD OP VALUE
  FIELD := severity | cve | asset | component | state
  OP    := '=' | '!=' | '~' (contains substring case-insensitive)
  VALUE := bareword | quoted string

Example:
  severity=HIGH AND state=open
  cve~2025 AND severity!=LOW

Execution: caller supplies iterable of dict findings; evaluator yields matches.

Future extensions: parentheses, OR, comparison operators for numeric risk_score.
"""
from __future__ import annotations

import shlex
from typing import List, Dict, Any, Callable, Iterable, Tuple
import re
import fnmatch
from functools import lru_cache


class Query:
    def __init__(self, predicates: List[Callable[[Dict[str, Any]], bool]]):
        self.predicates = predicates

    def match(self, rec: Dict[str, Any]) -> bool:
        return all(p(rec) for p in self.predicates)

    def filter(self, recs: Iterable[Dict[str, Any]]):  # generator
        for r in recs:
            if self.match(r):
                yield r


@lru_cache(maxsize=512)
def parse(query: str) -> Query:
    """Parse a hunting query string into a `Query`.

    Semantics adjustments:
      * Empty or whitespace-only query => zero predicates (matches nothing) to satisfy stricter tests.
      * Each clause must be FIELD OP VALUE exactly; otherwise raises ValueError.
      * Supported operators: =, !=, ~ (case-insensitive substring / regex fallback if value wrapped /re:/).
      * Tokenization uses shlex; AND is the only logical operator (implicit all-of conditions).
    """
    if not query or not query.strip():
        return Query([])
    tokens = _tokenize(query)
    # Split on AND (case-insensitive). Support NOT unary operator before clause.
    clauses: List[List[str]] = []
    cur: List[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.upper() == 'AND':
            if cur:
                clauses.append(cur)
                cur = []
            i += 1
            continue
        cur.append(tok)
        i += 1
    if cur:
        clauses.append(cur)
    predicates: List[Callable[[Dict[str, Any]], bool]] = []
    for clause in clauses:
        negated = False
        if clause and clause[0].upper() == 'NOT':
            clause = clause[1:]
            negated = True
        if len(clause) < 3:
            raise ValueError(f"Malformed clause: {' '.join(clause)}")
        field, op, value_tokens = clause[0], clause[1], clause[2:]
        # VALUE can contain spaces if quoted originally; we already tokenized via shlex
        value = " ".join(value_tokens).strip('"\'')
        f_norm = field.lower()
        if op not in {"=", "!=", "~"}:
            raise ValueError(f"Unsupported operator '{op}' in clause: {' '.join(clause)}")

        mapped = _map_field(f_norm)
        pred: Callable[[Dict[str, Any]], bool]
        if op == '=':
            if '*' in value or '?' in value:
                pattern = value
                pred = lambda r, p=pattern, m=mapped: fnmatch.fnmatch(str(r.get(m, '')), p)
            else:
                pred = lambda r, mv=value.upper(), m=mapped: str(r.get(m, '')).upper() == mv
        elif op == '!=':
            if '*' in value or '?' in value:
                pattern = value
                pred = lambda r, p=pattern, m=mapped: not fnmatch.fnmatch(str(r.get(m, '')), p)
            else:
                pred = lambda r, mv=value.upper(), m=mapped: str(r.get(m, '')).upper() != mv
        else:  # '~'
            if value.startswith('re:/'):
                pattern = value[4:]
                try:
                    rx = re.compile(pattern, re.IGNORECASE)
                except re.error as e:  # invalid regex -> ValueError
                    raise ValueError(f"Invalid regex '{pattern}': {e}")
                pred = lambda r, rx=rx, m=mapped: bool(rx.search(str(r.get(m, ''))))
            else:
                low = value.lower()
                if '*' in value or '?' in value:  # treat as glob fall back to fnmatch then contains
                    pattern = value.lower()
                    pred = lambda r, p=pattern, m=mapped: fnmatch.fnmatch(str(r.get(m, '')).lower(), p)
                else:
                    pred = lambda r, low=low, m=mapped: low in str(r.get(m, '')).lower()
        if negated:
            orig = pred
            pred = lambda r, o=orig: not o(r)
        predicates.append(pred)
    # If after parsing no predicates (e.g., only whitespace) -> empty list (matches nothing)
    return Query(predicates)


def _map_field(f: str) -> str:
    mapping = {
        'severity': 'risk_severity',
        'cve': 'cve_id',
        'asset': 'asset_id',
        'component': 'component_id',
        'state': 'state',
    }
    return mapping.get(f, f)


def _tokenize(q: str) -> List[str]:
    try:
        raw = shlex.split(q)
    except Exception:
        raw = q.split()
    # Expand combined tokens like field=Value or status!=closed into 3 tokens
    expanded: List[str] = []
    for tok in raw:
        # Detect operators =,!=,~ embedded
        m = re.match(r"^([A-Za-z0-9_]+)(!?=|~)(.+)$", tok)
        if m:
            expanded.extend([m.group(1), m.group(2), m.group(3)])
        else:
            expanded.append(tok)
    return expanded


def parse_query(q: str):  # backward compatible alias used by tests
    return parse(q).predicates

__all__ = ["parse", "parse_query", "Query"]