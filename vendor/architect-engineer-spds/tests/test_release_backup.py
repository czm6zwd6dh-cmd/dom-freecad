import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import release_backup as rb


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.src = self.root/'source'; self.src.mkdir()
        (self.src/'model.FCStd').write_bytes(b'SYNTHETIC not CAD\x00')
        (self.src/'sheet.pdf').write_bytes(b'SYNTHETIC not PDF')
        self.backup = self.root/'backup'; self.dest = self.root/'restored'
        self.files = ['model.FCStd', 'sheet.pdf']

    def tearDown(self): self.tmp.cleanup()

    def make(self): return rb.snapshot(self.src, self.backup, self.files)

    def test_roundtrip(self):
        self.make(); rb.verify(self.backup); rb.restore(self.backup, self.dest)
        for n in self.files: self.assertEqual((self.src/n).read_bytes(), (self.dest/n).read_bytes())
        self.assertEqual(json.loads((self.dest/'RESTORED.json').read_text())['native_reopen'], 'NOT_RUN')

    def test_never_overwrite(self):
        self.make()
        with self.assertRaises(FileExistsError): self.make()
        self.dest.mkdir(); (self.dest/'keep').write_text('KEEP')
        with self.assertRaises(FileExistsError): rb.restore(self.backup, self.dest)
        self.assertEqual((self.dest/'keep').read_text(), 'KEEP')

    def test_corruption_rejected_before_output(self):
        self.make(); (self.backup/'model.FCStd').write_bytes(b'CORRUPT')
        with self.assertRaises(ValueError): rb.restore(self.backup, self.dest)
        self.assertFalse(self.dest.exists())

    def test_incomplete_rejected(self):
        self.backup.mkdir()
        with self.assertRaises(ValueError): rb.restore(self.backup, self.dest)
        self.assertFalse(self.dest.exists())

    def test_invalid_names(self):
        for ns in [[], ['../outside'], ['/absolute'], ['a/b'], ['a\\b'], ['snapshot.json'], ['RESTORED.json'], ['x','x'], [None]]:
            with self.subTest(ns=ns), self.assertRaises(ValueError): rb.snapshot(self.src,self.backup,ns)
        self.assertFalse(self.backup.exists())

    def test_symlink_rejected(self):
        (self.src/'link').symlink_to(self.src/'model.FCStd')
        with self.assertRaises(ValueError): rb.snapshot(self.src,self.backup,['link'])

    def test_extra_files_rejected(self):
        self.make(); (self.backup/'extra').write_text('extra')
        with self.assertRaises(ValueError): rb.verify(self.backup)

    def test_interrupted_copy_no_completion(self):
        with patch.object(rb, 'copy_checked', side_effect=OSError('synthetic interruption')):
            with self.assertRaises(OSError): self.make()
        self.assertTrue(self.backup.is_dir()); self.assertFalse((self.backup/'snapshot.json').exists())
        with self.assertRaises(ValueError): rb.verify(self.backup)

    def test_source_mutation_prevents_completion(self):
        original = rb.copy_checked
        def changing(source, target, expected):
            original(source,target,expected); source.write_bytes(b'changed')
        with patch.object(rb, 'copy_checked', side_effect=changing):
            with self.assertRaises(ValueError): self.make()
        self.assertFalse((self.backup/'snapshot.json').exists())

    def test_manifest_traversal_rejected(self):
        self.make(); p=self.backup/'snapshot.json'; d=json.loads(p.read_text())
        d['files'][0]['name']='../outside'; p.write_text(json.dumps(d))
        with self.assertRaises(ValueError): rb.restore(self.backup,self.dest)
        self.assertFalse(self.dest.exists())


if __name__ == '__main__': unittest.main()
