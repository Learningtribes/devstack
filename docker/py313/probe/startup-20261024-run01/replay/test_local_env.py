"""One-command local bring-up tooling: run creation, stages, status, teardown, smoke helpers; no Docker mutations."""
import ast
import contextlib
import http.server
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import acceptance_course
import bring_up
import core
import destroy_run
import http_client
import new_run
import smoke_http
import status
from core import SECRET_KEYS, config_hash, load_config
from test_core import example

HERE = Path(__file__).resolve().parent


GIT_ENV = {'PATH': os.environ['PATH'], 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_AUTHOR_NAME': 't',
           'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't', 'GIT_COMMITTER_EMAIL': 't@t'}


def git(path, *command):
    return subprocess.run(['git', '-C', str(path), *command], check=True, env=GIT_ENV, capture_output=True,
                          text=True).stdout.strip()


def git_repo(path):
    path.mkdir()
    git(path, 'init', '-q')
    git(path, 'commit', '-q', '--allow-empty', '-m', 'init')
    return git(path, 'rev-parse', 'HEAD')


class NewRunTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.platform = self.root / 'platform'
        self.devstack = self.root / 'devstack'
        self.platform_head = git_repo(self.platform)
        self.devstack_head = git_repo(self.devstack)
        for name, value in [('docker_network_subnets', []), ('host_routes', []),
                            ('generate_jwt_key', b'-----BEGIN PRIVATE KEY-----\nfixture\n')]:
            patcher = patch.object(new_run, name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def args(self, **changes):
        values = dict(run_id='master313x', lms_port=18100, cms_port=18110, platform_repo=str(self.platform),
                      platform_commit=None, devstack_repo=str(self.devstack), devstack_commit=None,
                      root=str(self.root / 'runs/master313x'), subnet=None, runtime_image=None)
        values.update(changes)
        return type('Args', (), values)

    def test_creates_private_layout_and_a_config_that_passes_the_replay_contract(self):
        target, config = new_run.create_run(self.args())
        run = target.parent
        self.assertEqual(load_config(target), config)
        self.assertEqual(stat.S_IMODE((run / 'private').stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((run / 'private/jwt.pem').stat().st_mode), 0o600)
        self.assertEqual(config['platform_commit'], self.platform_head)
        self.assertEqual(config['devstack_commit'], self.devstack_head)
        self.assertEqual(config['course_key'], 'course-v1:PY313+master313x+2026')
        self.assertEqual(config['network_subnet'], '172.30.1.0/24')
        self.assertEqual(config['test_database'], 'py313_rebuild_master313x_test')
        example_config = core.read_json(new_run.EXAMPLE)
        self.assertEqual(config['images'], example_config['images'])
        self.assertEqual(config['theme_commit'], example_config['theme_commit'])
        for key in ('evidence_dir', 'export_dir'):
            self.assertFalse(os.path.lexists(config[key]))
        self.assertFalse((run / 'private/services.env').exists())

    def test_live_platform_flag_records_the_mount_mode_in_a_valid_config(self):
        target, config = new_run.create_run(self.args(live_platform=True))
        self.assertEqual(config['platform_mount'], 'live')
        self.assertEqual(load_config(target)['platform_mount'], 'live')

    def test_default_run_has_no_platform_mount_key(self):
        _, config = new_run.create_run(self.args())
        self.assertNotIn('platform_mount', config)

    def test_existing_run_directory_is_refused(self):
        new_run.create_run(self.args())
        with self.assertRaisesRegex(ValueError, 'Refusing existing run directory'):
            new_run.create_run(self.args())

    def test_invalid_contract_creates_nothing_on_disk(self):
        with self.assertRaisesRegex(ValueError, 'Ports must differ'):
            new_run.create_run(self.args(cms_port=18100))
        self.assertFalse((self.root / 'runs').exists())
        with self.assertRaisesRegex(ValueError, 'run_id'):
            new_run.create_run(self.args(run_id='Bad_Id'))
        with self.assertRaisesRegex(ValueError, 'outside platform_repo'):
            new_run.create_run(self.args(root=str(self.platform / 'run')))
        self.assertFalse((self.platform / 'run').exists())

    def test_dirty_or_moved_repositories_are_refused(self):
        git(self.platform, 'commit', '-q', '--allow-empty', '-m', 'two')
        with self.assertRaisesRegex(ValueError, 'not the checked-out HEAD'):
            new_run.create_run(self.args(platform_commit=self.platform_head))
        (self.devstack / 'tracked.txt').write_text('a')
        git(self.devstack, 'add', 'tracked.txt')
        with self.assertRaisesRegex(ValueError, 'clean tracked tree'):
            new_run.create_run(self.args())

    def test_explicit_subnet_must_not_overlap_docker_networks(self):
        with patch.object(new_run, 'docker_network_subnets', return_value=['172.30.9.0/24']):
            with self.assertRaisesRegex(ValueError, 'overlaps'):
                new_run.create_run(self.args(subnet='172.30.9.0/24'))
            target, config = new_run.create_run(self.args(subnet='172.30.10.0/24'))
        self.assertEqual(config['network_subnet'], '172.30.10.0/24')

    def test_main_prints_only_the_config_path_on_stdout_and_no_secret_material(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            new_run.main(['--run-id', 'master313y', '--lms-port', '18100', '--cms-port', '18110',
                          '--platform-repo', str(self.platform), '--devstack-repo', str(self.devstack),
                          '--root', str(self.root / 'runs/y')])
        self.assertEqual(out.getvalue().strip(), str(self.root / 'runs/y/config.json'))
        self.assertNotIn('PRIVATE KEY', out.getvalue() + err.getvalue())

    def test_route_parsing_and_subnet_choice_avoid_docker_and_host_networks(self):
        routes = new_run.parse_routes(
            'Routing tables\n\nInternet:\nDestination        Gateway            Flags\n'
            'default            10.0.0.1           UGScg\n127                127.0.0.1          UCS\n'
            '172.30.1/24        link#14            UC\n172.30.2.5        link#14            UHW\n'
            '169.254            link#4             UCS\n224.0.0/4        link#4             UmCS\n')
        self.assertIn(new_run.ipaddress.ip_network('172.30.1.0/24'), routes)
        self.assertIn(new_run.ipaddress.ip_network('127.0.0.0/8'), routes)
        self.assertIn(new_run.ipaddress.ip_network('172.30.2.5/32'), routes)
        self.assertEqual(new_run.pick_subnet(['172.30.3.0/24'], routes), '172.30.4.0/24')
        self.assertEqual(new_run.parse_routes('10.0.0.0/8 dev eth0\ndefault via 1.1.1.1\n'),
                         [new_run.ipaddress.ip_network('10.0.0.0/8')])


    def test_split_default_routes_of_a_tun_proxy_do_not_exhaust_the_subnet_pool(self):
        routes = new_run.parse_routes(
            'Destination        Gateway            Flags\n1                  198.18.0.1         UGSc\n'
            '2/7                198.18.0.1         UGSc\n4/6                198.18.0.1         UGSc\n'
            '8/5                198.18.0.1         UGSc\n16/4               198.18.0.1         UGSc\n'
            '32/3               198.18.0.1         UGSc\n64/2               198.18.0.1         UGSc\n'
            '128.0/1            198.18.0.1         UGSc\n172.30.1/24        link#14            UC\n')
        self.assertEqual(new_run.pick_subnet([], routes), '172.30.2.0/24')


class LocalRunFixture(unittest.TestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.config = example(self.root / 'run')
        (self.root / 'run').mkdir()
        self.config['evidence_dir'] = str(self.root / 'run/evidence')
        self.config['export_dir'] = str(self.root / 'run/export')
        self.config['secret_env'] = str(self.root / 'run/private/services.env')
        self.config['credentials_file'] = str(self.root / 'run/private/acceptance.json')
        self.config['jwt_file'] = str(self.root / 'run/private/jwt.pem')
        self.config_path = self.root / 'run/config.json'
        self.config_path.write_text(json.dumps(self.config))
        self.load = patch.object(bring_up, 'load_config', return_value=self.config)
        self.load.start()
        self.addCleanup(self.load.stop)


class BringUpTests(LocalRunFixture):
    NAMES = ['unittest', 'provision-secrets', 'provision-acceptance', 'preflight', 'prepare', 'create', 'install',
             'schema', 'assets', 'services', 'heartbeats', 'course-build', 'course-seed', 'superuser', 'smoke',
             'superuser-login']

    def test_stage_order_matches_the_documented_sequence_and_can_skip_unit_tests(self):
        self.assertEqual([name for name, _ in bring_up.stages(self.config_path, False)], self.NAMES)
        self.assertEqual([name for name, _ in bring_up.stages(self.config_path, True)], self.NAMES[1:])
        commands = dict(bring_up.stages(self.config_path, False))
        self.assertEqual(commands['create'][-3:], ['--config', str(self.config_path), 'create'])
        self.assertTrue(commands['schema'][2].endswith('replay_after_install.py'))
        self.assertIsNone(commands['heartbeats'])

    def run_all(self, failing=None):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            stage = next(name for name, argv in bring_up.stages(self.config_path, False) if argv == command)
            return subprocess.CompletedProcess(command, 1 if stage == failing else 0)

        with (patch.object(bring_up.subprocess, 'run', side_effect=fake_run),
              patch.object(bring_up, 'wait_for_heartbeats', return_value={'lms': 200, 'cms': 200}),
              contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO())):
            outcome = bring_up.bring_up(self.config_path)
        return outcome, calls, out.getvalue()

    def test_success_writes_summary_and_result_without_passwords(self):
        outcome, calls, printed = self.run_all()
        run = self.root / 'run'
        self.assertEqual(outcome['status'], 'PASS')
        self.assertEqual(len(calls), len(self.NAMES) - 1)
        summary = (run / 'stage-logs/summary.txt').read_text().splitlines()
        self.assertEqual([line.split()[0] for line in summary], ['stage=' + name for name in self.NAMES])
        self.assertTrue(all(' rc=0 ' in line and 'dur=' in line for line in summary))
        result = json.loads((run / 'bring-up-result.json').read_text())
        self.assertEqual(result['lms_url'], 'http://localhost:18240')
        self.assertEqual(result['credentials_file'], self.config['credentials_file'])
        self.assertIn(self.config['credentials_file'], printed)
        self.assertNotIn('password', printed.lower().replace('password not printed', ''))

    def test_first_nonzero_stage_stops_the_sequence(self):
        outcome, calls, _ = self.run_all(failing='create')
        self.assertEqual(outcome['status'], 'FAIL')
        self.assertEqual(outcome['failed_stage'], 'create')
        self.assertEqual([stage['name'] for stage in outcome['stages']], self.NAMES[:6])
        self.assertEqual(len(calls), 6)
        self.assertFalse((self.root / 'run/stage-logs/install.log').exists())

    def test_unready_heartbeat_fails_the_stage(self):
        with (patch.object(bring_up.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)),
              patch.object(bring_up, 'wait_for_heartbeats', return_value={'lms': 200, 'cms': None}),
              contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO())):
            outcome = bring_up.bring_up(self.config_path, skip_unit_tests=True)
        self.assertEqual(outcome['failed_stage'], 'heartbeats')


class StatusTests(LocalRunFixture):
    def test_published_ports_and_health_rules(self):
        ports = {'18000/tcp': [{'HostIp': '127.0.0.1', 'HostPort': '18240'}], '3306/tcp': None}
        self.assertEqual(status.published(ports), '127.0.0.1:18240->18000/tcp')
        rows = [{'state': 'running'}, {'state': 'running'}]
        self.assertTrue(status.healthy(rows, {'lms': 200, 'cms': 200}))
        self.assertFalse(status.healthy(rows, {'lms': 200, 'cms': None}))
        self.assertFalse(status.healthy(rows + [{'state': 'absent'}], {'lms': 200, 'cms': 200}))

    def test_collect_reports_absent_containers(self):
        with patch.object(status, 'inspect_container', return_value=None), patch.object(status, 'heartbeat',
                                                                                         return_value=None):
            rows, heartbeats = status.collect(self.config)
        self.assertEqual({row['state'] for row in rows}, {'absent'})
        self.assertEqual(len(rows), 7)
        self.assertEqual(heartbeats, {'lms': None, 'cms': None})


class DestroyTests(LocalRunFixture):
    def fake_docker(self, containers, volumes=None, network=None, users=None):
        """Scripted docker: label maps per resource, container users per volume/network."""
        removed = []
        users = users or {}

        def run(*args):
            kind = args[0]
            if args[:2] == ('ps', '-a'):
                return subprocess.CompletedProcess(args, 0, '\n'.join(users.get(args[3].split('=', 1)[1], [])), '')
            if kind == 'rm':
                removed.append(('container', args[-1]))
                return subprocess.CompletedProcess(args, 0, '', '')
            if args[1] == 'rm':
                removed.append((kind, args[-1]))
                return subprocess.CompletedProcess(args, 0, '', '')
            table = {'container': containers, 'volume': volumes or {}, 'network': network or {}}[kind]
            name = args[-1]
            if name not in table:
                return subprocess.CompletedProcess(args, 1, '', 'No such object')
            return subprocess.CompletedProcess(args, 0, json.dumps(table[name]), '')

        return run, removed

    def test_only_owned_resources_are_removed_and_foreign_ones_reported(self):
        label = {'py313.replay.config': config_hash(self.config)}
        containers = {self.config['runtime_container']: label,
                      self.config['services']['mysql']['container']: label,
                      self.config['services']['mongo']['container']: {'py313.replay.config': 'other'},
                      self.config['services']['valkey']['container']: {}}
        volumes = {self.config['runtime_volume']: label,
                   self.config['services']['mysql']['volume']: label,
                   self.config['services']['mongo']['volume']: label}
        users = {self.config['services']['mongo']['volume']: [self.config['services']['mongo']['container']],
                 self.config['runtime_volume']: [self.config['runtime_container']],
                 self.config['network']: [self.config['runtime_container'], 'ut1106a-app']}
        run, removed = self.fake_docker(containers, volumes, {self.config['network']: label}, users)
        with patch.object(destroy_run, 'docker', side_effect=run):
            report = destroy_run.destroy(self.config)
        self.assertEqual(sorted(name for kind, name in removed if kind == 'container'),
                         sorted([self.config['runtime_container'], self.config['services']['mysql']['container']]))
        self.assertEqual(report['containers_skipped_foreign'], [self.config['services']['mongo']['container'],
                                                                 self.config['services']['valkey']['container']])
        self.assertEqual(sorted(report['volumes_removed']),
                         sorted([self.config['runtime_volume'], self.config['services']['mysql']['volume']]))
        self.assertEqual([item['name'] for item in report['volumes_skipped']], [self.config['services']['mongo']['volume']])
        self.assertFalse(report['network_removed'])
        self.assertIn('ut1106a-app', report['network_skipped'])
        self.assertNotIn(('network', self.config['network']), removed)

    def test_unlabelled_volume_and_dry_run_are_never_removed(self):
        run, removed = self.fake_docker({}, {self.config['runtime_volume']: {}}, {self.config['network']: {}})
        with patch.object(destroy_run, 'docker', side_effect=run):
            report = destroy_run.destroy(self.config)
        self.assertEqual(removed, [])
        self.assertEqual(report['volumes_skipped'][0]['reason'], 'ownership label differs')
        label = {'py313.replay.config': config_hash(self.config)}
        run, removed = self.fake_docker({self.config['runtime_container']: label},
                                        {self.config['runtime_volume']: label})
        with patch.object(destroy_run, 'docker', side_effect=run):
            report = destroy_run.destroy(self.config, dry_run=True)
        self.assertEqual(removed, [])
        self.assertEqual(report['containers_removed'], [self.config['runtime_container']])

    def test_purge_removes_only_known_outputs_and_keeps_unknown_files(self):
        run = self.root / 'run'
        for relative in ('evidence/a.txt', 'export/b.txt', 'stage-logs/c.log', 'private/services.env',
                         'private/acceptance.json', 'private/jwt.pem', 'bring-up-result.json', 'unrelated.txt'):
            path = run / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('x')
        (run / 'export/b.txt').chmod(0o444)
        destroy_run.purge(self.config, self.config_path)
        self.assertEqual(sorted(path.name for path in run.iterdir()), ['unrelated.txt'])


class HttpAndSmokeTests(unittest.TestCase):
    def test_superuser_defaults_and_overrides(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(http_client.dev_superuser(),
                             {'username': 'edx', 'email': 'edx@example.com', 'password': 'edx'})
        with patch.dict(os.environ, {'PY313_DEV_SUPERUSER_PASSWORD': 'other'}):
            self.assertEqual(http_client.dev_superuser()['password'], 'other')

    def test_environment_forwards_only_superuser_overrides_of_host_py313_values(self):
        with tempfile.TemporaryDirectory() as directory:
            config = example(Path(directory))
            secret = Path(config['secret_env'])
            secret.write_text(''.join(key + '=' + '1' * 48 + '\n' for key in SECRET_KEYS))
            secret.chmod(0o600)
            with patch.dict(os.environ, {'PY313_DEV_SUPERUSER_PASSWORD': 'x', 'PY313_RUNTIME_CONTAINER': 'stale',
                                         'PY313_MYSQL_USER': 'stale'}):
                env = core.environment(config)
        self.assertEqual(env['PY313_DEV_SUPERUSER_PASSWORD'], 'x')
        self.assertEqual(env['PY313_RUNTIME_CONTAINER'], config['runtime_container'])
        self.assertEqual(env['PY313_MYSQL_USER'], 'edxapp')

    def test_heartbeat_wait_returns_when_both_answer_or_on_timeout(self):
        config = {'lms_port': 18000, 'cms_port': 18010}
        answers = iter([None, 200, 200, 200])
        with patch.object(http_client, 'heartbeat', side_effect=lambda url: next(answers)):
            sleeps = []
            codes = http_client.wait_for_heartbeats(config, 60, sleep=sleeps.append, clock=lambda: 0)
        self.assertEqual(codes, {'lms': 200, 'cms': 200})
        self.assertEqual(len(sleeps), 1)
        ticks = iter(range(0, 1000, 40))
        with patch.object(http_client, 'heartbeat', return_value=None):
            codes = http_client.wait_for_heartbeats(config, 60, sleep=lambda delay: None, clock=lambda: next(ticks))
        self.assertEqual(codes, {'lms': None, 'cms': None})

    def test_client_session_carries_csrf_and_cookies_to_a_login_endpoint(self):
        seen = {}

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                self.send_response(200)
                self.send_header('Set-Cookie', 'csrftoken=tok; Path=/')
                self.end_headers()
                self.wfile.write(b'OK')

            def do_POST(self):
                seen['csrf'] = self.headers.get('X-CSRFToken')
                seen['body'] = self.rfile.read(int(self.headers['Content-Length'])).decode()
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"success": true}')

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.addCleanup(server.server_close)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        config = {'lms_port': server.server_address[1], 'cms_port': server.server_address[1] + 1}
        client, code, body = http_client.login_lms(config, {'email': 'a@b.c', 'password': 'pw'})
        self.assertEqual((code, body), (200, b'{"success": true}'))
        self.assertEqual(seen['csrf'], 'tok')
        self.assertIn('email=a%40b.c', seen['body'])
        self.assertEqual(http_client.heartbeat('http://127.0.0.1:%d' % server.server_address[1]), 200)
        self.assertIsNone(http_client.heartbeat('http://127.0.0.1:1'))

    def test_smoke_check_flags_missing_body_text_and_unexpected_status(self):
        class Fake:
            def req(self, method, path, **kwargs):
                return 200, {}, b'<html>hello</html>'

        smoke = smoke_http.Smoke()
        with contextlib.redirect_stdout(io.StringIO()):
            smoke.check('has', Fake(), 'GET', '/', contains='hello')
            smoke.check('lacks', Fake(), 'GET', '/', contains='absent')
            smoke.check('status', Fake(), 'GET', '/', expected=(404,))
        self.assertEqual([row[1] for row in smoke.rows], ['PASS', 'FAIL', 'FAIL'])
        self.assertEqual(smoke.rows[1][2], 'BODY')
        self.assertEqual(len(smoke.failures()), 2)

    def test_course_labels_are_derived_from_the_run(self):
        config = {'run_id': 'master313z'}
        self.assertEqual(acceptance_course.html_marker(config), 'master313z acceptance html body')
        self.assertEqual(acceptance_course.display_name(config), 'master313z acceptance course')


class SuperuserRuntimeTests(unittest.TestCase):
    SCRIPT = HERE / 'superuser_runtime.py'

    def test_runtime_script_is_valid_python_and_never_prints_the_password(self):
        tree = ast.parse(self.SCRIPT.read_text())
        prints = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                  and getattr(node.func, 'id', '') == 'print']
        self.assertTrue(prints)
        for call in prints:
            names = {node.id for node in ast.walk(call) if isinstance(node, ast.Name)}
            self.assertNotIn('password', names)

    def test_script_reads_credentials_from_the_environment_with_documented_defaults(self):
        source = self.SCRIPT.read_text()
        for key, default in zip(core.DEV_SUPERUSER_KEYS, ('edx', 'edx@example.com', 'edx')):
            self.assertIn("os.environ.get('%s', '%s')" % (key, default), source)
        self.assertIn('LOCAL DEVSTACK ONLY', source)

    def test_host_entry_runs_the_script_through_the_lms_shell(self):
        import ensure_superuser
        self.assertEqual(ensure_superuser.SCRIPT, '/startup/replay/superuser_runtime.py')
        self.assertTrue((HERE / 'superuser_runtime.py').is_file())


if __name__ == '__main__':
    unittest.main()
