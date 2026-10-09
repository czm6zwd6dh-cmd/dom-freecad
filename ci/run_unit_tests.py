#!/usr/bin/env python3
"""Execute, count and preserve real cloud-subset/harness test results."""
import json
from pathlib import Path
import re
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root / 'build/smoke'
out.mkdir(parents=True, exist_ok=True)
results = []
for name, folder in [('skill-cloud-subset', 'vendor/architect-engineer-spds/tests'), ('cloud-harness', 'tests')]:
    command = [sys.executable, '-m', 'unittest', 'discover', '-s', folder, '-p', 'test_*.py', '-v']
    result = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=180)
    counts = re.findall(r'Ran (\d+) tests? in', result.stderr)
    count = int(counts[-1]) if counts else 0
    results.append(dict(suite=name, exit_code=result.returncode, tests=count,
                        stdout=result.stdout, stderr=result.stderr))
report = {'status': 'PASS' if all(r['exit_code'] == 0 and r['tests'] > 0 for r in results) else 'FAILED',
          'tests': sum(r['tests'] for r in results), 'suites': results,
          'scope': 'Cloud subset and CI harness, NOT the full host skill suite or native CAD',
          'construction_ready': False}
(out / 'unit-tests.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
for r in results:
    print(r['suite'], 'tests:', r['tests'], 'exit:', r['exit_code'])
    if r['exit_code']:
        print(r['stderr'])
raise SystemExit(0 if report['status'] == 'PASS' else 1)
