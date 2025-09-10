# Connector & Detector Specification (Batch 5)

## Overview
This document defines the JSON payload schemas for the new domain ingestion connectors and the behavioral/network detectors introduced in Batch 5.

Connectors normalize incoming source‑specific events into the internal generic event model consumed by the detection pipeline. Each connector POST endpoint returns a lightweight status plus any anomalies generated synchronously.

## Connectors
### 1. EDR (`POST /ingest/edr`)
Example:
```json
{
  "user": "alice",          // optional user / principal
  "process_name": "reg.exe", // leaf process name
  "parent_process": "powershell.exe", // parent process name
  "command_line": "reg add HKCU\\Software\\Run",
  "dst_ip": "10.0.0.15"      // optional destination IP (if network activity)
}
```

### 2. DNS (`POST /ingest/dns`)
```json
{
  "query": "abcd1234longsubdomain.example.com", // FQDN requested
  "src_ip": "192.168.1.10"                      // optional origin host IP
}
```

### 3. Netflow (`POST /ingest/netflow`)
```json
{
  "src_ip": "192.168.1.10",
  "dst_ip": "8.8.8.8",
  "bytes": 512,
  "protocol": "tcp" // optional
}
```

### 4. SIEM (`POST /ingest/siem`)
Flexible catch‑all for already normalized security events.
```json
{
  "message": "Failed login",
  "user": "bob",
  "src_ip": "10.0.0.5",
  "dst_ip": "10.0.0.20"
}
```

## Behavioral / Network Detectors
Each detector emits anomaly records shaped:
```json
{
  "detector": "<name>",
  "score": 0.8,
  "reason": "short_explanation",
  "metadata": { ... },
  "mitre_techniques": ["TXXXX", ...],
  "threat_intel": {"score": 0.73, "tags": ["heuristic", "stub"]}
}
```

### lateral_movement
Heuristic: Track distinct destination IPs per user. When distinct count >= 5 (configurable in code) a new destination triggers an anomaly.
Metadata fields: `user`, `distinct_dests`.
Candidate MITRE: T1021, T1080.

### persistence
Heuristic: Suspicious parent → child process combination (e.g., `powershell.exe` spawning `reg.exe`, `schtasks.exe`, etc.).
Metadata: `parent`, `proc`, `cmd`.
Candidate MITRE: T1547, T1050.

### beaconing
Heuristic: Low‑jitter periodic netflow intervals per (src,dst) with average interval < 60s and std dev < 15% of mean for recent window (>=5 intervals).
Metadata: `src`, `dst`, `avg_interval_s`, `std`.
Candidate MITRE: T1071, T1095.

### dns_tunneling
Heuristic: DNS query whose first label length > 30 and high character uniqueness ratio (>0.6).
Metadata: `query`, `label_len`, `unique_ratio`.
Candidate MITRE: T1095, T1572.

## Enrichment Modules
- MITRE Enrichment (`mitre_enrichment.enrich_with_mitre`): Static mapping based on detector name (idempotent).
- Threat Intel Enrichment (`intel_enrichment.enrich_with_intel`): Stub assigning deterministic pseudo score + tags.
Both are chained in fusion arbitrator after strategy selection to ensure uniform coverage.

## Runtime Parameters (Behavioral Detectors)
The following runtime params (when supported by the active param store) allow tuning without code changes:

| Param Key | Detector | Description | Default |
|-----------|----------|-------------|---------|
| `detector.lateral.threshold` | lateral_movement | Distinct destination count threshold per user | 5 |
| `detector.lateral.ttl_seconds` | lateral_movement | TTL window for counting distinct destinations | 1800 |
| `detector.beacon.min_intervals` | beaconing | Minimum intervals required before evaluation | 5 |
| `detector.beacon.max_intervals` | beaconing | Max stored intervals per flow key | 12 |
| `detector.beacon.ttl_seconds` | beaconing | Flow inactivity TTL for pruning | 1800 |
| `detector.beacon.jitter_ratio` | beaconing | Max std/avg jitter ratio allowed to qualify | 0.15 |
| `detector.beacon.max_avg_interval` | beaconing | Max average interval (seconds) to qualify | 60 |
| `detector.dns.min_label_len` | dns_tunneling | Minimum first label length | 30 |
| `detector.dns.min_unique_ratio` | dns_tunneling | Minimum unique char ratio in first label | 0.6 |
| `detector.persistence.parents` | persistence | List override suspicious parent processes | [powershell.exe, cmd.exe, bash] |
| `detector.persistence.targets` | persistence | List override target child processes | [reg.exe, schtasks.exe, launchctl, systemctl] |

All parameters are optional; missing values fall back to defaults in code.

## Testing Strategy
`tests/test_behavioral_detectors.py` crafts synthetic events to trigger each detector and asserts presence of enrichment fields.

## Future Enhancements
- Externalized thresholds (runtime params) for detector tuning.
- Stateful decay / time‑window expiration for lateral movement user map.
- Real threat intel feed correlation (IOC / reputation).
- Expanded MITRE mapping using metadata context (e.g., specific registry paths, service installation flags).

