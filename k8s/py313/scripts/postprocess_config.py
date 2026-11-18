"""Post-processes the files of /startup/generate_aws_config.py for the local pods and checks them. Prints key names and verdicts only.

    uv run --no-project --python 3.13 python -B postprocess_config.py <dir> --lms-domain D --cms-domain D --es-ca-path P --es-user U
"""
import argparse
import json
from pathlib import Path
import sys

SYSTEMS = ('lms', 'cms')


def load(directory, name):
    return json.loads((directory / name).read_text())


def store(directory, name, data):
    path = directory / name
    path.write_text(json.dumps(data, indent=1))
    path.chmod(0o600)


def process(directory, lms_domain, cms_domain, es_ca_path, es_user, scheme=None, cookie_domain=None):
    """Switches LOG_DESTINATION to console (pods log to stdout; the generator writes `file`) and returns a list of failed checks.

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
        store(directory, f'{system}.env.json', env)
        auth = load(directory, f'{system}.auth.json')
        entry = (env.get('ELASTIC_SEARCH_CONFIG') or [{}])[0]
        expect(env['LOG_DESTINATION'] == 'console', f'{system}.env.json LOG_DESTINATION is console')
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
