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
assert connection.settings_dict['NAME'] in {'py313_startup_20261024', 'py313_rebuild_20261024'}
assert not MigrationRecorder(connection).applied_migrations(), 'Historical migration records forbidden here'
call_command('migrate', run_syncdb=True, interactive=False, skip_checks=True)
exec(compile(Path('/startup/reconcile_schema.py').read_text(), '/startup/reconcile_schema.py', 'exec'))
assert not MigrationRecorder(connection).applied_migrations()
with connection.cursor() as cursor:
    tables = set(connection.introspection.table_names(cursor))
    models = [m for m in apps.get_models() if m._meta.managed and not m._meta.proxy and m._meta.can_migrate(connection)]
    for model in models:
        assert model._meta.db_table in tables, model._meta.label
        columns = {column.name for column in connection.introspection.get_table_description(cursor, model._meta.db_table)}
        assert {f.column for f in model._meta.local_fields} <= columns, model._meta.label
        constraints = connection.introspection.get_constraints(cursor, model._meta.db_table)
        for field in model._meta.local_fields:
            matching = [c for c in constraints.values() if c['columns'] == [field.column]]
            if field.primary_key:
                assert any(c['primary_key'] for c in matching), (model._meta.label, field.name, 'PK')
            elif field.unique:
                assert any(c['unique'] for c in matching), (model._meta.label, field.name, 'unique')
            elif field.db_index:
                assert any((c['index'] or c['unique']) and c['columns'][:1] == [field.column] for c in constraints.values()), (model._meta.label, field.name, 'index')
            if field.is_relation and field.db_constraint:
                target = (field.target_field.model._meta.db_table, field.target_field.column)
                assert any(c['foreign_key'] == target for c in matching), (model._meta.label, field.name, 'FK')
        for fields in model._meta.unique_together:
            expected_columns = [model._meta.get_field(name).column for name in fields]
            assert any(c['unique'] and c['columns'] == expected_columns for c in constraints.values()), model._meta.label

print(json.dumps({'apps': len(actual), 'managed_models': len(models), 'tables':len(tables), 'historical_migrations_applied':0}))
