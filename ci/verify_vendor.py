#!/usr/bin/env python3
"""Reject accidental edits to the reviewed v0.13.0 remote execution subset."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def verify(folder):
    folder = Path(folder)
    spec = json.loads((folder / 'ORIGIN.json').read_text(encoding='utf-8'))
    if spec.get('upstream_version') != '0.13.0' or spec.get('skill') != 'architect-engineer-spds':
        raise ValueError('Unexpected skill version')
    records = spec.get('files')
    if not isinstance(records, dict) or not records:
        raise ValueError('Missing source hash allowlist')
    for name, digest in records.items():
        path = Path(name)
        if path.is_absolute() or '..' in path.parts or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('Invalid vendor manifest entry')
        file = folder / path
        if file.is_symlink() or not file.is_file():
            raise ValueError('Missing or unsafe vendor file')
        if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
            raise ValueError('Vendor source checksum mismatch: ' + name)
    actual = {str(p.relative_to(folder)) for p in folder.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts}
    if actual != set(records) | {'ORIGIN.json'}:
        raise ValueError('Unexpected vendor files')
    return spec


if __name__ == '__main__':
    spec = verify(ROOT / 'vendor/architect-engineer-spds')
    print('VENDOR HASH PASS:', spec['upstream_version'], len(spec['files']), 'reviewed source files')
