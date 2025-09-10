# Exposure Weighting (External vs Internal Assets)

## TL;DR (Non‑Technical)
Some systems sit on the public internet (externally exposed). Attackers can reach these **immediately**. Others are only reachable from inside the company network. We slightly boost the risk score of vulnerabilities on externally exposed assets so they float to the top of the queue earlier. This does **not** change the underlying CVE severity; it only changes prioritization order.

Analogy: Two identical houses have the same weak lock. One is on a quiet private campus (internal), the other is on a busy street (external). Which do you fix first? The busy street one – higher exposure. That multiplier captures this.

## What We Chose: Option C (Score Multiplier + Logistic Feature)
We add exposure information in **two** complementary ways:
1. A small multiplicative boost to the final normalized risk score (e.g. 1.15x) for externally exposed assets.
2. A binary feature (`asset_external_exposure = 0/1`) fed into the logistic emergence probability model so that future predictive learning can internalize exposure context.

This keeps today’s prioritization responsive while also seeding tomorrow’s model improvements (the model can learn nuanced non‑linear interactions between exposure, EPSS, KEV listing, exploit availability, drift, etc.).

## Why Not Only One Mechanism?
| Approach | Pros | Cons | Reason it’s Insufficient Alone |
|----------|------|------|--------------------------------|
| Just raw multiplier | Immediate, transparent | Hard‑coded; model can’t learn diminishing/conditional effects | Freezes exposure impact; brittle tuning cycle |
| Just logistic feature | Flexible; model can learn | No benefit until model retrained; current outputs unchanged | Delayed value; invisible to analysts now |
| (Chosen) Multiplier + Feature | Immediate + future adaptive | Slightly more code paths | Balanced – instant analyst value + future learning |

## How the Multiplier Works (Plain Language)
1. System computes a base risk score from factors (exploit signals, enrichment, age decay, KEV, etc.).
2. If the finding’s asset is marked `external_exposure=true`, we multiply that score by a configurable factor (default 1.15). Example: 0.62 → 0.713.
3. Severity banding (CRITICAL/HIGH/MEDIUM/LOW) remains governed by the (possibly boosted) numeric risk. Adjust staging thresholds if drift is observed.

## How the Logistic Feature Works (Plain Language)
The emergence probability model is (conceptually) a logistic regression / shallow learner over a feature vector. We add a new dimension that simply says “is this externally exposed?”. Models can learn that (for example) an externally exposed MEDIUM with KEV listing might outrank an internal HIGH without exploit intelligence.

## Technical Details
Field additions inside `risk_recompute_all`:
```jsonc
factors: {
  "asset_external_exposure": true|false,
  "exposure_multiplier_applied": 1.15, // only when true
  "emergence_p": 0.xxx,
  ...
}
```

Computation order:
1. Derive base normalized score.
2. Populate dynamic predictive factors (drift, reservoir energy, feed confidence, emergence probability, etc.).
3. Look up asset exposure flag from the `assets` table (column `external_exposure`).
4. If external → apply multiplier; record `exposure_multiplier_applied`.
5. Persist updated `risk_score`, `risk_severity`, and `risk_factors` JSON.

Config parameter (overridable at runtime):
`vuln.risk.external_multiplier` (defaults to `1.15`).

## Governance / Audit Considerations
| Concern | Mitigation |
|---------|------------|
| Over‑inflating risk artificially | Multiplier deliberately small (<< 2x). Tune gradually. |
| Analyst confusion | Factor is explicitly stored in `risk_factors`. Surfaces in reports. |
| Model double counting later | Future retraining can reduce / remove multiplier once model proves stable encoding of exposure effect. |
| Scope creep (adding many multipliers) | Exposure is a primary contextual axis; additional axes must justify measurable triage improvement. |

## When to Adjust the Multiplier
Increase slightly (e.g. 1.15 → 1.2) if: external exploitable vulns still routinely buried under internal noise. Decrease if: internal critical items starved of attention or backlog bias emerges.

## FAQ (Analyst Friendly)
Q: Does this change CVSS?  A: No – it only changes our internal prioritization ordering.
Q: Could an attacker game this? A: Exposure flag comes from asset inventory, not user input.
Q: Why store the multiplier in factors? A: Transparency & downstream ML traceability.
Q: Will this disappear later? A: Possibly, if the predictive model subsumes it (feature importance confirms) – then we can safely dial back the static boost.

## RAG / Chunking Guidance
Key keywords for retrieval embeddings: "external exposure", "risk multiplier", "prioritization boost", "emergence probability feature", "asset context weighting".

---
Last updated: 2025-09-05
