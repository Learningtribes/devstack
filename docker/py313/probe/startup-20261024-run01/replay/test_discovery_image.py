"""Preflight presence check for the optional discovery image; no Docker daemon access.

Discovery has no published py3.13 release, so a missing tag can only be fixed by a local build.
The check exists so that failure names the command instead of surfacing a bare `manifest unknown`
from `docker run` five stages into the bring-up.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import core
from core import ensure_discovery_image
from test_core import example

TAG = 'ltdps/discovery:py313-local'
DIGEST_REFERENCE = 'ltdps/discovery@sha256:' + '4' * 64


class DiscoveryImageTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.config = example(self.root)
        self.config['discovery_repo'] = str(self.root / 'discovery')
        self.config['discovery_image'] = TAG
        for key, content in [('credentials_file', '{}'), ('jwt_file', 'fixture')]:
            Path(self.config[key]).write_text(content)
            Path(self.config[key]).chmod(0o600)
        Path(self.config['secret_env']).write_text(
            ''.join(key + '=' + '1' * 48 + '\n' for key in core.SECRET_KEYS))
        Path(self.config['secret_env']).chmod(0o600)

    def image(self):
        return {'Id': 'sha256:' + 'a' * 64, 'Os': 'linux', 'Architecture': 'arm64',
                'RepoDigests': [DIGEST_REFERENCE]}

    def test_a_run_without_discovery_never_touches_docker(self):
        del self.config['discovery_repo']
        with patch('core.subprocess.run') as run:
            self.assertIsNone(ensure_discovery_image(self.config))
        run.assert_not_called()

    def test_a_present_tag_is_used_without_pulling(self):
        inspected = subprocess.CompletedProcess([], 0, json.dumps(self.image()), '')
        with patch('core.subprocess.run', return_value=inspected) as run:
            record = ensure_discovery_image(self.config, sleep=lambda delay: None)
        self.assertEqual(record['reference'], TAG)
        self.assertEqual(record['platform'], 'linux/arm64')
        # Only the inspect ran: a tag is never pulled, because no py3.13 release exists.
        self.assertEqual([call.args[0][1] for call in run.call_args_list], ['image'])

    def test_a_missing_tag_names_the_build_command(self):
        missing = subprocess.CompletedProcess([], 1, '', 'No such image')
        with patch('core.subprocess.run', return_value=missing) as run:
            with self.assertRaisesRegex(ValueError, 'not present locally') as error:
                ensure_discovery_image(self.config, sleep=lambda delay: None)
        self.assertIn('make build-discovery', str(error.exception))
        self.assertIn(self.config['discovery_repo'], str(error.exception))
        # A tag is not pulled: the registry has nothing to offer for it.
        self.assertEqual([call.args[0][1] for call in run.call_args_list], ['image'])

    def test_a_missing_digest_is_pulled(self):
        missing = subprocess.CompletedProcess([], 1, '', 'No such image')
        ok = subprocess.CompletedProcess([], 0, '', '')
        present = subprocess.CompletedProcess([], 0, json.dumps(self.image()), '')
        self.config['discovery_image'] = DIGEST_REFERENCE
        with patch('core.subprocess.run', side_effect=[missing, ok, present]) as run:
            record = ensure_discovery_image(self.config, sleep=lambda delay: None)
        self.assertEqual(record['reference'], DIGEST_REFERENCE)
        pulls = [call.args[0] for call in run.call_args_list if call.args[0][1] == 'pull']
        self.assertEqual(pulls, [['docker', 'pull', '--quiet', DIGEST_REFERENCE]])

    def test_a_digest_that_never_pulls_fails_with_the_retry_count(self):
        missing = subprocess.CompletedProcess([], 1, '', 'timeout')
        self.config['discovery_image'] = DIGEST_REFERENCE
        delays = []
        with patch('core.subprocess.run', return_value=missing):
            with self.assertRaisesRegex(ValueError, 'not present locally'):
                ensure_discovery_image(self.config, sleep=delays.append)
        self.assertEqual(delays, list(core.RUNTIME_PULL_BACKOFF))

    def test_preflight_reports_the_discovery_image_only_when_present(self):
        record = {'reference': TAG, 'image_id': 'sha256:' + 'a' * 64, 'platform': 'linux/arm64'}
        with (patch('core.source_repository_roots', return_value={}), patch('core.validate_path_isolation'),
              patch('core.check_conflicts'), patch('core.inventory'), patch('core.docker_network_subnets',
              return_value=[]), patch('core.validate_network_subnet', return_value='10.254.44.0/24'),
              patch('core.socket.socket'), patch('core.subprocess.check_output', return_value='a' * 40),
              patch('core.subprocess.run'), patch('core.ensure_runtime_image', return_value=None),
              patch('core.ensure_discovery_image', return_value=record), patch('core.check_platform_layout')):
            self.config['platform_commit'] = self.config['devstack_commit'] = 'a' * 40
            report = core.fresh_preflight(self.config, before_prepare=False)
        self.assertEqual(report['discovery_image'], record)
        self.assertNotIn('runtime_image', report)
