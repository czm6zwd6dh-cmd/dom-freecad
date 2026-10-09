#!/usr/bin/env python3
"""Defensive public-file checks, not a substitute for human privacy review."""
from pathlib import Path
import re
import subprocess

root = Path(__file__).resolve().parents[1]
tracked = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z']).split(b'\0')
allowed = {'.py', '.md', '.json', '.svg', '.yml', '.yaml', '.txt', '.sh', '.FCMacro'}
special = {'.gitignore'}
blocked_parts = {'private', 'projects', 'scans', 'secrets', 'r1'}
blocked_patterns = [
    re.compile(r'gh[pousr]_[a-zA-Z0-9]{30,}'),
    re.compile(r'github_pat_[a-zA-Z0-9_]{40,}'),
    re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----'),
]
for raw in tracked:
    if not raw:
        continue
    relative = Path(raw.decode('utf-8'))
    if relative.is_absolute() or '..' in relative.parts:
        raise SystemExit(f'Unsafe file path: {relative}')
    if any(part.lower() in blocked_parts for part in relative.parts):
        raise SystemExit(f'Potential private project path: {relative}')
    if relative.suffix not in allowed and relative.name not in special:
        raise SystemExit(f'Unreviewed or binary file in public repository: {relative}')
    target = root / relative
    if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root):
        raise SystemExit(f'Symlink or unsafe source file: {relative}')
    data = target.read_bytes()
    if len(data) > 1_000_000 or b'\x00' in data:
        raise SystemExit(f'Unreviewed large or binary file: {relative}')
    content = data.decode('utf-8')
    if any(pattern.search(content) for pattern in blocked_patterns):
        raise SystemExit(f'Potential credential in public file: {relative}')
print(f'PUBLIC SOURCE GUARD PASS: {len(tracked) - 1} tracked source files checked')
print('This heuristic runs AFTER a push: review all intended public changes before publishing.')
