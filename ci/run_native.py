#!/usr/bin/env python3
"""Run exactly one synthetic macro in a fresh, bounded FreeCAD GUI process."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import uuid

PHASES = ('build', 'cold-reopen', 'mutate', 'native-tools', 'restore-reopen')
ROOT = Path(__file__).resolve().parents[1]


def validate_report(report, phase, invocation, sha):
    if report.get('status') != 'PASS' or report.get('source') != 'SYNTHETIC_ONLY':
        raise ValueError('Native phase failed or returned unexpected data')
    if report.get('phase') != phase or report.get('invocation_id') != invocation:
        raise ValueError('Stale report from another invocation')
    if report.get('head_sha') != sha or report.get('version') != '1.1.4':
        raise ValueError('Wrong commit or FreeCAD version')
    if report.get('construction_ready') is not False:
        raise ValueError('Unexpected construction qualification')
    if type(report.get('pid')) is not int or report['pid'] <= 0:
        raise ValueError('Missing native process identity')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=PHASES)
    args = parser.parse_args()
    sha = os.environ.get('GITHUB_SHA', '')
    if not re.fullmatch('[0-9a-f]{40}', sha):
        raise ValueError('Full reviewed GITHUB_SHA is required')
    out = ROOT / 'build/smoke'
    out.mkdir(parents=True, exist_ok=True)
    target = out / ('report.json' if args.phase == 'build' else args.phase + '.json')
    if target.exists():
        raise FileExistsError('Never reuse a previous native phase report')
    invocation = uuid.uuid4().hex
    env = dict(os.environ, DOM_REPO_ROOT=str(ROOT), DOM_PHASE=args.phase,
               DOM_INVOCATION_ID=invocation, QT_QPA_PLATFORM='xcb', QT_OPENGL='software',
               LIBGL_ALWAYS_SOFTWARE='1')
    with tempfile.TemporaryDirectory(prefix='dom-freecad-', dir=os.environ.get('RUNNER_TEMP')) as cfg:
        command = ['xvfb-run', '-a', '-s', '-screen 0 1600x1200x24',
                   'timeout', '--signal=TERM', '--kill-after=10s', '240',
                   str(ROOT / '.runtime/freecad/squashfs-root/AppRun'),
                   '--user-cfg', str(Path(cfg) / 'user.cfg'),
                   '--system-cfg', str(Path(cfg) / 'system.cfg'), str(ROOT / 'ci/smoke.FCMacro')]
        with (out / ('freecad-' + args.phase + '.log')).open('xb') as log:
            subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                           timeout=280, check=True)
    report = json.loads(target.read_text(encoding='utf-8'))
    validate_report(report, args.phase, invocation, sha)
    print('NATIVE PHASE PASS:', args.phase, 'PID:', report['pid'], 'INVOCATION:', invocation)


if __name__ == '__main__':
    main()
