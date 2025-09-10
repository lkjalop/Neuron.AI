#!/usr/bin/env python3
"""
NEURON Platform - Threat Hunting Templates
Pre-built hunt queries for common threat scenarios
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any

class ThreatHuntTemplates:
    """Pre-built threat hunting templates for NEURON platform"""
    
    def __init__(self, api_url="http://localhost:8000"):
        self.api_url = api_url
    
    def hunt_lateral_movement(self) -> Dict:
        """Hunt for lateral movement indicators"""
        return {
            "hunt_name": "Lateral Movement Detection",
            "hypothesis": "Detect adversary lateral movement using admin shares and remote tools",
            "mitre_techniques": ["T1021.001", "T1021.002", "T1570"],
            "query": {
                "event_types": ["network_connection", "auth_success", "process_creation"],
                "features": {
                    "internal_to_internal": True,
                    "admin_tools": ["psexec", "wmiexec", "smbexec", "winrm"],
                    "unusual_service_access": True,
                    "privilege_escalation": True
                },
                "time_window": "24h",
                "correlation_rules": [
                    "Multiple internal connections from same source",
                    "Admin tool execution + network activity",
                    "Successful authentication to multiple systems"
                ]
            },
            "expected_indicators": [
                "SMB/445 connections to multiple internal IPs",
                "WMI process creation on remote systems", 
                "PowerShell remoting activity",
                "Service installation on remote hosts"
            ],
            "false_positive_filters": [
                "Exclude known admin workstations",
                "Filter legitimate remote management",
                "Exclude scheduled maintenance windows"
            ]
        }
    
    def hunt_credential_access(self) -> Dict:
        """Hunt for credential harvesting activities"""
        return {
            "hunt_name": "Credential Access Hunt",
            "hypothesis": "Detect credential dumping and harvesting techniques",
            "mitre_techniques": ["T1003", "T1558", "T1606"],
            "query": {
                "event_types": ["process_creation", "file_access", "registry_access"],
                "features": {
                    "lsass_access": True,
                    "sam_database_access": True,
                    "kerberos_ticket_requests": True,
                    "credential_file_access": True
                },
                "suspicious_processes": [
                    "mimikatz", "procdump", "comsvcs.dll", "ntdsutil"
                ],
                "registry_keys": [
                    "HKLM\\SAM\\SAM\\Domains\\Account\\Users",
                    "HKLM\\SECURITY\\Cache"
                ]
            },
            "expected_indicators": [
                "LSASS memory access by non-system processes",
                "Registry credential store access",
                "Kerberos ticket extraction",
                "Credential file creation in temp directories"
            ]
        }
    
    def hunt_persistence(self) -> Dict:
        """Hunt for persistence mechanisms"""
        return {
            "hunt_name": "Persistence Mechanism Hunt", 
            "hypothesis": "Detect adversary persistence across system reboots",
            "mitre_techniques": ["T1547", "T1053", "T1543"],
            "query": {
                "event_types": ["service_creation", "registry_modification", "scheduled_task", "file_creation"],
                "features": {
                    "startup_folder_access": True,
                    "run_key_modification": True,
                    "service_installation": True,
                    "scheduled_task_creation": True
                },
                "persistence_locations": [
                    "HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
                    "HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", 
                    "C:\\Windows\\System32\\Tasks",
                    "C:\\Users\\*\\AppData\\Roaming\\Microsoft\\Windows\\Start Menu\\Programs\\Startup"
                ]
            },
            "expected_indicators": [
                "New services with suspicious names/paths",
                "Registry run key modifications",
                "Scheduled tasks with unusual triggers",
                "Files dropped in startup locations"
            ]
        }
    
    def hunt_command_control(self) -> Dict:
        """Hunt for command and control communication"""
        return {
            "hunt_name": "Command & Control Hunt",
            "hypothesis": "Detect C2 communication channels and beaconing",
            "mitre_techniques": ["T1071", "T1573", "T1008"],
            "query": {
                "event_types": ["network_connection", "dns_query", "http_request"],
                "features": {
                    "external_connections": True,
                    "regular_intervals": True,
                    "suspicious_user_agents": True,
                    "encoded_payloads": True,
                    "domain_generation": True
                },
                "behavioral_patterns": [
                    "Regular beaconing intervals",
                    "Low-volume data transfers",
                    "Unusual destination ports",
                    "Domain fronting techniques"
                ]
            },
            "expected_indicators": [
                "Connections to newly registered domains",
                "Regular HTTP/HTTPS beacons",
                "DNS tunneling patterns",
                "Suspicious TLS certificates"
            ]
        }
    
    def hunt_data_exfiltration(self) -> Dict:
        """Hunt for data exfiltration activities"""
        return {
            "hunt_name": "Data Exfiltration Hunt",
            "hypothesis": "Detect large-scale data theft and unauthorized transfers",
            "mitre_techniques": ["T1041", "T1048", "T1567"],
            "query": {
                "event_types": ["file_access", "network_transfer", "cloud_upload"],
                "features": {
                    "large_file_transfers": True,
                    "sensitive_file_access": True,
                    "compression_activity": True,
                    "cloud_storage_uploads": True,
                    "unusual_transfer_volumes": True
                },
                "file_patterns": [
                    "*.zip", "*.rar", "*.7z",
                    "*.doc*", "*.xls*", "*.pdf",
                    "*.sql", "*.db", "*.mdb"
                ]
            },
            "expected_indicators": [
                "Large archive files created",
                "High-volume external transfers", 
                "Access to file shares with sensitive data",
                "Uploads to public cloud services"
            ]
        }
    
    def hunt_privilege_escalation(self) -> Dict:
        """Hunt for privilege escalation attempts"""
        return {
            "hunt_name": "Privilege Escalation Hunt",
            "hypothesis": "Detect attempts to gain higher privileges",
            "mitre_techniques": ["T1068", "T1134", "T1548"],
            "query": {
                "event_types": ["process_creation", "token_manipulation", "service_creation"],
                "features": {
                    "uac_bypass": True,
                    "token_impersonation": True,
                    "exploit_usage": True,
                    "service_privilege_change": True
                },
                "suspicious_binaries": [
                    "rundll32.exe", "regsvr32.exe", "mshta.exe",
                    "cmstp.exe", "fodhelper.exe"
                ]
            },
            "expected_indicators": [
                "UAC bypass techniques",
                "Process token manipulation",
                "Exploitation of vulnerable services",
                "DLL hijacking attempts"
            ]
        }
    
    def hunt_defense_evasion(self) -> Dict:
        """Hunt for defense evasion techniques"""
        return {
            "hunt_name": "Defense Evasion Hunt",
            "hypothesis": "Detect attempts to evade security controls",
            "mitre_techniques": ["T1055", "T1027", "T1562"],
            "query": {
                "event_types": ["process_injection", "file_modification", "service_stop"],
                "features": {
                    "process_hollowing": True,
                    "code_injection": True,
                    "file_deletion": True,
                    "log_clearing": True,
                    "av_evasion": True
                },
                "evasion_techniques": [
                    "Process injection into legitimate processes",
                    "Obfuscated scripts and payloads",
                    "Security service manipulation",
                    "Log file tampering"
                ]
            },
            "expected_indicators": [
                "Suspicious process memory modifications",
                "Obfuscated PowerShell commands",
                "Security log clearing events",
                "Antivirus service disruption"
            ]
        }
    
    def execute_hunt(self, hunt_template: Dict, save_results: bool = True) -> Dict:
        """Execute a hunt template against NEURON platform"""
        
        print(f"🔍 Executing hunt: {hunt_template['hunt_name']}")
        print(f"📋 Hypothesis: {hunt_template['hypothesis']}")
        
        results = {
            "hunt_name": hunt_template['hunt_name'],
            "execution_time": datetime.now().isoformat(),
            "indicators_found": [],
            "anomalies_detected": 0,
            "suspicious_events": [],
            "recommendations": []
        }
        
        try:
            # Query NEURON for relevant anomalies
            for event_type in hunt_template['query'].get('event_types', []):
                response = requests.get(
                    f"{self.api_url}/anomalies",
                    params={
                        "event_type": event_type,
                        "limit": 50
                    }
                )
                
                if response.status_code == 200:
                    anomalies = response.json()
                    if isinstance(anomalies, list):
                        results['anomalies_detected'] += len(anomalies)
                        results['suspicious_events'].extend(anomalies)
            
            # Analyze results and generate recommendations
            results['recommendations'] = self._generate_hunt_recommendations(
                hunt_template, results
            )
            
            if save_results:
                self._save_hunt_results(results)
                
        except Exception as e:
            print(f"❌ Error executing hunt: {e}")
            results['error'] = str(e)
        
        return results
    
    def _generate_hunt_recommendations(self, template: Dict, results: Dict) -> List[str]:
        """Generate recommendations based on hunt results"""
        recommendations = []
        
        anomaly_count = results['anomalies_detected']
        
        if anomaly_count == 0:
            recommendations.extend([
                "No immediate threats detected for this hunt scenario",
                "Consider expanding time window or adjusting detection thresholds",
                "Schedule follow-up hunt in 7 days"
            ])
        elif anomaly_count < 5:
            recommendations.extend([
                "Low-volume suspicious activity detected",
                "Investigate individual anomalies for false positives",
                "Monitor affected systems for 24-48 hours"
            ])
        elif anomaly_count < 20:
            recommendations.extend([
                "Moderate suspicious activity detected",
                "Escalate to SOC Level 2 for investigation",
                "Implement additional monitoring on affected systems",
                "Consider threat intelligence correlation"
            ])
        else:
            recommendations.extend([
                "HIGH VOLUME suspicious activity detected",
                "IMMEDIATE escalation to incident response team",
                "Consider containment actions for affected systems",
                "Activate threat hunting team for expanded investigation"
            ])
        
        # Add technique-specific recommendations
        techniques = template.get('mitre_techniques', [])
        if 'T1021' in str(techniques):  # Lateral movement
            recommendations.append("Review network segmentation effectiveness")
        if 'T1003' in str(techniques):  # Credential access
            recommendations.append("Force password resets for potentially compromised accounts")
        if 'T1071' in str(techniques):  # C2
            recommendations.append("Review firewall logs for blocked connection attempts")
            
        return recommendations
    
    def _save_hunt_results(self, results: Dict):
        """Save hunt results to file"""
        import os
        
        os.makedirs("hunt_results", exist_ok=True)
        
        filename = f"hunt_results/{results['hunt_name'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"💾 Hunt results saved: {filename}")
    
    def get_all_hunt_templates(self) -> List[Dict]:
        """Get all available hunt templates"""
        return [
            self.hunt_lateral_movement(),
            self.hunt_credential_access(),
            self.hunt_persistence(),
            self.hunt_command_control(),
            self.hunt_data_exfiltration(),
            self.hunt_privilege_escalation(),
            self.hunt_defense_evasion()
        ]
    
    def run_daily_hunt_suite(self):
        """Run all hunt templates as a daily hunting routine"""
        
        print("🚀 Starting Daily Threat Hunt Suite")
        print("=" * 50)
        
        templates = self.get_all_hunt_templates()
        all_results = []
        
        for template in templates:
            print(f"\n▶️  Running: {template['hunt_name']}")
            results = self.execute_hunt(template)
            all_results.append(results)
            print(f"✅ Completed: {results['anomalies_detected']} anomalies found")
        
        # Generate summary report
        self._generate_daily_summary(all_results)
        
        return all_results
    
    def _generate_daily_summary(self, results: List[Dict]):
        """Generate daily hunt summary report"""
        
        summary = {
            "report_date": datetime.now().isoformat(),
            "hunts_executed": len(results),
            "total_anomalies": sum(r.get('anomalies_detected', 0) for r in results),
            "high_priority_hunts": [],
            "recommendations": []
        }
        
        # Identify high-priority hunts
        for result in results:
            if result.get('anomalies_detected', 0) > 10:
                summary['high_priority_hunts'].append({
                    "hunt_name": result['hunt_name'],
                    "anomaly_count": result['anomalies_detected']
                })
        
        # Generate overall recommendations
        if summary['total_anomalies'] > 50:
            summary['recommendations'].extend([
                "HIGH ACTIVITY DAY - Consider elevated threat posture",
                "Review all high-priority hunt results immediately",
                "Consider activating incident response procedures"
            ])
        elif summary['total_anomalies'] > 20:
            summary['recommendations'].extend([
                "MODERATE ACTIVITY - Continue enhanced monitoring",
                "Focus on high-priority hunt follow-ups"
            ])
        else:
            summary['recommendations'].extend([
                "NORMAL ACTIVITY LEVELS - Continue routine operations",
                "Review false positive rates in low-activity hunts"
            ])
        
        # Save summary
        with open(f"hunt_results/daily_summary_{datetime.now().strftime('%Y%m%d')}.json", 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n📊 Daily Summary Generated:")
        print(f"   Total Hunts: {summary['hunts_executed']}")
        print(f"   Total Anomalies: {summary['total_anomalies']}")
        print(f"   High Priority: {len(summary['high_priority_hunts'])}")


# Example usage
if __name__ == "__main__":
    hunter = ThreatHuntTemplates()
    
    print("🎯 NEURON Threat Hunting Templates")
    print("=" * 50)
    
    # List available templates
    templates = hunter.get_all_hunt_templates()
    print(f"\n📋 Available Hunt Templates ({len(templates)}):")
    for i, template in enumerate(templates, 1):
        print(f"   {i}. {template['hunt_name']}")
        print(f"      TTPs: {', '.join(template.get('mitre_techniques', []))}")
    
    # Example: Execute lateral movement hunt
    print(f"\n🔍 Executing Lateral Movement Hunt...")
    lateral_hunt = hunter.hunt_lateral_movement()
    results = hunter.execute_hunt(lateral_hunt)
    
    print(f"\n📊 Hunt Results:")
    print(f"   Anomalies Detected: {results['anomalies_detected']}")
    print(f"   Recommendations: {len(results['recommendations'])}")
    
    for rec in results['recommendations']:
        print(f"   • {rec}")
    
    print(f"\n💡 Pro Tip: Run 'python hunt_templates.py' daily to maintain threat awareness!")
    print(f"Use hunter.run_daily_hunt_suite() to execute all hunts automatically.")