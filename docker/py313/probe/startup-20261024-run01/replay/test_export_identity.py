"""Proposed filesystem contract tests; not acceptance of the product runtime."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from export_identity import PLACEHOLDERS, verify_export_identity


class ExportIdentityTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.startup_relative = Path('probe/startup')
        self.startup = self.root / 'devstack' / self.startup_relative
        self.platform = self.root / 'platform'
        self.startup.mkdir(parents=True)
        self.platform.mkdir()
        (self.startup / 'lock.txt').write_bytes(b'fixed-lock')
        (self.platform / 'setup.py').write_bytes(b'fixed-source')
        self.identity = {'trees': {
            'startup': {'lock.txt': {'sha256': hashlib.sha256(b'fixed-lock').hexdigest()}},
            'platform': {'setup.py': {'sha256': hashlib.sha256(b'fixed-source').hexdigest()}}}}
        self.write_identity()

    def write_identity(self):
        (self.root / 'export-identity.json').write_text(json.dumps(self.identity))

    def verify(self, **kwargs):
        return verify_export_identity(self.root, self.startup_relative, **kwargs)

    def test_unchanged_and_empty_placeholders(self):
        digest = self.verify()
        for name in PLACEHOLDERS:
            (self.startup / name).touch()
        self.assertEqual(self.verify(expected_sha256=digest, allow_placeholders=True), digest)

    def test_changed_and_missing_input(self):
        for path in (self.startup / 'lock.txt', self.platform / 'setup.py'):
            original = path.read_bytes()
            with self.subTest(path=path, action='changed'):
                path.write_bytes(b'changed')
                with self.assertRaises(ValueError):
                    self.verify()
            with self.subTest(path=path, action='missing'):
                path.unlink()
                with self.assertRaises(ValueError):
                    self.verify()
            path.write_bytes(original)

    def test_extra_file_rejected_before_contents_are_read(self):
        (self.platform / '.env').write_bytes(b'fixture-only')
        import export_identity
        original = export_identity.read_regular

        def guarded(path):
            self.assertNotEqual(Path(path).name, '.env')
            return original(path)

        with patch('export_identity.read_regular', side_effect=guarded):
            with self.assertRaises(ValueError):
                self.verify()

    def test_changed_manifest_rejected_even_if_tree_matches(self):
        digest = self.verify()
        self.write_identity()
        with (self.root / 'export-identity.json').open('a') as stream:
            stream.write('\n')
        with self.assertRaises(ValueError):
            self.verify(expected_sha256=digest)

    def test_literal_symlink_and_target_change(self):
        link = self.platform / 'dangling'
        link.symlink_to('absent-target')
        self.identity['trees']['platform']['dangling'] = {'link': 'absent-target'}
        self.write_identity()
        self.verify()
        link.unlink()
        link.symlink_to('different-target')
        with self.assertRaises(ValueError):
            self.verify()

    def test_parent_directory_symlink_is_rejected(self):
        empty = self.root / 'outside-fixture'
        empty.mkdir()
        self.platform.rename(self.root / 'saved-platform')
        self.platform.symlink_to(empty, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.verify()

    def test_placeholder_value_or_symlink_is_rejected(self):
        for name in PLACEHOLDERS:
            (self.startup / name).touch()
        target = self.startup / sorted(PLACEHOLDERS)[0]
        target.write_bytes(b'fixture-only')
        with self.assertRaises(ValueError):
            self.verify(allow_placeholders=True)
        target.unlink()
        target.symlink_to('lock.txt')
        with self.assertRaises(ValueError):
            self.verify(allow_placeholders=True)

    def test_parent_path_in_manifest_is_rejected(self):
        self.identity['trees']['platform']['../escape'] = {'link': 'literal-only'}
        self.write_identity()
        with self.assertRaises(ValueError):
            self.verify()

    def test_duplicate_json_keys_at_each_identity_level(self):
        raw = (self.root / 'export-identity.json').read_text()
        cases = [
            '{"trees": {}, ' + raw[1:],
            raw.replace('"startup":', '"startup": {}, "startup":', 1),
            raw.replace('"lock.txt":', '"lock.txt": {}, "lock.txt":', 1),
            raw.replace('"sha256":', '"sha256": "discarded", "sha256":', 1),
        ]
        for value in cases:
            with self.subTest(value=value):
                (self.root / 'export-identity.json').write_text(value)
                with self.assertRaisesRegex(ValueError, 'Duplicate export identity key'):
                    self.verify()

    def test_invalid_manifest_shapes(self):
        cases = [None, [], {}, {'trees': None}, {'trees': []},
                 {'trees': {}}, {'trees': {'startup': {}, 'platform': {}, 'extra': {}}},
                 {'trees': {'startup': {}, 'platform': []}},
                 {'trees': {'startup': {}, 'platform': {'bad': None}}},
                 {'trees': {'startup': {}, 'platform': {'bad': {'sha256': 'invalid'}}}},
                 {'trees': {'startup': {}, 'platform': {'bad': {'link': 3}}}},
                 {'trees': {'startup': {}, 'platform': {'bad': {'link': 'x', 'extra': 1}}}}]
        for value in cases:
            with self.subTest(value=value):
                self.identity = value
                self.write_identity()
                with self.assertRaises(ValueError):
                    self.verify()

    def test_both_schemas_validated_before_tree_reads(self):
        import export_identity
        original = export_identity.read_regular
        self.identity['trees']['platform']['bad'] = {'sha256': 'invalid'}
        self.write_identity()
        reads = []

        def guarded(path):
            self.assertEqual(Path(path), self.root / 'export-identity.json')
            reads.append(Path(path))
            return original(path)

        with patch('export_identity.read_regular', side_effect=guarded):
            with self.assertRaisesRegex(ValueError, 'Invalid file identity'):
                self.verify()
        self.assertEqual(reads, [self.root / 'export-identity.json'])

    def test_missing_host_placeholder_is_rejected_without_opening_it(self):
        import export_identity
        original = export_identity.read_regular
        for missing in sorted(PLACEHOLDERS):
            for name in PLACEHOLDERS:
                path = self.startup / name
                if path.exists():
                    path.unlink()
                if name != missing:
                    path.touch()

            def guarded(path):
                self.assertNotIn(Path(path).name, PLACEHOLDERS)
                return original(path)

            with self.subTest(missing=missing):
                with patch('export_identity.read_regular', side_effect=guarded):
                    with self.assertRaises(FileNotFoundError):
                        self.verify(allow_placeholders=True)

    def test_malformed_json_is_rejected(self):
        for value in ('', '{', '{"trees":'):
            with self.subTest(value=value):
                (self.root / 'export-identity.json').write_text(value)
                with self.assertRaises(ValueError):
                    self.verify()


    def test_equal_duplicate_keys_are_rejected(self):
        raw = (self.root / 'export-identity.json').read_text()
        raw = raw.replace('"sha256":', '"sha256": "discarded", "sha256":', 1)
        value = self.identity['trees']['startup']['lock.txt']['sha256']
        raw = raw.replace('"discarded"', json.dumps(value), 1)
        (self.root / 'export-identity.json').write_text(raw)
        with self.assertRaisesRegex(ValueError, 'Duplicate export identity key'):
            self.verify()

    def test_noncanonical_and_protected_manifest_paths_are_rejected(self):
        for name in ('/absolute', './relative', 'double//slash', 'trailing/', '..', '.',
                     'nested/../escape', '.env', 'nested/jwt-private.pem', '.acceptance-credentials.json'):
            with self.subTest(name=name):
                self.identity['trees']['platform'][name] = {'link': 'fixture-target'}
                self.write_identity()
                with self.assertRaises(ValueError):
                    self.verify()
                del self.identity['trees']['platform'][name]

    def test_manifest_symlink_is_rejected(self):
        manifest = self.root / 'export-identity.json'
        saved = self.root / 'saved-identity.json'
        manifest.rename(saved)
        manifest.symlink_to(saved.name)
        with self.assertRaisesRegex(ValueError, 'Expected regular file'):
            self.verify()

    def test_file_replaced_with_symlink_is_rejected_without_following_target(self):
        target = self.platform / 'setup.py'
        target.unlink()
        target.symlink_to('/fixture-does-not-exist')
        with self.assertRaisesRegex(ValueError, 'Export file identities differ'):
            self.verify()

    def test_fifo_is_rejected_without_opening_it(self):
        fifo = self.platform / 'fifo'
        os.mkfifo(fifo)
        with self.assertRaisesRegex(ValueError, 'Unsupported exported file type'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
