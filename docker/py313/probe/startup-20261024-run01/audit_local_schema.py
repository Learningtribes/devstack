"""Read-only audit of the explicit local model schema, including M2M tables.

Run with startup_schema; this does not validate historical migration chains.
"""
import json
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder

inventory = json.loads(Path('/startup/schema-app-inventory.json').read_text())
expected = {entry['label'] for entry in inventory['lms'] + inventory['cms']}
assert set(apps.app_configs) == expected
assert set(settings.MIGRATION_MODULES) == expected
assert all(value is None for value in settings.MIGRATION_MODULES.values())
assert connection.settings_dict['NAME'].startswith(('py313_startup_', 'py313_rebuild_'))
assert not MigrationRecorder(connection).applied_migrations()
models = [model for model in apps.get_models(include_auto_created=True)
          if model._meta.managed and not model._meta.proxy and model._meta.can_migrate(connection)]
report = []
with connection.cursor() as cursor:
    tables = set(connection.introspection.table_names(cursor))
    for model in models:
        table = model._meta.db_table
        assert table in tables, (model._meta.label, 'missing table')
        columns = {column.name: column for column in connection.introspection.get_table_description(cursor, table)}
        constraints = connection.introspection.get_constraints(cursor, table)
        for field in model._meta.local_fields:
            assert field.column in columns, (model._meta.label, field.name, 'missing column')
            assert bool(columns[field.column].null_ok) == field.null, (model._meta.label, field.name, 'nullability')
            matching = [item for item in constraints.values() if item['columns'] == [field.column]]
            if field.primary_key:
                assert any(item['primary_key'] for item in matching), (model._meta.label, field.name, 'PK')
            elif field.unique:
                assert any(item['unique'] for item in matching), (model._meta.label, field.name, 'unique')
            elif field.db_index:
                assert any((item['index'] or item['unique']) and item['columns'][:1] == [field.column]
                           for item in constraints.values()), (model._meta.label, field.name, 'index')
            if field.is_relation and field.db_constraint:
                target = (field.target_field.model._meta.db_table, field.target_field.column)
                assert any(item['foreign_key'] == target for item in matching), (model._meta.label, field.name, 'FK')
        for fields in model._meta.unique_together:
            target = [model._meta.get_field(name).column for name in fields]
            assert any(item['unique'] and item['columns'] == target for item in constraints.values()), (model._meta.label, 'unique_together')
        for declared in [*model._meta.indexes, *model._meta.constraints]:
            assert declared.name in constraints, (model._meta.label, declared.name, 'declared constraint/index')
        report.append({'model': model._meta.label, 'table': table, 'columns': len(columns),
                       'constraints': len(constraints), 'auto_created': bool(model._meta.auto_created)})
print(json.dumps({'apps': len(expected), 'models_including_m2m': len(models), 'tables': len(tables),
                  'historical_migrations_applied': 0, 'schema_route': 'local-model-sync',
                  'models': report}, sort_keys=True, indent=2))
