"""Script to validate required metrics are registered in core.metrics."""
from core import metrics

REQUIRED = [
    'VULN_RISK_SCORE',
    'VULN_ACTIVE_FINDINGS',
    'VULN_SLA_COUNTDOWN_DAYS',
    'VULN_SCAN_CYCLES_TOTAL',
    'VULN_NORMALIZATION_LATENCY',
]

def main():
    missing = []
    for name in REQUIRED:
        if not hasattr(metrics, name):
            missing.append(name)
    if missing:
        print(f"Missing metrics: {missing}")
        exit(1)
    print("All required metrics present.")

if __name__ == "__main__":
    main()
