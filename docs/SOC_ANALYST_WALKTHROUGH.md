# NEURON Analyst Walkthrough (Non‑Technical)

This guide helps SOC analysts use NEURON’s intelligent security platform day‑to‑day: asking questions with natural language (NLP), reviewing graphs and metrics, diagnosing issues, creating/editing reports, performing vulnerability assessments, running threat hunts, and triaging basic forensics.

## 1) Getting started
- Open the Analyst Console: `frontend/console/index.html` (or the hosted UI).
- Modes:
  - Main: actions, graphs, findings, reporting.
  - Wiki: explanations and walkthroughs.
- Command palette: press `Ctrl+K` (or click “⌘K”) to open quick actions (e.g., “Open Metrics & Findings Hub”).

## 2) Ask questions with NLP (Main/Wiki)
- In the bottom composer, type questions like:
  - “Summarize findings by severity this week for tenant Alpha.”
  - “Explain the spike in anomalies and likely root cause.”
- Press Enter to send. You’ll see cards added to the thread with context.
- Use Explain panel (right side) and toggle “Explain for C‑suite” to simplify language.

Tips:
- Keep questions short with one intent.
- Include tenant/time window if you need specifics (e.g., “tenantA, last 24h”).

## 3) Graphs and metrics
- Open “Metrics & Findings Hub” (palette or left panel → Detach Metrics).
- Click the “Graphs” tab.
- Tenant & Time controls:
  - Tenant dropdown persists your choice across sessions.
  - Time dropdown sets the time range (e.g., Last 6h) and updates the graph.
- If graphs fail, a red banner shows: “Graphs unavailable (proxy error or unconfigured).”

What you’ll see:
- Grafana panels with KPIs like alert counts, detection weights, ingestion latency.
- These render via a backend proxy; credentials never reach the browser.

## 4) Findings and KPIs
- The “Metrics” and “Findings” tabs in the Hub show top counters and snapshots.
- Use buttons like “Live/7d/30d” to pivot time windows where available.
- Diagnostic hints appear in Explain panel (right) when you click “Explain.”

## 5) Reporting workflow (Editable Report)
- Open “Editable Report — Executive Summary” window via palette (“Open Editable Report”) or by adding cards to the report.
- Drag cards from the thread to the report canvas to embed them.
- Toolbar actions:
  - Export PDF/HTML (snapshot-by-default).
  - “Shareable View” to generate a read‑only link.
  - “Apply Recommended View” to set a curated layout.
- Story Mode (optional): combines timeline and narrative for leadership updates.

Tips:
- Keep embeds small; prefer higher-level views with annotations for execs.
- Use Templates (composer toolbar) for consistent structure.

## 6) Vulnerability assessment & analysis
- In Dashboards, review: total vulnerabilities, exploit availability, KEV coverage, avg risk.
- Focus areas:
  - “Top risk findings” by risk score.
  - Enrichment coverage: EPSS/KEV percentages.
  - Severity distribution: CRITICAL > HIGH > MEDIUM > LOW.
- Actions:
  - Use filters (tenant/time/severity) to scope.
  - Generate a report section summarizing exposure and progress.

## 7) Threat hunting basics
- Ask NLP: “Show events matching failed logins from suspicious IP ranges last 6h.”
- Use Hunt patterns (if available) to search messages/fields (e.g., via `/hunt/query`).
- Add key findings as cards, then “Add to Report.”
- Explain panel → “Explain” to justify hypotheses and next steps.

Hints:
- Iterate queries; narrow the tenant/time; pivot to related indicators.
- Track a short list of indicators of compromise (IOCs); add them to the IOC store when appropriate.

## 8) Forensics triage (lightweight)
- From a case or anomaly, use actions (e.g., “Acquire memory”) if available.
- Monitor Forensics Jobs (Jobs tab if present) for status and artifacts.
- Chain of custody: verify via the custody endpoint/view when needed.
- Export artifacts via the forensics download action.

Caution:
- Forensics operations may be time‑intensive and should be approved by a lead.

## 9) Approvals & governance
- The right sidebar shows “Approvals.” Request an approval for changes (e.g., tuner weight adjustments).
- After approval, changes apply with a rollback window.
- Governance views show recent recommendations and diagnostics, including a composite risk band.

## 10) Best practices cheat‑sheet
- Always set the correct tenant/time first.
- Summarize narratives in exec‑friendly terms; attach graphs sparingly.
- Use “Explain for C‑suite” for clarity in leadership briefings.
- Keep a small set of watchlists (watchers) to notify stakeholders.
- Document key decisions within the report/story timeline.

## 11) Troubleshooting quick tips
- Graphs error banner: backend proxies or Grafana URL misconfigured.
- Readiness degraded: dev mode allowed; ask platform owner to set required envs.
- Metrics auth: missing API key header → 401; rate limit burst exceeded → 429.

## 12) Glossary
- Tenant: logical customer/account scope.
- EPSS: Exploit Prediction Scoring System.
- KEV: Known Exploited Vulnerabilities list.
- Governance composite: blended risk signal band (low/medium/high).

---
For hands‑on training, use the included templates and run through a weekly drill: review KPIs → triage top risks → hunt suspicious patterns → capture a brief report.
