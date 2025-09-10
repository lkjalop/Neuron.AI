# NEURON Analyst Console — Three-Column UI Spec (Hybrid + Palette, Bottom Input)

Date: 2025-09-09
Owner: Platform UX/AI
Status: Draft (Spec complete; ready for scaffold)

## 1) Overview
A simple-by-default, powerful-on-demand analyst console with:
- Global mode switch: `Main` (operate reports, graphs, findings via NLP) and `Wiki` (non‑tech Q&A, walkthroughs, concepts).
- Three columns: Left (Mission/Filters/Templates), Center (Chat + Results cards), Right (Explain/Tuners/Approvals).
- Bottom-aligned chat input like ChatGPT/Claude.
- Detach/dock: Any card can detach into windows. Two primary windows:
  1) Editable Report (WYSIWYG/Markdown hybrid)
  2) Metrics & Findings Hub (Prometheus/Grafana/API)
- Command Palette (Ctrl/⌘+K) for quick actions (switch mode, open report, start guided workflows).

## 2) Wireframe snapshot (condensed)
```
Top Bar: [ Main ● ] [ Wiki ○ ] | [ ⌘K Palette ] | Tenant | Time | Status
Left [Detach] | Center: Chat + Cards (Detach/Add to Report) | Right [Detach]
Bottom Input: [ Main ● | Wiki ○ ]  [Mic][Templates][Attach][?]  ▌Ask...
Detached 1: Editable Report (drag cards, snapshot-by-default)
Detached 2: Metrics & Findings Hub (Prometheus/Grafana/API)
```

## 3) Core behavior decisions
- Editable Report embeds are snapshot-by-default.
  - Rationale: Governance consistency, reproducibility for C‑suite.
  - Option: Enable "Live" per-embed with explicit toggle; show provenance and time.
  - New findings popup: When new relevant data is detected since snapshot, show non-blocking notification offering to update; log analyst decision.
- Notifications: Analysts working a thread/report/alert receive gentle in-app toasts for new-findings; notifications respect tenant/time scope.
- Grafana integration (see §6): Interactive iframes for exploration; server-side rendered images for reports (performance/governance).
- Tuner changes are locked by default; require SOC Lead or Platform Admin approval; changes are time-bounded, audited, and rollback-capable.

## 4) UI → Backend/API mapping (adapters)
Backend endpoints (existing):
- `GET /dashboard/latest` (predict-protected): Center cards initial load; cached snapshot with recompute fallback.
- `GET /insights` (public/minimal): Right-panel shims for basic insights; can be extended.
- `POST /feedback` (flag-gated): Captures analyst feedback on answers/cards.
- `POST /agents/run_once` (admin): Background single-cycle triggers (rarely used from UI).
- `GET /findings/sla/upcoming` (predict): Cards for SLA risk.
- `POST /tickets/remediation` (predict): Create remediation/ticket stubs.
- `POST /admin/flush` (admin): Maintenance.

Adapters (frontend or via backend proxy):
- Prometheus HTTP API: Read-only queries for metrics cards (e.g., `neuron_alert_dispatch_total`, `fusion_temporal_weight`).
- Grafana: Panel iframes for interactive exploration; rendered images for report embeds.
- Auth: Predict/Admin API keys as configured; backend proxy preferred to avoid exposing secrets and to normalize errors.

Adapter contract sketch (TypeScript-like):
```ts
interface DashboardAdapter {
  latest(scope: {tenant: string; time: string}): Promise<DashboardSnapshot>;
}
interface InsightsAdapter {
  list(params: {tenant: string}): Promise<Insight[]>;
}
interface MetricsAdapter {
  queryPromQL(q: string, range: TimeRange): Promise<Series[]>;
}
interface GrafanaAdapter {
  iframeUrl(panelId: string, vars: Record<string,string>): string; // exploration
  renderImage(panelId: string, vars: Record<string,string>): Promise<Blob>; // reports
}
interface FindingsAdapter {
  slaUpcoming(scope: Scope): Promise<SlaItem[]>;
  cves(filter: CveFilter): Promise<CveRow[]>;
}
interface TicketsAdapter {
  createRemediation(input: TicketInput): Promise<TicketDraft>;
}
interface FeedbackAdapter {
  submit(input: Feedback): Promise<{ok: true}>;
}
```

Error mapping (aligned to tests):
- Service/storage/list failures ⇒ HTTP 503 with `{"error": {"code": "list_unavailable"}}` etc.
- Unauthorized ⇒ 401; unset keys ⇒ 503 per contract.

## 5) Metrics examples (Prometheus)
- `neuron_alert_dispatch_total{channel, outcome}` for alert pipeline health.
- `fusion_temporal_weight{tenant}` and `fusion_transformer_weight{tenant}` for tuner observability.
- `ingestion_latency_ms` and relevant SLO indicators.

Frontend queries via MetricsAdapter → backend proxy (recommended) to avoid CORS/auth issues; proxy enforces allowlists of PromQL.

## 6) Grafana integration — choices and defaults
- Native iframe panels (interactive)
  - Pros: Full interactivity, drill-downs, variable controls; fastest for analysts.
  - Cons: Requires viewer auth/session; heavier; potential CORS/embed policies.
  - Use: Metrics & Findings Hub (exploration).
- Server-side rendered images (static)
  - Pros: Lightweight, stable, great for reports; no client-side auth; reproducible.
  - Cons: No interactivity; need backend render endpoint or Grafana render API.
  - Use: Editable Report embeds by default.

Recommendation:
- Use iframes in-app (Hub), images in reports. Implement backend proxy that signs/filters iframe URLs and fetches rendered images for embeds.

## 7) Tuner approvals, audit, rollback
- Roles:
  - SOC Lead, Platform Admin can approve changes.
  - Analysts can preview in a sandbox but cannot apply.
- Workflow:
  1) Preview impact: show before/after metrics and risk projections.
  2) Request Approval: generate approvable change with scope, duration (e.g., 2 hours), reason.
  3) Approve/Reject: signed action; audit trail recorded.
  4) Auto-expire: change reverts after window; manual rollback allowed anytime.
- Security & audit:
  - Immutable audit log entry (hash-chained event) with user, time, diff, reason.
  - Tamper detection alerts if changes occur outside approvals.
  - Notification to responders when tuners change and when they revert.

## 8) Editable Report behavior & notifications
- Embeds are snapshot-by-default; per-embed Live toggle available.
- New findings popup: "New data since snapshot — Update this embed? [Preview Diff][Update][Keep]".
- Provenance ribbon on every embed: dataset/time/filters/query hash.
- Export: PDF/HTML; Live embeds forced to snapshot on publish unless explicitly allowed.

## 9) Guided Mode, ELI5, Story Mode, Shareable Views
- Guided Mode: Converts Wiki answers into step overlays; any write requires approval; track completion.
- ELI5 Toggle: Rewrites explanations to non-technical language; preserves provenance/disclaimers.
- Story Mode: Timeline annotations linking cards (what happened, why, actions, outcome); exportable.
- One‑click Shareable Views: Read-only link snapshotting current filters/cards; respects access control.

## 10) Accessibility and simplicity
- Keyboard: `/` focus chat, `F1` help, `Ctrl/⌘+K` palette.
- High-contrast UI, large targets, clear focus rings.
- Plain-language tooltips (“Explain for C‑suite”) and microcopy.

## 11) Acceptance criteria (non‑tech friendly)
- A new analyst can: ask a question, detach a card, add to report, explain for C‑suite, export a report — all in under 10 minutes.
- No destructive action is possible without explicit approval.
- Every card/report shows provenance and timestamps.

## 12) Implementation phases (batches)
- Batch 1 (this): Spec + decisions + API mapping.
- Batch 2: Frontend shell scaffold (Left/Center/Right, Detach Manager, Dock, Palette) with mock adapters.
- Batch 3: Adapters: API + Prometheus proxy + Grafana (iframe/images) + Metrics/Findings Hub.
- Batch 4: Editable Report (drag-in embeds, snapshot/live, export, provenance, notifications).
- Batch 5: Tuner sandbox, approvals, audit, rollback, alerts.
- Batch 6: Guided Mode + ELI5 toggle.
- Batch 7: Story Mode + Shareable Views.
- Batch 8: Architecture/service/deployment diagrams (docs) and polish.

## 13) Security notes
- Prefer backend proxies for Prometheus/Grafana; never expose tokens to the browser.
- Rate-limit and 2FA for approvals; notify on unusual tuner activity.
- Enforce content security policies for iframes.
