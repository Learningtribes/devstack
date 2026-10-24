"""Resume model sync after MySQL non-transactional DDL, preserving all data.

Generate every deferred FK/index from current Django models and apply only absent
named constraints. Unknown SQL forms fail closed. No migration records are faked.
"""
import re
from django.apps import apps
from django.db import connection
models = [m for m in apps.get_models() if m._meta.managed and not m._meta.proxy and m._meta.can_migrate(connection)]
with connection.schema_editor(collect_sql=True) as editor:
    for model in models:
        editor.create_model(model)
    deferred = [str(statement) for statement in editor.deferred_sql]
count = 0
for sql in deferred:
    match = re.match(r'ALTER TABLE `([^`]+)` ADD CONSTRAINT `([^`]+)`', sql)
    if match:
        table, name = match.groups()
    else:
        match = re.match(r'CREATE (?:UNIQUE )?INDEX `([^`]+)` ON `([^`]+)`',sql)
        if not match:
            raise RuntimeError('Unrecognized deferred schema statement')
        name, table = match.groups()
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor,table)
        if name not in constraints:
            cursor.execute(sql)
            count += 1
print('Deferred constraints reconciled:', count, 'of', len(deferred))
