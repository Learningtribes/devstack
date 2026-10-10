# -*- coding: utf-8 -*-
"""Run the R1 Studio edit/publish provisioner against an E6 private-store stack.

E6 serves the canonical ``localhost:18010`` / ``localhost:18000`` Sites of the
private clone. R1 renamed fixed Site ids to per-gate domains and replaced their
configuration; here the two existing Site rows are kept and only the keys the
gate needs are merged in. Studio's course listing reads ``course_org_filter``
through the server's cached Site, so ``provision`` runs before the servers
start (``PY36_R2_E6_PRESTART``); the other actions run against the live stack.
usage: r2-e6-studio.py {provision|preflight|reset|midcondition|postflight}
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import imp
import os

R1 = imp.load_source(
    'r1_studio_provision',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'provision-p1b-studio-edit-publish.py'),
)
for _runtime, _fixture in R1.FIXTURES.items():
    _fixture.update({
        'site_cms': 'localhost:18010',
        'site_lms': 'localhost:18000',
        'namespace': 'py36-r2-e6-{}'.format(_runtime),
    })


def _ensure_canonical_sites(fixture_data):
    site_ids = {}
    for service, domain in (('cms', fixture_data['site_cms']), ('lms', fixture_data['site_lms'])):
        site = R1.Site.objects.get(domain=domain)
        config = R1.SiteConfiguration.objects.get(site=site)
        values = dict(config.values or {})
        previous = values.get('course_org_filter')
        values.update({
            'course_org_filter': fixture_data['course_key_object'].org,
            'ENABLE_LAST_ACTIVITY': True,
        })
        config.enabled = True
        config.values = values
        config.save()
        site_ids[service] = site.id
        print('E6_STUDIO_SITE service={} site_id={} domain={} course_org_filter={}->{}'.format(
            service, site.id, domain, previous, values['course_org_filter'],
        ))
    return site_ids


R1.ensure_sites = _ensure_canonical_sites

if __name__ == '__main__':
    R1.main()
