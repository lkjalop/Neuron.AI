#!/usr/bin/env python3
"""
MOCK VULNERABILITY FINDINGS GENERATOR
=====================================

Creates mock vulnerability findings based on uploaded SBOM components.
This simulates the vulnerability detection process for demo purposes.
"""

import json
import requests
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API Configuration
API_BASE = "http://localhost:8000"
API_KEY = "neuron-ai-demo-key-2024"
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}

# Known vulnerabilities for common packages
VULNERABILITY_DB = {
    "log4j-core": {
        "2.14.1": [
            {
                "cve": "CVE-2021-44228",
                "severity": "CRITICAL", 
                "cvss_score": 10.0,
                "description": "Apache Log4j2 Remote Code Execution (Log4Shell)",
                "remediation": "Upgrade to log4j-core 2.17.0 or later",
                "sla_days": 1  # Critical = 1 day SLA
            }
        ]
    },
    "spring-core": {
        "5.3.9": [
            {
                "cve": "CVE-2022-22965",
                "severity": "CRITICAL",
                "cvss_score": 9.8, 
                "description": "Spring Framework RCE via Data Binding (Spring4Shell)",
                "remediation": "Upgrade to Spring Framework 5.3.18 or later",
                "sla_days": 1
            }
        ]
    },
    "jackson-databind": {
        "2.9.8": [
            {
                "cve": "CVE-2019-12384",
                "severity": "HIGH",
                "cvss_score": 7.5,
                "description": "Jackson Databind deserialization vulnerability", 
                "remediation": "Upgrade to jackson-databind 2.9.9 or later",
                "sla_days": 7  # High = 7 days SLA
            }
        ]
    },
    "openssl": {
        "1.1.1k": [
            {
                "cve": "CVE-2021-3711",
                "severity": "HIGH",
                "cvss_score": 9.8,
                "description": "OpenSSL buffer overflow vulnerability",
                "remediation": "Upgrade to OpenSSL 1.1.1l or later", 
                "sla_days": 7
            }
        ]
    },
    "nginx": {
        "1.18.0": [
            {
                "cve": "CVE-2021-23017", 
                "severity": "MEDIUM",
                "cvss_score": 6.5,
                "description": "Nginx DNS resolver off-by-one heap write",
                "remediation": "Upgrade to nginx 1.20.1 or later",
                "sla_days": 30  # Medium = 30 days SLA
            }
        ]
    }
}

def generate_mock_findings(components):
    """Generate mock vulnerability findings for components"""
    findings = []
    
    for comp in components:
        package_name = comp.get("name", "")
        version = comp.get("version", "")
        
        # Check if we have vulnerabilities for this package/version
        if package_name in VULNERABILITY_DB:
            if version in VULNERABILITY_DB[package_name]:
                vulns = VULNERABILITY_DB[package_name][version]
                
                for vuln in vulns:
                    finding = {
                        "id": f"finding-{package_name}-{version}-{vuln['cve']}",
                        "package": package_name,
                        "version": version,
                        "cve": [vuln["cve"]],
                        "risk": vuln["cvss_score"],
                        "severity": vuln["severity"],
                        "description": vuln["description"],
                        "remediation": vuln["remediation"],
                        "sla_due_days": vuln["sla_days"],
                        "status": "open",
                        "created_at": datetime.now().isoformat(),
                        "purl": comp.get("purl", ""),
                        "asset_id": "demo-asset-001"
                    }
                    findings.append(finding)
                    
    return findings

def post_mock_findings_to_memory():
    """Post mock findings to in-memory storage via API manipulation"""
    
    # This is a demonstration of what the findings would look like
    # Since there's no direct endpoint to post findings, we'll show what
    # would be generated and provide instructions for testing
    
    logger.info("Generating mock vulnerability findings...")
    
    # Get sample components that would have been uploaded
    sample_components = [
        {"name": "log4j-core", "version": "2.14.1", "purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1"},
        {"name": "spring-core", "version": "5.3.9", "purl": "pkg:maven/org.springframework/spring-core@5.3.9"},
        {"name": "jackson-databind", "version": "2.9.8", "purl": "pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.9.8"},
        {"name": "openssl", "version": "1.1.1k", "purl": "pkg:generic/openssl@1.1.1k"},
        {"name": "nginx", "version": "1.18.0", "purl": "pkg:generic/nginx@1.18.0"}
    ]
    
    findings = generate_mock_findings(sample_components)
    
    logger.info(f"Generated {len(findings)} vulnerability findings:")
    for finding in findings:
        logger.info(f"  - {finding['cve'][0]}: {finding['package']} {finding['version']} ({finding['severity']})")
    
    return findings

def create_findings_json_file(findings):
    """Create a JSON file with the findings for manual inspection"""
    
    findings_file = "mock_vulnerability_findings.json"
    
    output = {
        "generated_at": datetime.now().isoformat(),
        "total_findings": len(findings),
        "findings": findings,
        "summary": {
            "critical": len([f for f in findings if f["severity"] == "CRITICAL"]),
            "high": len([f for f in findings if f["severity"] == "HIGH"]),
            "medium": len([f for f in findings if f["severity"] == "MEDIUM"]),
            "low": len([f for f in findings if f["severity"] == "LOW"])
        }
    }
    
    with open(findings_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    logger.info(f"Mock findings saved to {findings_file}")
    return findings_file

def main():
    """Main execution"""
    logger.info("=== Mock Vulnerability Findings Generator ===")
    
    # Generate mock findings
    findings = post_mock_findings_to_memory()
    
    # Save to file for inspection
    findings_file = create_findings_json_file(findings)
    
    logger.info("\n" + "="*60)
    logger.info("MOCK VULNERABILITY FINDINGS GENERATED")
    logger.info("="*60)
    
    if findings:
        logger.info(f"📄 Total findings: {len(findings)}")
        logger.info("🔥 Critical vulnerabilities found:")
        for finding in findings:
            if finding["severity"] == "CRITICAL":
                logger.info(f"   • {finding['cve'][0]}: {finding['package']} {finding['version']}")
                logger.info(f"     Risk Score: {finding['risk']}/10")
                logger.info(f"     SLA: {finding['sla_due_days']} days")
    
    logger.info(f"\n📁 Full details saved to: {findings_file}")
    logger.info("\n💡 To see these in the web interface:")
    logger.info("   1. The vulnerability detection system needs database connectivity")
    logger.info("   2. Or the findings endpoint needs to return this mock data")
    logger.info("   3. This demonstrates what WOULD be detected with proper setup")

if __name__ == "__main__":
    main()