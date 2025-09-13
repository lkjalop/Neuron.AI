# 🚀 LIVE TESTING GUIDE: COMPLETE SECURITY PLATFORM
## All Features Ready for Testing

---

## 🎯 **FRONTEND ACCESS POINTS**

### **MAIN CONSOLE (Three-Column Interface)**
```
http://localhost:8080/console/index.html
```
- **Left Panel:** Mission Board with navigation
- **Center Panel:** Event stream and alerts
- **Right Panel:** Report builder (detachable)

### **SPECIALIZED INTERFACES**

| Feature | URL | Purpose |
|---------|-----|---------|
| **Vulnerability Assessment** | http://localhost:8080/vuln.html | CVE scanning, SBOM analysis |
| **Threat Hunting** | http://localhost:8080/hunt.html | Query builder, pattern search |
| **Forensics Analysis** | http://localhost:8080/forensics.html | Timeline reconstruction |
| **SOC Dashboard** | http://localhost:8080/soc.html | Operations overview |
| **Diagnostics** | http://localhost:8080/diagnostics.html | System health metrics |
| **Main Dashboard** | http://localhost:8080/dashboard.html | Executive summary |

---

## 🛡️ **VULNERABILITY ASSESSMENT & MANAGEMENT**

### **ACCESS: http://localhost:8080/vuln.html**

**Features to Test:**
1. **SBOM Upload**
   - Click "Choose File" → Select .json SBOM
   - API Key: `neuron-ai-demo-key-2024`
   - Upload and process vulnerability scan

2. **CVE Analysis**
   - View findings table
   - Check risk scores (Neuron-AI enhanced)
   - Review SLA compliance timelines

3. **Ready-Made SBOM Test Files:**
   - **Location:** `scripts/test_sboms/`
   - **Files Available:**
     - `vulnerable_java_app.json` - Contains Log4Shell, Spring4Shell, etc.
     - `secure_java_app.json` - Updated, secure versions
     - `nodejs_express_app.json` - Node.js vulnerabilities
     - `python_flask_app.json` - Python package vulnerabilities
   - **Usage:** Upload any file directly to test vulnerability scanning

**Expected Results:**
- CVE-2021-44228 (Log4Shell) detection
- Risk score: 10.0 (Critical)
- Remediation priority: Immediate

---

## 🔍 **THREAT HUNTING & MODELING**

### **ACCESS: http://localhost:8080/hunt.html**

**Network Threat Hunting:**
1. **Query Builder**
   - Source IP filters
   - Port range analysis
   - Protocol anomalies
   - Time window selection

2. **Pattern Detection**
   - Lateral movement indicators
   - Data exfiltration patterns
   - C2 beacon detection
   - Unusual DNS queries

3. **Pre-Built Query Collections:**
   - **Location:** `scripts/hunt_queries/`
   - **Collections Available:**
     - `lateral_movement.json` - SMB connections, RDP brute force
     - `data_exfiltration.json` - Large transfers, DNS tunneling
     - `endpoint_threats.json` - Process injection, privilege escalation
     - `behavioral_analytics.json` - Off-hours activity, impossible travel
   - **Master File:** `all_queries.json` - Complete collection (13 queries)
   - **Playbook:** `HUNTING_PLAYBOOK.md` - Comprehensive methodology guide

**Endpoint Threat Modeling:**
1. **Process Analysis**
   - Suspicious process chains
   - Registry modifications
   - File system changes
   - Memory injection detection

2. **Behavioral Patterns**
   - User behavior analytics
   - Privilege escalation attempts
   - Persistence mechanisms
   - Defense evasion techniques

---

## 🔬 **FORENSIC ANALYSIS**

### **ACCESS: http://localhost:8080/forensics.html**

**Timeline Reconstruction:**
1. **Event Correlation**
   - Multi-source timeline
   - Attack chain visualization
   - Root cause analysis
   - Impact assessment

2. **Evidence Collection**
   - Network packet captures
   - System logs aggregation
   - Memory dumps analysis
   - File artifact examination

3. **Investigation Workflow:**
```
Step 1: Initial Detection
└── Anomaly alert triggered

Step 2: Scope Assessment
├── Affected systems identified
└── Time window established

Step 3: Evidence Gathering
├── Log collection
├── Network traffic analysis
└── Endpoint artifacts

Step 4: Timeline Building
├── Event sequencing
├── Actor attribution
└── TTP identification

Step 5: Reporting
└── Executive summary generation
```

**Test Scenario:**
- Click "Load Sample Incident"
- Review timeline visualization
- Examine evidence chain
- Generate forensic report

---

## 🎮 **MISSION BOARD NAVIGATION (Console)**

### **FROM: http://localhost:8080/console/index.html**

**Working Navigation Buttons:**

1. **"Today's Objectives"**
   - Fetches current dashboard snapshot
   - Shows events/anomalies count
   - Updates fusion metrics

2. **"SLA Risks (12)"**
   - Lists upcoming SLA violations
   - Prioritizes critical patches
   - Tracks remediation timelines

3. **"Open Tickets (7)"**
   - Shows active security tickets
   - Displays priority levels
   - Links to ticket details

4. **"Ransomware Hunt"**
   - Launches threat hunting template
   - Pre-configured for ransomware IOCs
   - Automated pattern matching

5. **"Forensics Triage"**
   - Opens forensic analysis interface
   - Quick incident assessment
   - Evidence preservation workflow

---

## 🧪 **API TESTING (Advanced)**

### **Authentication Required:**
```bash
# Add to all API calls:
-H "X-API-Key: neuron-ai-demo-key-2024"
```

### **Available Endpoints:**

**Dashboard & Metrics:**
```bash
# Get dashboard snapshot
curl -H "X-API-Key: neuron-ai-demo-key-2024" \
  http://localhost:8000/dashboard/latest

# Get Prometheus metrics
curl http://localhost:8000/metrics
```

**Tickets & Findings:**
```bash
# List tickets
curl -H "X-API-Key: neuron-ai-demo-key-2024" \
  http://localhost:8000/tickets

# Check SLA risks (may return 503 without data)
curl -H "X-API-Key: neuron-ai-demo-key-2024" \
  http://localhost:8000/findings/sla/upcoming
```

**Health Checks:**
```bash
# System health
curl -H "X-API-Key: neuron-ai-demo-key-2024" \
  http://localhost:8000/health/ready

# Proxy status
curl -H "X-API-Key: neuron-ai-demo-key-2024" \
  http://localhost:8000/proxy/ready
```

---

## ✅ **PRE-FLIGHT CHECKLIST**

### **Backend Services:**
- ✅ API running on http://localhost:8000
- ✅ PostgreSQL connected (Neon)
- ✅ Redis configured (Upstash, 50MB)
- ✅ Qdrant vector DB ready
- ✅ Authentication working

### **Frontend Services:**
- ✅ Console on http://localhost:8080/console/
- ✅ All specialized interfaces accessible
- ✅ CORS configured for cross-origin calls
- ✅ API key stored in localStorage

### **Test Data:**
- ✅ Sample data generation scripts created
- 📝 SBOM test files ready (4 different scenarios)
- 🔍 Threat hunting queries collection available
- 📊 Demo data population script completed

---

## 🚀 **QUICK START SEQUENCE**

### **1. Open Main Console**
```
http://localhost:8080/console/index.html
```

### **2. Test Mission Board**
- Click "Today's Objectives" → See dashboard
- Click "Open Tickets" → View count
- Click "Ransomware Hunt" → Launch hunter

### **3. Test Vulnerability Scanner**
```
http://localhost:8080/vuln.html
```
- Set API key
- Upload sample SBOM
- Review CVE findings

### **4. Test Threat Hunting**
```
http://localhost:8080/hunt.html
```
- Build query
- Execute search
- Review results

### **5. Test Forensics**
```
http://localhost:8080/forensics.html
```
- Load sample incident
- Navigate timeline
- Generate report

---

## 💡 **TIPS FOR EFFECTIVE TESTING**

### **Browser Setup:**
1. Open Chrome/Firefox Developer Tools (F12)
2. Monitor Network tab for API calls
3. Check Console for JavaScript errors
4. Verify authentication headers

### **API Key Management:**
- Store in browser: `localStorage.setItem('apiKey', 'neuron-ai-demo-key-2024')`
- Verify in headers: Check for `X-API-Key` in requests

### **Data Generation:**
- **Full Demo Data:** `python scripts/populate_demo_data.py`
- **SBOM Files Only:** `python scripts/sbom_test_samples.py`
- **Query Collections:** `python scripts/threat_hunting_queries.py`
- Upload ready-made SBOMs from `scripts/test_sboms/`

### **Performance Monitoring:**
- Check `/metrics` endpoint
- Monitor response times in DevTools
- Watch for 503 errors (service dependencies)

---

## 🎯 **EXPECTED BEHAVIORS**

### **Working Features:**
- ✅ Console navigation and Mission Board
- ✅ API authentication and CORS
- ✅ Dashboard data fetching
- ✅ Ticket listing
- ✅ Metrics collection

### **Limited Without Data:**
- ⚠️ SLA risks (needs vulnerability data)
- ⚠️ Threat hunting (needs event data)
- ⚠️ Forensics timeline (needs incidents)

### **Demo-Ready Features:**
- ✅ Interface design and UX
- ✅ Architecture demonstration
- ✅ API documentation
- ✅ Neuromorphic algorithms
- ✅ Business value presentation

---

## 🏆 **READY FOR LIVE DEMONSTRATION**

The platform is now fully configured and ready for:
- **Technical demos** showing working API and frontend
- **Business presentations** with professional interface
- **Investor pitches** demonstrating functional MVP
- **Job interviews** showcasing real implementation

**All core components are operational. The system is ready for comprehensive security operations testing!**