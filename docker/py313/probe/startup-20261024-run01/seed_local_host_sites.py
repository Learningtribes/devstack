"""Register local sites by natural key and emit their runtime PK mapping."""
import json
from pathlib import Path

from django.conf import settings
from django.contrib.sites.models import Site
from django.db import transaction
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration

assert settings.DATABASES['default']['NAME'].startswith('py313_')
site_ids = {}
with transaction.atomic():
    for domain in ('localhost:18000', 'localhost:18010'):
        site, site_created = Site.objects.get_or_create(domain=domain, defaults={'name': domain})
        cfg, created = SiteConfiguration.objects.get_or_create(site=site, defaults={'values': {}, 'enabled': True})
        values = dict(cfg.values)
        for key, value in {
            'course_org_filter': 'PY313', 'site_domain': domain,
            'LMS_ROOT_URL': 'http://localhost:18000', 'CMS_ROOT_URL': 'http://localhost:18010',
            'show_only_org_on_student_dashboard': True,
        }.items():
            values.setdefault(key, value)
        cfg.values = values
        cfg.save()
        site_ids[domain] = site.pk
        print(
            'Local host configuration ready:', domain,
            'site created:', site_created,
            'configuration created:', created,
        )
Site.objects.clear_cache()
mapping = Path('/runtime/config/site-ids.json')
mapping.parent.mkdir(parents=True, exist_ok=True)
tmp = mapping.with_suffix('.json.tmp')
tmp.write_text(json.dumps(site_ids, sort_keys=True) + '\n')
tmp.replace(mapping)
print('Wrote domain-keyed runtime Site map:', ', '.join(sorted(site_ids)))
