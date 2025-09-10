# NEURON Platform - Security Testing & Threat Hunting Guide

## 🔒 Overview
This guide provides comprehensive instructions for testing the NEURON platform's security capabilities, including vulnerability scanning, threat modeling, and threat hunting features.

## 📋 Prerequisites

```bash
# Install security testing dependencies
pip install bandit safety pip-audit semgrep

# Install additional testing tools
pip install pytest-cov hypothesis locust

# For threat modeling
pip install pytm threatspec
```

## 🚀 Quick Start

### 1. Start the Core Platform

```bash
# Set environment variables for full security features
$env:VULN_SCAN_ENABLED = "1"
$env:EXPERIMENTAL_ISOFOREST = "true"
$env:ENABLE_SNN = "true"
$env:ENABLE_FUSION = "true"
$env:NEURON_DEBUG = "true"

# Start the API server
python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
```

### 2. Run Initial Tests

```bash
# Run all security-related tests
pytest tests/test_security_governance.py -v
pytest tests/test_attack_simulation.py -v
pytest tests/test_scanner_*.py -v

# Run vulnerability scanner tests
pytest tests/scanner/ -v
```

## 🔍 Vulnerability Testing

### A. Static Code Analysis

```powershell
# Run Bandit for Python security issues
bandit -r src -f json -o artifacts/security/bandit_report.json

# Run safety check on dependencies
safety check --json > artifacts/security/safety_report.json

# Run pip-audit for known vulnerabilities
pip-audit -r requirements.txt -f json -o artifacts/security/pip_audit.json

# Use the provided PowerShell script
.\scripts\security_scan.ps1
```

### B. Dynamic Vulnerability Scanning

```bash
# Ingest a test SBOM for vulnerability scanning
curl -X POST http://localhost:8000/vuln/ingest_sbom \
  -H "Content-Type: application/json" \
  -d '{
    "asset_name": "test-service",
    "document": {
      "components": [
        {"name": "openssl", "version": "3.0.13", "purl": "pkg:openssl/openssl@3.0.13"},
        {"name": "log4j", "version": "2.14.0", "purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.0"}
      ]
    },
    "asset_metadata": {"criticality": 0.9}
  }'

# List detected vulnerabilities
curl http://localhost:8000/vulnerabilities?severity=HIGH

# Get vulnerability summary
curl http://localhost:8000/vuln/summary
```

### C. Simulate Attack Patterns

```python
# Create a test script: test_attack_patterns.py
import requests
import json
import time

API_URL = "http://localhost:8000"

def simulate_attack_pattern(pattern_type):
    """Simulate various attack patterns for testing"""
    
    if pattern_type == "credential_stuffing":
        # Rapid authentication attempts
        for i in range(100):
            event = {
                "event_type": "auth_failure",
                "severity": 0.7,
                "features": {
                    "failed_attempts": i,
                    "source_ip_entropy": 0.9,
                    "user_agent_diversity": 0.1
                },
                "metadata": {
                    "attack_pattern": "credential_stuffing"
                }
            }
            requests.post(f"{API_URL}/ingest", json=event)
            time.sleep(0.1)
    
    elif pattern_type == "port_scan":
        # Sequential port access pattern
        for port in range(1000, 1100):
            event = {
                "event_type": "network_scan",
                "features": {
                    "port": port,
                    "scan_velocity": 100,
                    "connection_attempts": 1
                },
                "metadata": {
                    "attack_pattern": "port_scan"
                }
            }
            requests.post(f"{API_URL}/ingest", json=event)
    
    elif pattern_type == "data_exfiltration":
        # Large data transfer anomaly
        event = {
            "event_type": "data_transfer",
            "severity": 0.9,
            "features": {
                "bytes_transferred": 10000000000,  # 10GB
                "transfer_rate": 1000000,  # 1MB/s
                "destination_reputation": -0.8
            },
            "metadata": {
                "attack_pattern": "data_exfiltration"
            }
        }
        requests.post(f"{API_URL}/ingest", json=event)

# Run simulations
simulate_attack_pattern("credential_stuffing")
simulate_attack_pattern("port_scan")
simulate_attack_pattern("data_exfiltration")
```

## 🎯 Threat Modeling

### A. System Threat Model

```python
# Create threat_model.py
from pytm import TM, Server, Datastore, Dataflow, Boundary, Actor

tm = TM("NEURON Platform")
tm.description = "Neuromorphic Security Intelligence Platform"

# Define boundaries
internet = Boundary("Internet")
platform = Boundary("NEURON Platform")

# Define actors
analyst = Actor("Security Analyst")
attacker = Actor("Attacker")

# Define components
api_server = Server("API Server")
api_server.inBoundary = platform
api_server.OS = "Linux"
api_server.isHardened = True

event_store = Datastore("Event Store")
event_store.inBoundary = platform
event_store.isSQL = False
event_store.inScope = True

vuln_db = Datastore("Vulnerability DB")
vuln_db.inBoundary = platform
vuln_db.isSQL = True
vuln_db.inScope = True

# Define data flows
analyst_to_api = Dataflow(analyst, api_server, "API Requests")
analyst_to_api.protocol = "HTTPS"
analyst_to_api.dstPort = 8000

api_to_event = Dataflow(api_server, event_store, "Store Events")
api_to_vuln = Dataflow(api_server, vuln_db, "Query Vulnerabilities")

# Generate threat model
tm.process()
```

### B. STRIDE Analysis

```bash
# Run STRIDE analysis on key components
python scripts/threat_analysis.py --model stride --component api_server
python scripts/threat_analysis.py --model stride --component event_store
```

## 🔎 Threat Hunting

### A. Hunt for Anomalies

```bash
# Query for baseline anomalies
curl http://localhost:8000/anomalies?detector=baseline&limit=100

# Query for SNN-detected anomalies
curl http://localhost:8000/anomalies?detector=snn&limit=100

# Query fusion results
curl http://localhost:8000/anomalies?detector=fusion&limit=100
```

### B. Advanced Hunting Queries

```python
# Create hunt_queries.py
import requests
import json

def hunt_lateral_movement():
    """Hunt for lateral movement indicators"""
    query = {
        "event_type": ["auth_success", "remote_access"],
        "features": {
            "source_ip_internal": True,
            "destination_ip_internal": True,
            "unusual_time": True
        },
        "time_range": "last_24h"
    }
    response = requests.post("http://localhost:8000/hunt", json=query)
    return response.json()

def hunt_persistence():
    """Hunt for persistence mechanisms"""
    query = {
        "event_type": ["service_creation", "scheduled_task", "registry_modification"],
        "features": {
            "system_startup": True,
            "privileged_operation": True
        }
    }
    response = requests.post("http://localhost:8000/hunt", json=query)
    return response.json()

def hunt_privilege_escalation():
    """Hunt for privilege escalation attempts"""
    query = {
        "event_type": ["process_creation", "token_manipulation"],
        "features": {
            "parent_process_privilege": "low",
            "child_process_privilege": "high",
            "suspicious_process_tree": True
        }
    }
    response = requests.post("http://localhost:8000/hunt", json=query)
    return response.json()

# Execute hunts
lateral_results = hunt_lateral_movement()
persistence_results = hunt_persistence()
privesc_results = hunt_privilege_escalation()

print(f"Lateral Movement Indicators: {len(lateral_results)}")
print(f"Persistence Mechanisms: {len(persistence_results)}")
print(f"Privilege Escalation Attempts: {len(privesc_results)}")
```

### C. Correlation Analysis

```bash
# Run correlation between vulnerabilities and anomalies
python scripts/correlate_vuln_anomalies.py

# Check for exploit correlation
curl http://localhost:8000/correlations?type=exploit_activity
```

## 📊 Dashboard & Visualization

### A. Backend API Testing

```bash
# Test dashboard endpoints
curl http://localhost:8000/dashboard/latest
curl http://localhost:8000/vulnerabilities
curl http://localhost:8000/assets
curl http://localhost:8000/system/gate_status
```

### B. Metrics & Monitoring

```bash
# Access Prometheus metrics
curl http://localhost:8000/metrics

# Key metrics to monitor:
# - neuron_events_total
# - neuron_anomalies_total
# - neuron_snn_inference_latency_seconds
# - neuron_fusion_anomalies_total
# - neuron_vuln_findings_total
```

### C. Generate Reports

```bash
# Generate executive summary
curl -X POST http://localhost:8000/reports/exec_summary

# Download HTML report
curl http://localhost:8000/reports/latest -o report.html
```

## 🧪 Performance & Load Testing

```python
# Create load_test.py using Locust
from locust import HttpUser, task, between
import random
import json

class NeuronUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(10)
    def ingest_event(self):
        event = {
            "event_type": random.choice(["network", "auth", "file"]),
            "features": {
                "value": random.gauss(0, 1),
                "count": random.randint(0, 100),
                "rate": random.random()
            }
        }
        self.client.post("/ingest", json=event)
    
    @task(5)
    def query_vulnerabilities(self):
        self.client.get("/vulnerabilities?limit=10")
    
    @task(3)
    def check_anomalies(self):
        self.client.get("/anomalies?limit=20")
    
    @task(1)
    def get_dashboard(self):
        self.client.get("/dashboard/latest")

# Run with: locust -f load_test.py --host=http://localhost:8000
```

## 🛡️ Security Hardening Checklist

- [ ] Run all static security analyzers (bandit, safety, pip-audit)
- [ ] Test with malformed inputs and edge cases
- [ ] Verify tenant isolation with multi-tenant tests
- [ ] Check rate limiting and DoS protection
- [ ] Validate authentication and authorization
- [ ] Test encryption for sensitive data
- [ ] Verify audit logging completeness
- [ ] Check for information disclosure vulnerabilities
- [ ] Test failover and recovery mechanisms
- [ ] Validate input sanitization and validation

## 📈 Continuous Security Testing

```yaml
# Create .github/workflows/security.yml for CI/CD
name: Security Testing
on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run Bandit
        run: bandit -r src -f json
      
      - name: Run Safety
        run: safety check
      
      - name: Run Security Tests
        run: pytest tests/test_security*.py
      
      - name: SAST Scan
        uses: AppThreat/sast-scan-action@master
```

## 🚨 Incident Response Testing

```bash
# Simulate security incident
python scripts/simulate_incident.py --type ransomware

# Check detection
curl http://localhost:8000/incidents/active

# Verify response actions
curl http://localhost:8000/response/recommendations
```

## 📚 Additional Resources

- [NEURON Threat Model](docs/THREAT_MODEL.md)
- [Security Practices](docs/SECURITY_PRACTICES.md)
- [SOC Analyst Guide](docs/SOC_ANALYST_GUIDE.md)
- [Attack Matrix Coverage](tests/test_coverage_attack_matrix.py)

## ⚠️ Important Notes

1. **Never run these tests in production** - Use isolated test environment
2. **Monitor resource usage** - Some tests are resource-intensive
3. **Review all findings** - Not all detections are true positives
4. **Document results** - Keep audit trail of all security testing
5. **Follow responsible disclosure** - Report any real vulnerabilities properly

## 🎯 Next Steps

1. Set up automated security testing pipeline
2. Integrate with SIEM/SOAR platforms
3. Develop custom threat hunting playbooks
4. Create attack simulation scenarios
5. Build threat intelligence feeds integration

---

*Remember: Security testing is an ongoing process. Regular testing and updates are essential for maintaining a robust security posture.*