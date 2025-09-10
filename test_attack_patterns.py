#!/usr/bin/env python3
"""
NEURON Platform - Attack Pattern Simulation Script
Use this to test the platform's detection capabilities
"""

import requests
import json
import time
import random
from datetime import datetime

API_URL = "http://localhost:8000"

def check_server():
    """Check if the server is running"""
    try:
        response = requests.get(f"{API_URL}/health", timeout=2)
        if response.status_code == 200:
            print("✓ Server is running")
            return True
    except:
        pass
    print("✗ Server is not running. Please start it first with START_TESTING.bat")
    return False

def simulate_attack_pattern(pattern_type):
    """Simulate various attack patterns for testing"""
    
    print(f"\n[*] Simulating {pattern_type}...")
    
    if pattern_type == "credential_stuffing":
        # Rapid authentication attempts
        print("  → Generating 50 failed login attempts...")
        for i in range(50):
            event = {
                "event_type": "auth_failure",
                "tenant_id": "test_tenant",
                "severity": 0.7,
                "features": {
                    "failed_attempts": i,
                    "source_ip_entropy": 0.9,
                    "user_agent_diversity": 0.1,
                    "time_between_attempts": 0.5,
                    "value": i * 10  # For SNN detection
                },
                "metadata": {
                    "attack_pattern": "credential_stuffing",
                    "source_ip": f"192.168.1.{i%255}",
                    "username": f"user{i%10}"
                }
            }
            try:
                requests.post(f"{API_URL}/ingest", json=event)
                if i % 10 == 0:
                    print(f"    Sent {i} events...")
            except:
                pass
            time.sleep(0.05)
        print("  ✓ Credential stuffing simulation complete")
    
    elif pattern_type == "port_scan":
        # Sequential port access pattern
        print("  → Scanning ports 1000-1050...")
        for port in range(1000, 1051):
            event = {
                "event_type": "network_scan",
                "tenant_id": "test_tenant",
                "severity": 0.5,
                "features": {
                    "port": port,
                    "scan_velocity": 100,
                    "connection_attempts": 1,
                    "value": port  # For anomaly detection
                },
                "metadata": {
                    "attack_pattern": "port_scan",
                    "source_ip": "10.0.0.100",
                    "scan_type": "SYN"
                }
            }
            try:
                requests.post(f"{API_URL}/ingest", json=event)
            except:
                pass
            time.sleep(0.01)
        print("  ✓ Port scan simulation complete")
    
    elif pattern_type == "data_exfiltration":
        # Large data transfer anomaly
        print("  → Simulating large data transfers...")
        for i in range(5):
            bytes_transferred = random.randint(1000000000, 10000000000)  # 1-10GB
            event = {
                "event_type": "data_transfer",
                "tenant_id": "test_tenant",
                "severity": 0.9,
                "features": {
                    "bytes_transferred": bytes_transferred,
                    "transfer_rate": 1000000,  # 1MB/s
                    "destination_reputation": -0.8,
                    "value": bytes_transferred / 1000000  # MB for detection
                },
                "metadata": {
                    "attack_pattern": "data_exfiltration",
                    "destination_ip": "185.220.101.45",  # Known bad IP
                    "protocol": "HTTPS",
                    "file_count": random.randint(100, 1000)
                }
            }
            try:
                response = requests.post(f"{API_URL}/ingest", json=event)
                print(f"    Transfer {i+1}: {bytes_transferred/1e9:.1f}GB")
            except:
                pass
            time.sleep(1)
        print("  ✓ Data exfiltration simulation complete")
    
    elif pattern_type == "privilege_escalation":
        print("  → Simulating privilege escalation attempts...")
        for i in range(10):
            event = {
                "event_type": "process_creation",
                "tenant_id": "test_tenant", 
                "severity": 0.8,
                "features": {
                    "parent_privilege_level": 1,
                    "child_privilege_level": 10,
                    "suspicious_command": 1,
                    "value": i * 100
                },
                "metadata": {
                    "attack_pattern": "privilege_escalation",
                    "process_name": random.choice(["cmd.exe", "powershell.exe", "wmic.exe"]),
                    "command_line": "whoami /priv",
                    "user": f"lowpriv_user_{i}"
                }
            }
            try:
                requests.post(f"{API_URL}/ingest", json=event)
            except:
                pass
            time.sleep(0.5)
        print("  ✓ Privilege escalation simulation complete")
    
    elif pattern_type == "ransomware":
        print("  → Simulating ransomware behavior...")
        # File encryption pattern
        for i in range(20):
            event = {
                "event_type": "file_modification",
                "tenant_id": "test_tenant",
                "severity": 0.95,
                "features": {
                    "files_modified_rate": 100 + i * 10,
                    "entropy_change": 0.9,
                    "extension_changed": 1,
                    "value": 1000 + i * 50
                },
                "metadata": {
                    "attack_pattern": "ransomware",
                    "file_extension": ".encrypted",
                    "process": "suspicious.exe",
                    "directory": f"C:\\Users\\victim\\Documents\\folder{i}"
                }
            }
            try:
                requests.post(f"{API_URL}/ingest", json=event)
            except:
                pass
            time.sleep(0.1)
        print("  ✓ Ransomware simulation complete")

def check_detections():
    """Check what anomalies were detected"""
    print("\n[*] Checking detection results...")
    
    try:
        # Check different detectors
        detectors = ["baseline", "snn", "iforest", "temporal", "fusion"]
        total_anomalies = 0
        
        for detector in detectors:
            response = requests.get(f"{API_URL}/anomalies?detector={detector}&limit=100")
            if response.status_code == 200:
                anomalies = response.json()
                count = len(anomalies) if isinstance(anomalies, list) else anomalies.get('count', 0)
                if count > 0:
                    print(f"  → {detector}: {count} anomalies detected")
                    total_anomalies += count
        
        if total_anomalies > 0:
            print(f"\n✓ Total anomalies detected: {total_anomalies}")
        else:
            print("\n⚠ No anomalies detected yet. The detectors might need more data or different thresholds.")
            
    except Exception as e:
        print(f"  ✗ Error checking detections: {e}")

def check_metrics():
    """Display key metrics"""
    print("\n[*] Platform Metrics:")
    try:
        response = requests.get(f"{API_URL}/metrics")
        if response.status_code == 200:
            metrics_text = response.text
            # Parse key metrics
            for line in metrics_text.split('\n'):
                if 'neuron_events_total' in line and not line.startswith('#'):
                    print(f"  → Events processed: {line.split()[-1]}")
                elif 'neuron_anomalies_total' in line and not line.startswith('#'):
                    print(f"  → Anomalies detected: {line.split()[-1]}")
        
        # Also check vulnerability summary
        response = requests.get(f"{API_URL}/vuln/summary")
        if response.status_code == 200:
            summary = response.json()
            print(f"  → Vulnerabilities tracked: {summary.get('total_vulnerabilities', 0)}")
            
    except Exception as e:
        print(f"  ✗ Error fetching metrics: {e}")

def main():
    """Main execution"""
    print("=" * 60)
    print("  NEURON PLATFORM - ATTACK SIMULATION TESTING")
    print("=" * 60)
    
    if not check_server():
        return
    
    print("\nStarting attack simulations...")
    print("-" * 40)
    
    # Run different attack patterns
    attack_patterns = [
        "credential_stuffing",
        "port_scan", 
        "data_exfiltration",
        "privilege_escalation",
        "ransomware"
    ]
    
    for pattern in attack_patterns:
        simulate_attack_pattern(pattern)
        time.sleep(2)  # Brief pause between patterns
    
    print("\n" + "=" * 60)
    print("All attack patterns simulated!")
    print("=" * 60)
    
    # Wait a bit for processing
    print("\nWaiting for detection processing...")
    time.sleep(5)
    
    # Check results
    check_detections()
    check_metrics()
    
    print("\n" + "=" * 60)
    print("Testing complete! Check the dashboard at:")
    print("  http://localhost:8000/dashboard/latest")
    print("=" * 60)

if __name__ == "__main__":
    main()