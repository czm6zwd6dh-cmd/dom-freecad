#!/usr/bin/env python3
"""Check the initial synthetic wall export; extended phases are checked separately."""
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
from check_extended import pdf_measurements, require

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'build/smoke')
report = json.loads((root / 'report.json').read_text(encoding='utf-8'))
require(report['status'] == 'PASS' and report['version'] == '1.1.4', 'Native build failed')
require(report['source'] == 'SYNTHETIC_ONLY' and report['construction_ready'] is False, 'Unexpected classification')
expected = 4000 * 300 * 3000 - 1000 * 300 * 1200
require(math.isclose(float(report['wall_net_volume_mm3']), expected, rel_tol=0, abs_tol=0.01), 'Incorrect volume')
for name in ('synthetic-wall.FCStd', 'synthetic-wall.step', 'synthetic-page.pdf', 'synthetic-page.svg'):
    require((root / name).is_file() and (root / name).stat().st_size > 100, 'Missing or empty ' + name)
require(ET.parse(root / 'synthetic-page.svg').getroot().tag.endswith('svg'), 'Invalid SVG')
result = pdf_measurements(root / 'synthetic-page.pdf', 1000)
(root / 'initial-pdf-check.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print('SYNTHETIC CAD PASS: solid/cut volume, FCStd, STEP, A3 PDF and bounded vector scales')
print('Visual review, linked dimensions, sections, DXF and full SPDS remain separate checks.')
