# NEURON Analyst Console (Prototype Shell)

This is a minimal, framework-less prototype of the three-column console (Batch 2–4):
- Left/Center/Right columns, bottom-aligned input
- Command Palette (Ctrl/⌘+K)
- Detachable windows:
  - Editable Report (snapshot-by-default embeds with per-embed Live toggle)
  - Metrics & Findings Hub (tabs; stubbed)
- Adapter stubs for APIs (Batch 3)

Open `frontend/console/index.html` in a static server. Interactions are mocked.

Next steps:
- Wire adapters to backend endpoints via a backend proxy for Prometheus/Grafana.
- Implement approval flows and audit trail for tuners.
- Flesh out Editable Report with provenance stamps and export.
