"""Assign only this configuration's natural-key Sites to the frozen theme."""
from django.conf import settings
from django.contrib.sites.models import Site
from openedx.core.djangoapps.theming.models import SiteTheme

sites = Site.objects.filter(domain__in=[settings.LMS_BASE, settings.CMS_BASE])
assert sites.count() == 2
for site in sites:
    theme, created = SiteTheme.objects.get_or_create(site=site, defaults={'theme_dir_name': 'hawthorn'})
    assert theme.theme_dir_name == 'hawthorn'
print('PASS two natural-key site themes')
