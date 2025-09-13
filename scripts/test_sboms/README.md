# SBOM Test Samples

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
