"""Initialize a registered fresh local schema; never clear or fake migrations."""
import json
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

inventory = json.loads(Path('/startup/schema-app-inventory.json').read_text())
expected = {entry['label'] for entry in inventory['lms'] + inventory['cms']}
actual = set(apps.app_configs)
assert expected == actual, 'App inventory changed; review before schema initialization'
assert set(settings.MIGRATION_MODULES) == actual
assert all(value is None for value in settings.MIGRATION_MODULES.values())
assert connection.settings_dict['NAME'].startswith(('py313_startup_', 'py313_rebuild_'))
assert not MigrationRecorder(connection).applied_migrations(), 'Historical migration records forbidden here'
call_command('migrate', run_syncdb=True, interactive=False, skip_checks=True)
exec(compile(Path('/startup/reconcile_schema.py').read_text(), '/startup/reconcile_schema.py', 'exec'))
assert not MigrationRecorder(connection).applied_migrations()
exec(compile(Path('/startup/audit_local_schema.py').read_text(), '/startup/audit_local_schema.py', 'exec'))
