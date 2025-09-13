#!/usr/bin/env python3
"""
NEURON-AI DEMO DATA POPULATION SCRIPT
===================================

Populates the platform with realistic security data for live testing:
- Vulnerability assessment data (CVEs, packages, findings)
- Threat hunting events (network, endpoint activities)  
- Forensic incidents (attack timelines, evidence chains)

Run this script to enable full functionality testing of all security features.
"""

import json
import requests
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API Configuration
API_BASE = "http://localhost:8000"
API_KEY = "neuron-ai-demo-key-2024"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

class DemoDataPopulator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        
    def populate_vulnerability_data(self):
        """Populate vulnerability assessment data"""
        logger.info("Populating vulnerability assessment data...")
        
        # Sample vulnerable packages with known CVEs
        vulnerable_packages = [
            {
                "package": "log4j-core",
                "version": "2.14.1",
                "cve": "CVE-2021-44228",
                "severity": "CRITICAL",
                "cvss_score": 10.0,
                "description": "Apache Log4j2 Remote Code Execution (Log4Shell)",
                "remediation": "Upgrade to log4j-core 2.17.0 or later"
            },
            {
                "package": "spring-core",
                "version": "5.3.9", 
                "cve": "CVE-2022-22965",
                "severity": "CRITICAL",
                "cvss_score": 9.8,
                "description": "Spring Framework RCE via Data Binding (Spring4Shell)",
                "remediation": "Upgrade to Spring Framework 5.3.18 or later"
            },
            {
                "package": "jackson-databind",
                "version": "2.9.8",
                "cve": "CVE-2019-12384",
                "severity": "HIGH", 
                "cvss_score": 7.5,
                "description": "Jackson Databind deserialization vulnerability",
                "remediation": "Upgrade to jackson-databind 2.9.9 or later"
            },
            {
                "package": "openssl",
                "version": "1.1.1k",
                "cve": "CVE-2021-3711",
                "severity": "HIGH",
                "cvss_score": 9.8,
                "description": "OpenSSL buffer overflow vulnerability",
                "remediation": "Upgrade to OpenSSL 1.1.1l or later"
            },
            {
                "package": "nginx",
                "version": "1.18.0",
                "cve": "CVE-2021-23017",
                "severity": "MEDIUM",
                "cvss_score": 6.5,
                "description": "Nginx DNS resolver off-by-one heap write",
                "remediation": "Upgrade to nginx 1.20.1 or later"
            }
        ]
        
        # Create tickets for critical vulnerabilities
        for vuln in vulnerable_packages:
            if vuln["severity"] in ["CRITICAL", "HIGH"]:
                self._create_vulnerability_ticket(vuln)
                
        # Create SLA risk entries
        self._create_sla_risks(vulnerable_packages)
        
        logger.info(f"Created {len(vulnerable_packages)} vulnerability entries")
        
    def populate_threat_hunting_data(self):
        """Populate threat hunting events"""
        logger.info("Populating threat hunting data...")
        
        # Network threat events
        network_events = self._generate_network_events(50)
        
        # Endpoint threat events  
        endpoint_events = self._generate_endpoint_events(30)
        
        # Authentication events
        auth_events = self._generate_auth_events(25)
        
        all_events = network_events + endpoint_events + auth_events
        
        # Submit events to ingestion endpoint
        for event in all_events:
            self._ingest_security_event(event)
            time.sleep(0.1)  # Rate limiting
            
        logger.info(f"Ingested {len(all_events)} security events")
        
    def populate_forensic_data(self):
        """Populate forensic incident data"""
        logger.info("Populating forensic incident data...")
        
        # Create sample incident timeline
        incident = self._create_sample_incident()
        
        # Create evidence artifacts
        evidence = self._create_evidence_artifacts(incident["incident_id"])
        
        logger.info("Created forensic incident timeline and evidence")
        
    def _create_vulnerability_ticket(self, vuln: Dict[str, Any]):
        """Create security ticket for vulnerability"""
        ticket_data = {
            "title": f"Fix {vuln['cve']} in {vuln['package']}",
            "description": f"Critical vulnerability: {vuln['description']}",
            "priority": "critical" if vuln["severity"] == "CRITICAL" else "high",
            "status": "open",
            "assigned_to": "security-team",
            "cve_id": vuln["cve"],
            "package": vuln["package"],
            "version": vuln["version"],
            "cvss_score": vuln["cvss_score"],
            "remediation": vuln["remediation"],
            "created_at": datetime.now().isoformat(),
            "sla_deadline": (datetime.now() + timedelta(days=7)).isoformat()
        }
        
        try:
            response = self.session.post(f"{API_BASE}/tickets", json=ticket_data)
            if response.status_code == 201:
                logger.info(f"Created ticket for {vuln['cve']}")
            else:
                logger.warning(f"Failed to create ticket: {response.status_code}")
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            
    def _create_sla_risks(self, vulnerabilities: List[Dict]):
        """Create SLA risk entries"""
        sla_risks = []
        
        for vuln in vulnerabilities:
            if vuln["severity"] == "CRITICAL":
                days_remaining = random.randint(1, 3)
            elif vuln["severity"] == "HIGH":
                days_remaining = random.randint(2, 7)
            else:
                days_remaining = random.randint(5, 14)
                
            risk = {
                "cve_id": vuln["cve"],
                "package": vuln["package"],
                "severity": vuln["severity"],
                "days_remaining": days_remaining,
                "risk_score": vuln["cvss_score"],
                "status": "at_risk" if days_remaining <= 3 else "upcoming"
            }
            sla_risks.append(risk)
            
        try:
            response = self.session.post(f"{API_BASE}/findings/sla/bulk", json={"risks": sla_risks})
            if response.status_code == 201:
                logger.info(f"Created {len(sla_risks)} SLA risk entries")
        except Exception as e:
            logger.error(f"Error creating SLA risks: {e}")
            
    def _generate_network_events(self, count: int) -> List[Dict]:
        """Generate network security events"""
        events = []
        
        suspicious_ips = ["192.168.1.100", "10.0.0.15", "172.16.0.99", "203.0.113.42"]
        malicious_domains = ["malware-c2.com", "phishing-site.net", "suspicious-domain.org"]
        
        for i in range(count):
            event_types = [
                self._create_lateral_movement_event(suspicious_ips),
                self._create_data_exfiltration_event(suspicious_ips),
                self._create_c2_beacon_event(malicious_domains),
                self._create_port_scan_event(suspicious_ips),
                self._create_dns_tunneling_event(malicious_domains)
            ]
            
            events.append(random.choice(event_types))
            
        return events
    
    def _generate_endpoint_events(self, count: int) -> List[Dict]:
        """Generate endpoint security events"""
        events = []
        
        hostnames = ["workstation-01", "server-web-01", "laptop-finance-03", "db-server-02"]
        
        for i in range(count):
            event_types = [
                self._create_process_injection_event(hostnames),
                self._create_registry_modification_event(hostnames),
                self._create_privilege_escalation_event(hostnames),
                self._create_persistence_mechanism_event(hostnames),
                self._create_file_modification_event(hostnames)
            ]
            
            events.append(random.choice(event_types))
            
        return events
    
    def _generate_auth_events(self, count: int) -> List[Dict]:
        """Generate authentication events"""
        events = []
        
        users = ["alice.smith", "bob.jones", "charlie.brown", "diana.wilson"]
        
        for i in range(count):
            event_types = [
                self._create_brute_force_event(users),
                self._create_impossible_travel_event(users),
                self._create_privilege_abuse_event(users),
                self._create_account_lockout_event(users)
            ]
            
            events.append(random.choice(event_types))
            
        return events
        
    def _create_lateral_movement_event(self, ips: List[str]) -> Dict:
        """Create lateral movement detection event"""
        return {
            "event_type": "lateral_movement",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 48))).isoformat(),
            "source_ip": random.choice(ips),
            "dest_ip": f"192.168.1.{random.randint(10, 254)}",
            "protocol": "SMB",
            "port": 445,
            "description": "Suspicious lateral movement detected via SMB connections",
            "severity": "high",
            "tenant": "default"
        }
    
    def _create_data_exfiltration_event(self, ips: List[str]) -> Dict:
        """Create data exfiltration event"""
        return {
            "event_type": "data_exfiltration", 
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 24))).isoformat(),
            "source_ip": random.choice(ips),
            "dest_ip": f"203.0.113.{random.randint(1, 254)}",
            "protocol": "HTTPS",
            "port": 443,
            "bytes_out": random.randint(1000000, 50000000),
            "description": "Large data transfer to external IP",
            "severity": "critical",
            "tenant": "default"
        }
    
    def _create_c2_beacon_event(self, domains: List[str]) -> Dict:
        """Create C2 beacon event"""
        return {
            "event_type": "c2_beacon",
            "timestamp": (datetime.now() - timedelta(minutes=random.randint(0, 1440))).isoformat(),
            "source_ip": f"192.168.1.{random.randint(10, 100)}",
            "dest_domain": random.choice(domains),
            "protocol": "HTTPS",
            "port": 443,
            "beacon_interval": random.randint(300, 3600),
            "description": "Regular beaconing to suspicious domain detected",
            "severity": "critical",
            "tenant": "default"
        }
    
    def _create_process_injection_event(self, hosts: List[str]) -> Dict:
        """Create process injection event"""
        return {
            "event_type": "process_injection",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 12))).isoformat(),
            "hostname": random.choice(hosts),
            "process_name": "svchost.exe",
            "parent_process": "explorer.exe",
            "injection_type": "DLL_injection",
            "description": "Suspicious process injection detected",
            "severity": "high",
            "tenant": "default"
        }
    
    def _create_port_scan_event(self, ips: List[str]) -> Dict:
        """Create port scanning event"""
        return {
            "event_type": "port_scan",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 12))).isoformat(),
            "source_ip": random.choice(ips),
            "dest_ip": f"192.168.1.{random.randint(10, 254)}",
            "ports_scanned": random.randint(50, 1000),
            "protocol": "TCP",
            "description": "Port scanning activity detected",
            "severity": "medium",
            "tenant": "default"
        }
    
    def _create_dns_tunneling_event(self, domains: List[str]) -> Dict:
        """Create DNS tunneling event"""
        return {
            "event_type": "dns_tunneling",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 8))).isoformat(),
            "source_ip": f"192.168.1.{random.randint(10, 100)}",
            "dest_domain": random.choice(domains),
            "query_length": random.randint(100, 500),
            "response_size": random.randint(512, 2048),
            "description": "Suspicious DNS tunneling pattern detected",
            "severity": "high",
            "tenant": "default"
        }
    
    def _create_registry_modification_event(self, hosts: List[str]) -> Dict:
        """Create registry modification event"""
        return {
            "event_type": "registry_modification",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 6))).isoformat(),
            "hostname": random.choice(hosts),
            "registry_key": "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            "value_name": f"malware_{random.randint(1000, 9999)}",
            "operation": "create",
            "description": "Suspicious registry modification for persistence",
            "severity": "medium",
            "tenant": "default"
        }
    
    def _create_privilege_escalation_event(self, hosts: List[str]) -> Dict:
        """Create privilege escalation event"""
        return {
            "event_type": "privilege_escalation",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 4))).isoformat(),
            "hostname": random.choice(hosts),
            "user": f"user_{random.randint(1, 100)}",
            "technique": "token_impersonation",
            "success": random.choice([True, False]),
            "description": "Privilege escalation attempt detected",
            "severity": "critical",
            "tenant": "default"
        }
    
    def _create_persistence_mechanism_event(self, hosts: List[str]) -> Dict:
        """Create persistence mechanism event"""
        return {
            "event_type": "persistence_mechanism",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 8))).isoformat(),
            "hostname": random.choice(hosts),
            "mechanism": "scheduled_task",
            "task_name": f"Update_{random.randint(1000, 9999)}",
            "description": "Suspicious persistence mechanism created",
            "severity": "high",
            "tenant": "default"
        }
    
    def _create_file_modification_event(self, hosts: List[str]) -> Dict:
        """Create file modification event"""
        return {
            "event_type": "file_modification",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 6))).isoformat(),
            "hostname": random.choice(hosts),
            "file_path": f"C:\\Windows\\System32\\drivers\\{random.choice(['malware', 'backdoor', 'rootkit'])}.sys",
            "operation": "create",
            "file_hash": f"sha256:{random.randint(10**63, 10**64-1):064x}",
            "description": "Suspicious system file modification",
            "severity": "high",
            "tenant": "default"
        }
    
    def _create_impossible_travel_event(self, users: List[str]) -> Dict:
        """Create impossible travel event"""
        return {
            "event_type": "impossible_travel",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 12))).isoformat(),
            "username": random.choice(users),
            "location1": f"City_{random.randint(1, 100)}, Country_{random.randint(1, 50)}",
            "location2": f"City_{random.randint(101, 200)}, Country_{random.randint(51, 100)}",
            "travel_speed": random.randint(1000, 5000),
            "description": "Impossible travel pattern detected for user",
            "severity": "high",
            "tenant": "default"
        }
    
    def _create_privilege_abuse_event(self, users: List[str]) -> Dict:
        """Create privilege abuse event"""
        return {
            "event_type": "privilege_abuse",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 6))).isoformat(),
            "username": random.choice(users),
            "action": "bulk_file_access",
            "resource": "sensitive_documents",
            "count": random.randint(100, 1000),
            "description": "Unusual privilege usage pattern detected",
            "severity": "medium",
            "tenant": "default"
        }
    
    def _create_account_lockout_event(self, users: List[str]) -> Dict:
        """Create account lockout event"""
        return {
            "event_type": "account_lockout",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 4))).isoformat(),
            "username": random.choice(users),
            "source_ip": f"203.0.113.{random.randint(1, 254)}",
            "failed_attempts": random.randint(5, 20),
            "description": "Account lockout due to failed authentication",
            "severity": "medium",
            "tenant": "default"
        }
    
    def _create_brute_force_event(self, users: List[str]) -> Dict:
        """Create brute force authentication event"""
        return {
            "event_type": "brute_force",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 6))).isoformat(),
            "username": random.choice(users),
            "source_ip": f"203.0.113.{random.randint(1, 254)}",
            "failed_attempts": random.randint(10, 100),
            "success": random.choice([True, False]),
            "description": "Multiple failed authentication attempts detected",
            "severity": "high",
            "tenant": "default"
        }
    
    def _ingest_security_event(self, event: Dict):
        """Submit security event to ingestion API"""
        try:
            response = self.session.post(f"{API_BASE}/events/ingest", json=event)
            if response.status_code == 201:
                logger.debug(f"Ingested {event['event_type']} event")
            else:
                logger.warning(f"Failed to ingest event: {response.status_code}")
        except Exception as e:
            logger.error(f"Error ingesting event: {e}")
    
    def _create_sample_incident(self) -> Dict:
        """Create comprehensive forensic incident"""
        incident_id = f"INC-{datetime.now().strftime('%Y%m%d')}-001"
        
        # Multi-stage attack timeline
        timeline_events = [
            {
                "timestamp": (datetime.now() - timedelta(hours=72)).isoformat(),
                "stage": "initial_access",
                "description": "Spear phishing email with malicious attachment received",
                "artifact": "phishing_email.eml",
                "severity": "medium"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=71)).isoformat(),
                "stage": "execution",
                "description": "Malicious macro executed, dropped payload to %TEMP%",
                "artifact": "malware_sample.exe",
                "severity": "high"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=70)).isoformat(),
                "stage": "persistence",
                "description": "Registry key created for persistence",
                "artifact": "registry_modification.reg",
                "severity": "high"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=68)).isoformat(),
                "stage": "privilege_escalation",
                "description": "Local privilege escalation via kernel exploit",
                "artifact": "privilege_escalation.log",
                "severity": "critical"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=48)).isoformat(),
                "stage": "lateral_movement",
                "description": "SMB connections to multiple internal hosts",
                "artifact": "network_connections.pcap",
                "severity": "high"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=24)).isoformat(),
                "stage": "collection",
                "description": "Sensitive files compressed and staged",
                "artifact": "file_access.log",
                "severity": "high"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=12)).isoformat(),
                "stage": "exfiltration",
                "description": "Large data transfer to external C2 server",
                "artifact": "network_traffic.pcap",
                "severity": "critical"
            },
            {
                "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
                "stage": "impact",
                "description": "Ransomware deployment across network",
                "artifact": "ransomware_note.txt",
                "severity": "critical"
            }
        ]
        
        incident = {
            "incident_id": incident_id,
            "title": "Advanced Persistent Threat - Ransomware Attack",
            "description": "Multi-stage APT attack culminating in ransomware deployment",
            "status": "active",
            "severity": "critical",
            "timeline": timeline_events,
            "affected_systems": ["workstation-01", "server-web-01", "db-server-02"],
            "attacker_ips": ["203.0.113.42", "198.51.100.15"],
            "iocs": [
                "malware_sample.exe (SHA256: a1b2c3d4e5f6...)",
                "phishing-site.com",
                "ransom-note.txt"
            ]
        }
        
        # Submit incident to API
        try:
            response = self.session.post(f"{API_BASE}/incidents", json=incident)
            if response.status_code == 201:
                logger.info(f"Created forensic incident {incident_id}")
        except Exception as e:
            logger.error(f"Error creating incident: {e}")
            
        return incident
    
    def _create_evidence_artifacts(self, incident_id: str):
        """Create forensic evidence artifacts"""
        artifacts = [
            {
                "incident_id": incident_id,
                "artifact_type": "email",
                "name": "phishing_email.eml",
                "hash": "sha256:1a2b3c4d5e6f7890abcdef1234567890",
                "size": 15423,
                "collected_by": "forensics-team",
                "chain_of_custody": "Collected from Exchange server logs"
            },
            {
                "incident_id": incident_id,
                "artifact_type": "malware",
                "name": "malware_sample.exe", 
                "hash": "sha256:fedcba0987654321abcdef1234567890",
                "size": 524288,
                "collected_by": "forensics-team",
                "chain_of_custody": "Isolated from infected workstation"
            },
            {
                "incident_id": incident_id,
                "artifact_type": "network_capture",
                "name": "exfiltration_traffic.pcap",
                "hash": "sha256:9876543210fedcba1234567890abcdef",
                "size": 10485760,
                "collected_by": "network-team",
                "chain_of_custody": "Captured from network TAP during incident"
            }
        ]
        
        # Submit artifacts to API
        for artifact in artifacts:
            try:
                response = self.session.post(f"{API_BASE}/evidence", json=artifact)
                if response.status_code == 201:
                    logger.debug(f"Created evidence artifact {artifact['name']}")
            except Exception as e:
                logger.error(f"Error creating artifact: {e}")
        
        return artifacts

def main():
    """Main execution function"""
    logger.info("Starting Neuron-AI demo data population...")
    
    # Check if backend is accessible
    try:
        response = requests.get(f"{API_BASE}/dashboard/latest", headers=HEADERS, timeout=5)
        if response.status_code != 200:
            logger.error("Backend API not accessible. Start the backend first!")
            return
    except Exception as e:
        logger.error(f"Cannot connect to backend: {e}")
        logger.error("Make sure backend is running on http://localhost:8000")
        return
    
    # Initialize populator
    populator = DemoDataPopulator()
    
    try:
        # Populate all demo data types
        populator.populate_vulnerability_data()
        time.sleep(2)
        
        populator.populate_threat_hunting_data()
        time.sleep(2)
        
        populator.populate_forensic_data()
        
        logger.info("\n" + "="*60)
        logger.info("DEMO DATA POPULATION COMPLETE!")
        logger.info("="*60)
        logger.info("Vulnerability Assessment: Ready with 5+ CVEs")
        logger.info("Threat Hunting: 105 security events ingested") 
        logger.info("Forensic Analysis: Sample APT incident created")
        logger.info("\nYou can now test all security features with realistic data!")
        logger.info("Access the console at: http://localhost:8080/console/index.html")
        
    except KeyboardInterrupt:
        logger.info("Population interrupted by user")
    except Exception as e:
        logger.error(f"Error during population: {e}")

if __name__ == "__main__":
    main()