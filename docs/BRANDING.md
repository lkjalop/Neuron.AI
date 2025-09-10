# Branding & Design Tokens (Draft)

Status: Draft – Establishes initial visual + verbal identity primitives for future dashboard & docs. All tokens are *proposed*; modify only with audit entry.

## 1. Brand Pillars
| Pillar | Description | Tone Cues |
|--------|-------------|-----------|
| Transparent Intelligence | Always explain *why* an alert fired | "because", causal connectors |
| Governed Evolution | Changes are deliberate & auditable | verbs: "recorded", "verified" |
| Human-Centric Acceleration | Amplify analysts, never obscure | active voice, low jargon |
| Neuromorphic Pragmatism | Innovation only with evidence | words: "uplift", "baseline" |

## 2. Naming Conventions
| Concept | Pattern | Example |
|---------|---------|---------|
| Metrics | `neuron_<noun>_...` | `neuron_anomalies_total` |
| Feature Flags | UPPER_SNAKE | `ENABLE_SNN_SHADOW` |
| Runtime Params | dotted lower | `baseline.stddev_threshold` |
| Endpoints (Exec) | `/executive/<noun>` | `/executive/summary` |
| Internal Modules | snake_case | `resource_monitor.py` |

## 3. Color Tokens
(Accessible contrast aim: WCAG AA for text ≥ 14px.)

| Token | Hex | Usage |
|-------|-----|-------|
| `color.bg.base` | `#0F1115` | App background / dark theme base |
| `color.bg.panel` | `#161A20` | Panels / cards |
| `color.border.muted` | `#2A313C` | Dividers / outlines |
| `color.text.primary` | `#E6ECF2` | Primary text |
| `color.text.secondary` | `#9AA7B5` | Secondary text |
| `color.accent.primary` | `#4F9BFF` | Interactive / links |
| `color.accent.success` | `#3BC482` | Healthy status |
| `color.accent.warning` | `#F6C552` | Degraded / heads-up |
| `color.accent.danger` | `#FF5F56` | Critical / failure |
| `color.graph.anomaly` | `#FF5F56` | Anomaly points |
| `color.graph.baseline` | `#4F9BFF` | Baseline series |
| `color.graph.snn` | `#9B59FF` | SNN series (Phase 3+) |

## 4. Typography Tokens
| Token | Value | Notes |
|-------|-------|-------|
| `font.family.base` | `Inter, system-ui, sans-serif` | Modern legibility |
| `font.size.sm` | `12px` | Metadata, labels |
| `font.size.md` | `14px` | Body text |
| `font.size.lg` | `18px` | Section headings |
| `font.size.xl` | `24px` | Dashboard key KPI |
| `font.weight.regular` | 400 | Body |
| `font.weight.medium` | 500 | Emphasis |
| `font.weight.semibold` | 600 | Headings |

## 5. Spacing & Layout Tokens
| Token | Value |
|-------|-------|
| `space.xs` | 4px |
| `space.sm` | 8px |
| `space.md` | 12px |
| `space.lg` | 16px |
| `space.xl` | 24px |
| `radius.sm` | 3px |
| `radius.md` | 6px |

## 6. Iconography Guidelines
- Use a minimal set: anomaly (spark), baseline (line), SNN (pulse), governance (shield), param change (sliders).
- Outline style at 1.5px stroke for dark background clarity.

## 7. Tone & Microcopy
| Scenario | Preferred Style | Example |
|----------|-----------------|---------|
| Successful param update | Past tense, audit anchored | "Threshold updated (A09 audit)." |
| Anomaly highlight | Causal justification | "CPU spike 3.7σ above rolling mean." |
| Warning state | Actionable next step | "Elevated anomaly rate. Run threshold sweep?" |
| Safe mode | Calm reassurance | "Safe mode active; baseline only while SNN stabilizes." |

## 8. Data Visualization Rules
| Element | Rule |
|---------|------|
| Anomaly Marker | Use `color.graph.anomaly`, filled circle, size 6px |
| Baseline Series | Solid line, 2px, `color.graph.baseline` |
| SNN Series | Dashed line (4 3), 2px, `color.graph.snn` |
| Confidence Band | 20% opacity of series color |
| Alert Banner | `color.accent.warning` background, `color.text.primary` text |

## 9. Theming Extension Points
Expose token JSON for frontend consumption (future): `artifacts/branding/tokens.json` (generation script TBD).

## 10. Change Control
All token changes require: reason, accessibility check, audit entry, version bump in token manifest.

## 11. Future Considerations
- Light theme variant
- Motion tokens for subtle transitions (avoid distraction)
- Internationalization microcopy guidelines

## 12. Quick Reference (JSON Snippet)
```json
{
  "color": {"accent": {"primary": "#4F9BFF", "danger": "#FF5F56"}},
  "font": {"size": {"md": "14px", "xl": "24px"}},
  "space": {"sm": 8, "lg": 16}
}
```

---
Draft complete; integrate token export script in a later iteration.
