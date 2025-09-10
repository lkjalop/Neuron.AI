#!/usr/bin/env python3
"""
Neuron-AI Frontend Demo with NLP/RAG Query Interface
Creates a web frontend for natural language querying
"""

import requests
import json
import time
import webbrowser
from flask import Flask, render_template_string, request, jsonify
import threading
from datetime import datetime

app = Flask(__name__)
BASE_URL = "http://localhost:8000"

# Sample security knowledge base for RAG
SECURITY_KNOWLEDGE = {
    "vulnerabilities": {
        "CVE-2021-44228": {
            "name": "Log4Shell",
            "severity": "CRITICAL",
            "cvss": 10.0,
            "description": "Remote code execution in Apache Log4j",
            "mitigation": "Update to Log4j 2.17.0 or later, disable JNDI lookups",
            "impact": "Complete system compromise"
        },
        "CVE-2023-23397": {
            "name": "Outlook Zero-Click",
            "severity": "CRITICAL", 
            "cvss": 9.8,
            "description": "Microsoft Outlook privilege escalation",
            "mitigation": "Apply KB5023778 security update",
            "impact": "Privilege escalation, credential theft"
        }
    },
    "threats": {
        "ransomware": {
            "indicators": ["file encryption", "ransom note", ".encrypted extension"],
            "response": "Isolate affected systems, activate backup recovery, notify authorities",
            "prevention": "Regular backups, patch management, user training"
        },
        "apt": {
            "indicators": ["persistence mechanisms", "lateral movement", "data staging"],
            "response": "Forensic analysis, threat hunting, indicator extraction",
            "prevention": "Defense in depth, monitoring, threat intelligence"
        }
    },
    "procedures": {
        "incident_response": {
            "steps": ["Identify", "Contain", "Eradicate", "Recover", "Lessons Learned"],
            "timeline": "Initial response within 1 hour, full assessment within 24 hours"
        }
    }
}

def query_rag_system(query):
    """Simple RAG system simulation"""
    query_lower = query.lower()
    results = []
    
    # Search vulnerabilities
    for cve, vuln in SECURITY_KNOWLEDGE["vulnerabilities"].items():
        if any(term in query_lower for term in [cve.lower(), vuln["name"].lower(), "vulnerability", "cve"]):
            results.append({
                "type": "vulnerability",
                "id": cve,
                "relevance": 0.9,
                "data": vuln
            })
    
    # Search threats
    for threat_type, threat in SECURITY_KNOWLEDGE["threats"].items():
        if threat_type in query_lower or any(ind.lower() in query_lower for ind in threat["indicators"]):
            results.append({
                "type": "threat",
                "id": threat_type,
                "relevance": 0.8,
                "data": threat
            })
    
    # Search procedures
    if any(term in query_lower for term in ["incident", "response", "procedure", "how to"]):
        results.append({
            "type": "procedure",
            "id": "incident_response",
            "relevance": 0.7,
            "data": SECURITY_KNOWLEDGE["procedures"]["incident_response"]
        })
    
    return sorted(results, key=lambda x: x["relevance"], reverse=True)

@app.route('/')
def index():
    """Main frontend interface"""
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Neuron-AI Security Operations Center</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
        }
        
        .header {
            background: rgba(0, 0, 0, 0.2);
            padding: 20px;
            text-align: center;
            border-bottom: 2px solid rgba(255, 255, 255, 0.1);
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header .status {
            display: inline-block;
            background: #4CAF50;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }
        
        .card h3 {
            margin-bottom: 15px;
            color: #FFD700;
        }
        
        .query-section {
            grid-column: 1 / -1;
        }
        
        .query-input {
            width: 100%;
            padding: 15px;
            font-size: 1.1em;
            border: none;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.9);
            color: #333;
            margin-bottom: 15px;
        }
        
        .btn {
            background: #FF6B35;
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 1em;
            cursor: pointer;
            margin-right: 10px;
            transition: background 0.3s;
        }
        
        .btn:hover {
            background: #FF8C61;
        }
        
        .btn-secondary {
            background: #6C757D;
        }
        
        .results {
            margin-top: 20px;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .result-item {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
            border-left: 4px solid #4CAF50;
        }
        
        .result-header {
            font-weight: bold;
            margin-bottom: 8px;
            color: #FFD700;
        }
        
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .metric-card {
            background: rgba(0, 0, 0, 0.2);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        
        .metric-value {
            font-size: 2em;
            font-weight: bold;
            color: #4CAF50;
        }
        
        .metric-label {
            font-size: 0.9em;
            opacity: 0.8;
        }
        
        .api-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }
        
        .api-endpoint {
            background: rgba(0, 0, 0, 0.2);
            padding: 15px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
        }
        
        .method {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }
        
        .method.get { background: #4CAF50; }
        .method.post { background: #FF9800; }
        .method.put { background: #2196F3; }
        .method.delete { background: #f44336; }
        
        .loading {
            text-align: center;
            padding: 20px;
            opacity: 0.7;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .pulsing {
            animation: pulse 2s infinite;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛡️ Neuron-AI Security Operations Center</h1>
        <div class="status pulsing">SYSTEM ONLINE • MONITORING ACTIVE</div>
    </div>
    
    <div class="container">
        <div class="grid">
            <!-- NLP Query Interface -->
            <div class="card query-section">
                <h3>🤖 Natural Language Security Query</h3>
                <input type="text" id="queryInput" class="query-input" 
                       placeholder="Ask me anything about security... (e.g., 'What is Log4Shell?', 'How to respond to ransomware?', 'Show me recent vulnerabilities')">
                <button onclick="queryNLP()" class="btn">Ask AI Assistant</button>
                <button onclick="loadSampleQueries()" class="btn btn-secondary">Sample Queries</button>
                <div id="queryResults" class="results"></div>
            </div>
            
            <!-- Live Metrics -->
            <div class="card">
                <h3>📊 Live Security Metrics</h3>
                <div class="metrics-grid">
                    <div class="metric-card">
                        <div class="metric-value" id="threatsDetected">0</div>
                        <div class="metric-label">Threats Detected</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" id="activeCases">0</div>
                        <div class="metric-label">Active Cases</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" id="iocCount">0</div>
                        <div class="metric-label">IOCs Tracked</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-value" id="systemStatus">ONLINE</div>
                        <div class="metric-label">System Status</div>
                    </div>
                </div>
            </div>
            
            <!-- Recent Detections -->
            <div class="card">
                <h3>🚨 Recent Security Events</h3>
                <div id="recentEvents"></div>
            </div>
            
            <!-- API Endpoints -->
            <div class="card">
                <h3>🔌 Available API Endpoints</h3>
                <div class="api-grid">
                    <div class="api-endpoint">
                        <span class="method post">POST</span> /anomalies<br>
                        <small>Report security anomalies</small>
                    </div>
                    <div class="api-endpoint">
                        <span class="method get">GET</span> /cases<br>
                        <small>List incident cases</small>
                    </div>
                    <div class="api-endpoint">
                        <span class="method post">POST</span> /ioc<br>
                        <small>Add threat indicators</small>
                    </div>
                    <div class="api-endpoint">
                        <span class="method post">POST</span> /forensics/jobs<br>
                        <small>Submit forensic analysis</small>
                    </div>
                    <div class="api-endpoint">
                        <span class="method get">GET</span> /threat-feeds/indicators<br>
                        <small>Query threat intelligence</small>
                    </div>
                    <div class="api-endpoint">
                        <span class="method post">POST</span> /hunt/query<br>
                        <small>Execute threat hunting</small>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Sample security events
        const sampleEvents = [
            { time: '10:34:22', type: 'CRITICAL', event: 'Ransomware detected on finance-server-01', status: 'CONTAINED' },
            { time: '10:31:15', type: 'HIGH', event: 'Suspicious PowerShell execution detected', status: 'INVESTIGATING' },
            { time: '10:28:45', type: 'MEDIUM', event: 'Failed login attempts from 185.159.158.1', status: 'BLOCKED' },
            { time: '10:25:12', type: 'INFO', event: 'Vulnerability scan completed - 23 findings', status: 'COMPLETED' }
        ];
        
        // NLP Query function
        async function queryNLP() {
            const query = document.getElementById('queryInput').value;
            if (!query.trim()) return;
            
            const resultsDiv = document.getElementById('queryResults');
            resultsDiv.innerHTML = '<div class="loading">🤖 Processing your query...</div>';
            
            try {
                const response = await fetch('/api/query', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: query })
                });
                
                const results = await response.json();
                displayQueryResults(results);
            } catch (error) {
                resultsDiv.innerHTML = '<div class="result-item">❌ Error processing query. Please try again.</div>';
            }
        }
        
        function displayQueryResults(results) {
            const resultsDiv = document.getElementById('queryResults');
            
            if (results.length === 0) {
                resultsDiv.innerHTML = '<div class="result-item">🤔 No relevant information found. Try asking about vulnerabilities, threats, or procedures.</div>';
                return;
            }
            
            let html = '<h4>🎯 Query Results:</h4>';
            results.forEach(result => {
                html += `
                    <div class="result-item">
                        <div class="result-header">${getResultIcon(result.type)} ${result.id.toUpperCase()}</div>
                        <div>${formatResultData(result)}</div>
                    </div>
                `;
            });
            
            resultsDiv.innerHTML = html;
        }
        
        function getResultIcon(type) {
            switch(type) {
                case 'vulnerability': return '🔴';
                case 'threat': return '⚠️';
                case 'procedure': return '📋';
                default: return '📄';
            }
        }
        
        function formatResultData(result) {
            const data = result.data;
            let html = '';
            
            if (result.type === 'vulnerability') {
                html = `
                    <strong>Severity:</strong> ${data.severity} (CVSS: ${data.cvss})<br>
                    <strong>Description:</strong> ${data.description}<br>
                    <strong>Impact:</strong> ${data.impact}<br>
                    <strong>Mitigation:</strong> ${data.mitigation}
                `;
            } else if (result.type === 'threat') {
                html = `
                    <strong>Indicators:</strong> ${data.indicators.join(', ')}<br>
                    <strong>Response:</strong> ${data.response}<br>
                    <strong>Prevention:</strong> ${data.prevention}
                `;
            } else if (result.type === 'procedure') {
                html = `
                    <strong>Steps:</strong> ${data.steps.join(' → ')}<br>
                    <strong>Timeline:</strong> ${data.timeline}
                `;
            }
            
            return html;
        }
        
        function loadSampleQueries() {
            const samples = [
                "What is CVE-2021-44228?",
                "How do I respond to ransomware?",
                "Show me APT indicators",
                "What are the incident response steps?",
                "Tell me about Outlook vulnerabilities"
            ];
            
            const query = samples[Math.floor(Math.random() * samples.length)];
            document.getElementById('queryInput').value = query;
            queryNLP();
        }
        
        // Update live metrics
        async function updateMetrics() {
            try {
                // Get anomalies count
                const anomaliesResponse = await fetch('http://localhost:8000/anomalies');
                const anomalies = await anomaliesResponse.json();
                document.getElementById('threatsDetected').textContent = anomalies.items?.length || '0';
                
                // Get cases count
                const casesResponse = await fetch('http://localhost:8000/cases');
                const cases = await casesResponse.json();
                document.getElementById('activeCases').textContent = cases.items?.length || '0';
                
                // Get IOCs count
                const iocResponse = await fetch('http://localhost:8000/ioc');
                const iocs = await iocResponse.json();
                document.getElementById('iocCount').textContent = iocs.items?.length || '0';
                
            } catch (error) {
                console.log('Metrics update error:', error);
            }
        }
        
        // Display recent events
        function displayRecentEvents() {
            const eventsDiv = document.getElementById('recentEvents');
            let html = '';
            
            sampleEvents.forEach(event => {
                const severity = event.type === 'CRITICAL' ? '🔴' : 
                               event.type === 'HIGH' ? '🟠' : 
                               event.type === 'MEDIUM' ? '🟡' : '🔵';
                
                html += `
                    <div class="result-item">
                        ${severity} <strong>${event.time}</strong> - ${event.event}
                        <div style="float: right; font-size: 0.9em;">${event.status}</div>
                    </div>
                `;
            });
            
            eventsDiv.innerHTML = html;
        }
        
        // Enter key support for query input
        document.getElementById('queryInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                queryNLP();
            }
        });
        
        // Initialize
        updateMetrics();
        displayRecentEvents();
        setInterval(updateMetrics, 30000); // Update every 30 seconds
    </script>
</body>
</html>
    """)

@app.route('/api/query', methods=['POST'])
def query_api():
    """Handle NLP queries"""
    data = request.json
    query = data.get('query', '')
    
    # Use the RAG system
    results = query_rag_system(query)
    
    return jsonify(results)

def run_frontend():
    """Run the frontend server"""
    app.run(debug=False, port=5001, host='0.0.0.0')

if __name__ == "__main__":
    print("="*60)
    print("NEURON-AI FRONTEND WITH NLP/RAG")
    print("="*60)
    print("\nStarting enhanced frontend with:")
    print("• Natural Language Query Interface")
    print("• Real-time Security Metrics")
    print("• Interactive API Testing")
    print("• Live Event Monitoring")
    
    print(f"\nFrontend will be available at:")
    print(f"🌐 http://localhost:5001")
    print(f"\nAPI Backend running at:")
    print(f"🔧 http://localhost:8000")
    
    print(f"\nOpening browser in 3 seconds...")
    
    # Start frontend server in background
    frontend_thread = threading.Thread(target=run_frontend, daemon=True)
    frontend_thread.start()
    
    # Wait and open browser
    time.sleep(3)
    webbrowser.open('http://localhost:5001')
    
    print(f"\n✅ Frontend launched!")
    print(f"Try asking questions like:")
    print(f"  • 'What is Log4Shell?'")
    print(f"  • 'How do I respond to ransomware?'")
    print(f"  • 'Show me APT indicators'")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n👋 Shutting down frontend...")