#!/usr/bin/env python3
"""Explicit closed-release byte snapshots; no native CAD repair or model edits."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil

RESERVED = {'snapshot.json', 'RESTORED.json'}


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''): h.update(chunk)
    return h.hexdigest()


def names(values):
    if not isinstance(values, list) or not values or any(
        not isinstance(n, str) or not n or n in {'.', '..'} | RESERVED or
        '/' in n or '\\' in n or '\x00' in n for n in values):
        raise ValueError('nonempty list of plain filenames required; reserved names forbidden')
    if len(set(values)) != len(values): raise ValueError('duplicate filenames')
    return values


def regular(root, name):
    p = root / name
    if p.is_symlink() or not p.is_file(): raise ValueError('missing file or symlink: ' + name)
    return p


def write_json(path, data):
    with path.open('x') as f:
        json.dump(data, f, indent=2, ensure_ascii=False); f.write('\n')
        f.flush(); os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def copy_checked(source, target, expected):
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst)
        dst.flush(); os.fsync(dst.fileno())
    if sha(target) != expected or sha(source) != expected:
        raise ValueError('bytes changed during copy: ' + source.name)


def snapshot(source, destination, files):
    source, destination = Path(source), Path(destination)
    files = names(files)
    if not source.is_dir(): raise ValueError('source directory required')
    records = [{'name': n, 'sha256': sha(regular(source, n))} for n in files]
    destination.mkdir(mode=0o700)  # Exclusive; never reuse or overwrite an earlier release.
    for item in records:
        copy_checked(regular(source, item['name']), destination/item['name'], item['sha256'])
    # Check all source bytes again before publishing the completion manifest.
    if any(sha(regular(source, x['name'])) != x['sha256'] for x in records):
        raise ValueError('source changed before completion')
    result = {'schema': 1, 'scope': 'BYTE_SNAPSHOT_ONLY', 'files': records,
              'native_reopen': 'NOT_RUN', 'construction_ready': False}
    write_json(destination/'snapshot.json', result)
    return result


def verify(folder):
    folder = Path(folder)
    data = json.loads(regular(folder, 'snapshot.json').read_text())
    if not isinstance(data, dict) or set(data) != {'schema','scope','files','native_reopen','construction_ready'}:
        raise ValueError('invalid snapshot manifest')
    if type(data['schema']) is not int or data['schema'] != 1 or data['scope'] != 'BYTE_SNAPSHOT_ONLY' or data['native_reopen'] != 'NOT_RUN' or data['construction_ready'] is not False:
        raise ValueError('invalid snapshot qualification')
    records = data['files']
    if not isinstance(records, list) or any(not isinstance(x, dict) or set(x) != {'name','sha256'} for x in records):
        raise ValueError('invalid file records')
    names([x['name'] for x in records])
    for item in records:
        if not isinstance(item['sha256'], str) or not re.fullmatch('[0-9a-f]{64}', item['sha256']):
            raise ValueError('invalid SHA256')
        if sha(regular(folder, item['name'])) != item['sha256']: raise ValueError('corrupt snapshot: '+item['name'])
    if set(p.name for p in folder.iterdir()) != {x['name'] for x in records} | {'snapshot.json'}:
        raise ValueError('unexpected snapshot entries')
    return data


def restore(folder, destination):
    folder, destination = Path(folder), Path(destination)
    data = verify(folder)  # Reject corrupt/incomplete snapshot before creating output.
    destination.mkdir(mode=0o700)
    for item in data['files']:
        copy_checked(regular(folder, item['name']), destination/item['name'], item['sha256'])
    verify(folder)
    result = {'scope':'RESTORED_BYTES_ONLY', 'files':data['files'], 'native_reopen':'NOT_RUN'}
    write_json(destination/'RESTORED.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    a = sub.add_parser('snapshot'); a.add_argument('source'); a.add_argument('destination'); a.add_argument('files', nargs='+')
    a = sub.add_parser('verify'); a.add_argument('folder')
    a = sub.add_parser('restore'); a.add_argument('folder'); a.add_argument('destination')
    args = parser.parse_args()
    try:
        if args.action == 'snapshot': result = snapshot(args.source, args.destination, args.files)
        elif args.action == 'verify': result = verify(args.folder)
        else: result = restore(args.folder, args.destination)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'status':'REJECTED','reason':str(exc),'native_reopen':'NOT_RUN'})); return 2
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0


if __name__ == '__main__': raise SystemExit(main())
