# Neuron-AI Algorithm Documentation

## September 2025 Delta (Addendum 2): Retrieval Vector Modes, Persistence, Scheduler & Governance

### Lightweight Vector & Hybrid Vector Retrieval
The RAG corpus (`src/rag/corpus.py`) now supports two additional scoring modes controlled by `retrieval.scoring.mode`:

* `vector`: Cosine similarity over deterministic pseudo-embeddings (32-dim hashed token bins) replacing keyword scoring.
* `hybrid_vector`: Blends normalized keyword TF score with cosine similarity using weight `retrieval.hybrid.embedding_weight` (0..1).

Deterministic pseudo-embeddings avoid external model dependencies while enabling approximate semantic grouping for early experimentation. Embeddings are lazily generated per document and cached under the `embedding` key. The public helper `set_embedding(doc_id, embedding)` allows later injection of real model vectors.

### Persistence Extensions
* Threat Models: `threat/model_registry.py` supports `save()` / `load()` to `artifacts/threat_models.json`.
* RAG Corpus: `rag/corpus.py` supports `save()` / `load()` to `artifacts/rag_corpus.json` (stores id/text/metadata; tokens & embeddings rebuilt on load).
* Maintenance CLI: `scripts/maintenance_cli.py` provides commands:
    - `python -m scripts.maintenance_cli save-all` / `load-all`
    - `export-corpus <path>` / `import-corpus <path>` for portable snapshotting.

### Unified Report Scheduler
Periodic generation of executive & coverage report bundles via `scheduler/report_scheduler.py`, gated by runtime params:
* `report.bundle.enable` (bool)
* `report.bundle.interval_seconds` (int; default cadence)
Produces JSON/HTML artifacts consolidated by `reports/unified_pipeline.py` for downstream dashboards or archiving.

### Adaptive Weight Governance Loop
`governance/weight_governor.py` invokes the adaptive regulator (`adaptive/weight_regulator.py`) on interval to propose fusion (or other) weight adjustments. Controlled by:
* `governance.weight.enable`
* `governance.weight.interval_s`

Current implementation uses a placeholder observed metric (0.0) and audits applied adjustments; future work will wire real precision/recall proxies for closed-loop optimization.

### Hunting DSL Edge Coverage
Additional tests validate parser robustness for unsupported operators, regex, inequality, spacing, and case-insensitive logical connectors ensuring resilient threat hunting query handling.

### Coverage Matrix Validation
`coverage/attack_matrix.py` summary output now has integrity tests ensuring tactic-level aggregation aligns with global technique counts and ratios stay bounded.

---
## September 2025 Delta (Addendum 3): Metric-Governed Weights, On-Demand Reports, Embedding Provider, Artifact Versioning

### Real Metric Integration for Weight Governance
`governance/weight_governor.py` now sources the observed signal from the rolling SNN unique ratio gauge (`FUSION_SNN_UNIQUE_RATIO_ROLLING`) instead of a static placeholder. The loop reads the most recent gauge sample (best-effort) and feeds it into `adaptive.weight_regulator.propose_adjustment` for the `detection.temporal.weight` parameter. Audit context (observed, target, new value) is logged on adjustment.

### On-Demand Unified Report Endpoint
`/admin/report/generate` (admin key protected) triggers `reports.unified_pipeline.build_report_bundle` regardless of scheduler state, returning JSON & HTML artifact paths. This enables ad-hoc executive package generation (e.g., pre-board review) without waiting for the periodic scheduler.

### Pluggable Embedding Provider
`rag/embeddings.py` introduces a minimal provider abstraction (`set_provider`, `get_provider`). The corpus now first attempts the registered provider for vector / hybrid_vector modes; if absent it falls back to deterministic hash embeddings. This allows seamless future upgrade to real model embeddings without changing retrieval call sites.

### Artifact Versioning (Backward Compatible)
Persisted artifacts now wrap payloads with a version envelope:

* Threat Models (`artifacts/threat_models.json`): `{ "version": 1, "models": [...] }`
* RAG Corpus (`artifacts/rag_corpus.json`): `{ "version": 1, "documents": [...] }`

Load functions remain backward compatible with legacy list-only (v0) files. Increment `_ARTIFACT_VERSION` upon schema evolution; loaders should map old fields accordingly in future revisions.

### Vector Retrieval Test Coverage
`tests/test_rag_vector_modes.py` asserts vector & hybrid_vector modes return results and that ordering or scores differ from pure keyword scoring in at least one scenario, ensuring the new blend path is exercised.

---

## September 2025 Delta: Vulnerability Risk & Enrichment

### Enrichment Gating
Risk scoring now supports dynamic gating of enrichment factors (EPSS, KEV) via the runtime parameter `vuln.enrichment.apply`. When disabled, enrichment weights are excluded from normalization and risk calculation, ensuring deterministic fallback for test isolation and offline operation.

### Deterministic Enrichment Fixtures
For development and testing, deterministic enrichment fixtures are provided in `scanner/enrichment.py`. EPSS probabilities are derived from a stable hash of CVE IDs, and KEV membership is selected sparsely by hash modulo. This ensures reproducible enrichment values without external dependencies.

### Correlation Factor
Anomaly correlation is injected into risk scoring via a pseudo anomaly count per component, gated by `vuln.risk.weights.anomaly_correlation`. This factor is computed deterministically and can be tuned or disabled via runtime params.

### SLA Countdown Gauge
The metric `VULN_SLA_COUNTDOWN_DAYS` tracks the minimum remaining days to SLA breach for each severity among open findings. This enables dashboard and alerting integration for vulnerability remediation deadlines.

### /vuln/summary Endpoint
Aggregate vulnerability and finding statistics are exposed via the `/vuln/summary` API route, including counts, average risk, top findings, severity distribution, and enrichment coverage.

---

## Overview
This document provides detailed explanations of the complex algorithms and decision logic implemented in the Neuron-AI anomaly detection system.

## Core Detection Algorithms

### 1. Spiking Neural Network (SNN) Detection

#### Algorithm Overview
The SNN detector implements a neuromorphic computing approach to anomaly detection, converting continuous-valued features into spike trains for temporal pattern recognition.

#### Key Components

##### Rate Encoder V2 (`src/core/detect/snn.py:94-237`)
**Purpose**: Converts feature vectors into deterministic spike trains

**Algorithm Steps**:
1. **Normalization**: Uses robust statistics (median + MAD) for feature scaling
   ```
   median = median(feature_values)
   mad = median(|feature_values - median|)
   reference = median + mad
   normalized = feature_value / reference
   ```

2. **Burst Gating**: Features exceeding threshold get boost factor
   ```
   if feature_value > median + k*mad:
       normalized *= burst_boost_factor
   ```

3. **Rate Conversion**: Maps normalized values to spike rates
   ```
   spike_rate = min(max_rate, tanh(normalized) * max_rate)
   ```

4. **Density Capping**: Prevents spike density from exceeding limits
   ```
   if projected_spikes > density_cap * window_size:
       apply_proportional_scaling()
   ```

5. **Spike Generation**: Accumulates fractional spikes deterministically
   ```
   for timestep in window:
       accumulator += spike_rate
       if accumulator >= 1.0:
           emit_spike()
           accumulator -= 1.0
   ```

**Key Parameters**:
- `window`: Temporal window size (default: 20)
- `rate_scale`: Maximum spike rate (default: 1.0)
- `burst_k`: Burst detection multiplier (default: 3.0)
- `burst_boost`: Boost factor for bursts (default: 1.8)
- `density_cap`: Maximum spike density (default: 0.35)

##### LIF (Leaky Integrate-and-Fire) Model (`src/core/snn/model.py:53-73`)
**Purpose**: Processes spike trains to compute neural activity

**Algorithm**:
```python
voltage = 0.0
for timestep in spike_matrix:
    spike_input = sum(timestep)
    voltage = voltage * decay_factor + spike_input
return voltage
```

**Decision Logic**: Activity above threshold indicates anomaly
```python
anomaly_score = max(0, activity - threshold)
```

#### Auto-Calibration System (`src/core/detect/autocal.py`)
**Purpose**: Dynamically adjusts detection thresholds based on performance

**Algorithm**:
1. **Statistics Collection**: Tracks anomaly rates, baseline overlap
2. **Threshold Adjustment**: 
   ```
   if snn_anomaly_rate > target_rate:
       threshold += adjustment_step
   elif snn_anomaly_rate < min_rate:
       threshold -= adjustment_step
   ```
3. **Convergence Detection**: Stops when rate stabilizes

### 2. Baseline Statistical Detection

#### Algorithm Overview (`src/core/detect/baseline.py`)
Implements adaptive statistical anomaly detection with robust statistics.

#### Core Algorithm

##### Welford's Online Variance (`src/core/detect/baseline.py:29-50`)
**Purpose**: Efficiently compute running statistics

```python
def update(value, window):
    window.append(value)
    if len(window) > max_len:
        window.popleft()
        recompute_statistics()
    else:
        # Welford's method
        n = len(window)
        delta = value - mean
        mean += delta / n
        delta2 = value - mean
        m2 += delta * delta2
```

##### Median Absolute Deviation (MAD) Fallback
**Purpose**: Robust anomaly detection when variance is zero

```python
def mad_threshold(values):
    median = median(values)
    deviations = [abs(x - median) for x in values]
    mad = median(deviations)
    return mad_factor * 1.4826 * mad  # Scale to approximate stddev
```

#### Decision Logic
```python
if std_dev > 0:
    z_score = (value - mean) / std_dev
    is_anomaly = abs(z_score) >= threshold
else:
    # Fallback to MAD-based detection
    deviation = abs(value - median(window))
    is_anomaly = deviation >= mad_threshold(window)
```

### 3. Fusion Strategy

#### Weighted Temporal Fusion (`src/fusion/weighted_temporal.py`)
**Purpose**: Combines results from multiple detectors with temporal weighting

##### Algorithm Steps
1. **Weight Calculation**: Based on detector performance metrics
   ```python
   weight = base_weight * performance_factor * confidence_factor
   ```

2. **Temporal Decay**: Recent anomalies weighted more heavily
   ```python
   time_weight = exp(-decay_rate * age_seconds)
   final_weight = detector_weight * time_weight
   ```

3. **Score Aggregation**: Weighted sum of anomaly scores
   ```python
   fused_score = sum(weight[i] * score[i] for i in detectors) / sum(weights)
   ```

4. **Suppression Logic**: Removes redundant or low-confidence anomalies
   ```python
   if fused_score < suppression_threshold:
       suppress_anomaly()
   ```

#### Auto-Tuning System (`scripts/run_tuner.py`)
**Purpose**: Automatically adjusts fusion weights based on detector performance

##### Multi-Factor Tuning Algorithm
1. **Unique Contribution Tracking**:
   ```python
   unique_ratio = unique_anomalies / total_anomalies
   if unique_ratio > high_threshold:
       increase_weight()
   elif unique_ratio < low_threshold:
       decrease_weight()
   ```

2. **Precision Proxy Penalty**:
   ```python
   if false_positive_rate > penalty_threshold:
       weight_penalty = step_size * penalty_multiplier
       new_weight = max(min_weight, current_weight - weight_penalty)
   ```

3. **Cooldown Management**: Prevents rapid weight oscillation
   ```python
   if (current_time - last_adjustment) < cooldown_period:
       skip_adjustment()
   ```

## Risk Assessment Algorithms

### Vulnerability Risk Scoring (`src/scanner/risk.py`)

#### Multi-Factor Risk Model
**Purpose**: Comprehensive risk assessment combining multiple threat intelligence sources

##### Components
1. **Severity Scoring**: Maps categorical severity to numeric scale
   ```python
   severity_score = SEVERITY_ORDER.index(severity) / (len(SEVERITY_ORDER) - 1)
   ```

2. **Temporal Decay**: Risk decreases over time
   ```python
   age_days = (now - published_date).days
   temporal_factor = 0.5 ** (age_days / half_life_days)
   ```

3. **Exploitability Factors**:
   - EPSS Score: `epss_boost = epss_weight * epss_score` if `epss > threshold`
   - KEV Status: `kev_boost = kev_weight` if listed
   - Available Exploits: `exploit_boost = exploit_bonus_max * current_score`

4. **Asset Context**: `asset_factor = asset_criticality_score`

##### Final Risk Calculation
```python
raw_score = (
    severity_score * severity_weight +
    exploit_available * exploit_weight +
    temporal_factor * temporal_weight +
    asset_factor * asset_weight +
    epss_boost + kev_boost
) / total_weights

# Apply exploit bonus
if exploit_available:
    raw_score = min(1.0, raw_score + exploit_bonus)
```

## Natural Language Processing

### Query Translation (`src/nlp/translator.py`)

#### Rule-Based IR Generation
**Purpose**: Converts natural language queries to structured intermediate representation

##### Algorithm Steps
1. **Tokenization**: Split on whitespace and punctuation
2. **Domain Detection**: Identify target (vulnerabilities vs findings)
3. **Semantic Parsing**:
   ```python
   # Severity extraction
   for token in tokens:
       if token in SEVERITY_WORDS:
           clauses.append({
               'type': 'severity',
               'operator': 'equals',
               'value': SEVERITY_WORDS[token]
           })
   ```

4. **Pattern Matching**: Regular expressions for complex patterns
   ```python
   # Age patterns: "older than N days"
   match = re.search(r"older than (\d+) days", query)
   if match:
       clauses.append({
           'type': 'age',
           'operator': '>',
           'value': int(match.group(1))
       })
   ```

5. **Confidence Scoring**: Based on recognized token ratio
   ```python
   confidence = (recognized_tokens / total_tokens) ** 0.65
   ```

## Performance Optimization Strategies

### Resource Guards

#### SNN Resource Guard (`src/core/detect/snn.py:525-546`)
**Purpose**: Prevents resource exhaustion under load

```python
def evaluate_resource_guard(latency_samples, spike_density):
    # P95 latency check
    if latency_samples:
        p95_latency = percentile(latency_samples, 95)
        if p95_latency > max_latency_threshold:
            return True
    
    # Spike density check
    if spike_density > max_density_threshold:
        return True
    
    return False
```

#### Rate Limiting (`src/core/ratelimit.py`)
**Purpose**: Controls event ingestion rate per tenant

**Token Bucket Algorithm**:
```python
def allow_request(tenant_id):
    bucket = get_bucket(tenant_id)
    now = time.time()
    
    # Add tokens based on elapsed time
    elapsed = now - bucket.last_update
    tokens_to_add = elapsed * refill_rate
    bucket.tokens = min(bucket_capacity, bucket.tokens + tokens_to_add)
    bucket.last_update = now
    
    # Check if request can be served
    if bucket.tokens >= 1:
        bucket.tokens -= 1
        return True
    return False
```

### Memory Management

#### Sequence Buffers (`src/core/sequence/buffer.py`)
**Purpose**: Bounded memory usage for temporal data

```python
class SequenceBuffer:
    def add(self, value):
        if len(self.buffer) >= self.max_size:
            self.buffer.popleft()  # Remove oldest
        self.buffer.append(value)
```

## Metrics and Monitoring

### Prometheus Integration (`src/core/metrics.py`)
**Purpose**: Real-time system monitoring and alerting

#### Key Metrics Categories
1. **Throughput**: Events/second, anomalies/second
2. **Latency**: Processing time distributions
3. **Quality**: Precision proxies, suppression rates
4. **Resource**: Memory usage, CPU utilization
5. **Detector-Specific**: Spike density, calibration events

#### Example Metric Definition
```python
SNN_INFERENCE_LATENCY = Histogram(
    "neuron_snn_inference_latency_seconds",
    "SNN detector inference latency",
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1),
    registry=registry()
)
```

## Configuration Management

### Runtime Parameters (`src/config/runtime_params.py`)
**Purpose**: Dynamic configuration without restarts

```python
def get_param(key, default=None):
    # Check environment override
    env_value = os.getenv(f"NEURON_{key.upper().replace('.', '_')}")
    if env_value:
        return env_value
    
    # Check database/file config
    stored_value = storage.get(key)
    return stored_value or default
```

## Decision Trees and Thresholds

### Anomaly Severity Classification
```
Raw Score → Severity Label:
>= 0.85 → CRITICAL
>= 0.65 → HIGH  
>= 0.4  → MEDIUM
>  0    → LOW
== 0    → NONE
```

### Fusion Suppression Logic
```
if suppression_rate > alert_threshold:
    trigger_alert("High suppression rate detected")
    
if unique_contribution < min_threshold:
    reduce_detector_weight()
    
if false_positive_rate > hard_cap:
    apply_double_penalty()
```

## Error Handling and Recovery

### Graceful Degradation Patterns
1. **Detector Failures**: Continue with remaining detectors
2. **Storage Failures**: Use in-memory fallback
3. **Network Issues**: Implement retry with exponential backoff
4. **Resource Exhaustion**: Activate resource guards

### Circuit Breaker Pattern
```python
if consecutive_failures > failure_threshold:
    open_circuit()
    return cached_result()

if circuit_half_open and test_request_succeeds():
    close_circuit()
```

This documentation provides the foundation for understanding the complex decision-making processes within the Neuron-AI system.