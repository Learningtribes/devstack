"""Name guard for the destructive replay scripts (schema sync, seeds)."""
import os

REPLAY_PREFIXES = ('py313_startup_', 'py313_rebuild_')


def is_replay_database(name, prefixes=REPLAY_PREFIXES):
    """True for a replay-namespaced database, or for the one exact name the operator adopted.

    PY313_ADOPTED_DATABASE must hold the full database name. It is the operator's explicit statement that this
    existing database may be wiped and rebuilt by the replay scripts; a prefix or an empty value never matches.
    """
    adopted = os.environ.get('PY313_ADOPTED_DATABASE', '')
    return name.startswith(prefixes) or (bool(adopted) and name == adopted)
