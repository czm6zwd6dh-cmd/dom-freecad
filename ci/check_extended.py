#!/usr/bin/env python3
"""Independent byte/report/vector checks for this bounded synthetic CAD fixture."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import fitz

PT_TO_MM = 25.4 / 72
PAPER_TOLERANCE_MM = 0.2  # internal drawing-control tolerance, not a survey tolerance
PHASES = ('build', 'cold-reopen', 'mutate', 'native-tools', 'restore-reopen')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pdf_measurements(path, opening_width_mm):
    with fitz.open(path) as document:
        require(len(document) == 1, 'Expected exactly one A3 page')
        page = document[0]
        require(abs(page.rect.width * PT_TO_MM - 420) <= PAPER_TOLERANCE_MM and
                abs(page.rect.height * PT_TO_MM - 297) <= PAPER_TOLERANCE_MM, 'Wrong paper size')
        rectangles = []
        for drawing in page.get_drawings():
            items = drawing['items']
            if len(items) == 1 and items[0][0] == 're':
                pass  # MuPDF may canonicalize a closed four-edge path to a rectangle.
            elif len(items) == 1 and items[0][0] == 'qu':
                points = {(round(p.x, 2), round(p.y, 2)) for p in items[0][1]}
                xs, ys = {p[0] for p in points}, {p[1] for p in points}
                if len(xs) != 2 or len(ys) != 2 or points != {(x, y) for x in xs for y in ys}:
                    continue
            elif len(items) == 4 and all(item[0] == 'l' for item in items):
                if not all(abs(item[1].x - item[2].x) < 0.02 or abs(item[1].y - item[2].y) < 0.02 for item in items):
                    continue
                vertices = [(round(item[k].x, 2), round(item[k].y, 2)) for item in items for k in (1, 2)]
                if len(set(vertices)) != 4 or any(vertices.count(v) != 2 for v in set(vertices)):
                    continue
            else:
                continue
            r = drawing['rect']
            rectangles.append([r.x0 * PT_TO_MM, r.y0 * PT_TO_MM, r.width * PT_TO_MM, r.height * PT_TO_MM])
        expected = {'elevation': [70, 79, 200, 150],
                    'window': [145, 124, opening_width_mm / 20, 60],
                    'top': [312, 74, 80, 6]}
        measured = {}
        for name, target in expected.items():
            matches = [r for r in rectangles if all(abs(a - b) <= PAPER_TOLERANCE_MM for a, b in zip(r, target))]
            require(len(matches) == 1, 'Missing, duplicated, or incorrectly scaled vector rectangle: ' + name)
            measured[name] = matches[0]
        page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).save(str(Path(path).with_name('preview.png')))
        return {'paper_mm': [page.rect.width * PT_TO_MM, page.rect.height * PT_TO_MM],
                'rectangles_mm': measured, 'paper_tolerance_mm': PAPER_TOLERANCE_MM,
                'text_is_searchable': bool(page.get_text().strip()),
                'font_and_cyrillic_appearance': 'REQUIRES_VISUAL_REVIEW'}


def check(root, expected_sha):
    root = Path(root)
    require(re.fullmatch('[0-9a-f]{40}', expected_sha) is not None, 'Full reviewed commit required')
    reports = {}
    for phase in PHASES:
        name = 'report.json' if phase == 'build' else phase + '.json'
        report = json.loads((root / name).read_text(encoding='utf-8'))
        require(report.get('status') == 'PASS' and report.get('source') == 'SYNTHETIC_ONLY', 'Failed native phase')
        require(report.get('phase') == phase and report.get('head_sha') == expected_sha, 'Mixed phase/commit evidence')
        require(report.get('version') == '1.1.4' and report.get('construction_ready') is False, 'Invalid qualification')
        require(type(report.get('pid')) is int and report['pid'] > 0, 'Missing native PID')
        require(re.fullmatch('[0-9a-f]{32}', report.get('invocation_id', '')) is not None, 'Missing invocation ID')
        reports[phase] = report
    require(len({r['pid'] for r in reports.values()}) == len(PHASES), 'Separate native processes not established')
    require(len({r['invocation_id'] for r in reports.values()}) == len(PHASES), 'Repeated invocation evidence')
    baseline = sha(root / 'synthetic-wall.FCStd')
    require(reports['build']['model_sha256'] == baseline, 'Original model changed after build')
    for phase in ('cold-reopen', 'mutate', 'restore-reopen'):
        require(reports[phase]['source_model_sha256'] == baseline and reports[phase]['source_unchanged'] is True,
                'Baseline not preserved during ' + phase)
    for phase, width in [('build', 1000), ('cold-reopen', 1000), ('mutate', 1200), ('restore-reopen', 1000)]:
        expected_volume = 4000 * 300 * 3000 - width * 300 * 1200
        require(math.isclose(reports[phase]['wall_net_volume_mm3'], expected_volume, rel_tol=0, abs_tol=0.01),
                'Incorrect native volume in ' + phase)
    require(sha(root / 'restored/synthetic-wall.FCStd') == baseline, 'Restored model differs')
    require(sha(root / 'mutated/synthetic-wall.FCStd') == reports['mutate']['mutated_model_sha256'], 'Mutation bytes differ')
    tools = reports['native-tools']
    require(tools['upstream_version'] == '0.13.0' and tools['empty_void_probe']['passed'] is True,
            'Skill native positive control failed')
    require(tools['deliberate_obstruction_rejected']['passed'] is False, 'Skill negative control failed')
    require(any(f['code'] == 'REQUIRED_VOID_OCCUPIED' for f in tools['deliberate_obstruction_rejected']['findings']),
            'Wrong negative-control finding')
    backup = json.loads((root / 'backup-verification.json').read_text(encoding='utf-8'))
    require(backup['status'] == 'PASS' and backup['construction_ready'] is False, 'Backup verification failed')
    for item in backup['files']:
        name = item['name']
        require(Path(name).name == name and name not in {'.', '..'}, 'Unsafe snapshot file')
        for parent in (root, root / 'backup', root / 'restored'):
            require(sha(parent / name) == item['sha256'], 'Snapshot/restore byte mismatch')
    pages = {}
    for folder, width in [('.', 1000), ('cold', 1000), ('mutated', 1200), ('restored-proof', 1000)]:
        pdf = root / folder / 'synthetic-page.pdf'
        svg = root / folder / 'synthetic-page.svg'
        require(ET.parse(svg).getroot().tag.endswith('svg'), 'Invalid SVG')
        pages[folder] = pdf_measurements(pdf, width)
    return {'status': 'PASS', 'scope': 'SYNTHETIC_NATIVE_CAD_SETUP', 'head_sha': expected_sha,
            'skill_cloud_subset': '0.13.0', 'native_process_count': len(PHASES),
            'original_sha256': baseline, 'pages': pages,
            'native_cold_reopen': 'PASS', 'disposable_parameter_change': 'PASS',
            'snapshot_restore_and_native_reopen': 'PASS', 'visual_review': 'NOT_AUTOMATED',
            'full_host_skill_on_runner': False, 'DXF': 'NOT_TESTED',
            'linked_dimensions_and_sections': 'NOT_TESTED', 'SPDS': 'NOT_QUALIFIED',
            'private_project_route': 'NOT_CONFIGURED', 'construction_ready': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--expected-sha', required=True)
    args = parser.parse_args()
    result = check(args.directory, args.expected_sha)
    (args.directory / 'qualification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
