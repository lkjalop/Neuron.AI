# NEURONS Frontend MVP Scope (Conservative Baseline)

> Version: 0.1 (Validation Tier · 33% Capacity)  
> Branding: **NEURONS** — *Neuromorphic Enhanced Unified Response to Offensive Network Signals*  
> Guiding Principles: Predictive > Reactive · Deterministic First · Evidence-Centric · Cost-Minimal Baseline · Progressive Enablement

---
## 1. Purpose
Deliver the minimal, end-to-end user interface required for a single operator (security engineer / analyst) to:  
1. Observe exposure posture & key risk KPIs.  
2. Investigate vulnerabilities & affected assets.  
3. Validate scanner ingestion health.  
4. Export executive / weekly exposure reports.  
5. Trial natural‑language exposure queries (alpha).  
6. Confirm system “vital signs” (data freshness, feature pipeline recency, model gating status).

---
## 2. Target Users & Roles (MVP)
| Role | Description | Permissions (MVP) |
|------|-------------|-------------------|
| `analyst` (default) | Single-tenant operator validating platform | Read all, export reports |
| `admin` (future) | Adds API keys, manages auth & rate policies | NOT in MVP |
| `viewer` (future) | Read-only dashboards | NOT in MVP |

MVP: All authenticated users behave as `analyst` (role abstraction placeholder for future RBAC).

---
## 3. Navigation & Information Architecture
Primary left nav (vertical):
1. **Dashboard** – KPIs & trend widgets
2. **Vulnerabilities** – List & detail view
3. **Assets** – Inventory & exposure summary
4. **Findings** – (Optional toggle) Raw normalized finding rows (tech user)
5. **Scans / Ingestion** – Connector status + last ingest timestamps
6. **Reports** – Generate / download most recent HTML → PDF
7. **Query (NLP)** – Natural language → structured filter interpreter (alpha)
8. **System** – Gating metrics, feature snapshot recency, model readiness indicators

Breadcrumbs: `Section > Subview > Entity` (e.g., `Vulnerabilities > CVE-2024-12345`).

---
## 4. Screen Breakdown & Acceptance Criteria
### 4.1 Dashboard
**Widgets (Validation Tier):**
- Open Vulnerabilities by Severity (bar: Critical/High/Medium/Low)
- Exposure Trend (7d line; derived from snapshot aggregator)
- Top 5 Risky Assets (table: asset_id | open_crit | exposure_score)
- SLA Breach % (count where age > SLA threshold per severity) – placeholder if data insufficient (show grace state)
- Scan Coverage (% assets with at least 1 finding last 7d)

**Acceptance:** All widgets load ≤ 2s with seed dataset; missing data gracefully shows neutral state + tooltip.

### 4.2 Vulnerabilities List
Columns: `cve_id` | `title` | `severity` | `affected_assets` | `exploit_status` | `age_days` | `exposure_score`  
Filters: severity (multi), exploit (yes/no), age range, search (substring in title / cve_id).  
Pagination: 25/page (client requests backend with `?limit=25&offset=`).  
Sort: severity desc (default), exposure_score, age_days.

### 4.3 Vulnerability Detail
Panels:
- Header: CVE + title + severity pill + exploit badge
- Metrics: exposure_score, affected_assets_count, first_seen, last_seen
- Affected Assets table (asset_id | highest_finding_severity | open_findings)
- Knowledge & Links: related ATT&CK techniques, controls (if graph edges exist)
- Report Actions: “Export snippet” (future placeholder)

### 4.4 Assets Inventory
Columns: `asset_id` | `crit_count` | `high_count` | `med_count` | `low_count` | `exposure_score` | `last_seen`
Filters: min_exposure_score, has_exploit (derived), search asset_id prefix.  
Detail Drawer (inline slide-over): severity distribution + recent findings timeline.

### 4.5 Findings (Raw) – Technical View (Feature Flag)
Allows QA of normalization & idempotency.  
Columns: `finding_id` | `vuln_ref` | `asset_id` | `state` | `severity` | `source` | `first_seen` | `last_seen`.

### 4.6 Scans / Ingestion Health
Cards: Qualys (synthetic) + Tenable (skeleton) + SIEM events.  
Fields: last_ingest_timestamp, events_ingested_24h, status (OK / STALE > 2h / ERROR).  
Color semantics: Green / Amber / Red.

### 4.7 Reports
List: Generated report runs (timestamp, type, status, download link).  
Action: “Generate Executive Summary” -> triggers backend job (returns 202 + polling).  
Download: HTML → client-side print-to-PDF (MVP).  
Empty State: “No reports generated yet – run your first executive summary.”

### 4.8 NLP Query (Alpha)
Input: free text (placeholder examples).  
On submit: shows parsed structured filter JSON + sample result set (top 20 vulnerabilities).  
Displays confidence & tokens recognized (severity, exploit, timeframe, asset filter).  
Errors: partial parse -> degrade to substring search fallback.

### 4.9 System (Gate Status)
Fields: feature_snapshot_last_run, variance_ok (bool), gating_report_version, anomaly_model_ready (bool placeholder), total_assets, total_vulnerabilities.  
If any gate fails -> highlight + link to docs.

---
## 5. Component Inventory (Initial)
| Component | Type | Reuse Notes |
|-----------|------|-------------|
| `KpiCard` | Presentational | Title + value + delta badge |
| `SeverityBarChart` | Data viz | Map severity->color tokens |
| `TrendSparkline` | Data viz | 7d small multiple |
| `ExposureScoreBadge` | Badge | Deterministic color thresholds |
| `PaginatedTable` | Layout | Shared pagination + empty state |
| `FilterPanel` | Form | Controlled multi-select + range |
| `AsyncStatusChip` | Badge | OK/STALE/ERROR tri-state |
| `ParsedQueryView` | Panel | Shows NLP IR JSON pretty-printed |
| `GraphLinksList` | Panel | Related knowledge edges |

---
## 6. Technical Stack (MVP Recommendation)
- Build Tool: Vite + React (TS) (fast local iteration; can deploy static)
- State: React Query (server cache) + URL params for filters
- UI Framework: Minimal Tailwind (design tokens only) or lightweight CSS Modules; avoid heavy component libs
- Charts: Lightweight (e.g., Chart.js or Recharts) – only 2–3 charts
- Auth: Temporary shared API key via header (`X-API-Key`) until JWT layer (future task #56)
- Error Handling: Central interceptor -> toast + fallback panel
- Environment: `.env` (VITE_API_BASE_URL, VITE_API_KEY)

---
## 7. Branding & Visual Language (Derived)
Core identity: Neuromorphic cognition + predictive calm.  
Color Tokens (suggested accessible palette):
- Primary: `#374D9A` (Focused Indigo)
- Accent: `#5BC4BF` (Neural Teal)
- Critical: `#D64545`
- High: `#E67E22`
- Medium: `#F1C40F`
- Low: `#7F8C8D`
- Surface Base: `#0F1115`
- Surface Alt: `#1B1F27`
- Border Subtle: `#2A3039`
- Text Primary: `#E6EDF3`
Font Direction: System stack or Inter (if permitted).  
Tone: Clinical, concise, engineering-first.

Typography Scale: `12 / 14 / 16 / 20 / 24 / 32` (rem based).

---
## 8. Performance & Budget Constraints
Validation Tier Targets:
- Any list fetch < 800ms server-side (baseline dataset)
- Bundle size initial < 300KB gzipped
- First Contentful Paint < 2.5s on mid laptop
- No realtime websockets in MVP (polling intervals: Dashboard 30s, System 60s)

---
## 9. API Touchpoints (Read Only Initial)
| View | Endpoint (existing/planned) | Method | Notes |
|------|-----------------------------|--------|-------|
| Dashboard | `/dashboard/latest` | GET | Aggregated snapshot |
| Vulnerabilities List | `/vulnerabilities` | GET | Supports filters, pagination |
| Vulnerability Detail | `/vulnerabilities/{id}` | GET | Add related graph references |
| Assets List | `/assets` | GET | Need exposure_score & counts |
| Asset Detail | `/assets/{id}` | GET | Inline detail data |
| Findings (raw) | `/findings` | GET | Feature-flag in UI |
| Ingestion Health | `/ingest/status` | GET | New endpoint stub needed |
| Reports List | `/reports` | GET | Existing generator integration |
| Report Generate | `/reports/exec_summary` | POST | Async job / immediate render |
| NLP Query | `/query/nlp` | POST | Returns parsed + results |
| System Gate | `/system/gate_status` | GET | Compose gating scripts outputs |

---
## 10. Non-Goals (MVP)
- Multi-tenant UI theming
- Role-based view segmentation
- Real-time push (websocket/eventsource)
- Inline ticketing or SOAR action triggers
- Complex graph visualization
- Full text search across knowledge corpus (basic semantic search only)

---
## 11. Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| Missing some backend endpoints | Delays UI integration | Stub mock service layer; parallel endpoint build |
| NLP parser low precision early | User distrust | Show transparency panel (tokens recognized + fallback) |
| Exposure score recalculation drift | UI inconsistency | Lock regression test + badge version tag |
| Performance regression with added filters | Slow lists | Always request minimal field sets; server pagination |

---
## 12. Acceptance Checklist
- [ ] All listed screens navigable with seed data
- [ ] Empty & loading states implemented for each table/chart
- [ ] Severity & exploit filters deterministic & idempotent
- [ ] NLP query panel returns parse object for ≥80% of canned examples
- [ ] Reports export produces HTML printable to PDF
- [ ] System gate panel reflects gating script JSON
- [ ] Bundle size & performance targets met

---
## 13. Iteration Path (Post-MVP)
1. Add Auth (JWT / API keys rotation)
2. Anomaly & Forecast overlays on Dashboard
3. Asset similarity (SNN / embedding) insights tab
4. Real-time push (optional SSE)
5. Multi-user roles + audit trails
6. Advanced executive & anomaly narrative reports

---
## 14. Implementation Notes
- Prefer **composition** over large dashboards page; each widget fetches own data (in parallel) via React Query.
- Use **semantic class tokens** for severity (`sev-critical`, etc.) mapping to palette above.
- Maintain a **UI contract file** exporting TypeScript interfaces mirroring API schema for early compile-time safety.
- Add a `MockApiProvider` for local development before all endpoints land.

---
Prepared for validation tier delivery.
