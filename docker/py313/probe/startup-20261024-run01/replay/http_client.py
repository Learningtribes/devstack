"""Stdlib HTTP helpers for the local LMS/CMS: heartbeat, cookie sessions and logins.

Everything is derived from the replay config; credentials are read at call time from the
protected files and never printed.
"""
import http.cookiejar
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

from core import DEV_SUPERUSER_KEYS

DEV_SUPERUSER_DEFAULTS = dict(zip(DEV_SUPERUSER_KEYS, ('edx', 'edx@example.com', 'edx')))


def base_urls(config):
    return {'lms': 'http://localhost:%d' % config['lms_port'], 'cms': 'http://localhost:%d' % config['cms_port']}


def run_root(config):
    """Directory that holds the run's evidence, export, private inputs and bring-up logs."""
    return Path(config['evidence_dir']).parent


def credentials(config):
    return json.loads(Path(config['credentials_file']).read_text())


def dev_superuser():
    return {key.rsplit('_', 1)[1].lower(): os.environ.get(key, default)
            for key, default in DEV_SUPERUSER_DEFAULTS.items()}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, base, follow=False):
        self.base = base
        self.jar = http.cookiejar.CookieJar()
        handlers = [urllib.request.HTTPCookieProcessor(self.jar)]
        if not follow:
            handlers.append(NoRedirect())
        self.opener = urllib.request.build_opener(*handlers)

    def following(self):
        """Same session, following redirects."""
        other = Client(self.base, follow=True)
        other.jar = self.jar
        other.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        return other

    def csrf(self):
        return next((cookie.value for cookie in self.jar if cookie.name == 'csrftoken'), '')

    def req(self, method, path, data=None, json_body=None, headers=None, timeout=120):
        url = path if path.startswith('http') else self.base + path
        hdrs = {'X-CSRFToken': self.csrf(), 'Referer': self.base + '/', 'Origin': self.base,
                'X-Requested-With': 'XMLHttpRequest'} if method != 'GET' else {}
        body = None
        if json_body is not None:
            body = json.dumps(json_body).encode()
            hdrs['Content-Type'] = 'application/json'
            hdrs['Accept'] = 'application/json'
        elif data is not None:
            body = urllib.parse.urlencode(data).encode()
            hdrs['Content-Type'] = 'application/x-www-form-urlencoded'
        hdrs.update(headers or {})
        request = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            response = self.opener.open(request, timeout=timeout)
        except urllib.error.HTTPError as error:
            response = error
        raw = response.read()
        return response.status, dict(response.headers), raw

    def get(self, path, **kwargs):
        return self.req('GET', path, **kwargs)


def login_lms(config, identity):
    client = Client(base_urls(config)['lms'])
    client.get('/login')
    status, _, body = client.req('POST', '/user_api/v1/account/login_session/',
                                 data={'email': identity['email'], 'password': identity['password']})
    return client, status, body[:200]


def login_cms(config, identity):
    client = Client(base_urls(config)['cms'])
    client.get('/signin')
    status, _, body = client.req('POST', '/login_post', data={
        'email': identity['email'], 'password': identity['password'], 'honor_code': 'true'})
    return client, status, body[:200]


def heartbeat(base, timeout=5):
    """HTTP status of /heartbeat, or None while nothing answers."""
    try:
        with urllib.request.urlopen(base + '/heartbeat', timeout=timeout) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, OSError):
        return None


def wait_for_heartbeats(config, timeout, interval=3, sleep=time.sleep, clock=time.monotonic):
    """Block until LMS and CMS both answer 200; return {'lms': code, 'cms': code}."""
    urls = base_urls(config)
    deadline = clock() + timeout
    while True:
        codes = {name: heartbeat(url) for name, url in urls.items()}
        if all(code == 200 for code in codes.values()) or clock() >= deadline:
            return codes
        sleep(interval)
