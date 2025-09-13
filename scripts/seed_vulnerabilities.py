#!/usr/bin/env python3
"""
VULNERABILITY DATABASE SEEDER
==============================

Seeds the vulnerability database with real CVE data for testing.
Includes Log4Shell and other critical vulnerabilities.
"""

import json
import requests
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API Configuration
API_BASE = "http://localhost:8000"
API_KEY = "neuron-ai-demo-key-2024"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

def get_critical_vulnerabilities():
    """Return critical vulnerabilities including Log4Shell"""
    return [
        {
            "cve_id": "CVE-2021-44228",
            "package": "log4j-core",
            "affected_versions": ["2.14.1", "2.14.0", "2.13.3", "2.13.2", "2.13.1", "2.13.0", "2.12.2", "2.12.1"],
            "cvss_score": 10.0,
            "severity": "CRITICAL",
            "description": "Apache Log4j2 Remote Code Execution (Log4Shell)",
            "published_date": "2021-12-09",
            "references": ["https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2021-44228"],
            "remediation": "Upgrade to log4j-core 2.17.0 or later"
        },
        {
            "cve_id": "CVE-2022-22965",
            "package": "spring-core",
            "affected_versions": ["5.3.9", "5.3.8", "5.3.7", "5.3.6", "5.3.5"],
            "cvss_score": 9.8,
            "severity": "CRITICAL",
            "description": "Spring Framework RCE via Data Binding (Spring4Shell)",
            "published_date": "2022-03-31",
            "references": ["https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2022-22965"],
            "remediation": "Upgrade to Spring Framework 5.3.18 or later"
        },
        {
            "cve_id": "CVE-2019-12384",
            "package": "jackson-databind",
            "affected_versions": ["2.9.8", "2.9.7", "2.9.6", "2.9.5"],
            "cvss_score": 7.5,
            "severity": "HIGH",
            "description": "Jackson Databind deserialization vulnerability",
            "published_date": "2019-06-19",
            "references": ["https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2019-12384"],
            "remediation": "Upgrade to jackson-databind 2.9.9 or later"
        },
        {
            "cve_id": "CVE-2021-3711",
            "package": "openssl",
            "affected_versions": ["1.1.1k", "1.1.1j", "1.1.1i", "1.1.1h"],
            "cvss_score": 9.8,
            "severity": "HIGH",
            "description": "OpenSSL buffer overflow vulnerability",
            "published_date": "2021-08-24",
            "references": ["https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2021-3711"],
            "remediation": "Upgrade to OpenSSL 1.1.1l or later"
        },
        {
            "cve_id": "CVE-2021-23017",
            "package": "nginx",
            "affected_versions": ["1.18.0", "1.17.10", "1.17.9", "1.17.8"],
            "cvss_score": 6.5,
            "severity": "MEDIUM",
            "description": "Nginx DNS resolver off-by-one heap write",
            "published_date": "2021-05-25",
            "references": ["https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2021-23017"],
            "remediation": "Upgrade to nginx 1.20.1 or later"
        }
    ]

def seed_vulnerabilities():
    """Seed vulnerabilities into the database"""
    logger.info("Starting vulnerability database seeding...")
    
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # Check if backend is accessible
    try:
        response = session.get(f"{API_BASE}/vuln/vulnerabilities", timeout=5)
        if response.status_code != 200:
            logger.error("Backend API not accessible!")
            return False
    except Exception as e:
        logger.error(f"Cannot connect to backend: {e}")
        return False
    
    vulnerabilities = get_critical_vulnerabilities()
    logger.info(f"Seeding {len(vulnerabilities)} vulnerabilities...")
    
    success_count = 0
    for vuln in vulnerabilities:
        try:
            # Try to POST to vulnerability endpoint
            # Note: This endpoint might not exist, this is a demonstration
            response = session.post(f"{API_BASE}/vuln/vulnerabilities", json=vuln)
            
            if response.status_code in [201, 200]:
                logger.info(f"Successfully added {vuln['cve_id']}")
                success_count += 1
            else:
                logger.warning(f"Failed to add {vuln['cve_id']}: HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error adding {vuln['cve_id']}: {e}")
    
    logger.info(f"Seeding complete: {success_count}/{len(vulnerabilities)} vulnerabilities added")
    return success_count > 0

def create_vuln_catalog_file():
    """Create an enhanced vulnerability catalog file"""
    vulnerabilities = get_critical_vulnerabilities()
    
    # Convert to simpler format for the catalog
    catalog = []
    for vuln in vulnerabilities:
        for version in vuln["affected_versions"]:
            catalog.append({
                "package": vuln["package"],
                "affected": f"<={version}",
                "cve": vuln["cve_id"],
                "severity": vuln["severity"],
                "cvss_base": vuln["cvss_score"],
                "description": vuln["description"],
                "remediation": vuln["remediation"]
            })
    
    catalog_path = "../artifacts/vuln_catalog_enhanced.json"
    with open(catalog_path, 'w', encoding='utf-8') as f:
        json.dump(catalog, f, indent=2)
    
    logger.info(f"Enhanced vulnerability catalog created at {catalog_path}")
    logger.info(f"Contains {len(catalog)} vulnerability entries")
    
    return catalog_path

def trigger_vulnerability_scan():
    """Try to trigger vulnerability scanning"""
    session = requests.Session()
    session.headers.update(HEADERS)
    
    logger.info("Attempting to trigger vulnerability scan...")
    
    # Try various scan endpoints that might exist
    scan_endpoints = [
        "/scanner/scan/run",
        "/vuln/scan/trigger", 
        "/scanner/run",
        "/scan/vulnerabilities"
    ]
    
    for endpoint in scan_endpoints:
        try:
            response = session.post(f"{API_BASE}{endpoint}", json={})
            if response.status_code == 200:
                logger.info(f"Successfully triggered scan via {endpoint}")
                return True
            else:
                logger.debug(f"Endpoint {endpoint} returned {response.status_code}")
        except Exception as e:
            logger.debug(f"Endpoint {endpoint} failed: {e}")
    
    logger.warning("No scan trigger endpoint found")
    return False

def main():
    """Main execution"""
    logger.info("=== Neuron-AI Vulnerability Database Seeder ===")
    
    # Create enhanced catalog file
    catalog_path = create_vuln_catalog_file()
    
    # Try to seed vulnerabilities via API
    success = seed_vulnerabilities()
    
    if not success:
        logger.warning("API seeding failed - this is expected if endpoints don't exist")
        logger.info("Enhanced vulnerability catalog file created instead")
    
    # Try to trigger scanning
    trigger_vulnerability_scan()
    
    logger.info("=== Seeding Complete ===")
    logger.info("Next steps:")
    logger.info("1. Check if vulnerabilities appear in /vuln/vulnerabilities endpoint")
    logger.info("2. Upload SBOM files again to test matching")
    logger.info("3. Check /vuln/findings for results")

if __name__ == "__main__":
    main()