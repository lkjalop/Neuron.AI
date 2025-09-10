from __future__ import annotations
from ingest.base import BaseConnector, register_connector
import random, time

class ScannerConnector(BaseConnector):
    source_type = "scanner"
    def poll(self):
        # Synthetic placeholder producing a small set of vulnerabilities
        sample = []
        for _ in range(int(self.config.get("batch_size", 3))):
            sample.append({
                "cve": f"CVE-2025-{random.randint(1000,9999)}",
                "severity": random.choice(["LOW","MEDIUM","HIGH","CRITICAL"]),
                "detected_at": time.time(),
            })
        return sample
    def normalize(self, raw):
        return {
            "type": "vuln",
            "cve": raw["cve"],
            "severity": raw["severity"],
            "ts": raw["detected_at"],
        }

register_connector("scanner", ScannerConnector)
