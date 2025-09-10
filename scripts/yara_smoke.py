import sys, json, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from config import runtime_params as rp
from forensics.memory import submit_memory_job

# Enable YARA scanning; point to default rules dir if present
rp.update_param('forensics.yara.enabled', True, reason='smoke')
rp.update_param('forensics.yara.rules_dir', 'artifacts/yara_rules', reason='smoke')
rp.update_param('forensics.yara.max_runtime_s', 5, reason='smoke')

# Use sample file if present; else fall back to non-existent path (triggers synthetic artifact)
sample = 'artifacts/yara_samples/sample.bin'

async def main():
    rec = await submit_memory_job('asset_x', {'dump_path': sample})
    out = {
        'id': rec.get('id'),
        'status': rec.get('status'),
        'yara_summary': rec.get('yara_summary'),
        'warnings': rec.get('warnings'),
        'artifacts_count': len(rec.get('artifacts', [])),
        'artifact_types': list({a.get('type') for a in rec.get('artifacts', [])}),
        'artifact_sample': rec.get('artifacts', [])[:2],
    }
    print(json.dumps(out, indent=2, default=str))

if __name__ == '__main__':
    asyncio.run(main())
