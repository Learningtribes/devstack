"""Author, publish and release the acceptance course over the Studio HTTP API, then seed its roles.

`build` uses the run-scoped staff identity (a Studio login user, not a Django superuser) and
needs LMS-independent Studio only. `seed` runs the replay's course seeding in the runtime.
"""
import argparse
import json
import os
from pathlib import Path

from core import load_config, ownership, shell
from http_client import credentials, login_cms, run_root

IDS_FILE = 'acceptance-course.json'
SEED_SCRIPT = '/startup/seed_rebuild_course_acceptance.py'


def display_name(config):
    return config['run_id'] + ' acceptance course'


def html_marker(config):
    return config['run_id'] + ' acceptance html body'


def build_course(config):
    key = config['course_key']
    org, number, run = key.split(':', 1)[1].split('+')
    client, status, body = login_cms(config, credentials(config)['staff'])
    if status != 200 or b'"success": true' not in body:
        raise SystemExit('Studio staff login failed: HTTP %s' % status)
    status, _, body = client.req('POST', '/course/', json_body={
        'org': org, 'number': number, 'run': run, 'display_name': display_name(config)})
    print('create course', status, body[:200])
    if status != 200 or b'course_key' not in body:
        raise SystemExit('Course creation failed')
    course_usage = 'block-v1:%s+%s+%s+type@course+block@course' % (org, number, run)

    def add(parent, category, name):
        status, _, body = client.req('POST', '/xblock/', json_body={
            'parent_locator': parent, 'category': category, 'display_name': name})
        print('add', category, status)
        if status != 200:
            raise SystemExit('Adding %s failed: HTTP %s' % (category, status))
        return json.loads(body)['locator']

    chapter = add(course_usage, 'chapter', 'Section 1')
    sequential = add(chapter, 'sequential', 'Subsection 1')
    vertical = add(sequential, 'vertical', 'Unit 1')
    html = add(vertical, 'html', 'Text 1')
    for label, path, payload in [
            ('save html', '/xblock/' + html, {'data': '<p>%s</p>' % html_marker(config), 'metadata': {}}),
            ('publish unit', '/xblock/' + vertical, {'publish': 'make_public'})]:
        status, _, body = client.req('POST', path, json_body=payload)
        print(label, status)
        if status != 200:
            raise SystemExit(label + ' failed: HTTP %s' % status)
    status, _, body = client.get('/settings_update/details/' + key, headers={'Accept': 'application/json'})
    if status != 200:
        raise SystemExit('Reading course details failed: HTTP %s' % status)
    details = json.loads(body)
    # A past start date plus the released status makes the course visible to enrolled learners.
    details.update(start_date='2020-01-01T00:00:00Z', course_status='released')
    status, _, body = client.req('POST', '/settings_update/details/' + key, json_body=details)
    print('release course', status)
    if status != 200:
        raise SystemExit('Releasing the course failed: HTTP %s' % status)
    ids = {'course_key': key, 'course_usage': course_usage, 'chapter': chapter, 'sequential': sequential,
           'vertical': vertical, 'html': html}
    target = run_root(config) / IDS_FILE
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644), 'w') as stream:
        stream.write(json.dumps(ids, indent=2, sort_keys=True) + '\n')
    print('PASS course built and released:', key)
    return ids


def seed_course(config):
    ownership(config)
    shell(config, 'lms', 'seed-rebuild-course-acceptance', SEED_SCRIPT)


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('action', choices=['build', 'seed'])
    args = parser.parse_args()
    config = load_config(args.config)
    {'build': build_course, 'seed': seed_course}[args.action](config)


if __name__ == '__main__':
    main()
