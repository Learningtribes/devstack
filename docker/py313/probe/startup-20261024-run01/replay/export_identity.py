"""Recheck the two exported input trees; never inspect protected file values."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat


PLACEHOLDERS = {'.acceptance-credentials.json', 'jwt-private.pem'}
PROTECTED = PLACEHOLDERS | {'.env'}


def regular(path):
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Expected regular file: ' + str(path))


def directory(path):
    if not stat.S_ISDIR(path.lstat().st_mode):
        raise ValueError('Expected real directory: ' + str(path))


def read_regular(path):
    regular(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError('Expected regular file: ' + str(path))
        return stream.read()


def manifest_path(value):
    if not isinstance(value, str) or not value:
        raise ValueError('Invalid relative identity path')
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value or '..' in path.parts or value == '.':
        raise ValueError('Invalid relative identity path')
    if any(part in PROTECTED for part in path.parts):
        raise ValueError('Protected path cannot be part of an exported identity')
    return path


def snapshot(base, expected, *, placeholders=False):
    """List first; reject unknown paths before reading any file contents."""
    directory(base)
    observed = {}

    def walk(folder):
        with os.scandir(folder) as entries:
            for entry in entries:
                path = Path(entry.path)
                relative = path.relative_to(base).as_posix()
                if placeholders and relative in PLACEHOLDERS:
                    regular(path)
                    if path.lstat().st_size != 0:
                        raise ValueError('Expected empty host placeholder: ' + relative)
                    continue  # Never open or hash placeholder/credential contents.
                if entry.is_symlink():
                    observed[relative] = ('link', path)
                elif entry.is_dir(follow_symlinks=False):
                    walk(path)
                elif entry.is_file(follow_symlinks=False):
                    observed[relative] = ('file', path)
                else:
                    raise ValueError('Unsupported exported file type: ' + relative)

    walk(base)
    if set(observed) != set(expected):
        raise ValueError('Export file set differs: missing=' + str(sorted(set(expected) - set(observed))) +
                         ', extra=' + str(sorted(set(observed) - set(expected))))
    actual = {}
    for relative, (kind, path) in sorted(observed.items()):
        manifest_path(relative)
        if kind == 'link':
            actual[relative] = {'link': os.readlink(path)}
        else:
            actual[relative] = {'sha256': hashlib.sha256(read_regular(path)).hexdigest()}
    if actual != expected:
        raise ValueError('Export file identities differ: ' + str(sorted(k for k in actual if actual[k] != expected[k])))
    if placeholders:
        for name in PLACEHOLDERS:
            path = base / name
            regular(path)
            if path.lstat().st_size != 0:
                raise ValueError('Expected empty host placeholder: ' + name)


def unique_object(pairs):
    """Reject duplicate keys at every JSON object level, before information is lost."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate export identity key')
        result[key] = value
    return result


def validate_trees(identity):
    """Validate both maps completely before snapshot reads any tree contents."""
    if not isinstance(identity, dict) or not isinstance(identity.get('trees'), dict):
        raise ValueError('Expected export identity object with input trees')
    trees = identity['trees']
    if set(trees) != {'startup', 'platform'}:
        raise ValueError('Expected exactly startup and platform input trees')
    for label in ('startup', 'platform'):
        expected = trees[label]
        if not isinstance(expected, dict):
            raise ValueError('Invalid input tree')
        for name, record in expected.items():
            manifest_path(name)
            if not isinstance(record, dict) or not (
                    set(record) == {'sha256'} and isinstance(record['sha256'], str) and re.fullmatch('[0-9a-f]{64}', record['sha256'])
                    or set(record) == {'link'} and isinstance(record['link'], str)):
                raise ValueError('Invalid file identity: ' + name)
    return trees


def verify_export_identity(root, startup_relative, *, expected_sha256=None, allow_placeholders=False):
    """Return the initial manifest digest to pin in the prepared evidence record.

    Assumes a private export with no concurrent writers. Empty directories and
    executable permission bits are outside the existing manifest schema.
    """
    root = Path(root)
    directory(root)
    raw = read_regular(root / 'export-identity.json')
    digest = hashlib.sha256(raw).hexdigest()
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('Export identity manifest changed after prepare')
    identity = json.loads(raw, object_pairs_hook=unique_object)
    trees = validate_trees(identity)
    startup_path = PurePosixPath(str(startup_relative))
    if startup_path.is_absolute() or '..' in startup_path.parts:
        raise ValueError('Invalid startup path')
    startup = root / 'devstack'
    directory(startup)
    for part in startup_path.parts:
        startup = startup / part
        directory(startup)
    for label, base in [('startup', startup), ('platform', root / 'platform')]:
        expected = trees[label]
        snapshot(base, expected, placeholders=label == 'startup' and allow_placeholders)
    return digest
