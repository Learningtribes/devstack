"""Exercise replay export gates with real temporary trees and mocked external effects."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import run as replay_run
from core import STARTUP_REL, config_hash
from export_identity import PLACEHOLDERS


class ReplayExportIdentityTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.export = self.root / 'export'
        self.evidence = self.root / 'evidence'
        self.startup = self.export / 'devstack' / STARTUP_REL
        self.platform = self.export / 'platform'
        self.startup.mkdir(parents=True)
        self.platform.mkdir()
        (self.startup / 'lock.txt').write_bytes(b'fixed-lock')
        (self.platform / 'source.py').write_bytes(b'fixed-source')
        self.config = {
            'evidence_dir': str(self.evidence), 'export_dir': str(self.export),
            'devstack_repo': str(self.root / 'devstack-repo'), 'devstack_commit': 'a' * 40,
            'platform_repo': str(self.root / 'platform-repo'), 'platform_commit': 'b' * 40,
            'theme_repo': str(self.root / 'theme-repo'), 'theme_commit': 'c' * 40, 'runtime_volume': 'fixture-runtime-data',
            'runtime_container': 'fixture-runtime', 'network': 'fixture-network',
            'network_subnet': '10.254.44.0/24', 'services': {},
            'images': {'runtime': 'sha256:' + 'd' * 64}, 'lms_port': 18240, 'cms_port': 18250,
            'secret_env': str(self.root / 'unused-fixture.env'),
            'credentials_file': str(self.root / 'unused-credentials.json'),
            'jwt_file': str(self.root / 'unused-private.pem'),
        }
        self.identity = {'repositories': {'devstack': {'commit': 'a' * 40},
                                         'platform': {'commit': 'b' * 40}}, 'trees': {}}
        for label, base in [('startup', self.startup), ('platform', self.platform)]:
            self.identity['trees'][label] = {
                p.relative_to(base).as_posix(): {'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in base.rglob('*') if p.is_file()}
        self.manifest = self.export / 'export-identity.json'
        self.manifest.write_text(json.dumps(self.identity))
        self.events = Mock()
        for name, kwargs in (
            ('capture', {}), ('ownership', {}), ('fresh_preflight', {'return_value': {}}),
            ('compose', {'return_value': {'fixture': True}}),
            ('docker_exec', {'return_value': ['mock-docker-exec']}),
            ('verify_export_identity', {'wraps': replay_run.verify_export_identity}),
        ):
            patcher = patch.object(replay_run, name, **kwargs)
            mock = patcher.start()
            self.addCleanup(patcher.stop)
            self.events.attach_mock(mock, name)
            setattr(self, name, mock)
        # Any unmocked subprocess is a test failure, never a Docker operation.
        patcher = patch.object(replay_run.subprocess, 'check_output', side_effect=AssertionError('external call'))
        self.external = patcher.start()
        self.addCleanup(patcher.stop)

    def prepare(self):
        replay_run.prepare(self.config)
        self.capture.reset_mock()
        self.fresh_preflight.reset_mock()
        self.events.reset_mock()

    def prepared(self):
        return json.loads((self.evidence / 'prepared.json').read_text())

    def save_prepared(self, value):
        (self.evidence / 'prepared.json').write_text(json.dumps(value))

    def assert_both_consumers_reject(self, exception):
        for action in (replay_run.create, replay_run.install):
            self.events.reset_mock()
            with self.subTest(action=action.__name__), self.assertRaises(exception):
                action(self.config)
            self.capture.assert_not_called()
            self.fresh_preflight.assert_not_called()
            if action is replay_run.install:
                self.ownership.assert_called_once_with(self.config)
                self.assertEqual(self.events.mock_calls[0][0], 'ownership')

    def test_prepare_requires_a_theme_checkout_before_creating_any_evidence(self):
        del self.config['theme_repo']
        with self.assertRaisesRegex(ValueError, '--theme-repo'):
            replay_run.prepare(self.config)
        self.assertFalse(self.evidence.exists())

    def test_prepare_pins_raw_manifest_before_creating_empty_placeholders(self):
        digest = hashlib.sha256(self.manifest.read_bytes()).hexdigest()
        replay_run.prepare(self.config)
        self.assertEqual(self.prepared(), {'configuration_sha256': config_hash(self.config),
                                           'export_identity_sha256': digest})
        self.verify_export_identity.assert_called_once_with(self.export, STARTUP_REL)
        for name in PLACEHOLDERS:
            self.assertEqual((self.startup / name).stat().st_size, 0)
        self.capture.assert_called_once()
        self.assertEqual(self.capture.call_args.args[1], 'export')

    def test_prepare_rejects_ambiguous_manifest_before_placeholders_or_prepared_record(self):
        raw = self.manifest.read_text()
        self.manifest.write_text('{"trees": {}, ' + raw[1:])
        with self.assertRaisesRegex(ValueError, 'Duplicate export identity key'):
            replay_run.prepare(self.config)
        self.assertFalse((self.evidence / 'prepared.json').exists())
        self.assertFalse(any((self.startup / name).exists() for name in PLACEHOLDERS))
        self.compose.assert_not_called()
        self.assertEqual([c.args[1] for c in self.capture.call_args_list], ['export'])

    def test_changed_input_rejected_before_any_consumer_capture(self):
        self.prepare()
        (self.platform / 'source.py').write_bytes(b'changed')
        self.assert_both_consumers_reject(ValueError)

    def test_changed_manifest_rejected_even_when_rehashed_to_match_changed_tree(self):
        self.prepare()
        (self.platform / 'source.py').write_bytes(b'changed')
        self.identity['trees']['platform']['source.py']['sha256'] = hashlib.sha256(b'changed').hexdigest()
        self.manifest.write_text(json.dumps(self.identity))
        self.assert_both_consumers_reject(ValueError)

    def test_old_or_malformed_prepared_record_cannot_bypass_pinned_digest(self):
        self.prepare()
        original = self.prepared()
        for value in (None, '', 'invalid', 'A' * 64, 3):
            with self.subTest(digest=value):
                self.save_prepared({**original, 'export_identity_sha256': value})
                self.assert_both_consumers_reject(ValueError)
        self.save_prepared({'configuration_sha256': original['configuration_sha256']})
        self.assert_both_consumers_reject(ValueError)
        for value in (None, [], {}):
            with self.subTest(prepared=value):
                self.save_prepared(value)
                self.assert_both_consumers_reject(ValueError)

    def test_configuration_mismatch_rejected(self):
        self.prepare()
        prepared = self.prepared()
        prepared['configuration_sha256'] = '0' * 64
        self.save_prepared(prepared)
        self.assert_both_consumers_reject(ValueError)

    def test_missing_placeholder_rejected_before_consumer_capture(self):
        self.prepare()
        (self.startup / sorted(PLACEHOLDERS)[0]).unlink()
        self.assert_both_consumers_reject(FileNotFoundError)

    def test_extra_protected_file_is_rejected_without_reading_its_contents(self):
        self.prepare()
        protected = self.platform / '.env'
        protected.touch()  # Empty fixture, never real configuration.
        self.assert_both_consumers_reject(ValueError)

    def test_create_checks_export_before_readiness_and_resource_mutations(self):
        self.prepare()
        self.external.side_effect = None
        self.external.return_value = json.dumps({'py313.replay.config': config_hash(self.config)})
        replay_run.create(self.config)
        self.verify_export_identity.assert_called_once_with(
            self.export, STARTUP_REL, expected_sha256=self.prepared()['export_identity_sha256'],
            allow_placeholders=True)
        self.assertEqual([c[0] for c in self.events.mock_calls[:2]], ['verify_export_identity', 'fresh_preflight'])
        self.assertEqual([c.args[1] for c in self.capture.call_args_list],
                         ['create-volume-runtime', 'create-network', 'create-infra', 'create-runtime'])

    def create_runtime_mounts(self):
        self.prepare()
        self.external.side_effect = None
        self.external.return_value = json.dumps({'py313.replay.config': config_hash(self.config)})
        replay_run.create(self.config)
        command = self.capture.call_args_list[-1].args[2]
        return [command[i + 1] for i, value in enumerate(command) if value == '--mount']

    def test_snapshot_run_never_mounts_the_platform_checkout(self):
        mounts = self.create_runtime_mounts()
        self.assertFalse(any('dst=/workspace/platform' in mount for mount in mounts))

    def test_runtime_volume_is_the_application_root_and_runtime_is_not_mounted(self):
        mounts = self.create_runtime_mounts()
        self.assertIn('type=volume,src=fixture-runtime-data,dst=/edx/app/edxapp', mounts)
        self.assertFalse(any('dst=/runtime' in mount for mount in mounts))

    def test_live_run_mounts_the_platform_checkout_read_write_outside_runtime(self):
        self.config['platform_mount'] = 'live'
        mounts = self.create_runtime_mounts()
        live = [mount for mount in mounts if 'dst=/workspace/platform' in mount]
        self.assertEqual(live, ['type=bind,src=%s,dst=/workspace/platform' % self.config['platform_repo']])
        self.assertTrue(any('dst=/input/platform,readonly' in mount for mount in mounts))

    def test_theme_repo_is_mounted_read_write_as_theme_hawthorn(self):
        self.config['theme_repo'] = '/Users/example/triboo-theme'
        mounts = self.create_runtime_mounts()
        theme = [mount for mount in mounts if '/workspace/themes' in mount]
        self.assertEqual(theme, ['type=bind,src=/Users/example/triboo-theme,dst=/workspace/themes/hawthorn'])

    def test_infra_project_is_named_per_run_so_runs_never_share_services(self):
        self.prepare()
        self.external.side_effect = None
        self.external.return_value = json.dumps({'py313.replay.config': config_hash(self.config)})
        replay_run.create(self.config)
        command = next(c.args[2] for c in self.capture.call_args_list if c.args[1] == 'create-infra')
        self.assertEqual(command[command.index('-p') + 1], self.config['network'])

    def test_install_ownership_precedes_export_check_and_install_captures(self):
        self.prepare()
        replay_run.install(self.config)
        self.assertEqual([c[0] for c in self.events.mock_calls[:3]],
                         ['ownership', 'verify_export_identity', 'capture'])
        self.assertEqual([c.args[1] for c in self.capture.call_args_list],
                         ['prepare-install-inputs', 'install', 'platform-identity',
                          'installed-companion-report', 'platform-identity-report',
                          'install-receipt', 'resolved-lock', 'complete-lock'])

    def test_live_install_links_the_host_checkout_after_all_identity_reports(self):
        self.config['platform_mount'] = 'live'
        self.prepare()
        replay_run.install(self.config)
        labels = [c.args[1] for c in self.capture.call_args_list]
        self.assertEqual(labels[-1], 'link-live-platform')
        self.assertEqual(labels[:-1], ['prepare-install-inputs', 'install', 'platform-identity',
                                       'installed-companion-report', 'platform-identity-report',
                                       'install-receipt', 'resolved-lock', 'complete-lock'])
        script = self.capture.call_args_list[-1].args[2][-1]
        self.assertEqual(script, 'rm -rf /edx/app/edxapp/edx-platform && ln -s /workspace/platform /edx/app/edxapp/edx-platform')

    def test_snapshot_install_keeps_the_copy(self):
        self.prepare()
        replay_run.install(self.config)
        self.assertNotIn('link-live-platform', [c.args[1] for c in self.capture.call_args_list])

    def test_install_failure_stops_before_identity_or_success_reports(self):
        self.prepare()
        def fail_install(config, label, command, **kwargs):
            if label == 'install':
                raise SystemExit(42)
        self.capture.side_effect = fail_install
        with self.assertRaises(SystemExit) as error:
            replay_run.install(self.config)
        self.assertEqual(error.exception.code, 42)
        self.assertEqual([c.args[1] for c in self.capture.call_args_list],
                         ['prepare-install-inputs', 'install'])

    def test_runtime_keeps_original_inputs_read_only(self):
        self.prepare()
        self.external.side_effect = None
        self.external.return_value = json.dumps({'py313.replay.config': config_hash(self.config)})
        replay_run.create(self.config)
        command = self.capture.call_args_list[-1].args[2]
        mounts = [command[i + 1] for i, value in enumerate(command) if value == '--mount']
        for target in ('/paired-startup', '/input/platform', '/canary',
                       '/startup/.acceptance-credentials.json', '/startup/jwt-private.pem'):
            self.assertTrue(any(('dst=' + target + ',readonly') in mount for mount in mounts), target)
        self.assertFalse(any('dst=/startup,readonly' in mount for mount in mounts))

    def test_failed_ownership_does_not_read_export_or_dispatch_install(self):
        self.prepare()
        self.ownership.side_effect = ValueError('ownership fixture rejected')
        with self.assertRaisesRegex(ValueError, 'ownership fixture rejected'):
            replay_run.install(self.config)
        self.verify_export_identity.assert_not_called()
        self.capture.assert_not_called()


if __name__ == '__main__':
    unittest.main()
