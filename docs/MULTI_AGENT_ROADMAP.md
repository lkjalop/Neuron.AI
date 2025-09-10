## Multi-Agent Architecture Roadmap

Objective: Establish a governed, auditable set of cooperative agents augmenting detection, tuning, retrieval enrichment, and governance.

### 1. Core Components
1. Agent Registry (DONE): in-memory singleton providing registration and one-shot stepping.
2. Agent Context: shared dict with lightweight mutation (future: immutability snapshots for audit).
3. Hooks: post-step observers writing audit records (`runtime_params.audit_agent_decision`).

### 2. Agent Roles (Initial Set)
- Planner: surfaces platform state, toggles strategic feature flags (proposal only; requires admin confirmation workflow later).
- Tuner: adjusts temporal fusion weight based on uplift ratios (hooks into existing tuner params).
- Retrieval Curator: periodically rebuilds retrieval corpus and triggers vector upserts when enabled.
- Compliance/Governance: validates provenance hashes & secret usage patterns; records anomalies to audit log.
- Drift Sentinel: reads drift monitor stats (future module) and proposes param adjustments (guarded).

### 3. Message Bus (Phase 2)
Light in-memory queue with topic strings:
- publish(topic, event_dict)
- subscribe(topic, callback)
Used for asynchronous proposals (e.g., tuner publishes weight_adjust proposal consumed by governance agent).

### 4. Decision Governance
Every agent decision shaped:
```
{
  "agent": name,
  "action": str,
  "detail": {...},
  "ts": epoch,
  "hash_chain": prev_hash -> curr_hash (appended via audit param change log helper)
}
```
Stored by reusing `audit_agent_decision` (already implemented) to maintain hash chain.

### 5. Safety & Guardrails
- Rate limiting: per-agent max decisions per minute (to prevent flapping).
- Proposal / Apply split: Planner and Tuner emit proposals; only an authorized executor (future ExecAgent) applies them via runtime param API.
- Shadow mode: Agents can run in observation-only mode (`agent.shadow_planner=true` param) producing recommendations but no proposals applied.

### 6. Scheduling
Short-term: invoked manually or via HTTP endpoint `/agents/run_once` (future addition).
Mid-term: cooperative background task calling `registry().run_once(ctx)` every N seconds (configurable, default 30s) with jitter.

### 7. Metrics
- `AGENT_DECISIONS_TOTAL(agent, role, outcome)` counter.
- `AGENT_RUNTIME_SECONDS(agent)` histogram.
- `AGENT_PROPOSALS_PENDING` gauge (size of proposal queue).

### 8. Roadmap Phases
Phase A: Docs + core registry (DONE) + planner registration at startup.
Phase B: Add tuner + retrieval curator agents (shadow mode).
Phase C: Governance enforcement (proposal approval chain) + message bus.
Phase D: Persistence of agent state snapshots (Neon) + replay.
Phase E: Distributed execution considerations (sharding by tenant).

### 9. Open Items
- Authentication for agent-triggering endpoints.
- Dead letter queue for failed agent actions.
- Backoff strategy for repeated guard trips.

---
Hash chain integration after first implementation milestone.
