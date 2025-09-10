@echo off
REM NEURON Platform - Quick Start Testing Script
REM This script sets up and launches the platform for security testing

echo ========================================
echo   NEURON PLATFORM - SECURITY TESTING
echo ========================================
echo.

REM Set environment variables for full features
echo [1/5] Setting environment variables...
set VULN_SCAN_ENABLED=1
set EXPERIMENTAL_ISOFOREST=true
set ENABLE_SNN=true
set ENABLE_FUSION=true
set NEURON_DEBUG=true
set FUSION_STRATEGY=weighted_sum
set SNN_DETERMINISTIC=true
set SNN_SEED=20250904

echo [2/5] Starting API server...
echo.
echo Starting server at http://localhost:8000
echo.
start cmd /k "python -m uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000"

REM Wait for server to start
timeout /t 5 /nobreak > nul

echo.
echo [3/5] Running initial tests...
start cmd /k "pytest tests/test_api_basic.py -v && pause"

echo.
echo [4/5] Opening browser to API documentation...
timeout /t 2 /nobreak > nul
start http://localhost:8000/docs

echo.
echo [5/5] Platform is ready!
echo.
echo ========================================
echo   AVAILABLE ENDPOINTS:
echo ========================================
echo.
echo API Documentation:    http://localhost:8000/docs
echo Health Check:         http://localhost:8000/health
echo Metrics:             http://localhost:8000/metrics
echo Vulnerabilities:     http://localhost:8000/vulnerabilities
echo Dashboard Data:      http://localhost:8000/dashboard/latest
echo.
echo ========================================
echo   QUICK TEST COMMANDS:
echo ========================================
echo.
echo Test vulnerability scanning:
echo   curl -X POST http://localhost:8000/vuln/ingest_sbom -H "Content-Type: application/json" -d @test_sbom.json
echo.
echo Simulate attack:
echo   python test_attack_patterns.py
echo.
echo Run security scan:
echo   powershell .\scripts\security_scan.ps1
echo.
echo Run all tests:
echo   pytest tests/ -v
echo.
echo ========================================
echo.
echo Press any key to exit...
pause > nul