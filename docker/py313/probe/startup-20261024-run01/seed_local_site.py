"""Create explicit organization configuration in the isolated acceptance database."""
from django.conf import settings
from django.contrib.sites.models import Site
from django.db import transaction
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration

assert settings.DATABASES['default']['NAME'].startswith('py313_'), 'Refuse a non-acceptance database'
with transaction.atomic():
    site = Site.objects.select_for_update().get(pk=settings.SITE_ID)
    assert site.domain in ('example.com', 'localhost'), 'Refuse to overwrite another site'
    site.domain = 'localhost'
    site.name = 'Python 3.13 local acceptance'
    site.save(update_fields=['domain', 'name'])
    configuration, created = SiteConfiguration.objects.get_or_create(site=site, defaults={'values': {}})
    assert isinstance(configuration.values, dict)
    values = dict(configuration.values)
    assert values.get('course_org_filter', 'PY313') == 'PY313', 'Refuse to replace another organization'
    values.update(course_org_filter='PY313', site_domain='localhost',
                  LMS_ROOT_URL='http://localhost:18000', CMS_ROOT_URL='http://localhost:18010',
                  show_only_org_on_student_dashboard=True)
    configuration.values = values
    configuration.enabled = True
    configuration.save()
Site.objects.clear_cache()
print('Local site configuration ready; organization PY313; created:', created)
