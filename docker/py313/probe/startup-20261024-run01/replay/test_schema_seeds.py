"""The schema phase must run every seed the runtime needs, each under its own evidence label.

`capture()` reserves an output file per label and refuses to repeat one, so a duplicated label
breaks the stage on its second use. And a seed that silently drops out of the phase leaves a
plainly-started environment missing configuration no migration creates.
"""
import ast
from pathlib import Path
import unittest

SCHEMA = Path(__file__).with_name('replay_after_install.py')
LEARNING_PATH_SEED = '/startup/seed_learning_path_config.py'


def _is_phase_check(test, phase):
    return (isinstance(test, ast.Compare) and isinstance(test.left, ast.Attribute)
            and test.left.attr == 'phase'
            and any(isinstance(comparator, ast.Constant) and comparator.value == phase
                    for comparator in test.comparators))


def _schema_body(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and _is_phase_check(node.test, 'schema'):
            return node.body
    raise AssertionError('No schema phase in %s' % SCHEMA)


def _shell_calls(body):
    """(label, script) for every `shell(config, system, label, script)` in the schema phase."""
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'shell':
            constants = [arg.value for arg in node.args if isinstance(arg, ast.Constant)]
            if len(constants) >= 2:
                yield constants[-2], constants[-1]


class SchemaPhaseSeedTests(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.calls = dict(_shell_calls(_schema_body(ast.parse(SCHEMA.read_text()))))

    def test_the_learning_path_configuration_is_seeded(self):
        self.assertIn(LEARNING_PATH_SEED, self.calls.values())

    def test_every_seed_has_its_own_evidence_label(self):
        labels = [label for label, _ in _shell_calls(_schema_body(ast.parse(SCHEMA.read_text())))]
        self.assertEqual(len(labels), len(set(labels)), 'duplicate evidence label: %s' % labels)


ACCEPTANCE_SEED = Path(__file__).resolve().parents[1] / 'seed_acceptance_users.py'


class AcceptanceSeedGuardTests(unittest.TestCase):
    """The acceptance seed creates staff users, so it must refuse a database that is not this run.

    Its credential-file assertion proves the identities belong to the run, not that the rows are
    going somewhere safe. The platform-side seeds already make the `is_replay_database` check;
    this one lives in the Devstack repository, so nothing in the platform's guard test saw it.
    """

    def test_the_acceptance_seed_refuses_a_foreign_database(self):
        tree = ast.parse(ACCEPTANCE_SEED.read_text())
        guarded = any(
            isinstance(node, ast.Assert) and any(
                isinstance(call, ast.Call) and getattr(call.func, 'id', None) == 'is_replay_database'
                for call in ast.walk(node.test))
            for node in tree.body)
        self.assertTrue(guarded, 'seed_acceptance_users.py writes rows with no database guard')
