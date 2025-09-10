# NEURONS NLP Query Layer Schema (Alpha)

> Version: 0.1 (Validation Tier)  
> Scope: Natural language → Deterministic Intermediate Representation (IR) → Backend filters  
> Principles: Deterministic First · Transparent Parsing · Safe Fallback · Extensible Slots

---
## 1. Objectives
Provide a transparent, explainable NLP translation layer that converts analyst free‑text queries about vulnerabilities, assets, exposure posture, and remediation priority into a structured intermediate representation (IR) consumed by existing list endpoints. Initial focus is on vulnerability filtering; later expansions add anomaly/forecast & similarity facets.

---
## 2. Query Domains (Phase 1 Alpha)
| Domain | Supported Intents (Examples) | Output Targets |
|--------|------------------------------|----------------|
| Vulnerability Filtering | "critical vulns exploited last 30 days", "high or critical with active exploit and >14 days old" | `/vulnerabilities` list filters |
| Asset Exposure | "assets with highest exposure score", "assets with critical overdue" | `/assets` list filters |
| Temporal Constraints | "last 7 days", "older than 30 days", "this week" | date range filter on `first_seen` / `last_seen` |
| Exploitability | "exploited", "has known exploit", "not exploited" | exploit_status boolean/enum |
| Severity Logic | "critical and high", "medium or high", "not low" | severity inclusion/exclusion set |
| Aging / SLA | "overdue", "older than 45 days critical" | age_days threshold rule |
| Count Thresholds | "more than 5 open critical" | numeric comparator on aggregated counts |
| Ranking | "top 10" / "highest exposure" | limit + sort spec |

---
## 3. Intermediate Representation (IR) Structure
```jsonc
{
  "domain": "vulnerabilities" | "assets",
  "clauses": [
    { "type": "severity", "operator": "in", "values": ["critical", "high"] },
    { "type": "exploit_status", "operator": "equals", "value": true },
    { "type": "age", "operator": ">", "value": 14 },
    { "type": "date_range", "field": "last_seen", "from": "2025-08-25", "to": "2025-09-01" },
    { "type": "exposure_score", "operator": ">=", "value": 700 },
    { "type": "limit", "value": 50 },
    { "type": "sort", "field": "exposure_score", "direction": "desc" }
  ],
  "meta": {
    "confidence": 0.82,
    "unparsed_tokens": ["remediate", "soon"],
    "tokens": [
      { "raw": "critical", "normalized": "critical", "tag": "severity" },
      { "raw": "exploited", "normalized": "exploit", "tag": "exploit_status" },
      { "raw": ">14", "normalized": "14", "tag": "age_threshold" }
    ],
    "fallback_used": false
  }
}
```

---
## 4. Canonical Slot Inventory
| Slot | Tag | Data Type | Description | Example Parse |
|------|-----|-----------|-------------|---------------|
| Severity Set | `severity` | list[str] | One or more severities | "critical high" -> [critical, high] |
| Exploit Status | `exploit_status` | bool/enum | Known exploited or not | "exploited" -> true |
| Age Threshold | `age_threshold` | int (days) | Age in days | ">30 days" -> 30 |
| Date Range Explicit | `date_range` | ISO dates | Bounded time window | "last 7 days" -> from/to |
| Exposure Score | `exposure_score` | int | Score threshold | ">700 exposure" |
| Asset ID Pattern | `asset_pattern` | string | Partial asset id filter | "asset srv-01" |
| Limit | `limit` | int | Result size | "top 20" -> 20 |
| Sort Field | `sort_field` | string | Ranking field | "highest exposure" -> exposure_score desc |
| SLA Keyword | `sla` | enum | SLA breach intent | "overdue" |
| Boolean Connective | `logic` | enum | AND/OR/NOT normalization | "and", "or", "not" |
| Negation | `negation` | marker | Exclusion toggle | "not low" |
| Unknown Token | `unknown` | string | For transparency | preserved |

---
## 5. Parsing Pipeline
1. **Pre-normalization:** lowercase, strip punctuation (retain comparative symbols), collapse whitespace.
2. **Tokenization:** regex splitting with preservation of composite patterns (e.g., `>30`, `7d`).
3. **Lexical Tagging:** deterministic pattern library (regex + enumerations) assigns tags.
4. **Chunk Assembly:** group adjacent severity tokens; interpret connectors (and/or) into clause groups.
5. **Temporal Resolution:** phrases like "last week", "past 30 days", "older than 45 days" → explicit date or age clause.
6. **Constraint Folding:** combine duplicate severity or age constraints; highest precedence: explicit numeric > relative phrase.
7. **Negation Handling:** "not low" → severity set minus low; precedence local to following token group.
8. **Confidence Scoring (Heuristic v0):** base 1.0 minus penalties: unknown_token *0.05 each, conflicting_clause *0.1, partial_date *0.1.
9. **Fallback Decision:** if confidence < 0.5 OR zero structural clauses -> fallback substring search (returns `{ fallback_used: true }`).
10. **Serialization:** produce ordered IR (non-filter structural clauses like limit/sort last).

---
## 6. Clause Semantics → Backend Mapping
| Clause Type | Backend Field | Translation Example |
|-------------|---------------|---------------------|
| severity | `severity` | `severity IN (...)` |
| exploit_status | `exploit_status` | `exploit_status = true` |
| age | `first_seen` or computed age | `NOW() - first_seen > interval '14 days'` |
| date_range | `last_seen` / `first_seen` | `last_seen BETWEEN from AND to` |
| exposure_score | `exposure_score` | `exposure_score >= 700` |
| asset_pattern | `asset_id` | `asset_id ILIKE 'srv-%'` |
| sla (overdue) | severity SLA table | `first_seen < NOW() - SLA(severity)` |
| limit | n/a | query limit parameter |
| sort | n/a | order by field |

---
## 7. Data Structures (Python Stub Alignment)
```python
@dataclass
class Token:
    raw: str
    normalized: str
    tag: str

@dataclass
class Clause:
    type: str
    operator: str
    field: str | None = None
    value: Any | None = None
    values: list[Any] | None = None
    from_ts: str | None = None
    to_ts: str | None = None

@dataclass
class QueryIR:
    domain: str
    clauses: list[Clause]
    tokens: list[Token]
    confidence: float
    fallback_used: bool
    unparsed_tokens: list[str]
```

---
## 8. Regex / Pattern Library (Initial)
| Tag | Pattern | Notes |
|-----|---------|-------|
| severity | `\b(critical|high|medium|low)\b` | multi-token grouping |
| exploit_status | `\b(exploited?|exploit available)\b` | maps true |
| negation | `\bnot\b` | toggles exclusion |
| age_threshold | `>(\d+)(?:\s*d(?:ays)?)?` | extract int |
| last_n_days | `last\s+(\d+)\s*d(?:ays)?` | range from today |
| past_n_days | `past\s+(\d+)\s*d(?:ays)?` | alias |
| last_week | `last\s+week` | 7 day range |
| older_than | `older\s+than\s+(\d+)` | age clause > value |
| top_n | `top\s+(\d+)` | limit |
| exposure_score | `exposure\s*(?:score)?\s*>?=?(\d{2,4})` | threshold extraction |
| overdue | `\boverdue\b` | SLA intent |
| asset_id | `asset\s+([A-Za-z0-9._-]+)` | pattern capture |

---
## 9. Confidence Heuristic Details
Start 1.0. Apply penalties:
- Unknown token (non-stopword) −0.05
- Negation with no following recognized token −0.1
- Conflicting severity logic (e.g., `critical only high`) −0.15
- Mixed domain signals (asset + vulnerability simultaneously) −0.1 (in alpha we constrain to single domain)
Floor at 0.0; if <0.5 -> fallback.

---
## 10. Examples
### Example A
Query: "critical or high exploited older than 30 days top 20"
IR: severity IN [critical, high]; exploit_status = true; age > 30; limit 20; default sort severity desc.

### Example B
Query: "assets with highest exposure not low"
Domain switch to assets; severity clause removes low; sort exposure_score desc; limit default (25).

### Example C (Fallback)
Query: "remediate soon complex kernel issue"
No resolvable structural tokens -> fallback substring search terms preserved.

---
## 11. Error / Transparency Strategy
Return IR even if partial; always expose `unparsed_tokens`. Client displays pill badges for recognized vs unknown to build user trust.

---
## 12. Extensibility Roadmap
Phase 2: Add forecast intents ("expected exposure next week"), anomaly intents ("recent unusual spikes"), similarity ("assets like srv-01").  
Phase 3: Add remediation prioritization phrases ("quick win", "patch group").

---
## 13. Security Considerations
- No direct query string interpolation; server maps IR to parameterized queries.  
- Reject excessively large numeric thresholds (>10k).  
- Rate limit `/query/nlp` separately (future), log unknown token clusters for pattern enrichment.

---
## 14. Acceptance Criteria
- ≥80% of curated test phrases produce ≥1 structural clause.  
- Fallback triggers for nonsensical inputs w/out server error.  
- Confidence value stable (±0.05) across repeated identical queries.  
- All regex patterns unit tested (positive + negative).

---
Prepared for implementation alongside existing `translator` stub evolution.
