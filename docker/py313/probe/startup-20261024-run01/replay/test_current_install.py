"""Offline staging/failure contracts; no Docker or application deployment."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from prepare_current_install import prepare, PLACEHOLDERS


class CurrentInstallTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.paths = {name: self.base / name for name in ('paired', 'startup', 'runtime', 'canary')}
        for path in self.paths.values():
            path.mkdir()
        self.lock = self.base / 'ci.lock'
        for name in PLACEHOLDERS:
            (self.paths['startup'] / name).write_text('protected-fixture')
        for name in ('image-inputs.py', 'install.py', 'verify-platform-identity.py',
                     'paver-tools.lock', 'test-tools.lock'):
            (self.paths['canary'] / name).touch()
        (self.paths['paired'] / 'internal-delivery.lock.txt').write_text('fixed')
        (self.paths['canary'] / 'companion_inputs.py').write_text(
            "def application_lock(startup):\n"
            "    if (startup / 'internal-delivery.lock.txt').read_text() != 'fixed':\n"
            "        raise ValueError('Unsupported paired application lock')\n")
        patcher = patch('prepare_current_install.subprocess.run')
        self.run = patcher.start()
        self.addCleanup(patcher.stop)

    def prepare(self):
        prepare(**self.paths, lock=self.lock)

    def test_current_contract_and_protected_mounts(self):
        def command(args, check):
            self.assertTrue(check)
            if args[-1] == str(self.paths['canary'] / 'image-inputs.py'):
                self.lock.write_text('joined-full-lock-fixture')
        self.run.side_effect = command
        self.prepare()
        self.assertEqual(len(self.run.call_args_list), 2)
        self.assertEqual(self.run.call_args_list[-1].args[0][-1], str(self.paths['canary'] / 'image-inputs.py'))
        for name in PLACEHOLDERS:
            self.assertEqual((self.paths['startup'] / name).read_text(), 'protected-fixture')
        self.assertEqual((self.paths['paired'] / 'internal-delivery.lock.txt').read_text(), 'fixed')

    def test_wrong_paired_lock_rejected_before_staging(self):
        (self.paths['paired'] / 'internal-delivery.lock.txt').write_text('wrong')
        with self.assertRaisesRegex(ValueError, 'Unsupported paired'):
            self.prepare()
        self.run.assert_not_called()

    def test_missing_current_contract_cannot_fall_back(self):
        (self.paths['canary'] / 'install.py').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing current Platform'):
            self.prepare()
        self.run.assert_not_called()

    def test_occupied_outputs_rejected(self):
        for path in (self.paths['runtime'] / 'prior', self.paths['startup'] / 'prior', self.lock):
            with self.subTest(path=path):
                path.touch()
                with self.assertRaises(ValueError):
                    self.prepare()
                self.run.assert_not_called()
                path.unlink()

    def test_subprocess_failure_propagates(self):
        self.run.side_effect = subprocess.CalledProcessError(42, ['fixture'])
        with self.assertRaises(subprocess.CalledProcessError) as error:
            self.prepare()
        self.assertEqual(error.exception.returncode, 42)
        self.assertEqual(self.run.call_count, 1)

    def test_missing_generated_lock_is_failure(self):
        with self.assertRaisesRegex(ValueError, 'did not produce'):
            self.prepare()


if __name__ == '__main__':
    unittest.main()
