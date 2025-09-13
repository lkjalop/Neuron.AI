#!/usr/bin/env python3
"""
SBOM TEST SAMPLES GENERATOR
===========================

Creates realistic SBOM files for testing vulnerability assessment features.
Includes both vulnerable and secure package versions for comprehensive testing.
"""

import json
import os
from datetime import datetime
from typing import Dict, List

def create_vulnerable_sbom() -> Dict:
    """Create SBOM with known vulnerable packages"""
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:vulnerable-app-{datetime.now().strftime('%Y%m%d')}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now().isoformat() + "Z",
            "tools": [
                {
                    "vendor": "Neuron-AI",
                    "name": "vulnerability-scanner",
                    "version": "1.0.0"
                }
            ],
            "component": {
                "type": "application",
                "name": "vulnerable-web-app",
                "version": "1.0.0"
            }
        },
        "components": [
            {
                "type": "library",
                "bom-ref": "log4j-core-2.14.1",
                "name": "log4j-core",
                "version": "2.14.1",
                "purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.14.1",
                "licenses": [
                    {"license": {"id": "Apache-2.0"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "spring-core-5.3.9",
                "name": "spring-core",
                "version": "5.3.9",
                "purl": "pkg:maven/org.springframework/spring-core@5.3.9",
                "licenses": [
                    {"license": {"id": "Apache-2.0"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "jackson-databind-2.9.8",
                "name": "jackson-databind",
                "version": "2.9.8",
                "purl": "pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.9.8",
                "licenses": [
                    {"license": {"id": "Apache-2.0"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "openssl-1.1.1k",
                "name": "openssl",
                "version": "1.1.1k",
                "purl": "pkg:generic/openssl@1.1.1k",
                "licenses": [
                    {"license": {"id": "OpenSSL"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "nginx-1.18.0",
                "name": "nginx",
                "version": "1.18.0",
                "purl": "pkg:generic/nginx@1.18.0",
                "licenses": [
                    {"license": {"id": "BSD-2-Clause"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "jquery-3.4.1",
                "name": "jquery",
                "version": "3.4.1",
                "purl": "pkg:npm/jquery@3.4.1",
                "licenses": [
                    {"license": {"id": "MIT"}}
                ]
            }
        ]
    }

def create_secure_sbom() -> Dict:
    """Create SBOM with updated, secure packages"""
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:secure-app-{datetime.now().strftime('%Y%m%d')}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now().isoformat() + "Z",
            "tools": [
                {
                    "vendor": "Neuron-AI",
                    "name": "vulnerability-scanner",
                    "version": "1.0.0"
                }
            ],
            "component": {
                "type": "application",
                "name": "secure-web-app",
                "version": "2.0.0"
            }
        },
        "components": [
            {
                "type": "library",
                "bom-ref": "log4j-core-2.17.0",
                "name": "log4j-core",
                "version": "2.17.0",
                "purl": "pkg:maven/org.apache.logging.log4j/log4j-core@2.17.0",
                "licenses": [
                    {"license": {"id": "Apache-2.0"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "spring-core-5.3.18",
                "name": "spring-core",
                "version": "5.3.18",
                "purl": "pkg:maven/org.springframework/spring-core@5.3.18",
                "licenses": [
                    {"license": {"id": "Apache-2.0"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "jackson-databind-2.13.2",
                "name": "jackson-databind",
                "version": "2.13.2",
                "purl": "pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.13.2",
                "licenses": [
                    {"license": {"id": "Apache-2.0"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "openssl-3.0.2",
                "name": "openssl",
                "version": "3.0.2",
                "purl": "pkg:generic/openssl@3.0.2",
                "licenses": [
                    {"license": {"id": "Apache-2.0"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "nginx-1.22.0",
                "name": "nginx",
                "version": "1.22.0",
                "purl": "pkg:generic/nginx@1.22.0",
                "licenses": [
                    {"license": {"id": "BSD-2-Clause"}}
                ]
            }
        ]
    }

def create_nodejs_sbom() -> Dict:
    """Create Node.js application SBOM with npm packages"""
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:nodejs-app-{datetime.now().strftime('%Y%m%d')}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now().isoformat() + "Z",
            "tools": [
                {
                    "vendor": "npm",
                    "name": "cyclonedx-npm",
                    "version": "1.7.0"
                }
            ],
            "component": {
                "type": "application",
                "name": "express-api",
                "version": "1.0.0"
            }
        },
        "components": [
            {
                "type": "library",
                "bom-ref": "express-4.17.1",
                "name": "express",
                "version": "4.17.1",
                "purl": "pkg:npm/express@4.17.1",
                "licenses": [
                    {"license": {"id": "MIT"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "lodash-4.17.20",
                "name": "lodash",
                "version": "4.17.20",
                "purl": "pkg:npm/lodash@4.17.20",
                "licenses": [
                    {"license": {"id": "MIT"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "axios-0.21.0",
                "name": "axios",
                "version": "0.21.0",
                "purl": "pkg:npm/axios@0.21.0",
                "licenses": [
                    {"license": {"id": "MIT"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "helmet-3.23.3",
                "name": "helmet",
                "version": "3.23.3",
                "purl": "pkg:npm/helmet@3.23.3",
                "licenses": [
                    {"license": {"id": "MIT"}}
                ]
            }
        ]
    }

def create_python_sbom() -> Dict:
    """Create Python application SBOM with pip packages"""
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.4",
        "serialNumber": f"urn:uuid:python-app-{datetime.now().strftime('%Y%m%d')}",
        "version": 1,
        "metadata": {
            "timestamp": datetime.now().isoformat() + "Z",
            "tools": [
                {
                    "vendor": "CycloneDX",
                    "name": "cyclonedx-python",
                    "version": "2.0.0"
                }
            ],
            "component": {
                "type": "application",
                "name": "flask-api",
                "version": "1.0.0"
            }
        },
        "components": [
            {
                "type": "library",
                "bom-ref": "flask-1.1.4",
                "name": "flask",
                "version": "1.1.4",
                "purl": "pkg:pypi/flask@1.1.4",
                "licenses": [
                    {"license": {"id": "BSD-3-Clause"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "requests-2.25.1",
                "name": "requests",
                "version": "2.25.1",
                "purl": "pkg:pypi/requests@2.25.1",
                "licenses": [
                    {"license": {"id": "Apache-2.0"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "pillow-8.1.0",
                "name": "pillow",
                "version": "8.1.0",
                "purl": "pkg:pypi/pillow@8.1.0",
                "licenses": [
                    {"license": {"id": "HPND"}}
                ]
            },
            {
                "type": "library",
                "bom-ref": "pyyaml-5.4.1",
                "name": "pyyaml",
                "version": "5.4.1",
                "purl": "pkg:pypi/pyyaml@5.4.1",
                "licenses": [
                    {"license": {"id": "MIT"}}
                ]
            }
        ]
    }

def save_sbom_files():
    """Save all SBOM test files"""
    # Create test_sboms directory
    os.makedirs("test_sboms", exist_ok=True)
    
    # Generate and save all SBOM variants
    sboms = {
        "vulnerable_java_app.json": create_vulnerable_sbom(),
        "secure_java_app.json": create_secure_sbom(),
        "nodejs_express_app.json": create_nodejs_sbom(),
        "python_flask_app.json": create_python_sbom()
    }
    
    for filename, sbom_data in sboms.items():
        filepath = os.path.join("test_sboms", filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(sbom_data, f, indent=2)
        print(f"Created {filepath}")
    
    # Create README for test files
    readme_content = """# SBOM Test Samples

These SBOM files are designed for testing the Neuron-AI vulnerability assessment features:

## Files:

### vulnerable_java_app.json
- Contains known vulnerable packages (Log4Shell, Spring4Shell, etc.)
- Expected to generate 4-5 critical/high severity findings
- Use for demonstrating vulnerability detection capabilities

### secure_java_app.json  
- Contains updated, secure versions of the same packages
- Should generate minimal or no vulnerability findings
- Use for demonstrating remediation verification

### nodejs_express_app.json
- Node.js/Express application dependencies
- Contains some older package versions with known issues
- Use for npm ecosystem vulnerability testing

### python_flask_app.json
- Python Flask application dependencies  
- Includes packages with historical vulnerabilities
- Use for PyPI ecosystem testing

## Usage:

1. Start the Neuron-AI backend: `python -m uvicorn core.main:app --reload`
2. Open vulnerability interface: http://localhost:8080/vuln.html
3. Set API key: `neuron-ai-demo-key-2024`
4. Upload any of these SBOM files
5. Review vulnerability findings and risk scores

Expected results vary by file - vulnerable_java_app.json should show the most critical findings.
"""
    
    with open("test_sboms/README.md", 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print("Created test_sboms/README.md")
    print("\nAll SBOM test files ready in test_sboms/ directory")

if __name__ == "__main__":
    print("Generating SBOM test samples...")
    save_sbom_files()
    print("\nYou can now test vulnerability assessment with realistic SBOM files!")
    print("See test_sboms/README.md for usage instructions")