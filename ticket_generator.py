#!/usr/bin/env python3
"""
NEURON Platform - Ticket Generation Templates
Standard templates for SOC ticket creation
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any
import requests

class TicketGenerator:
    """Generate standardized tickets from NEURON detections"""
    
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
        
    def create_incident_ticket(self, anomaly_data: Dict) -> Dict:
        """Create incident ticket from anomaly detection"""
        
        # Determine severity based on NEURON's risk score
        severity = self._calculate_severity(anomaly_data)
        
        ticket = {
            "ticket_type": "SECURITY_INCIDENT",
            "ticket_id": f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "created_date": datetime.now().isoformat(),
            "severity": severity,
            "priority": self._map_priority(severity),
            
            # Standard fields
            "title": self._generate_title(anomaly_data),
            "description": self._generate_description(anomaly_data),
            
            # Detection details
            "detection_source": "NEURON Platform",
            "detection_method": anomaly_data.get('detector', 'Unknown'),
            "confidence_score": anomaly_data.get('score', 0),
            
            # Affected entities
            "affected_assets": self._extract_assets(anomaly_data),
            "affected_users": anomaly_data.get('users', []),
            
            # Response requirements
            "required_actions": self._generate_actions(anomaly_data),
            "escalation_path": self._determine_escalation(severity),
            
            # Evidence
            "evidence": {
                "event_ids": anomaly_data.get('event_ids', []),
                "trace_id": anomaly_data.get('trace_id'),
                "raw_data": anomaly_data
            },
            
            # Compliance fields
            "regulatory_impact": self._assess_regulatory_impact(anomaly_data),
            "data_classification": anomaly_data.get('data_classification', 'INTERNAL'),
            
            # Assignment
            "assigned_to": self._auto_assign(severity),
            "status": "OPEN",
            "sla_deadline": self._calculate_sla(severity)
        }
        
        return ticket
    
    def create_vulnerability_ticket(self, vuln_data: Dict) -> Dict:
        """Create vulnerability remediation ticket"""
        
        ticket = {
            "ticket_type": "VULNERABILITY_REMEDIATION",
            "ticket_id": f"VULN-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "created_date": datetime.now().isoformat(),
            
            # Vulnerability details
            "cve_id": vuln_data.get('cve_id'),
            "cvss_score": vuln_data.get('cvss_score'),
            "risk_score": vuln_data.get('risk_score'),
            
            # Standard fields
            "title": f"Remediate {vuln_data.get('cve_id')} - {vuln_data.get('title', 'Unknown Vulnerability')}",
            "description": self._generate_vuln_description(vuln_data),
            
            # Impact assessment
            "affected_systems": vuln_data.get('affected_assets', []),
            "business_impact": self._assess_business_impact(vuln_data),
            "exploit_available": vuln_data.get('exploit_available', False),
            "actively_exploited": vuln_data.get('kev_listed', False),
            
            # Remediation details
            "remediation_steps": self._generate_remediation_steps(vuln_data),
            "patch_available": vuln_data.get('patch_available', False),
            "workaround": vuln_data.get('workaround', 'None available'),
            
            # Priority and SLA
            "priority": self._calculate_vuln_priority(vuln_data),
            "sla_deadline": self._calculate_vuln_sla(vuln_data),
            
            # Assignment
            "assigned_team": "Infrastructure" if vuln_data.get('component_type') == 'os' else "Application",
            "status": "OPEN",
            
            # Tracking
            "detection_date": vuln_data.get('first_seen'),
            "last_scan_date": vuln_data.get('last_seen'),
            "compliance_requirement": self._check_compliance_requirement(vuln_data)
        }
        
        return ticket
    
    def create_threat_hunt_ticket(self, hunt_results: Dict) -> Dict:
        """Create threat hunting investigation ticket"""
        
        ticket = {
            "ticket_type": "THREAT_HUNT_INVESTIGATION",
            "ticket_id": f"HUNT-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "created_date": datetime.now().isoformat(),
            
            # Hunt details
            "hunt_hypothesis": hunt_results.get('hypothesis'),
            "hunt_type": hunt_results.get('hunt_type', 'PROACTIVE'),
            
            # Findings
            "indicators_found": len(hunt_results.get('indicators', [])),
            "anomalies_detected": hunt_results.get('anomaly_count', 0),
            "ttps_identified": hunt_results.get('ttps', []),
            
            # Standard fields
            "title": f"Threat Hunt: {hunt_results.get('hunt_name', 'Investigation Required')}",
            "description": self._generate_hunt_description(hunt_results),
            
            # Investigation requirements
            "investigation_steps": [
                "1. Review detected indicators and anomalies",
                "2. Correlate with threat intelligence",
                "3. Check for lateral movement",
                "4. Identify root cause",
                "5. Document findings"
            ],
            
            # Evidence collection
            "artifacts_collected": hunt_results.get('artifacts', []),
            "queries_executed": hunt_results.get('queries', []),
            
            # Risk assessment
            "threat_level": self._assess_threat_level(hunt_results),
            "recommended_actions": self._generate_hunt_actions(hunt_results),
            
            # Assignment
            "assigned_to": "SOC_L2",
            "escalation_criteria": "If APT indicators found",
            "status": "INVESTIGATING",
            
            # Metrics
            "time_to_detect": hunt_results.get('detection_time'),
            "coverage_percentage": hunt_results.get('coverage', 0)
        }
        
        return ticket
    
    # Helper methods
    def _calculate_severity(self, data: Dict) -> str:
        score = data.get('score', 0)
        if score > 0.9: return "CRITICAL"
        elif score > 0.7: return "HIGH"
        elif score > 0.4: return "MEDIUM"
        else: return "LOW"
    
    def _map_priority(self, severity: str) -> str:
        return {
            "CRITICAL": "P1",
            "HIGH": "P2", 
            "MEDIUM": "P3",
            "LOW": "P4"
        }.get(severity, "P4")
    
    def _generate_title(self, data: Dict) -> str:
        event_type = data.get('event_type', 'Unknown')
        detector = data.get('detector', 'Unknown')
        return f"[{detector.upper()}] Suspicious {event_type} Activity Detected"
    
    def _generate_description(self, data: Dict) -> str:
        return f"""
EXECUTIVE SUMMARY:
The NEURON platform detected anomalous behavior using {data.get('detector', 'unknown')} detection method.
Risk Score: {data.get('score', 0):.2f}
Detection Time: {data.get('timestamp', 'Unknown')}

TECHNICAL DETAILS:
Event Type: {data.get('event_type')}
Tenant: {data.get('tenant_id', 'Unknown')}
Features Triggered: {json.dumps(data.get('features', {}), indent=2)}

CONTEXT:
This detection was triggered by unusual patterns in the monitored environment.
The fusion layer combined multiple detection methods to identify this anomaly.

RECOMMENDATION:
Immediate investigation recommended to determine if this is malicious activity.
        """
    
    def _generate_vuln_description(self, data: Dict) -> str:
        return f"""
VULNERABILITY SUMMARY:
CVE ID: {data.get('cve_id')}
CVSS Score: {data.get('cvss_score', 'N/A')}
Risk Score: {data.get('risk_score', 0):.2f}

AFFECTED SYSTEMS:
{len(data.get('affected_assets', []))} systems affected

EXPLOIT STATUS:
Exploit Available: {'Yes' if data.get('exploit_available') else 'No'}
KEV Listed: {'Yes' if data.get('kev_listed') else 'No'}

BUSINESS IMPACT:
High-priority remediation required due to risk score and exploit availability.
        """
    
    def _generate_hunt_description(self, data: Dict) -> str:
        return f"""
THREAT HUNT SUMMARY:
Hunt Type: {data.get('hunt_type', 'Proactive')}
Hypothesis: {data.get('hypothesis', 'Unknown')}

FINDINGS:
Indicators Found: {len(data.get('indicators', []))}
Anomalies Detected: {data.get('anomaly_count', 0)}
TTPs Identified: {', '.join(data.get('ttps', []))}

INVESTIGATION STATUS:
Requires detailed analysis to determine threat level and response actions.
        """
    
    def _generate_actions(self, data: Dict) -> List[str]:
        severity = self._calculate_severity(data)
        
        if severity == "CRITICAL":
            return [
                "1. IMMEDIATELY isolate affected systems",
                "2. Capture memory dump and disk image",
                "3. Review last 24 hours of logs",
                "4. Check for lateral movement",
                "5. Notify security leadership"
            ]
        elif severity == "HIGH":
            return [
                "1. Monitor affected systems closely",
                "2. Collect relevant logs",
                "3. Check for persistence mechanisms",
                "4. Review user activity",
                "5. Prepare containment plan"
            ]
        else:
            return [
                "1. Review detection details",
                "2. Validate if true positive",
                "3. Document findings",
                "4. Update detection rules if needed"
            ]
    
    def _generate_remediation_steps(self, vuln_data: Dict) -> List[str]:
        steps = [
            "1. Validate vulnerability presence on affected systems",
            "2. Assess business impact and downtime requirements",
            "3. Test patches in non-production environment",
            "4. Schedule maintenance window for patching",
            "5. Apply patches to affected systems",
            "6. Verify patch installation and system functionality",
            "7. Re-scan systems to confirm vulnerability remediation"
        ]
        
        if vuln_data.get('exploit_available'):
            steps.insert(1, "1.5. URGENT: Implement temporary mitigations immediately")
            
        return steps
    
    def _calculate_sla(self, severity: str) -> str:
        sla_hours = {
            "CRITICAL": 1,
            "HIGH": 4,
            "MEDIUM": 24,
            "LOW": 72
        }
        
        deadline = datetime.now() + timedelta(hours=sla_hours.get(severity, 72))
        return deadline.isoformat()
    
    def _calculate_vuln_sla(self, vuln_data: Dict) -> str:
        # More aggressive SLAs for vulnerabilities
        cvss = vuln_data.get('cvss_score', 0)
        
        if cvss >= 9.0 or vuln_data.get('kev_listed'):
            hours = 24  # 1 day for critical
        elif cvss >= 7.0:
            hours = 72  # 3 days for high
        elif cvss >= 4.0:
            hours = 168  # 1 week for medium
        else:
            hours = 720  # 30 days for low
            
        deadline = datetime.now() + timedelta(hours=hours)
        return deadline.isoformat()
    
    def _auto_assign(self, severity: str) -> str:
        if severity in ["CRITICAL", "HIGH"]:
            return "SOC_L2"
        else:
            return "SOC_L1"
    
    def _extract_assets(self, data: Dict) -> List[str]:
        # Extract asset information from anomaly data
        assets = []
        
        if 'asset_id' in data:
            assets.append(data['asset_id'])
        
        if 'metadata' in data:
            meta = data['metadata']
            if 'source_ip' in meta:
                assets.append(meta['source_ip'])
            if 'hostname' in meta:
                assets.append(meta['hostname'])
                
        return assets
    
    def _assess_regulatory_impact(self, data: Dict) -> str:
        # Simple regulatory impact assessment
        severity = self._calculate_severity(data)
        
        if severity in ["CRITICAL", "HIGH"]:
            return "Potential breach notification required - review with legal"
        else:
            return "Standard incident handling - no special regulatory requirements"
    
    def _assess_business_impact(self, vuln_data: Dict) -> str:
        risk_score = vuln_data.get('risk_score', 0)
        
        if risk_score > 0.8:
            return "HIGH - Critical systems potentially compromised"
        elif risk_score > 0.6:
            return "MEDIUM - Important systems may be affected"
        else:
            return "LOW - Limited business impact expected"
    
    def _calculate_vuln_priority(self, vuln_data: Dict) -> str:
        # Priority based on multiple factors
        if vuln_data.get('kev_listed') or vuln_data.get('cvss_score', 0) >= 9:
            return "P1"
        elif vuln_data.get('exploit_available') or vuln_data.get('cvss_score', 0) >= 7:
            return "P2"
        elif vuln_data.get('cvss_score', 0) >= 4:
            return "P3"
        else:
            return "P4"
    
    def _check_compliance_requirement(self, vuln_data: Dict) -> str:
        # Check if vulnerability affects compliance
        if vuln_data.get('kev_listed'):
            return "CISA KEV - Federal compliance requirement"
        elif vuln_data.get('cvss_score', 0) >= 7:
            return "High severity - PCI DSS/SOX review required"
        else:
            return "Standard compliance tracking"
    
    def _determine_escalation(self, severity: str) -> str:
        if severity == "CRITICAL":
            return "Immediate escalation to CISO and security leadership"
        elif severity == "HIGH":
            return "Escalate to security manager within 2 hours"
        else:
            return "Standard escalation path via team lead"
    
    def _assess_threat_level(self, hunt_data: Dict) -> str:
        indicators = len(hunt_data.get('indicators', []))
        anomalies = hunt_data.get('anomaly_count', 0)
        
        if indicators > 10 or anomalies > 20:
            return "HIGH"
        elif indicators > 5 or anomalies > 10:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _generate_hunt_actions(self, hunt_data: Dict) -> List[str]:
        threat_level = self._assess_threat_level(hunt_data)
        
        if threat_level == "HIGH":
            return [
                "1. Escalate to threat intel team",
                "2. Check for APT indicators",
                "3. Review network logs for C2",
                "4. Prepare incident response plan"
            ]
        else:
            return [
                "1. Continue monitoring",
                "2. Refine hunt queries",
                "3. Document findings",
                "4. Schedule follow-up hunt"
            ]
    
    def save_ticket(self, ticket: Dict, filename: str = None):
        """Save ticket to file"""
        if not filename:
            filename = f"tickets/{ticket['ticket_id']}.json"
        
        # Create tickets directory if it doesn't exist
        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(ticket, f, indent=2)
        
        print(f"✅ Ticket saved: {filename}")
        return filename
    
    def submit_to_ticketing_system(self, ticket: Dict):
        """Submit ticket to ticketing system (placeholder for integration)"""
        # This would integrate with ServiceNow, Jira, etc.
        print(f"📤 Submitting ticket {ticket['ticket_id']} to ticketing system...")
        
        # For now, just save locally
        return self.save_ticket(ticket)
    
    def get_neuron_anomalies(self, detector: str = None, limit: int = 10) -> List[Dict]:
        """Fetch anomalies from NEURON platform"""
        try:
            url = f"{self.api_url}/anomalies"
            params = {"limit": limit}
            if detector:
                params["detector"] = detector
                
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Failed to fetch anomalies: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error fetching anomalies: {e}")
            return []
    
    def get_neuron_vulnerabilities(self, severity: str = None, limit: int = 10) -> List[Dict]:
        """Fetch vulnerabilities from NEURON platform"""
        try:
            url = f"{self.api_url}/vulnerabilities"
            params = {"limit": limit}
            if severity:
                params["severity"] = severity
                
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Failed to fetch vulnerabilities: {response.status_code}")
                return []
        except Exception as e:
            print(f"❌ Error fetching vulnerabilities: {e}")
            return []


# Example usage
if __name__ == "__main__":
    generator = TicketGenerator()
    
    print("🎫 NEURON Ticket Generator")
    print("=" * 50)
    
    # Example: Create incident ticket from anomaly
    print("\n📋 Creating sample incident ticket...")
    sample_anomaly = {
        "detector": "fusion",
        "score": 0.85,
        "event_type": "lateral_movement", 
        "tenant_id": "client_demo",
        "features": {
            "admin_share_access": 1.0,
            "unusual_time": 0.8
        },
        "trace_id": "abc-123",
        "timestamp": datetime.now().isoformat(),
        "metadata": {
            "source_ip": "10.0.1.100",
            "hostname": "workstation-01"
        }
    }
    
    incident_ticket = generator.create_incident_ticket(sample_anomaly)
    generator.save_ticket(incident_ticket)
    
    # Example: Create vulnerability ticket
    print("\n🔒 Creating sample vulnerability ticket...")
    sample_vuln = {
        "cve_id": "CVE-2024-1234",
        "title": "Remote Code Execution in Web Framework",
        "cvss_score": 9.8,
        "risk_score": 0.95,
        "exploit_available": True,
        "kev_listed": True,
        "affected_assets": ["web-server-01", "web-server-02"],
        "first_seen": datetime.now().isoformat()
    }
    
    vuln_ticket = generator.create_vulnerability_ticket(sample_vuln)
    generator.save_ticket(vuln_ticket)
    
    # Example: Create hunt ticket
    print("\n🔍 Creating sample threat hunt ticket...")
    sample_hunt = {
        "hunt_name": "APT29 Activity Hunt",
        "hypothesis": "Detect APT29 TTPs in environment",
        "indicators": ["powershell.exe", "rundll32.exe", "suspicious_domain.com"],
        "anomaly_count": 15,
        "ttps": ["T1059", "T1055", "T1071"],
        "hunt_type": "REACTIVE"
    }
    
    hunt_ticket = generator.create_threat_hunt_ticket(sample_hunt)
    generator.save_ticket(hunt_ticket)
    
    print(f"\n✅ All sample tickets created!")
    print(f"📁 Check the 'tickets/' directory for generated files")