"""Fill missing local host site settings without changing user-managed site/theme rows."""
from django.conf import settings
from django.contrib.sites.models import Site
from django.db import transaction
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration
assert settings.DATABASES['default']['NAME'].startswith('py313_')
with transaction.atomic():
    for domain in ('localhost:18000', 'localhost:18010'):
        site = Site.objects.get(domain=domain)
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
        print('Local host configuration ready:', domain, 'created:', created)
Site.objects.clear_cache()
