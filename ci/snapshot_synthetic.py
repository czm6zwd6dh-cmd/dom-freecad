#!/usr/bin/env python3
"""Create and restore an allowlisted, closed synthetic release using skill v0.13.0."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'vendor/architect-engineer-spds/scripts'))
import release_backup

out = ROOT / 'build/smoke'
files = ['synthetic-wall.FCStd', 'synthetic-wall.step', 'synthetic-page.pdf', 'synthetic-page.svg', 'report.json']
snapshot = release_backup.snapshot(out, out / 'backup', files)
release_backup.verify(out / 'backup')
restored = release_backup.restore(out / 'backup', out / 'restored')
for name in files:
    if hashlib.sha256((out / name).read_bytes()).digest() != hashlib.sha256((out / 'restored' / name).read_bytes()).digest():
        raise ValueError('Restored bytes differ')
(out / 'backup-verification.json').write_text(json.dumps({
    'status': 'PASS', 'scope': 'SYNTHETIC_CLOSED_RELEASE', 'source': 'SYNTHETIC_ONLY',
    'files': snapshot['files'], 'native_reopen': 'CHECK_SEPARATE_RESTORE_REOPEN_REPORT',
    'off_device_persistence': 'NOT_PROVEN', 'construction_ready': False
}, indent=2), encoding='utf-8')
print('SYNTHETIC SNAPSHOT AND RESTORE PASS; native reopen is the next separate phase')
