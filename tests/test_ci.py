import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'ci'))
from run_native import validate_report
from verify_vendor import verify
from check_extended import pdf_measurements


class InvocationTests(unittest.TestCase):
    def setUp(self):
        self.report = dict(status='PASS', source='SYNTHETIC_ONLY', phase='build',
                           invocation_id='a' * 32, head_sha='b' * 40,
                           version='1.1.4', construction_ready=False, pid=123)

    def call(self, report):
        return validate_report(report, 'build', 'a' * 32, 'b' * 40)

    def test_valid(self):
        self.call(self.report)

    def test_failure_and_scope(self):
        for key, value in [('status', 'FAILED'), ('source', 'REAL'), ('construction_ready', True)]:
            bad = dict(self.report, **{key: value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.call(bad)

    def test_stale_phase_and_invocation(self):
        for key, value in [('phase', 'mutate'), ('invocation_id', 'old')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.call(dict(self.report, **{key: value}))

    def test_version_and_commit(self):
        for key, value in [('version', '0.21'), ('head_sha', 'c' * 40)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.call(dict(self.report, **{key: value}))

    def test_pid_required(self):
        for value in (None, 0, True, '123'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.call(dict(self.report, pid=value))


class VendorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'vendor'
        shutil.copytree(ROOT / 'vendor/architect-engineer-spds', self.folder,
                        ignore=shutil.ignore_patterns('__pycache__'))

    def test_current_subset(self):
        self.assertEqual(verify(self.folder)['upstream_version'], '0.13.0')

    def test_changed_source_rejected(self):
        with (self.folder / 'scripts/native_audit.py').open('a') as stream:
            stream.write('\n# changed\n')
        with self.assertRaises(ValueError):
            verify(self.folder)

    def test_extra_file_rejected(self):
        (self.folder / 'extra.txt').write_text('not allowlisted')
        with self.assertRaises(ValueError):
            verify(self.folder)

    def test_symlink_rejected(self):
        path = self.folder / 'scripts/native_audit.py'
        content = path.read_bytes()
        other = Path(self.temp.name) / 'other.py'
        other.write_bytes(content)
        path.unlink()
        path.symlink_to(other)
        with self.assertRaises(ValueError):
            verify(self.folder)


class VectorCheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.pdf = Path(self.temp.name) / 'test.pdf'

    def create(self, width=50, paper_width=420, missing=False, offset=0, separate=False, lost_edge=False, duplicate=False):
        scale = 72 / 25.4
        doc = fitz.open()
        page = doc.new_page(width=paper_width * scale, height=297 * scale)
        targets = [(70, 79, 200, 150), (312, 74, 80, 6)]
        if not missing:
            targets.append((145 + offset, 124, width, 60))
        for x, y, w, h in targets:
            points = [(x, y), (x+w, y), (x+w, y+h), (x, y+h), (x, y)]
            shape = page.new_shape()
            for index, (a, b) in enumerate(zip(points, points[1:])):
                if lost_edge and x == 145 + offset and index == 2:
                    continue
                shape.draw_line(fitz.Point(a[0]*scale, a[1]*scale), fitz.Point(b[0]*scale, b[1]*scale))
                if separate:
                    shape.finish(closePath=False)
                    shape.commit()
                    shape = page.new_shape()
            if not separate:
                shape.finish(closePath=False)
                shape.commit()
        if duplicate:
            page.draw_line(fitz.Point(145*scale, 124*scale), fitz.Point((145+width)*scale, 124*scale))
        doc.save(self.pdf)
        doc.close()

    def test_nominal_vectors(self):
        self.create()
        self.assertIn('window', pdf_measurements(self.pdf, 1000)['rectangles_mm'])

    def test_mutated_vectors(self):
        self.create(width=60)
        pdf_measurements(self.pdf, 1200)

    def test_wrong_scale_rejected(self):
        self.create(width=52)
        with self.assertRaises(ValueError):
            pdf_measurements(self.pdf, 1000)

    def test_missing_window_rejected(self):
        self.create(missing=True)
        with self.assertRaises(ValueError):
            pdf_measurements(self.pdf, 1000)

    def test_displaced_window_rejected(self):
        self.create(offset=2)
        with self.assertRaises(ValueError):
            pdf_measurements(self.pdf, 1000)

    def test_wrong_paper_rejected(self):
        self.create(paper_width=400)
        with self.assertRaises(ValueError):
            pdf_measurements(self.pdf, 1000)

    def test_separate_paths_supported(self):
        self.create(separate=True)
        pdf_measurements(self.pdf, 1000)

    def test_separate_mutated_paths_supported(self):
        self.create(width=60, separate=True)
        pdf_measurements(self.pdf, 1200)

    def test_stale_separate_mutation_rejected(self):
        self.create(width=50, separate=True)
        with self.assertRaises(ValueError):
            pdf_measurements(self.pdf, 1200)

    def test_missing_single_side_rejected(self):
        self.create(separate=True, lost_edge=True)
        with self.assertRaises(ValueError):
            pdf_measurements(self.pdf, 1000)

    def test_duplicate_side_rejected(self):
        self.create(separate=True, duplicate=True)
        with self.assertRaises(ValueError):
            pdf_measurements(self.pdf, 1000)


if __name__ == '__main__':
    unittest.main()
