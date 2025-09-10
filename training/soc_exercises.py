"""
SOC Analyst Training Exercises using Neuron-AI
Learn real-world threat hunting skills with your own platform
"""

import json
import random
import time
from datetime import datetime, timedelta
from typing import List, Dict

class SOCTrainingLab:
    """Interactive SOC training scenarios"""
    
    def __init__(self):
        self.scenarios = {
            "ransomware": self.generate_ransomware_attack,
            "lateral_movement": self.generate_lateral_movement,
            "data_exfiltration": self.generate_data_exfil,
            "vulnerability_scan": self.generate_vuln_scan,
            "apt_simulation": self.generate_apt_activity
        }
        self.skill_levels = {
            "beginner": 1,
            "intermediate": 2,
            "advanced": 3
        }
    
    def generate_ransomware_attack(self) -> List[Dict]:
        """Simulate ransomware kill chain"""
        events = []
        base_time = datetime.now()
        
        # Stage 1: Initial Access (Phishing)
        events.append({
            "event_id": f"phish_{random.randint(1000,9999)}",
            "timestamp": base_time.isoformat(),
            "event_type": "email",
            "severity": 3,
            "message": "User clicked suspicious link in email from unknown sender",
            "features": {
                "url_reputation": -0.8,
                "sender_trust": 0.1,
                "attachment_present": 1.0
            },
            "mitre_technique": "T1566.001",
            "stage": "initial_access"
        })
        
        # Stage 2: Execution (Malware drops)
        base_time += timedelta(minutes=5)
        events.append({
            "event_id": f"exec_{random.randint(1000,9999)}",
            "timestamp": base_time.isoformat(),
            "event_type": "process_creation",
            "severity": 7,
            "message": "Powershell spawned with encoded command",
            "features": {
                "process_anomaly": 0.9,
                "command_length": 2048,
                "base64_present": 1.0
            },
            "mitre_technique": "T1059.001",
            "stage": "execution"
        })
        
        # Stage 3: Persistence
        base_time += timedelta(minutes=10)
        events.append({
            "event_id": f"persist_{random.randint(1000,9999)}",
            "timestamp": base_time.isoformat(),
            "event_type": "registry_modification",
            "severity": 8,
            "message": "Registry Run key modified for persistence",
            "features": {
                "registry_risk": 0.95,
                "autostart": 1.0,
                "hidden_file": 1.0
            },
            "mitre_technique": "T1547.001",
            "stage": "persistence"
        })
        
        # Stage 4: Defense Evasion
        base_time += timedelta(minutes=2)
        events.append({
            "event_id": f"evade_{random.randint(1000,9999)}",
            "timestamp": base_time.isoformat(),
            "event_type": "service_modification",
            "severity": 9,
            "message": "Windows Defender disabled via registry",
            "features": {
                "av_disabled": 1.0,
                "security_product_tamper": 1.0
            },
            "mitre_technique": "T1562.001",
            "stage": "defense_evasion"
        })
        
        # Stage 5: Impact (Encryption)
        base_time += timedelta(minutes=15)
        events.append({
            "event_id": f"encrypt_{random.randint(1000,9999)}",
            "timestamp": base_time.isoformat(),
            "event_type": "file_modification",
            "severity": 10,
            "message": "Mass file encryption detected - *.encrypted extension",
            "features": {
                "file_entropy": 0.99,
                "mass_modification": 1.0,
                "encryption_markers": 1.0
            },
            "mitre_technique": "T1486",
            "stage": "impact"
        })
        
        return events
    
    def generate_lateral_movement(self) -> List[Dict]:
        """Simulate lateral movement patterns"""
        events = []
        base_time = datetime.now()
        
        source_ips = ["192.168.1.100", "192.168.1.101", "192.168.1.105"]
        target_ips = ["192.168.1.200", "192.168.1.201", "192.168.1.202", "192.168.1.203"]
        
        for i, source in enumerate(source_ips):
            for j, target in enumerate(target_ips[:2]):  # Each source hits 2 targets
                base_time += timedelta(minutes=random.randint(5, 15))
                
                # RDP/SMB connection attempts
                protocol = random.choice(["RDP", "SMB", "WMI"])
                events.append({
                    "event_id": f"lateral_{i}_{j}",
                    "timestamp": base_time.isoformat(),
                    "event_type": "network_connection",
                    "severity": 6,
                    "message": f"{protocol} connection from {source} to {target}",
                    "features": {
                        "internal_connection": 1.0,
                        "privileged_account": 0.8,
                        "unusual_hour": 0.7 if base_time.hour < 6 or base_time.hour > 22 else 0.2
                    },
                    "source_ip": source,
                    "dest_ip": target,
                    "protocol": protocol,
                    "mitre_technique": "T1021.001" if protocol == "RDP" else "T1021.002"
                })
        
        return events
    
    def generate_data_exfil(self) -> List[Dict]:
        """Simulate data exfiltration"""
        events = []
        base_time = datetime.now()
        
        # Stage 1: Data collection
        events.append({
            "event_id": f"collect_{random.randint(1000,9999)}",
            "timestamp": base_time.isoformat(),
            "event_type": "file_access",
            "severity": 5,
            "message": "Bulk access to sensitive documents folder",
            "features": {
                "files_accessed": 237,
                "sensitive_path": 1.0,
                "rapid_access": 0.9
            },
            "mitre_technique": "T1005"
        })
        
        # Stage 2: Compression
        base_time += timedelta(minutes=10)
        events.append({
            "event_id": f"compress_{random.randint(1000,9999)}",
            "timestamp": base_time.isoformat(),
            "event_type": "process_creation",
            "severity": 6,
            "message": "7zip process creating large archive",
            "features": {
                "archive_size_mb": 4500,
                "compression_ratio": 0.85,
                "password_protected": 1.0
            },
            "mitre_technique": "T1560.001"
        })
        
        # Stage 3: Exfiltration
        base_time += timedelta(minutes=20)
        events.append({
            "event_id": f"exfil_{random.randint(1000,9999)}",
            "timestamp": base_time.isoformat(),
            "event_type": "network_traffic",
            "severity": 9,
            "message": "Large data transfer to external cloud storage",
            "features": {
                "bytes_out": 4718592000,  # ~4.5GB
                "destination_reputation": -0.6,
                "tls_encrypted": 1.0,
                "unusual_port": 0.7
            },
            "destination": "mega.nz",
            "mitre_technique": "T1567.002"
        })
        
        return events
    
    def generate_vuln_scan(self) -> List[Dict]:
        """Generate vulnerability scan results"""
        vulns = []
        
        services = [
            ("apache", "2.4.41", "CVE-2021-44228", 9.8, "Log4Shell RCE"),
            ("openssh", "7.4", "CVE-2021-28041", 7.1, "SSH Privilege Escalation"),
            ("mysql", "5.7.20", "CVE-2021-22926", 7.5, "SQL Injection"),
            ("docker", "19.03.8", "CVE-2021-21284", 6.8, "Container Escape"),
            ("nginx", "1.16.0", "CVE-2021-23017", 7.7, "DNS Resolver Vulnerability")
        ]
        
        for service, version, cve, cvss, description in services:
            vulns.append({
                "finding_id": f"vuln_{random.randint(10000,99999)}",
                "asset": f"server-{random.randint(1,50)}",
                "service": service,
                "version": version,
                "cve": cve,
                "cvss_score": cvss,
                "severity": "CRITICAL" if cvss >= 9 else "HIGH" if cvss >= 7 else "MEDIUM",
                "description": description,
                "exploitable": random.choice([True, False]),
                "public_exploit": cve == "CVE-2021-44228",  # Log4Shell has public exploits
                "patch_available": True,
                "discovered": datetime.now().isoformat()
            })
        
        return vulns
    
    def generate_apt_activity(self) -> List[Dict]:
        """Advanced Persistent Threat simulation"""
        events = []
        base_time = datetime.now() - timedelta(days=30)  # APT starts 30 days ago
        
        # Long-term campaign phases
        phases = [
            ("recon", 10, "External reconnaissance via DNS queries"),
            ("initial_access", 5, "Spearphishing with macro-enabled document"),
            ("establish_foothold", 3, "Install custom backdoor"),
            ("escalate_privs", 7, "Kerberoasting attack for domain credentials"),
            ("internal_recon", 14, "Active Directory enumeration"),
            ("lateral_movement", 12, "Move to domain controller"),
            ("collection", 8, "Stage sensitive data for exfiltration"),
            ("exfiltration", 15, "Slow, encrypted data exfiltration"),
            ("maintain_presence", 999, "Maintain backdoor access")
        ]
        
        for phase, duration, description in phases:
            for day in range(min(duration, 30)):
                if random.random() < 0.3:  # APT is stealthy, not every day
                    base_time += timedelta(days=1, hours=random.randint(0,23))
                    events.append({
                        "event_id": f"apt_{phase}_{day}",
                        "timestamp": base_time.isoformat(),
                        "event_type": "apt_activity",
                        "severity": random.randint(3, 8),
                        "message": description,
                        "phase": phase,
                        "apt_group": "APT28",  # Fancy Bear simulation
                        "features": {
                            "stealth_score": random.uniform(0.7, 0.95),
                            "persistence": 1.0,
                            "advanced_technique": random.uniform(0.6, 1.0)
                        }
                    })
        
        return events
    
    def create_training_scenario(self, scenario_type: str, skill_level: str = "beginner"):
        """Create a complete training scenario with questions"""
        
        if scenario_type not in self.scenarios:
            return {"error": f"Unknown scenario: {scenario_type}"}
        
        # Generate events
        events = self.scenarios[scenario_type]()
        
        # Create investigation questions based on skill level
        questions = self.generate_questions(scenario_type, skill_level)
        
        # Create hunting queries
        hunt_queries = self.generate_hunt_queries(scenario_type)
        
        return {
            "scenario": scenario_type,
            "skill_level": skill_level,
            "events": events,
            "questions": questions,
            "hunt_queries": hunt_queries,
            "solution": self.generate_solution(scenario_type)
        }
    
    def generate_questions(self, scenario_type: str, skill_level: str) -> List[Dict]:
        """Generate investigation questions"""
        
        questions = {
            "ransomware": {
                "beginner": [
                    "What was the initial infection vector?",
                    "Which process showed suspicious behavior?",
                    "What persistence mechanism was used?"
                ],
                "intermediate": [
                    "Map the complete kill chain using MITRE ATT&CK",
                    "Identify all IOCs for threat intelligence sharing",
                    "What defensive measures failed?"
                ],
                "advanced": [
                    "Design detection rules to catch this earlier",
                    "Calculate the dwell time and blast radius",
                    "Create a remediation playbook"
                ]
            },
            "lateral_movement": {
                "beginner": [
                    "Which systems were compromised?",
                    "What protocols were used for movement?",
                    "Identify the source of the attack"
                ],
                "intermediate": [
                    "Map the attack path through the network",
                    "Which accounts were compromised?",
                    "Identify privileged escalation points"
                ],
                "advanced": [
                    "Design network segmentation to prevent this",
                    "Create behavioral detection rules",
                    "Perform impact analysis"
                ]
            }
        }
        
        return questions.get(scenario_type, {}).get(skill_level, [])
    
    def generate_hunt_queries(self, scenario_type: str) -> List[Dict]:
        """Generate threat hunting queries"""
        
        queries = {
            "ransomware": [
                {
                    "description": "Hunt for encoded PowerShell commands",
                    "query": "event_type:process_creation AND message:*encoded* AND message:*powershell*",
                    "expected_results": "Should find Stage 2 execution events"
                },
                {
                    "description": "Find registry persistence",
                    "query": "event_type:registry_modification AND features.autostart:1",
                    "expected_results": "Should identify persistence mechanisms"
                }
            ],
            "lateral_movement": [
                {
                    "description": "Hunt for internal RDP connections",
                    "query": "protocol:RDP AND features.internal_connection:1",
                    "expected_results": "Should map lateral movement paths"
                },
                {
                    "description": "Find unusual hour connections",
                    "query": "features.unusual_hour:>0.5 AND event_type:network_connection",
                    "expected_results": "Should identify after-hours activity"
                }
            ]
        }
        
        return queries.get(scenario_type, [])
    
    def generate_solution(self, scenario_type: str) -> Dict:
        """Generate solution guide"""
        
        solutions = {
            "ransomware": {
                "timeline": "Initial access -> 5 min -> Execution -> 10 min -> Persistence -> 2 min -> Evasion -> 15 min -> Impact",
                "key_findings": [
                    "Phishing email was initial vector",
                    "PowerShell used for execution",
                    "Registry Run key for persistence",
                    "Defender disabled before encryption"
                ],
                "remediation": [
                    "Isolate affected systems",
                    "Restore from backups",
                    "Reset compromised credentials",
                    "Patch email gateway"
                ]
            },
            "lateral_movement": {
                "timeline": "Compromise source systems -> Move laterally via RDP/SMB -> Establish foothold on targets",
                "key_findings": [
                    "3 source systems compromised",
                    "Multiple protocols used (RDP, SMB, WMI)",
                    "Targeted high-value servers"
                ],
                "remediation": [
                    "Segment network with firewalls",
                    "Implement MFA on privileged accounts",
                    "Enable RDP logging",
                    "Deploy EDR on all endpoints"
                ]
            }
        }
        
        return solutions.get(scenario_type, {})

# Save scenarios to files for import into Neuron-AI
def export_training_data():
    """Export training scenarios as JSONL for Neuron-AI ingestion"""
    
    lab = SOCTrainingLab()
    
    # Generate all scenarios
    all_scenarios = {
        "ransomware": lab.generate_ransomware_attack(),
        "lateral_movement": lab.generate_lateral_movement(),
        "data_exfil": lab.generate_data_exfil(),
        "apt": lab.generate_apt_activity()
    }
    
    # Export as JSONL
    for scenario_name, events in all_scenarios.items():
        filename = f"training_data_{scenario_name}.jsonl"
        with open(filename, 'w') as f:
            for event in events:
                # Add required fields for Neuron-AI
                event['event_id'] = event.get('event_id', f"train_{random.randint(10000,99999)}")
                event['tenant_id'] = 'training_lab'
                f.write(json.dumps(event) + '\n')
        print(f"Exported {len(events)} events to {filename}")

if __name__ == "__main__":
    # Example: Create a ransomware training scenario
    lab = SOCTrainingLab()
    scenario = lab.create_training_scenario("ransomware", "beginner")
    
    print("=== RANSOMWARE ATTACK SIMULATION ===")
    print(f"Skill Level: {scenario['skill_level']}")
    print(f"Events Generated: {len(scenario['events'])}")
    print("\nInvestigation Questions:")
    for i, q in enumerate(scenario['questions'], 1):
        print(f"{i}. {q}")
    
    print("\nThreat Hunting Queries:")
    for query in scenario['hunt_queries']:
        print(f"- {query['description']}")
        print(f"  Query: {query['query']}")
    
    # Export for Neuron-AI
    export_training_data()