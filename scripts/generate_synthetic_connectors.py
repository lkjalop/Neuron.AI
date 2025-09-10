"""Post synthetic connector events to validate new ingestion endpoints.

Usage:
  python scripts/generate_synthetic_connectors.py --base-url http://127.0.0.1:8000 --tenant demo --count 5

Emits sample payloads for: EDR, DNS, Netflow, SIEM.
"""
from __future__ import annotations
import argparse, random, time, requests, json

APIS = [
    ("edr", "/ingest/edr"),
    ("dns", "/ingest/dns"),
    ("netflow", "/ingest/netflow"),
    ("siem", "/ingest/siem"),
]

PROCESS_NAMES = ["cmd.exe","python.exe","bash","powershell.exe","svchost.exe"]
DOMAINS = ["example.com","beacon.test","malware.test","internal.corp","update.service"]
USERS = ["alice","bob","svc-backend","root"]


def edr_payload(tenant: str, i: int):
    return {
        "event_id": f"edr_{int(time.time()*1000)}_{i}",
        "tenant_id": tenant,
        "process_name": random.choice(PROCESS_NAMES),
        "parent_process": random.choice(PROCESS_NAMES),
        "user": random.choice(USERS),
        "command_line": "python script.py --arg test",
    }

def dns_payload(tenant: str, i: int):
    q = random.choice(DOMAINS)
    return {
        "event_id": f"dns_{int(time.time()*1000)}_{i}",
        "tenant_id": tenant,
        "query": q,
        "qtype": "A",
        "client_ip": f"10.0.0.{random.randint(1,250)}",
        "response_ips": [f"192.168.1.{random.randint(1,250)}"],
    }

def netflow_payload(tenant: str, i: int):
    return {
        "event_id": f"flow_{int(time.time()*1000)}_{i}",
        "tenant_id": tenant,
        "src_ip": f"10.1.{random.randint(0,5)}.{random.randint(1,254)}",
        "dst_ip": f"172.16.{random.randint(0,5)}.{random.randint(1,254)}",
        "bytes": random.randint(200, 50000),
        "packets": random.randint(1, 400),
        "protocol": random.choice(["TCP","UDP"]),
        "duration_ms": random.randint(10, 5000),
    }

def siem_payload(tenant: str, i: int):
    return {
        "event_id": f"siem_{int(time.time()*1000)}_{i}",
        "tenant_id": tenant,
        "vendor": "generic",
        "product": "appgw",
        "event_code": random.choice(["ALLOW","DENY","AUTH_FAIL"]),
        "message": "gateway event observed",
    }

GENS = {
    'edr': edr_payload,
    'dns': dns_payload,
    'netflow': netflow_payload,
    'siem': siem_payload,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base-url', default='http://127.0.0.1:8000')
    ap.add_argument('--tenant', default='demo')
    ap.add_argument('--count', type=int, default=5)
    ap.add_argument('--delay', type=float, default=0.05)
    args = ap.parse_args()
    total = 0
    for name, path in APIS:
        gen = GENS[name]
        for i in range(args.count):
            payload = gen(args.tenant, i)
            try:
                r = requests.post(args.base_url.rstrip('/') + path, json=payload, timeout=3)
                status = r.status_code
            except Exception:
                status = 'ERR'
            print(f"[{name}] {status} {payload['event_id']}")
            total += 1
            time.sleep(args.delay)
    print(f"[synthetic] Sent {total} connector events")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
