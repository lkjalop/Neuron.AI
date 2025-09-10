#!/usr/bin/env python3
"""
Real-time Dashboard Setup for Neuron-AI
Shows metrics, graphs, and detection results in browser
"""

import json
import time
import threading
import webbrowser
from datetime import datetime
from flask import Flask, render_template, jsonify
import requests
import plotly.graph_objs as go
import plotly.utils

app = Flask(__name__)

# Global metrics storage
metrics_history = {
    'timestamps': [],
    'detection_rate': [],
    'anomalies_detected': [],
    'events_processed': [],
    'latency_ms': [],
    'threat_scores': [],
    'vulnerabilities': [],
    'endpoints': [],
    'network_attacks': []
}

# Detection results storage
recent_detections = []
test_status = {
    'total_tests': 0,
    'passed': 0,
    'failed': 0,
    'in_progress': 0
}

def collect_metrics():
    """Continuously collect metrics from Neuron-AI"""
    global metrics_history, recent_detections
    
    while True:
        try:
            # Get metrics from Prometheus endpoint
            response = requests.get('http://localhost:8000/metrics')
            if response.status_code == 200:
                # Parse metrics (simplified)
                lines = response.text.split('\n')
                current_time = datetime.now().strftime('%H:%M:%S')
                
                # Add to history (keep last 100 points)
                metrics_history['timestamps'].append(current_time)
                if len(metrics_history['timestamps']) > 100:
                    metrics_history['timestamps'].pop(0)
                
                # Extract key metrics
                for line in lines:
                    if 'events_processed_total' in line and not line.startswith('#'):
                        value = float(line.split()[-1])
                        metrics_history['events_processed'].append(value)
                    elif 'anomalies_detected_total' in line and not line.startswith('#'):
                        value = float(line.split()[-1])
                        metrics_history['anomalies_detected'].append(value)
                    elif 'processing_latency' in line and 'quantile="0.5"' in line:
                        value = float(line.split()[-1]) * 1000  # Convert to ms
                        metrics_history['latency_ms'].append(value)
                
                # Trim histories
                for key in ['events_processed', 'anomalies_detected', 'latency_ms']:
                    if len(metrics_history[key]) > 100:
                        metrics_history[key].pop(0)
                        
        except Exception as e:
            print(f"Metrics collection error: {e}")
            
        time.sleep(2)  # Update every 2 seconds

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Neuron-AI Security Dashboard</title>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
        <style>
            body {
                font-family: 'Segoe UI', Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
                color: white;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
            }
            h1 {
                text-align: center;
                font-size: 2.5em;
                margin-bottom: 30px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            }
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .metric-card {
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 20px;
                text-align: center;
                border: 1px solid rgba(255,255,255,0.2);
            }
            .metric-value {
                font-size: 2.5em;
                font-weight: bold;
                margin: 10px 0;
            }
            .metric-label {
                font-size: 0.9em;
                opacity: 0.9;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .chart-container {
                background: rgba(255,255,255,0.1);
                backdrop-filter: blur(10px);
                border-radius: 15px;
                padding: 20px;
                margin-bottom: 20px;
                border: 1px solid rgba(255,255,255,0.2);
            }
            .detection-log {
                background: rgba(0,0,0,0.3);
                border-radius: 10px;
                padding: 15px;
                max-height: 400px;
                overflow-y: auto;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
            }
            .detection-item {
                padding: 8px;
                margin: 5px 0;
                border-left: 3px solid #4CAF50;
                background: rgba(76,175,80,0.1);
            }
            .threat-high {
                border-left-color: #f44336;
                background: rgba(244,67,54,0.1);
            }
            .threat-medium {
                border-left-color: #ff9800;
                background: rgba(255,152,0,0.1);
            }
            .status-indicator {
                display: inline-block;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 5px;
                animation: pulse 2s infinite;
            }
            .status-online {
                background: #4CAF50;
            }
            .status-processing {
                background: #2196F3;
            }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            .test-progress {
                background: rgba(255,255,255,0.1);
                border-radius: 50px;
                height: 30px;
                overflow: hidden;
                margin: 20px 0;
            }
            .progress-bar {
                height: 100%;
                background: linear-gradient(90deg, #4CAF50, #8BC34A);
                transition: width 0.3s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                color: white;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ Neuron-AI Security Operations Center</h1>
            
            <div class="metrics-grid" id="metrics">
                <div class="metric-card">
                    <div class="metric-label">
                        <span class="status-indicator status-online"></span>System Status
                    </div>
                    <div class="metric-value" id="status">ONLINE</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Events Processed</div>
                    <div class="metric-value" id="events">0</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Threats Detected</div>
                    <div class="metric-value" id="threats">0</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Detection Rate</div>
                    <div class="metric-value" id="detection-rate">0%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Avg Latency</div>
                    <div class="metric-value" id="latency">0ms</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">Active Tests</div>
                    <div class="metric-value" id="active-tests">0</div>
                </div>
            </div>
            
            <div class="test-progress">
                <div class="progress-bar" id="progress" style="width: 0%">0%</div>
            </div>
            
            <div class="chart-container">
                <h3>📈 Real-time Detection Metrics</h3>
                <div id="detection-chart"></div>
            </div>
            
            <div class="chart-container">
                <h3>⚡ Performance Metrics</h3>
                <div id="performance-chart"></div>
            </div>
            
            <div class="chart-container">
                <h3>🎯 Threat Categories</h3>
                <div id="threat-chart"></div>
            </div>
            
            <div class="chart-container">
                <h3>📝 Detection Log</h3>
                <div class="detection-log" id="detection-log">
                    <div class="detection-item">Waiting for detections...</div>
                </div>
            </div>
        </div>
        
        <script>
            // Update metrics every 2 seconds
            function updateMetrics() {
                $.get('/api/metrics', function(data) {
                    $('#events').text(data.events_processed || 0);
                    $('#threats').text(data.threats_detected || 0);
                    $('#detection-rate').text((data.detection_rate || 0).toFixed(1) + '%');
                    $('#latency').text((data.avg_latency || 0).toFixed(1) + 'ms');
                    $('#active-tests').text(data.active_tests || 0);
                    
                    // Update progress bar
                    var progress = data.test_progress || 0;
                    $('#progress').css('width', progress + '%').text(progress + '%');
                    
                    // Update detection chart
                    var detectionTrace = {
                        x: data.timestamps || [],
                        y: data.anomalies_detected || [],
                        type: 'scatter',
                        name: 'Anomalies',
                        line: {color: '#4CAF50', width: 2}
                    };
                    
                    var eventsTrace = {
                        x: data.timestamps || [],
                        y: data.events_processed || [],
                        type: 'scatter',
                        name: 'Events',
                        yaxis: 'y2',
                        line: {color: '#2196F3', width: 2}
                    };
                    
                    var detectionLayout = {
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        font: {color: 'white'},
                        showlegend: true,
                        yaxis: {title: 'Anomalies', gridcolor: 'rgba(255,255,255,0.1)'},
                        yaxis2: {
                            title: 'Events',
                            overlaying: 'y',
                            side: 'right',
                            gridcolor: 'rgba(255,255,255,0.1)'
                        },
                        xaxis: {gridcolor: 'rgba(255,255,255,0.1)'}
                    };
                    
                    Plotly.newPlot('detection-chart', [detectionTrace, eventsTrace], detectionLayout);
                    
                    // Update performance chart
                    var latencyTrace = {
                        x: data.timestamps || [],
                        y: data.latency_ms || [],
                        type: 'scatter',
                        name: 'Latency (ms)',
                        fill: 'tozeroy',
                        line: {color: '#FF9800', width: 2}
                    };
                    
                    var perfLayout = {
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        font: {color: 'white'},
                        yaxis: {title: 'Latency (ms)', gridcolor: 'rgba(255,255,255,0.1)'},
                        xaxis: {gridcolor: 'rgba(255,255,255,0.1)'}
                    };
                    
                    Plotly.newPlot('performance-chart', [latencyTrace], perfLayout);
                    
                    // Update threat categories pie chart
                    var threatData = [{
                        values: data.threat_categories_values || [30, 25, 20, 15, 10],
                        labels: data.threat_categories_labels || ['Vulnerabilities', 'Endpoint', 'Network', 'APT', 'Forensics'],
                        type: 'pie',
                        marker: {
                            colors: ['#f44336', '#ff9800', '#ffeb3b', '#4caf50', '#2196f3']
                        }
                    }];
                    
                    var threatLayout = {
                        paper_bgcolor: 'rgba(0,0,0,0)',
                        plot_bgcolor: 'rgba(0,0,0,0)',
                        font: {color: 'white'}
                    };
                    
                    Plotly.newPlot('threat-chart', threatData, threatLayout);
                });
            }
            
            // Update detection log
            function updateLog() {
                $.get('/api/detections', function(data) {
                    var logHtml = '';
                    data.detections.forEach(function(detection) {
                        var threatClass = '';
                        if (detection.severity === 'HIGH') threatClass = 'threat-high';
                        else if (detection.severity === 'MEDIUM') threatClass = 'threat-medium';
                        
                        logHtml += '<div class="detection-item ' + threatClass + '">';
                        logHtml += '<strong>' + detection.timestamp + '</strong> - ';
                        logHtml += detection.type + ': ' + detection.description;
                        logHtml += ' (Confidence: ' + detection.confidence + '%)';
                        logHtml += '</div>';
                    });
                    $('#detection-log').html(logHtml || '<div class="detection-item">No detections yet...</div>');
                });
            }
            
            // Start updates
            setInterval(updateMetrics, 2000);
            setInterval(updateLog, 3000);
            updateMetrics();
            updateLog();
        </script>
    </body>
    </html>
    '''

@app.route('/api/metrics')
def get_metrics():
    """API endpoint for metrics"""
    global metrics_history, test_status
    
    # Calculate current values
    events = len(metrics_history['events_processed'])
    threats = len(metrics_history['anomalies_detected'])
    detection_rate = (threats / events * 100) if events > 0 else 0
    avg_latency = sum(metrics_history['latency_ms'][-10:]) / 10 if metrics_history['latency_ms'] else 0
    
    # Calculate test progress
    total = test_status['total_tests']
    completed = test_status['passed'] + test_status['failed']
    progress = int((completed / total * 100)) if total > 0 else 0
    
    return jsonify({
        'events_processed': events,
        'threats_detected': threats,
        'detection_rate': detection_rate,
        'avg_latency': avg_latency,
        'active_tests': test_status['in_progress'],
        'test_progress': progress,
        'timestamps': metrics_history['timestamps'][-50:],
        'anomalies_detected': metrics_history['anomalies_detected'][-50:],
        'latency_ms': metrics_history['latency_ms'][-50:],
        'threat_categories_values': [30, 25, 20, 15, 10],
        'threat_categories_labels': ['Vulnerabilities', 'Endpoint', 'Network', 'APT', 'Forensics']
    })

@app.route('/api/detections')
def get_detections():
    """API endpoint for recent detections"""
    global recent_detections
    return jsonify({
        'detections': recent_detections[-20:]  # Last 20 detections
    })

def add_detection(detection_type, description, confidence, severity='MEDIUM'):
    """Add a detection to the log"""
    global recent_detections
    recent_detections.append({
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'type': detection_type,
        'description': description,
        'confidence': confidence,
        'severity': severity
    })
    if len(recent_detections) > 100:
        recent_detections.pop(0)

def run_dashboard():
    """Start the dashboard server"""
    # Start metrics collection in background
    collector_thread = threading.Thread(target=collect_metrics, daemon=True)
    collector_thread.start()
    
    # Open browser
    time.sleep(2)
    webbrowser.open('http://localhost:5000')
    
    # Run Flask app
    app.run(debug=False, port=5000)

if __name__ == '__main__':
    print("Starting Neuron-AI Dashboard...")
    print("Dashboard will open in your browser at http://localhost:5000")
    run_dashboard()