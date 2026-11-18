"""Post-processes the files of /startup/generate_aws_config.py for the local pods and checks them. Prints key names and verdicts only.

    uv run --no-project --python 3.13 python -B postprocess_config.py <dir> --lms-domain D --cms-domain D --es-ca-path P --es-user U
"""
import argparse
import json
from pathlib import Path
import sys

SYSTEMS = ('lms', 'cms')
DATA_MOUNT = '/edx/var/edxapp/data'


def load(directory, name):
    return json.loads((directory / name).read_text())


def store(directory, name, data):
    path = directory / name
    path.write_text(json.dumps(data, indent=1))
    path.chmod(0o600)


def process(directory, lms_domain, cms_domain, es_ca_path, es_user, scheme=None, cookie_domain=None):
    """Switches LOG_DESTINATION to console (pods log to stdout; the generator writes `file`), points every writable course-data path at
    the mounted data volume and returns a list of failed checks; every check reads the files back from disk.

    The settings default for these paths is /edx/app/edxapp/data, on the read-only root, and the generator keeps it in two places:
    cms GITHUB_REPO_ROOT (course import and export; cms/envs/aws.py reads it only from env.json, the generator never writes it) and
    the `fs_root` of every MODULESTORE store in lms.auth.json and cms.auth.json (a copy of the settings default taken before DATA_DIR
    is overridden; the split store creates <fs_root>/<org>/<course>/<run> whenever a course is loaded, so any course page would fail).

    With `scheme` (the Traefik mode) it also checks the root URLs, the cookie flags and that both site hosts are allowed hosts.
    """
    failures = []

    def expect(ok, text):
        print(('PASS   ' if ok else 'BLOCK  ') + text)
        if not ok:
            failures.append(text)

    for system in SYSTEMS:
        env = load(directory, f'{system}.env.json')
        env['LOG_DESTINATION'] = 'console'
        if system == 'cms':
            env['GITHUB_REPO_ROOT'] = DATA_MOUNT
        store(directory, f'{system}.env.json', env)
        env = load(directory, f'{system}.env.json')
        auth = load(directory, f'{system}.auth.json')
        for store_config in auth.get('MODULESTORE', {}).get('default', {}).get('OPTIONS', {}).get('stores', []):
            store_config.setdefault('OPTIONS', {})['fs_root'] = DATA_MOUNT
        store(directory, f'{system}.auth.json', auth)
        auth = load(directory, f'{system}.auth.json')
        entry = (env.get('ELASTIC_SEARCH_CONFIG') or [{}])[0]
        expect(env.get('LOG_DESTINATION') == 'console', f'{system}.env.json LOG_DESTINATION is console')
        if system == 'cms':
            expect(env.get('GITHUB_REPO_ROOT') == DATA_MOUNT == env.get('DATA_DIR'),
                   f'{system}.env.json GITHUB_REPO_ROOT is the writable data mount {DATA_MOUNT}')
        expect(env.get('LMS_BASE') == lms_domain and env.get('CMS_BASE') == cms_domain,
               f'{system}.env.json site domains are {lms_domain} / {cms_domain}')
        hosts = env.get('ALLOWED_HOSTS', [])
        expect('localhost' in hosts and '*' not in hosts, f'{system}.env.json ALLOWED_HOSTS has localhost and no wildcard')
        if scheme:
            root = f'{scheme}://{lms_domain}'
            expect(env.get('LMS_ROOT_URL') == root and env.get('LMS_INTERNAL_ROOT_URL') == root,
                   f'{system}.env.json LMS_ROOT_URL and LMS_INTERNAL_ROOT_URL are {root}')
            expect(env.get('SESSION_COOKIE_SECURE') is (scheme == 'https'), f'{system}.env.json SESSION_COOKIE_SECURE follows the {scheme} scheme')
            expect(env.get('SESSION_COOKIE_DOMAIN') == cookie_domain, f'{system}.env.json SESSION_COOKIE_DOMAIN is {cookie_domain!r}')
            expect(lms_domain in hosts and cms_domain in hosts, f'{system}.env.json ALLOWED_HOSTS has both site hosts')
        expect(entry.get('use_ssl') is True and entry.get('verify_certs') is True and entry.get('ca_certs') == es_ca_path
               and (entry.get('http_auth') or [None])[0] == es_user,
               f'{system}.env.json Elasticsearch: TLS, verified, CA {es_ca_path}, user {es_user}')
        expect(env.get('LOG_DIR') == f'/edx/var/log/{system}', f'{system}.env.json LOG_DIR is the mounted /edx/var/log/{system}')
        expect(env.get('MEDIA_ROOT') == '/edx/var/edxapp/media' and env.get('DATA_DIR') == '/edx/var/edxapp/data',
               f'{system}.env.json MEDIA_ROOT and DATA_DIR are the writable mounts')
        fs_roots = [item.get('OPTIONS', {}).get('fs_root') for item in auth.get('MODULESTORE', {}).get('default', {}).get('OPTIONS', {}).get('stores', [])]
        expect(fs_roots and set(fs_roots) == {DATA_MOUNT}, f'{system}.auth.json MODULESTORE fs_root of every store is the writable data mount (stores: {len(fs_roots)})')
        expect(auth.get('CELERY_BROKER_PASSWORD') and auth.get('SECRET_KEY'), f'{system}.auth.json has broker password and SECRET_KEY (not printed)')
        expect(('JWT_PRIVATE_SIGNING_KEY' in auth) == (system == 'lms'), f'{system}.auth.json JWT_PRIVATE_SIGNING_KEY only for lms')
        print('keys', f'{system}.env.json:', ' '.join(sorted(env)))
        print('keys', f'{system}.auth.json:', ' '.join(sorted(auth)))
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--lms-domain', required=True)
    parser.add_argument('--cms-domain', required=True)
    parser.add_argument('--es-ca-path', required=True)
    parser.add_argument('--es-user', required=True)
    parser.add_argument('--scheme', choices=('http', 'https'), help='enables the URL, cookie and host checks of the Traefik mode')
    parser.add_argument('--cookie-domain')
    args = parser.parse_args(argv)
    failures = process(args.directory, args.lms_domain, args.cms_domain, args.es_ca_path, args.es_user, args.scheme, args.cookie_domain)
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
