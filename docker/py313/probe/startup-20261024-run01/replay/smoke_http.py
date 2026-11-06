"""HTTP smoke of the running LMS and Studio. Prints a PASS/FAIL table; never prints credentials or cookies.

Three expectations are 404 by design in this Platform build: LMS /admin/ (Django admin site off),
/courses and /api/enrollment/v1/enrollment (routes not registered).
"""
import argparse
import json
import os
from pathlib import Path
import re
import time

from acceptance_course import html_marker
from core import load_config
from http_client import Client, base_urls, credentials, dev_superuser, login_cms, login_lms, run_root

RESULT_FILE = 'smoke-result.json'


class Smoke:
    def __init__(self):
        self.rows = []

    def record(self, name, status, expected, note=''):
        ok = status in expected
        self.rows.append((name, 'PASS' if ok else 'FAIL', status, note))
        print('%-5s %-48s %s %s' % ('PASS' if ok else 'FAIL', name, status, note), flush=True)

    def check(self, name, client, method, path, expected=(200,), contains=None, **kwargs):
        started = time.time()
        try:
            status, headers, body = client.req(method, path, **kwargs)
        except Exception as error:  # noqa: BLE001 - a transport failure is a FAIL row, not a crash
            self.record(name, 'EXC', expected, repr(error)[:150])
            return None, b''
        note = '%.1fs %dB' % (time.time() - started, len(body))
        if status in expected and contains and contains.encode() not in body:
            status, note = 'BODY', note + ' missing %r' % contains
        if status in (301, 302, 303):
            note += ' -> ' + headers.get('Location', '')[:80]
        self.record(name, status, expected, note)
        return headers, body

    def failures(self):
        return [row for row in self.rows if row[1] != 'PASS']


def run_smoke(config):
    smoke = Smoke()
    urls = base_urls(config)
    key = config['course_key']
    marker = html_marker(config)
    creds = credentials(config)
    anon = Client(urls['lms'])
    smoke.check('LMS /heartbeat', anon, 'GET', '/heartbeat', contains='OK')
    smoke.check('LMS / (index)', anon, 'GET', '/', expected=(200, 302))
    _, login_html = smoke.check('LMS /login (GET)', anon, 'GET', '/login', contains='<html')
    asset = re.search(rb'(/static/[^"\']+\.(?:css|js))', login_html or b'')
    if asset:
        smoke.check('LMS static asset ' + asset.group(1).decode()[:60], anon, 'GET', asset.group(1).decode())
    else:
        smoke.record('LMS static asset (none in login HTML)', 'NONE', (200,))
    smoke.check('LMS /admin/ (404 by design)', anon, 'GET', '/admin/', expected=(200, 302, 404))
    smoke.check('LMS /courses anon (404 by design)', anon, 'GET', '/courses', expected=(200, 404))

    lms, status, body = login_lms(config, creds['learner'])
    smoke.record('LMS login POST (login_session)', status, (200,), body.decode(errors='replace')[:60])
    smoke.check('LMS /dashboard', lms, 'GET', '/dashboard', contains='dashboard')
    smoke.check('LMS /courses authed (404 by design)', lms, 'GET', '/courses', expected=(200, 404))
    smoke.check('LMS course about', lms, 'GET', '/courses/%s/about' % key)
    smoke.check('LMS courseware (follow)', lms.following(), 'GET', '/courses/%s/courseware/' % key, contains=marker)
    smoke.check('LMS progress', lms, 'GET', '/courses/%s/progress' % key)
    smoke.check('LMS /api/courses/v1/courses/', lms, 'GET', '/api/courses/v1/courses/', contains='results')
    smoke.check('LMS /api/user/v1/me', lms, 'GET', '/api/user/v1/me', contains='username')
    smoke.check('LMS /api/enrollment/v1/enrollment (404 by design)', lms, 'GET', '/api/enrollment/v1/enrollment',
                expected=(200, 404))
    smoke.check('LMS /api/courses/v1/courses/<id>', lms, 'GET', '/api/courses/v1/courses/%s' % key,
                contains='course_id')

    cms_anon = Client(urls['cms'])
    smoke.check('CMS /heartbeat', cms_anon, 'GET', '/heartbeat', contains='OK')
    smoke.check('CMS /signin', cms_anon, 'GET', '/signin', contains='<html')
    cms, status, body = login_cms(config, creds['staff'])
    smoke.record('CMS login POST (login_post)', status, (200,), body.decode(errors='replace')[:60].replace('\n', ' '))
    smoke.check('CMS /home/', cms, 'GET', '/home/', contains='<html')
    smoke.check('CMS /course/<id> outline', cms, 'GET', '/course/%s' % key, contains='Section 1')
    smoke.check('CMS /settings/details/<id>', cms, 'GET', '/settings/details/%s' % key, contains='<html',
                headers={'Accept': 'text/html'})
    smoke.check('CMS xblock handler GET (course root)', cms, 'GET',
                '/xblock/block-v1:%s+type@course+block@course' % key.split(':', 1)[1],
                headers={'Accept': 'application/json'}, contains='display_name')
    smoke.check('CMS /assets/<id>/', cms, 'GET', '/assets/%s/' % key, contains='<html',
                headers={'Accept': 'text/html'})
    smoke.check('CMS /assets/<id>/ (json)', cms, 'GET', '/assets/%s/' % key, headers={'Accept': 'application/json'})
    return smoke


def run_superuser(config):
    """Log in as the local devstack superuser: LMS session then /dashboard, Studio /login_post then /home/."""
    smoke = Smoke()
    identity = dev_superuser()
    lms, status, _ = login_lms(config, identity)
    smoke.record('LMS superuser login_session', status, (200,))
    smoke.check('LMS superuser /dashboard', lms, 'GET', '/dashboard', contains='dashboard')
    cms, status, body = login_cms(config, identity)
    smoke.record('CMS superuser login_post', status, (200,), body.decode(errors='replace')[:60].replace('\n', ' '))
    smoke.check('CMS superuser /home/', cms, 'GET', '/home/', contains='<html')
    return smoke


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('suite', choices=['smoke', 'superuser'])
    args = parser.parse_args()
    config = load_config(args.config)
    smoke = {'smoke': run_smoke, 'superuser': run_superuser}[args.suite](config)
    print('\nTOTAL', len(smoke.rows), 'FAIL', len(smoke.failures()))
    target = run_root(config) / (args.suite + '-result.json' if args.suite != 'smoke' else RESULT_FILE)
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), 'w') as stream:
        stream.write(json.dumps(smoke.rows, indent=1) + '\n')
    raise SystemExit(1 if smoke.failures() else 0)


if __name__ == '__main__':
    main()
