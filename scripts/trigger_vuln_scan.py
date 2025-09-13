#!/usr/bin/env python3
"""
TRIGGER VULNERABILITY SCANNING
===============================

Manually triggers vulnerability matching between SBOM components and CVE data.
"""

import sys
import os
import asyncio
import logging

# Add src to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def run_vulnerability_scan():
    """Run vulnerability scanning and matching"""
    try:
        logger.info("Starting vulnerability scanning...")
        
        # Import the matcher module
        from scanner.matcher import run_component_match
        
        # Run the component matching
        result = await run_component_match(max_vulns=1000)
        
        logger.info(f"Vulnerability scan completed!")
        logger.info(f"Results: {result}")
        
        return result
        
    except ImportError as e:
        logger.error(f"Failed to import scanner modules: {e}")
        logger.error("Make sure you're running from the correct directory")
        return None
    except Exception as e:
        logger.error(f"Error during vulnerability scan: {e}")
        return None

async def check_database_status():
    """Check if components and vulnerabilities are in database"""
    try:
        from storage import postgres
        
        # Check components
        components = await postgres.fetch("SELECT COUNT(*) as count FROM sbom_components")
        comp_count = components[0]['count'] if components else 0
        logger.info(f"SBOM components in database: {comp_count}")
        
        # Check vulnerabilities  
        vulns = await postgres.fetch("SELECT COUNT(*) as count FROM vulnerabilities")
        vuln_count = vulns[0]['count'] if vulns else 0
        logger.info(f"Vulnerabilities in database: {vuln_count}")
        
        # Check findings
        findings = await postgres.fetch("SELECT COUNT(*) as count FROM findings")
        finding_count = findings[0]['count'] if findings else 0
        logger.info(f"Findings in database: {finding_count}")
        
        return {
            'components': comp_count,
            'vulnerabilities': vuln_count, 
            'findings': finding_count
        }
        
    except Exception as e:
        logger.error(f"Error checking database status: {e}")
        return None

async def main():
    """Main execution"""
    logger.info("=== Neuron-AI Vulnerability Scanner ===")
    
    # Check database status first
    logger.info("Checking database status...")
    status = await check_database_status()
    
    if status:
        if status['components'] == 0:
            logger.warning("No SBOM components found in database!")
            logger.info("Make sure you've uploaded SBOM files first")
            
        if status['vulnerabilities'] == 0:
            logger.warning("No vulnerabilities found in database!")
            logger.info("The vulnerability database needs to be populated")
    
    # Run vulnerability scan
    result = await run_vulnerability_scan()
    
    if result:
        logger.info("=== Scan Results ===")
        for key, value in result.items():
            logger.info(f"{key}: {value}")
    else:
        logger.error("Vulnerability scan failed")
    
    # Check status again to see changes
    logger.info("Checking database status after scan...")
    status_after = await check_database_status()

if __name__ == "__main__":
    asyncio.run(main())