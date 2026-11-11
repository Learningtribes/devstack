"""Enable genuine completion tracking in the isolated local acceptance database."""
from django.conf import settings
from completion.waffle import ENABLE_COMPLETION_TRACKING_SWITCH
from waffle.models import Switch
from database_guard import is_replay_database

assert is_replay_database(settings.DATABASES['default']['NAME'], ('py313_',))
switch, created = Switch.objects.get_or_create(
    name=ENABLE_COMPLETION_TRACKING_SWITCH.name,
    defaults={'active': True, 'note': 'Local Python 3.13 completion acceptance'},
)
assert switch.active, 'Existing disabled switch requires explicit review'
print('Completion tracking enabled; created:', created)
