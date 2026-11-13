"""Runtime image lock, locked-reference validation and image build helpers; no Docker daemon access."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import core
import run as replay_run
from core import (SECRET_KEYS, config_hash, ensure_runtime_image, load_config, validate_runtime_lock,
                  validate_selected_image)
from test_core import example

BUILDER = Path(__file__).resolve().parents[3] / 'build-runtime-image.py'
INDEX_DIGEST = 'sha256:' + '1' * 64
AMD64 = 'sha256:' + '2' * 64
ARM64 = 'sha256:' + '3' * 64
REFERENCE = 'ltdps/edxapp@' + INDEX_DIGEST


def runtime_lock(**changes):
    value = {'schema_version': 1, 'repository': 'ltdps/edxapp', 'tag': 'py313-devstack-20261106',
             'stage': 'internal-delivery', 'registry_manifest_type': core.IMAGE_INDEX_MEDIA_TYPE,
             'index_digest': INDEX_DIGEST, 'platforms': {'linux/amd64': AMD64, 'linux/arm64': ARM64},
             'devstack_commit': 'd' * 40, 'built_on': '2026-11-06'}
    value.update(changes)
    return value


def load_builder():
    spec = importlib.util.spec_from_file_location('build_runtime_image', BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LockedRuntimeTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.lock = self.root / 'runtime-image.lock.json'
        self.lock.write_text(json.dumps(runtime_lock()))
        patcher = patch.object(core, 'RUNTIME_LOCK_PATH', self.lock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config = example(self.root)
        self.config['images']['runtime'] = REFERENCE
        Path(self.config['platform_repo']).mkdir()
        Path(self.config['devstack_repo']).mkdir()
        self.path = self.root / 'config.json'
        for key, content in [('credentials_file', '{}'), ('jwt_file', 'fixture')]:
            Path(self.config[key]).write_text(content)
            Path(self.config[key]).chmod(0o600)
        Path(self.config['secret_env']).write_text(''.join(key + '=' + '1' * 48 + '\n' for key in SECRET_KEYS))
        Path(self.config['secret_env']).chmod(0o600)

    def write(self):
        self.path.write_text(json.dumps(self.config))

    def container(self, configured=REFERENCE, image_id='sha256:' + 'b' * 64):
        return {'name': '/' + self.config['runtime_container'], 'configured_image': configured,
                'image_id': image_id, 'labels': {'py313.replay.config': config_hash(self.config)}}

    def image(self, repo_digests=(REFERENCE,), architecture='arm64', variant=None):
        return {'Id': 'sha256:' + 'b' * 64, 'RepoDigests': list(repo_digests), 'Os': 'linux',
                'Architecture': architecture, 'Variant': variant}

    def test_locked_reference_and_local_image_id_are_both_accepted(self):
        self.write()
        self.assertEqual(load_config(self.path)['images']['runtime'], REFERENCE)
        self.config['images']['runtime'] = 'sha256:' + 'a' * 64
        self.write()
        self.assertEqual(load_config(self.path)['images']['runtime'], 'sha256:' + 'a' * 64)

    def test_unlocked_reference_is_rejected(self):
        for reference in ('ltdps/edxapp@sha256:' + '9' * 64, 'other/edxapp@' + INDEX_DIGEST,
                          'ltdps/edxapp:py313-devstack-20261106', 'ltdps/edxapp:latest'):
            self.config['images']['runtime'] = reference
            self.write()
            with self.assertRaisesRegex(ValueError, 'Runtime image must be a local sha256 image ID or the reference'):
                load_config(self.path)

    def test_locked_reference_requires_a_readable_lock(self):
        self.lock.unlink()
        self.write()
        with self.assertRaisesRegex(ValueError, 'Unable to read runtime image lock'):
            load_config(self.path)

    def test_lock_schema_rejects_mutable_tag_missing_platform_and_bad_digests(self):
        self.assertEqual(validate_runtime_lock(runtime_lock())['index_digest'], INDEX_DIGEST)
        for changes, message in [
                ({'tag': 'latest'}, 'explicit dated tag'),
                ({'repository': 'other/edxapp'}, 'repository'),
                ({'index_digest': 'sha256:bad'}, 'index digest'),
                ({'platforms': {'linux/amd64': AMD64}}, 'exactly linux/amd64 and linux/arm64'),
                ({'platforms': {'linux/amd64': AMD64, 'linux/arm64': 'sha256:bad'}}, 'platform digest'),
                ({'devstack_commit': 'abc'}, 'source commit'),
                ({'built_on': 'yesterday'}, 'build date'),
                ({'schema_version': True}, 'schema version')]:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, message):
                validate_runtime_lock(runtime_lock(**changes))
        lock = runtime_lock()
        lock['extra'] = 1
        with self.assertRaisesRegex(ValueError, 'invalid schema'):
            validate_runtime_lock(lock)

    def test_selected_locked_runtime_records_index_and_platform_digest(self):
        selected = validate_selected_image(self.config, 'runtime', self.container(), self.image())
        self.assertEqual(selected['index_digest'], INDEX_DIGEST)
        self.assertEqual(selected['locked_platform_manifest_digest'], ARM64)
        self.assertEqual(selected['source_tag'], 'ltdps/edxapp:py313-devstack-20261106')
        self.assertEqual(selected['repo_digests'], [REFERENCE])
        selected = validate_selected_image(self.config, 'runtime', self.container(),
                                           self.image(architecture='amd64'))
        self.assertEqual(selected['locked_platform_manifest_digest'], AMD64)

    def test_selected_locked_runtime_rejects_foreign_digest_platform_and_label(self):
        with self.assertRaisesRegex(ValueError, 'does not carry its locked repository digest: runtime'):
            validate_selected_image(self.config, 'runtime', self.container(),
                                    self.image(repo_digests=['ltdps/edxapp@sha256:' + '9' * 64]))
        with self.assertRaisesRegex(ValueError, 'platform is not present'):
            validate_selected_image(self.config, 'runtime', self.container(), self.image(architecture='riscv64'))
        with self.assertRaisesRegex(ValueError, 'image reference differs'):
            validate_selected_image(self.config, 'runtime', self.container(configured='sha256:' + 'b' * 64),
                                    self.image())
        container = self.container()
        container['labels'] = {}
        with self.assertRaisesRegex(ValueError, 'ownership differs'):
            validate_selected_image(self.config, 'runtime', container, self.image())

    def test_ensure_returns_none_for_local_image_id_without_docker(self):
        self.config['images']['runtime'] = 'sha256:' + 'a' * 64
        with patch('core.subprocess.run') as run:
            self.assertIsNone(ensure_runtime_image(self.config))
        run.assert_not_called()

    def test_ensure_uses_present_image_without_pulling(self):
        inspected = subprocess.CompletedProcess([], 0, json.dumps(self.image()), '')
        with patch('core.subprocess.run', return_value=inspected) as run:
            record = ensure_runtime_image(self.config, sleep=lambda delay: None)
        self.assertEqual(record['platform'], 'linux/arm64')
        self.assertEqual(record['repo_digests'], [REFERENCE])
        self.assertEqual([call.args[0][1] for call in run.call_args_list], ['image'])

    def test_ensure_pulls_missing_image_by_digest_with_backoff(self):
        missing = subprocess.CompletedProcess([], 1, '', 'No such image')
        reset = subprocess.CompletedProcess([], 1, '', 'i/o timeout')
        ok = subprocess.CompletedProcess([], 0, '', '')
        present = subprocess.CompletedProcess([], 0, json.dumps(self.image()), '')
        sequence = iter([missing, reset, reset, ok, present])
        delays = []
        with patch('core.subprocess.run', side_effect=lambda *a, **k: next(sequence)) as run:
            record = ensure_runtime_image(self.config, sleep=delays.append)
        self.assertEqual(delays, [5, 15])
        self.assertEqual(record['reference'], REFERENCE)
        pulls = [call.args[0] for call in run.call_args_list if call.args[0][1] == 'pull']
        self.assertEqual(pulls, [['docker', 'pull', '--quiet', REFERENCE]] * 3)

    def test_ensure_fails_when_pull_never_succeeds(self):
        failed = subprocess.CompletedProcess([], 1, '', 'timeout')
        delays = []
        with patch('core.subprocess.run', return_value=failed):
            with self.assertRaisesRegex(ValueError, 'could not be pulled'):
                ensure_runtime_image(self.config, sleep=delays.append)
        self.assertEqual(delays, list(core.RUNTIME_PULL_BACKOFF))

    def test_ensure_rejects_local_image_with_another_digest(self):
        foreign = subprocess.CompletedProcess([], 0, json.dumps(self.image(
            repo_digests=['ltdps/edxapp@sha256:' + '9' * 64])), '')
        with patch('core.subprocess.run', return_value=foreign):
            with self.assertRaisesRegex(ValueError, 'does not carry the locked repository digest'):
                ensure_runtime_image(self.config, sleep=lambda delay: None)

    def test_preflight_reports_runtime_image_only_for_locked_reference(self):
        record = {'reference': REFERENCE, 'image_id': 'sha256:' + 'b' * 64, 'repo_digests': [REFERENCE],
                  'platform': 'linux/arm64'}
        with (patch('core.source_repository_roots', return_value={}), patch('core.validate_path_isolation'),
              patch('core.check_conflicts'), patch('core.inventory'), patch('core.docker_network_subnets',
              return_value=[]), patch('core.validate_network_subnet', return_value='10.254.44.0/24'),
              patch('core.socket.socket'), patch('core.subprocess.check_output', return_value='a' * 40),
              patch('core.subprocess.run'), patch('core.ensure_runtime_image', return_value=record),
              patch('core.check_platform_layout') as layout):
            self.config['platform_commit'] = self.config['devstack_commit'] = 'a' * 40
            report = core.fresh_preflight(self.config, before_prepare=False)
        self.assertEqual(report['runtime_image'], record)
        layout.assert_called_once_with(self.config['platform_repo'])


class BuilderTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.builder = load_builder()

    def index(self, **changes):
        value = {'schemaVersion': 2, 'mediaType': core.IMAGE_INDEX_MEDIA_TYPE, 'manifests': [
            {'digest': AMD64, 'platform': {'os': 'linux', 'architecture': 'amd64'}},
            {'digest': ARM64, 'platform': {'os': 'linux', 'architecture': 'arm64', 'variant': 'v8'}}]}
        value.update(changes)
        return json.dumps(value).encode()

    def test_tag_must_be_new_dated_and_in_the_runtime_repository(self):
        self.assertEqual(self.builder.validate_tag('ltdps/edxapp:py313-devstack-20261106'),
                         'ltdps/edxapp:py313-devstack-20261106')
        self.builder.validate_tag('ltdps/edxapp:py313-devstack-20261106b')
        for tag in ('ltdps/edxapp', 'ltdps/edxapp:latest', 'ltdps/edxapp:py313-local',
                    'ltdps/edxapp:py313', 'ltdps/ci-edxapp:py313-devstack-20261106'):
            with self.subTest(tag=tag), self.assertRaises(SystemExit):
                self.builder.validate_tag(tag)

    def test_index_digest_and_platform_digests_are_recorded(self):
        raw = self.index()
        digest, platforms = self.builder.parse_index(raw)
        import hashlib
        self.assertEqual(digest, 'sha256:' + hashlib.sha256(raw).hexdigest())
        self.assertEqual(platforms, {'linux/amd64': AMD64, 'linux/arm64': ARM64})

    def test_index_must_be_oci_with_exactly_both_platforms_and_no_attestations(self):
        with self.assertRaises(SystemExit):
            self.builder.parse_index(self.index(mediaType='application/vnd.docker.distribution.manifest.v2+json'))
        with self.assertRaises(SystemExit):
            self.builder.parse_index(self.index(manifests=[
                {'digest': AMD64, 'platform': {'os': 'linux', 'architecture': 'amd64'}}]))
        with self.assertRaises(SystemExit):
            self.builder.parse_index(self.index(manifests=[
                {'digest': AMD64, 'platform': {'os': 'linux', 'architecture': 'amd64'}},
                {'digest': ARM64, 'platform': {'os': 'linux', 'architecture': 'arm64'}},
                {'digest': 'sha256:' + '4' * 64, 'platform': {'os': 'unknown', 'architecture': 'unknown'}}]))

    def test_missing_tag_is_definitive_but_network_errors_are_retried(self):
        missing = subprocess.CompletedProcess([], 1, '', 'ERROR: docker.io/ltdps/edxapp:x: not found')
        reset = subprocess.CompletedProcess([], 1, '', 'dial tcp: i/o timeout')
        with patch.object(self.builder.subprocess, 'run', return_value=missing) as run:
            self.assertFalse(self.builder.tag_exists('ltdps/edxapp:py313-devstack-20261106'))
        self.assertEqual(run.call_count, 1)
        with (patch.object(self.builder.subprocess, 'run', return_value=reset) as run,
              patch.object(self.builder.time, 'sleep') as sleep):
            with self.assertRaisesRegex(SystemExit, 'Cannot determine'):
                self.builder.tag_exists('ltdps/edxapp:py313-devstack-20261106')
        self.assertEqual(run.call_count, 1 + len(self.builder.REGISTRY_BACKOFF))
        self.assertEqual([call.args[0] for call in sleep.call_args_list], list(self.builder.REGISTRY_BACKOFF))

    def test_lock_record_matches_the_replay_schema(self):
        record = self.builder.lock_record('ltdps/edxapp:py313-devstack-20261106', INDEX_DIGEST,
                                          {'linux/amd64': AMD64, 'linux/arm64': ARM64}, 'd' * 40, '2026-11-06')
        self.assertEqual(record, runtime_lock())

    def test_dirty_tree_is_refused_before_any_registry_access(self):
        dirty = subprocess.CompletedProcess([], 0, ' M docker/py313/Dockerfile\n', '')
        with (patch.object(self.builder, 'git', return_value=dirty),
              patch.object(self.builder, 'tag_exists') as exists,
              patch.object(self.builder.subprocess, 'run') as run):
            with self.assertRaisesRegex(SystemExit, 'dirty tree'):
                self.builder.main(['--tag', 'ltdps/edxapp:py313-devstack-20261106', '--context', '/nonexistent/ctx'])
        exists.assert_not_called()
        run.assert_not_called()

    @staticmethod
    def clean_git(root, *args, **kwargs):
        return subprocess.CompletedProcess([], 0, '' if args[0] == 'status' else 'd' * 40, '')

    def test_existing_remote_tag_is_refused(self):
        with (patch.object(self.builder, 'git', side_effect=self.clean_git), patch.object(
                self.builder, 'tag_exists', return_value=True), patch.object(self.builder.subprocess, 'run') as run):
            with self.assertRaisesRegex(SystemExit, 'already exists remotely'):
                self.builder.main(['--tag', 'ltdps/edxapp:py313-devstack-20261106', '--context', '/nonexistent/ctx'])
        run.assert_not_called()

    def test_registry_proxy_applies_to_registry_reads_only(self):
        self.assertEqual(self.builder.registry_environment('http://127.0.0.1:1')['HTTPS_PROXY'], 'http://127.0.0.1:1')
        with patch.dict(self.builder.os.environ, {}, clear=True):
            self.assertNotIn('HTTPS_PROXY', self.builder.registry_environment(None))
        with (patch.object(self.builder, 'git', side_effect=self.clean_git), patch.object(
                self.builder, 'tag_exists', return_value=True) as exists, patch.object(self.builder.subprocess, 'run')):
            with self.assertRaisesRegex(SystemExit, 'already exists remotely'):
                self.builder.main(['--tag', 'ltdps/edxapp:py313-devstack-20261106', '--context', '/x',
                                   '--registry-proxy', 'http://127.0.0.1:1'])
        self.assertEqual(exists.call_args.args[1]['HTTPS_PROXY'], 'http://127.0.0.1:1')

    def test_lock_only_records_a_pushed_tag_without_building(self):
        with tempfile.TemporaryDirectory() as directory:
            lock = Path(directory) / 'lock.json'
            with (patch.object(self.builder, 'pushed_index', return_value=(INDEX_DIGEST, {
                    'linux/amd64': AMD64, 'linux/arm64': ARM64})), patch.object(self.builder.subprocess, 'run') as run):
                self.builder.main(['--tag', 'ltdps/edxapp:py313-devstack-20261106', '--lock-only',
                                   '--source-commit', 'd' * 40, '--lock', str(lock)])
            self.assertEqual(json.loads(lock.read_text())['devstack_commit'], 'd' * 40)
            run.assert_not_called()
            with self.assertRaisesRegex(SystemExit, 'source-commit'):
                self.builder.main(['--tag', 'ltdps/edxapp:py313-devstack-20261106', '--lock-only'])

    def test_build_args_are_restricted_to_mirror_settings(self):
        with self.assertRaisesRegex(SystemExit, '--build-arg'):
            self.builder.main(['--tag', 'ltdps/edxapp:py313-devstack-20261106', '--context', '/x',
                               '--build-arg', 'NODE_VERSION=18.0.0'])

    def test_build_inputs_exist_in_the_repository(self):
        root = BUILDER.parents[2]
        for relative in self.builder.BUILD_INPUTS:
            self.assertTrue((root / relative).is_file(), relative)
        self.assertIn('AS ' + self.builder.STAGE, (root / 'docker/py313/Dockerfile').read_text())


class MysqlTestDatabaseGrantTests(unittest.TestCase):
    SCRIPT = Path(__file__).with_name('mysql-grant-test-database.sh')

    def run_script(self, database):
        with tempfile.TemporaryDirectory() as directory:
            sql = Path(directory) / 'sql'
            program = ('docker_process_sql() { cat > "$SQL"; }; MYSQL_USER=edxapp; '
                       'PY313_TEST_DATABASE="$1"; . "$2"')
            result = subprocess.run(['bash', '-c', program, 'run', database, str(self.SCRIPT)],
                                    env={'SQL': str(sql), 'PATH': '/usr/bin:/bin'}, capture_output=True, text=True)
            return result, sql.read_text() if sql.exists() else None

    def test_grant_covers_exactly_the_configured_test_database(self):
        result, sql = self.run_script('py313_rebuild_master313r15_test')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sql, "GRANT ALL PRIVILEGES ON `py313\\_rebuild\\_master313r15\\_test`.* TO 'edxapp'@'%';\n")

    def test_missing_database_name_fails_initialization(self):
        result, _ = self.run_script('')
        self.assertNotEqual(result.returncode, 0)

    def test_compose_mounts_the_grant_script_and_names_the_test_database(self):
        config = example(Path('/nonexistent'))
        mysql = replay_run.compose(config)['services']['mysql']
        self.assertEqual(mysql['environment']['PY313_TEST_DATABASE'], config['test_database'])
        self.assertTrue(any(volume.endswith('/replay/mysql-grant-test-database.sh:'
                                            '/docker-entrypoint-initdb.d/20-grant-test-database.sh:ro')
                            for volume in mysql['volumes']))
        self.assertEqual(mysql['volumes'][0], 'mysql:/var/lib/mysql')


if __name__ == '__main__':
    unittest.main()
