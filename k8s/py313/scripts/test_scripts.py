"""Tests of the local scripts that need neither a cluster nor Docker.

    uv run --no-project --python 3.13 python -B -m unittest discover -s k8s/py313/scripts -p 'test_*.py' -v
"""
import contextlib
import datetime
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

import postprocess_config

HERE = Path(__file__).resolve().parent
SCRIPTS = ('up', 'status', 'smoke', 'down', 'gen-local-secrets', 'gen-local-config', 'setup-elasticsearch')


def env_json(system):
    return {
        'LMS_BASE': 'localhost:18000', 'CMS_BASE': 'localhost:18010', 'ALLOWED_HOSTS': ['localhost', 'localhost:18000'],
        'LOG_DIR': f'/edx/var/log/{system}', 'LOG_DESTINATION': 'file',
        'MEDIA_ROOT': '/edx/var/edxapp/media', 'DATA_DIR': '/edx/var/edxapp/data',
        'ELASTIC_SEARCH_CONFIG': [{'host': 'elasticsearch', 'port': 9200, 'use_ssl': True, 'verify_certs': True,
                                   'ca_certs': '/edx/app/edxapp/py313-config/es-ca.crt', 'http_auth': ['py313_search', 'x']}],
    }


def auth_json(system):
    data = {'SECRET_KEY': 'k', 'CELERY_BROKER_PASSWORD': 'p'}
    if system == 'lms':
        data['JWT_PRIVATE_SIGNING_KEY'] = 'pem'
    return data


class PostprocessTest(unittest.TestCase):
    def write(self, directory, mutate=None):
        for system in ('lms', 'cms'):
            env = env_json(system)
            if mutate:
                mutate(system, env)
            (directory / f'{system}.env.json').write_text(json.dumps(env))
            (directory / f'{system}.auth.json').write_text(json.dumps(auth_json(system)))

    def run_process(self, directory):
        with contextlib.redirect_stdout(io.StringIO()):
            return postprocess_config.process(directory, 'localhost:18000', 'localhost:18010',
                                              '/edx/app/edxapp/py313-config/es-ca.crt', 'py313_search')

    def test_log_destination_becomes_console_and_checks_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.write(directory)
            self.assertEqual(self.run_process(directory), [])
            for system in ('lms', 'cms'):
                self.assertEqual(json.loads((directory / f'{system}.env.json').read_text())['LOG_DESTINATION'], 'console')
                self.assertEqual(stat.S_IMODE((directory / f'{system}.env.json').stat().st_mode), 0o600)

    def test_wildcard_host_or_plain_http_search_fails(self):
        def wildcard(system, env):
            env['ALLOWED_HOSTS'].append('*')

        def plain(system, env):
            env['ELASTIC_SEARCH_CONFIG'][0]['use_ssl'] = False
        for mutate in (wildcard, plain):
            with tempfile.TemporaryDirectory() as tmp:
                directory = Path(tmp)
                self.write(directory, mutate)
                self.assertTrue(self.run_process(directory), mutate.__name__)


class ContextGuardTest(unittest.TestCase):
    """Every script refuses to touch a cluster whose current context is not `orbstack`; the stub kubectl records any call."""

    def test_wrong_context_is_refused_before_any_cluster_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / 'bin'
            bin_dir.mkdir()
            log = Path(tmp) / 'calls.log'
            stub = bin_dir / 'kubectl'
            stub.write_text('#!/bin/sh\n'
                            f'if [ "$1 $2" = "config current-context" ]; then echo production-cluster; exit 0; fi\n'
                            f'echo "$@" >> {log}\nexit 0\n')
            stub.chmod(0o755)
            for name in SCRIPTS:
                env = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}', LOCAL_DIR=str(Path(tmp) / 'local'))
                env.pop('ALLOW_CONTEXT', None)
                result = subprocess.run([str(HERE / name)], env=env, capture_output=True, text=True, timeout=60)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn("expected 'orbstack'", result.stderr, name)
            self.assertFalse(log.exists(), 'a script called kubectl against the wrong context')

    def test_allow_context_override_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / 'bin'
            bin_dir.mkdir()
            stub = bin_dir / 'kubectl'
            stub.write_text('#!/bin/sh\nif [ "$1 $2" = "config current-context" ]; then echo other; exit 0; fi\nexit 1\n')
            stub.chmod(0o755)
            env = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}', ALLOW_CONTEXT='other')
            result = subprocess.run([str(HERE / 'status')], env=env, capture_output=True, text=True, timeout=60)
            self.assertNotIn("expected 'other'", result.stderr)

    def test_namespace_is_not_configurable(self):
        text = (HERE / 'lib.sh').read_text()
        self.assertIn('readonly NS=py313-prod-local', text)
        for name in SCRIPTS:
            self.assertNotIn('NS=', (HERE / name).read_text().replace('$NS', ''), name)

    def test_no_script_deletes_docker_objects_or_other_namespaces(self):
        forbidden = ('docker rm', 'docker rmi', 'docker volume', 'docker system', 'docker image prune', 'docker container prune',
                     'delete namespace kube', 'delete ns ')
        for name in (*SCRIPTS, 'lib.sh'):
            text = (HERE / name).read_text()
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f'{name}: {phrase}')
        down = (HERE / 'down').read_text()
        self.assertEqual(down.count('delete namespace'), 1)
        self.assertIn('delete namespace "$NS"', down)

    def test_scripts_are_executable_and_pass_bash_n(self):
        for name in (*SCRIPTS, 'lib.sh'):
            path = HERE / name
            if name != 'lib.sh':
                self.assertTrue(os.access(path, os.X_OK), name)
            subprocess.run(['bash', '-n', str(path)], check=True)


TRAEFIK_SCRIPTS = ('traefik-install', 'traefik-status', 'traefik-smoke', 'traefik-down', 'gen-local-tls')
DOMAIN = 'local-prod.7mud.com'


def stub_bin(tmp, kubectl_body='exit 0', extra=()):
    """A directory of stub commands in front of PATH; every kubectl/docker call is appended to calls.log."""
    bin_dir = Path(tmp) / 'bin'
    bin_dir.mkdir(exist_ok=True)
    log = Path(tmp) / 'calls.log'
    (bin_dir / 'kubectl').write_text(
        '#!/bin/sh\n'
        'if [ "$1 $2" = "config current-context" ]; then echo orbstack; exit 0; fi\n'
        f'echo "kubectl $@" >> {log}\n{kubectl_body}\n')
    (bin_dir / 'docker').write_text(f'#!/bin/sh\necho "docker $@" >> {log}\nexit 0\n')
    for name in extra:
        (bin_dir / name).write_text(f'#!/bin/sh\necho "{name} $@" >> {log}\nexit 0\n')
    for path in bin_dir.iterdir():
        path.chmod(0o755)
    return bin_dir, log


def run_script(name, tmp, bin_dir, **env):
    full = dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}', LOCAL_DIR=str(Path(tmp) / 'local'), **env)
    full.pop('ALLOW_CONTEXT', None)
    for key in ('INGRESS',):
        if key not in env:
            full.pop(key, None)
    return subprocess.run([str(HERE / name)], env=full, capture_output=True, text=True, timeout=120)


class TraefikPostprocessTest(unittest.TestCase):
    def run_process(self, directory, scheme='https', cookie='.' + DOMAIN):
        with contextlib.redirect_stdout(io.StringIO()):
            return postprocess_config.process(directory, 'lms.' + DOMAIN, 'studio.' + DOMAIN,
                                              '/edx/app/edxapp/py313-config/es-ca.crt', 'py313_search', scheme, cookie)

    def write(self, directory, mutate=None):
        for system in ('lms', 'cms'):
            env = env_json(system)
            env.update({'LMS_BASE': 'lms.' + DOMAIN, 'CMS_BASE': 'studio.' + DOMAIN, 'LMS_ROOT_URL': 'https://lms.' + DOMAIN,
                        'LMS_INTERNAL_ROOT_URL': 'https://lms.' + DOMAIN, 'SESSION_COOKIE_SECURE': True,
                        'SESSION_COOKIE_DOMAIN': '.' + DOMAIN,
                        'ALLOWED_HOSTS': ['localhost', 'lms.' + DOMAIN, 'studio.' + DOMAIN]})
            if mutate:
                mutate(system, env)
            (directory / f'{system}.env.json').write_text(json.dumps(env))
            (directory / f'{system}.auth.json').write_text(json.dumps(auth_json(system)))

    def test_traefik_mode_checks_pass_and_fail_on_each_drift(self):
        def drift(key, value):
            def mutate(system, env):
                env[key] = value
            return mutate
        with tempfile.TemporaryDirectory() as tmp:
            self.write(Path(tmp))
            self.assertEqual(self.run_process(Path(tmp)), [])
        for key, value in (('SESSION_COOKIE_SECURE', False), ('SESSION_COOKIE_DOMAIN', None), ('LMS_ROOT_URL', 'http://lms.' + DOMAIN),
                           ('LMS_INTERNAL_ROOT_URL', 'http://localhost:18000'), ('ALLOWED_HOSTS', ['localhost'])):
            with tempfile.TemporaryDirectory() as tmp:
                self.write(Path(tmp), drift(key, value))
                self.assertTrue(self.run_process(Path(tmp)), key)


class TraefikScriptsTest(unittest.TestCase):
    def test_wrong_context_is_refused_before_any_cluster_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / 'bin'
            bin_dir.mkdir()
            log = Path(tmp) / 'calls.log'
            stub = bin_dir / 'kubectl'
            stub.write_text(f'#!/bin/sh\nif [ "$1 $2" = "config current-context" ]; then echo production-cluster; exit 0; fi\necho "$@" >> {log}\nexit 0\n')
            stub.chmod(0o755)
            for name in TRAEFIK_SCRIPTS[:4]:
                result = run_script(name, tmp, bin_dir)
                self.assertNotEqual(result.returncode, 0, name)
                self.assertIn("expected 'orbstack'", result.stderr, name)
            self.assertFalse(log.exists())

    def test_fixed_namespaces_and_no_docker_or_foreign_deletion(self):
        lib = (HERE / 'lib.sh').read_text()
        self.assertIn('readonly TNS=traefik', lib)
        self.assertIn('readonly NS=py313-prod-local', lib)
        forbidden = ('docker rm', 'docker rmi', 'docker volume', 'docker system', 'docker image prune', 'docker container prune',
                     'delete namespace kube', 'delete ns ', 'delete crd --all', '--all-namespaces', ' -A ')
        for name in (*TRAEFIK_SCRIPTS, 'traefik-doctor'):
            text = (HERE / name).read_text()
            for phrase in forbidden:
                self.assertNotIn(phrase, text, f'{name}: {phrase}')
            self.assertNotIn('NS=', text.replace('$NS', '').replace('$TNS', '').replace('"$MODE_ANNOTATION', ''), name)
        down = (HERE / 'traefik-down').read_text()
        self.assertEqual(down.count('delete namespace'), 1)
        self.assertIn('delete namespace "$TNS"', down)
        self.assertNotIn('delete namespace "$NS"', down)
        self.assertIn('kc -n kube-system delete configmap coredns-custom', down)
        self.assertEqual(down.count('kube-system delete'), 1)

    def test_scripts_are_executable_and_pass_bash_n(self):
        for name in (*TRAEFIK_SCRIPTS, 'traefik-doctor'):
            self.assertTrue(os.access(HERE / name, os.X_OK), name)
            subprocess.run(['bash', '-n', str(HERE / name)], check=True)

    def down_stub(self, keys='local-prod.override', crd='customresourcedefinition.apiextensions.k8s.io/middlewares.traefik.io'):
        return f"""
args="$*"
case "$args" in
  *'jsonpath'*'part-of'*) printf openedx ;;
  *'jsonpath'*'feature'*) printf traefik-local ;;
  *'go-template'*) printf '{keys}' ;;
  *'get crd --selector'*) echo {crd} ;;
  *'get configmap --selector'*) printf 'configmap/static-nginx-conf-abc\\nconfigmap/local-ca-bundle\\n' ;;
esac
exit 0"""

    def test_down_removes_only_labelled_objects_and_keeps_the_app_namespace_and_ca_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir, log = stub_bin(tmp, self.down_stub())
            result = run_script('traefik-down', tmp, bin_dir)
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = log.read_text().splitlines()
            deletes = [c for c in calls if ' delete ' in c]
            self.assertIn('kubectl --context orbstack -n py313-prod-local delete ingress,deployment,service --selector py313.learningtribes.com/feature=traefik-local --ignore-not-found --wait=true', deletes)
            self.assertIn('kubectl --context orbstack delete namespace traefik --wait=true --timeout=300s', deletes)
            self.assertIn('kubectl --context orbstack delete clusterrole traefik-py313-local', deletes)
            self.assertIn('kubectl --context orbstack delete customresourcedefinition.apiextensions.k8s.io/middlewares.traefik.io', deletes)
            self.assertIn('kubectl --context orbstack -n kube-system delete configmap coredns-custom', deletes)
            self.assertTrue(any('rollout restart deployment/coredns' in c for c in calls))
            self.assertTrue(any(c.endswith('delete configmap/static-nginx-conf-abc') for c in deletes))
            for call in deletes:
                self.assertNotIn('namespace py313-prod-local', call)
                self.assertNotIn('local-ca-bundle', call)
                self.assertNotIn('local-prod-tls', call)
                self.assertNotIn(' secret', call)

    def test_down_refuses_foreign_coredns_keys_and_foreign_crds(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir, log = stub_bin(tmp, self.down_stub(keys='local-prod.override\\nrewrite.override'))
            result = run_script('traefik-down', tmp, bin_dir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('refusing to delete', result.stderr)
            self.assertNotIn('delete configmap coredns-custom', log.read_text())
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir, log = stub_bin(tmp, self.down_stub(crd='customresourcedefinition.apiextensions.k8s.io/certificates.cert-manager.io'))
            result = run_script('traefik-down', tmp, bin_dir)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('cert-manager', ' '.join(c for c in log.read_text().splitlines() if ' delete ' in c))

    def test_up_refuses_to_switch_the_ingress_mode_of_an_existing_namespace(self):
        for mode_env, existing in (({'INGRESS': 'traefik'}, 'port-forward'), ({}, 'traefik')):
            with tempfile.TemporaryDirectory() as tmp:
                body = f'case "$*" in *"get namespace"*"jsonpath"*) printf {existing};; esac\nexit 0'
                bin_dir, log = stub_bin(tmp, body, extra=('openssl',))
                result = run_script('up', tmp, bin_dir, **mode_env)
                self.assertNotEqual(result.returncode, 0, mode_env)
                self.assertIn(f"created for ingress mode '{existing}'", result.stderr)
                self.assertIn('scripts/down', result.stderr)
                self.assertFalse([c for c in log.read_text().splitlines() if ' apply ' in c or ' create ' in c or ' annotate ' in c], 'nothing may change before the guard')

    def test_unknown_ingress_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir, log = stub_bin(tmp, extra=('openssl',))
            result = run_script('up', tmp, bin_dir, INGRESS='nginx')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("INGRESS must be unset or 'traefik'", result.stderr)

    def test_traefik_mode_accepts_only_its_own_application_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir, log = stub_bin(tmp, extra=('openssl',))
            result = run_script('up', tmp, bin_dir, INGRESS='traefik', APP_OVERLAY=str(HERE.parent / 'overlays/orbstack-local-all-workers'))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('supports only overlays/orbstack-local-traefik', result.stderr)

    def test_site_values_follow_the_mode(self):
        def value(key, **env):
            full = dict(os.environ, **env)
            full.pop('INGRESS', None) if 'INGRESS' not in env else None
            return subprocess.run(['bash', '-c', f'. "{HERE}/lib.sh"; bringup_value {key}'], env=full, capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(value('BRINGUP_LMS_DOMAIN'), 'localhost:18000')
        self.assertEqual(value('BRINGUP_LMS_DOMAIN', INGRESS='traefik'), 'lms.' + DOMAIN)
        self.assertEqual(value('BRINGUP_CMS_DOMAIN', INGRESS='traefik'), 'studio.' + DOMAIN)
        self.assertEqual(value('BRINGUP_SCHEME'), '')
        self.assertEqual(value('BRINGUP_SCHEME', INGRESS='traefik'), 'https')
        self.assertEqual(value('BRINGUP_ES_INDEX_PREFIX', INGRESS='traefik'), 'py313_prod_local')

    def test_smoke_of_the_port_forward_flow_refuses_traefik_namespaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir, log = stub_bin(tmp, 'case "$*" in *jsonpath*ingress-mode*) printf traefik;; esac\nexit 0')
            result = run_script('smoke', tmp, bin_dir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('use scripts/traefik-smoke', result.stderr)


class GenLocalTlsTest(unittest.TestCase):
    def run_tls(self, tmp):
        env = dict(os.environ, LOCAL_DIR=str(Path(tmp) / 'local'), NO_CLUSTER='1')
        return subprocess.run([str(HERE / 'gen-local-tls')], env=env, capture_output=True, text=True, timeout=120)

    @staticmethod
    def openssl(*args, stdin=None):
        return subprocess.run(['openssl', *args], capture_output=True, text=True, check=True).stdout

    def test_files_modes_names_validity_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = self.run_tls(tmp)
            self.assertEqual(first.returncode, 0, first.stderr)
            tls = Path(tmp) / 'local/tls'
            self.assertEqual(stat.S_IMODE(tls.stat().st_mode), 0o700)
            for name in ('ca.key', 'tls.key'):
                self.assertEqual(stat.S_IMODE((tls / name).stat().st_mode), 0o600, name)
            self.assertIn('PRIVATE KEY', (tls / 'ca.key').read_text().splitlines()[0])
            leaf = self.openssl('x509', '-in', str(tls / 'tls.crt'), '-noout', '-text')
            self.assertIn('DNS:*.%s, DNS:%s' % (DOMAIN, DOMAIN), leaf)
            self.assertIn('prime256v1', leaf)
            self.assertIn('TLS Web Server Authentication', leaf)
            self.assertIn('CA:FALSE', leaf)
            dates = self.openssl('x509', '-in', str(tls / 'tls.crt'), '-noout', '-startdate', '-enddate')
            fmt = '%b %d %H:%M:%S %Y %Z'
            start, end = (datetime.datetime.strptime(l.split('=')[1], fmt) for l in dates.strip().splitlines())
            self.assertLessEqual((end - start).days, 397)
            ca = self.openssl('x509', '-in', str(tls / 'ca.crt'), '-noout', '-text')
            self.assertIn('CA:TRUE, pathlen:0', ca)
            self.assertIn('Certificate Sign, CRL Sign', ca)
            self.assertIn('DNS:' + DOMAIN, ca)
            self.openssl('verify', '-CAfile', str(tls / 'ca.crt'), '-purpose', 'sslserver', str(tls / 'tls.crt'))
            before = {n: (tls / n).read_bytes() for n in ('ca.crt', 'ca.key', 'tls.crt', 'tls.key')}
            second = self.run_tls(tmp)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(before, {n: (tls / n).read_bytes() for n in before}, 'a rerun must not rotate anything')
            self.assertEqual(second.stdout.count('kept the existing'), 2)
            (tls / 'tls.crt').unlink()
            third = self.run_tls(tmp)
            self.assertEqual(third.returncode, 0, third.stderr)
            self.assertEqual(before['ca.crt'], (tls / 'ca.crt').read_bytes(), 'the CA (trusted by the user) survives a leaf renewal')
            self.assertNotEqual(before['tls.crt'], (tls / 'tls.crt').read_bytes())

    def test_ca_cannot_vouch_for_other_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.run_tls(tmp)
            tls = Path(tmp) / 'local/tls'
            work = Path(tmp)
            (work / 'x.cnf').write_text('[req]\ndistinguished_name=dn\nprompt=no\n[dn]\nCN=evil.example.com\n')
            (work / 'x.ext').write_text('subjectAltName=DNS:evil.example.com\nextendedKeyUsage=serverAuth\n')
            self.openssl('req', '-new', '-newkey', 'ec', '-pkeyopt', 'ec_paramgen_curve:P-256', '-nodes', '-keyout', str(work / 'x.key'),
                         '-config', str(work / 'x.cnf'), '-out', str(work / 'x.csr'))
            self.openssl('x509', '-req', '-in', str(work / 'x.csr'), '-CA', str(tls / 'ca.crt'), '-CAkey', str(tls / 'ca.key'),
                         '-set_serial', '7', '-days', '1', '-extfile', str(work / 'x.ext'), '-out', str(work / 'x.crt'))
            verdict = subprocess.run(['openssl', 'verify', '-CAfile', str(tls / 'ca.crt'), str(work / 'x.crt')], capture_output=True, text=True)
            self.assertNotEqual(verdict.returncode, 0)
            self.assertIn('permitted subtree violation', verdict.stdout + verdict.stderr)


class DoctorTest(unittest.TestCase):
    def test_doctor_is_read_only_and_prints_the_user_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([str(HERE / 'gen-local-tls')], env=dict(os.environ, LOCAL_DIR=str(Path(tmp) / 'local'), NO_CLUSTER='1'),
                           check=True, capture_output=True)
            bin_dir, log = stub_bin(tmp, extra=('sudo', 'security', 'lsof', 'curl'))
            (bin_dir / 'dscacheutil').write_text('#!/bin/sh\necho "dscacheutil $@" >> %s\nprintf "name: x\\nip_address: 198.18.4.94\\n"\n' % log)
            (bin_dir / 'scutil').write_text('#!/bin/sh\necho "scutil $@" >> %s\nprintf "<dictionary> {\\n  HTTPSEnable : 1\\n  HTTPSPort : 7890\\n  HTTPSProxy : 127.0.0.1\\n}\\n"\n' % log)
            (bin_dir / 'curl').write_text('#!/bin/sh\necho "curl $@" >> %s\nprintf 000\nexit 7\n' % log)
            (bin_dir / 'security').write_text('#!/bin/sh\necho "security $@" >> %s\nexit 1\n' % log)
            for path in bin_dir.iterdir():
                path.chmod(0o755)
            result = subprocess.run([str(HERE / 'traefik-doctor')], env=dict(os.environ, PATH=f'{bin_dir}:{os.environ["PATH"]}', LOCAL_DIR=str(Path(tmp) / 'local')),
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 1)
            out = result.stdout
            self.assertIn('198.18.0.0/16', out)
            self.assertIn('DOMAIN-SUFFIX,%s,DIRECT' % DOMAIN, out)
            self.assertIn("'+.%s'" % DOMAIN, out)
            self.assertIn('fake-ip-filter', out)
            self.assertIn('security add-trusted-cert -r trustRoot -k ~/Library/Keychains/login.keychain-db', out)
            calls = log.read_text()
            self.assertNotIn('sudo', calls)
            self.assertNotIn('kubectl', calls)
            self.assertNotIn('docker', calls)
            self.assertNotIn('add-trusted-cert', calls)
            for line in calls.splitlines():
                if line.startswith('security '):
                    self.assertTrue(line.startswith('security verify-cert'), line)
                if line.startswith('curl '):
                    self.assertNotIn('-X ', line)
                    self.assertNotIn('--data', line)
            for forbidden in ('/etc/hosts', 'networksetup', 'tee '):
                self.assertNotIn(forbidden, (HERE / 'traefik-doctor').read_text().replace('/etc/hosts file', ''), forbidden)


if __name__ == '__main__':
    unittest.main()
