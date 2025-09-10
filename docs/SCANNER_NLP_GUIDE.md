# NLP-Assisted Vulnerability Assessment, Threat Modeling & Threat Hunting

This guide explains how to leverage the platform's (existing / pluggable) NLP & retrieval capabilities together with the local scanner outputs to accelerate three workflows:
1. Vulnerability Assessment
2. Threat Modeling
3. Threat Hunting & Hypothesis Generation

> NOTE: Some advanced retrieval / embedding quality metrics are deferred. Guidance below shows current feasible flows plus near-term extensions.

## 1. Vulnerability Assessment Workflow
Goal: Rapidly understand risk posture impact of newly ingested vulnerabilities and prioritize remediation.

### Data Sources
- Findings (`/vuln/findings` or `/ui/findings`) including: risk_score, severity, exploit flags, KEV marker, SLA due date.
- Enriched vulnerability records (future: EPSS, CVSS vectors) via `/vuln/vulnerabilities`.
- Asset context (criticality, exposure) when persisted.

### NLP-Driven Steps
1. Summarize Top Risks:
   - Prompt template (pseudo):
     "Given these findings (JSON array), produce a concise prioritized list explaining why the top 5 matter, referencing exploitability or KEV flags when present."
2. Remediation Grouping:
   - Ask model to cluster findings by shared component or remediation action (e.g., upgrade `openssl` library) to produce consolidated change stories.
3. SLA Risk Alerts:
   - Provide model with days-to-zero forecast + slope and ask: "Which severities require acceleration to meet an assumed 30-day policy?".

### Example Prompt Snippet
```
System: You are a security expert.
User: Here are open findings: <JSON>. Generate a table with columns (Component, CVE, Severity, Key Factor, Recommended Action) limited to top 10 by risk_score.
```

## 2. Threat Modeling Workflow
Goal: Translate technical vulnerabilities into potential attack paths & business impact narratives.

### Inputs
- Findings with severity + exploit indicators.
- (If available) Exposure graph / asset metadata (external_exposure, criticality).
- Governance composite (shows detection posture adjustments) for context.

### NLP Augmentation
1. Attack Path Hypothesis:
   - Provide component + CVE description. Ask model: "What lateral movement or privilege escalation opportunities could this enable in a typical web service stack?".
2. Control Coverage Gap Analysis:
   - Feed recent governance adjustments + vulnerability list. Ask: "Are there detection blind spots given current composite signal behavior?".
3. Business Impact Narrative:
   - Provide criticality metadata + top 5 HIGH/CRITICAL findings. Ask: "Draft an executive summary of potential business impact if unpatched for 30 days.".

### Structured Output Pattern
Request JSON object with `attack_paths`, `control_gaps`, `business_impact_summary` for downstream dashboard embedding.

## 3. Threat Hunting & Hypothesis Generation
Goal: Turn vulnerability + enrichment signals into concrete hunt leads.

### Signals to Leverage
- KEV listed or exploit_available flags.
- Rapid slope drop stalls (burn-down flattening) -> potential remediation friction.
- Emergence / predictive placeholders once enabled (e.g., `emergence_p`).

### NLP Prompts
1. Generate Hunt Queries (pseudo detection language):
   "Given CVE-2025-12345 affecting OpenSSL on externally exposed asset(s), propose 5 log search queries to detect exploitation attempts (format: product: query)."
2. Anomaly Correlation Suggestions:
   "Using these vulnerability factors <JSON factors>, suggest which telemetry (TLS handshake anomalies, process spawn patterns, memory scanning indicators) to monitor.".
3. Prioritized Hunt Plan:
   "Aggregate the above into a 1-day tactical hunt plan with time-boxed tasks (max 4 hours total).".

## Integrating Retrieval (When Enabled)
- Embed SBOM component docs / advisories; retrieval step feeds top-k context chunks to model along with finding metadata.
- Scoring signals (future retrieval metrics) can weight relevance; pass to model for self-critique: "Given relevance scores, discard low-value chunks < threshold>.".

## Automation Hooks (Future Enhancements)
| Idea | Description | Effort | Value |
|------|-------------|--------|-------|
| Finding->Prompt Pipeline | Auto-generate assessment summary nightly | Low | High |
| SLA Breach Explainer | Model narrates SLA breach risk using burn-down slope | Low | Medium |
| Adaptive Hunt Seeds | If KEV spikes, auto-produce hunt plan draft | Medium | High |
| Mitigation Diff Reasoner | Compare two SBOM snapshots, explain risk delta | Medium | Medium |

## Safety & Accuracy Considerations
- Always include raw numeric risk_score & severity for user verification.
- Use temperature=0 or low for deterministic prioritization tables.
- Maintain prompt logs (audit) for governance traceability.

## Minimal API Data Bundle Example
```
{
  "findings": [ {"cve_id": "CVE-2025-12345", "component": "openssl", "risk_score": 0.82, "risk_severity": "HIGH", "kev_listed": true } ],
  "burn_down": {"latest_total": 12, "slope_per_day": -1.4, "est_days_to_zero": 9.0},
  "governance": {"composite": 0.67},
  "asset_context": {"external_exposed": 3, "internal": 5}
}
```

## Quick Start Prompts (Copy/Paste)
1. Assessment Table:
```
Summarize these findings <JSON> into a table: CVE | Component | Severity | Key Factor | Remediation Step.
Limit to top 8 by risk_score. Respond in GitHub-flavored markdown.
```
2. Threat Modeling Narration:
```
Using findings <JSON> and governance composite {{composite}}, draft 3 plausible attack scenarios (title + 2 sentence description) referencing which CVEs enable each stage.
```
3. Hunt Plan:
```
Given findings <JSON> produce a 4-hour hunt plan. For each task: name, objective, required data source, success criteria.
Return JSON array.
```

## Roadmap Alignment
This guide anticipates Batch C enhancements (retrieval quality metrics, PDF robustness) but is usable now with current APIs. Update as new risk factors and enrichment signals are exposed.

---
Document version: 2025-09-06
