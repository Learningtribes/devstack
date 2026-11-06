"""Build and push the multi-platform LMS/CMS runtime base image and write its lock.

The image is the `internal-delivery` stage of docker/py313/Dockerfile, built from committed
Git objects only and pushed as an OCI index (linux/amd64 + linux/arm64). The index digest and
the per-platform manifest digests are recorded in
docker/py313/probe/startup-20261024-run01/replay/runtime-image.lock.json, which the replay
accepts as `images.runtime` (`ltdps/edxapp@sha256:<index digest>`).

Run with Python 3.13 on the host: uv run --no-project --python 3.13 python -B docker/py313/build-runtime-image.py ...
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile
import time

REPLAY = Path(__file__).resolve().parent / 'probe/startup-20261024-run01/replay'
sys.path.insert(0, str(REPLAY))
from core import IMAGE_INDEX_MEDIA_TYPE, RUNTIME_LOCK_PATH, RUNTIME_REPOSITORY, validate_runtime_lock  # noqa: E402

STAGE = 'internal-delivery'
PLATFORMS = ('linux/amd64', 'linux/arm64')
# The Dockerfile only reads these files; keeping the context minimal keeps the archive reproducible.
BUILD_INPUTS = ('docker/py313/Dockerfile', 'docker/py313/requirements-infra.txt',
                'docker/py313/requirements-native-probe.txt')
BUILD_ARG_NAMES = {'DEBIAN_MIRROR', 'DEBIAN_SECURITY_MIRROR', 'PIP_INDEX_URL', 'NODE_DIST_URL'}
TAG_RE = re.compile(re.escape(RUNTIME_REPOSITORY) + r':[A-Za-z0-9_][A-Za-z0-9_.-]*\d{8}[a-z]?')
BACKOFF = (5, 15, 30)
# Registry reads are the calls a flapping VPN/DNS breaks; give them longer to recover.
REGISTRY_BACKOFF = (5, 15, 30, 60, 120)


def git(root, *args, **kwargs):
    # Ignore GIT_* inherited from hooks or worktree wrappers; operate on `root` only.
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    return subprocess.run(['git', '-C', str(root), *args], check=True, env=env, **kwargs)


def validate_tag(tag):
    if not TAG_RE.fullmatch(tag) or tag.rpartition(':')[2].startswith('latest'):
        raise SystemExit('Refusing a shared or implicit tag; use %s:<name>-YYYYMMDD[a-z]' % RUNTIME_REPOSITORY)
    return tag


def retrying(command, definitive=None, backoff=BACKOFF, **kwargs):
    # A VPN can reset registry connections mid-build; layers are cached, so a retry is cheap.
    result = None
    for delay in (*backoff, None):
        result = subprocess.run(command, **kwargs)
        if result.returncode == 0 or delay is None or (definitive and definitive(result)):
            return result
        print('retrying in %ds after exit %d: %s' % (delay, result.returncode, ' '.join(command[:4])), flush=True)
        time.sleep(delay)
    return result


def tag_missing(result):
    return bool(re.search(r'not found|manifest unknown|no such manifest', result.stderr, re.IGNORECASE))


def registry_environment(proxy):
    """Environment for client-side registry reads only (buildx would forward a proxy into the build)."""
    env = dict(os.environ)
    if proxy:
        env.update(HTTPS_PROXY=proxy, https_proxy=proxy)
    return env


def tag_exists(tag, env=None):
    result = retrying(['docker', 'buildx', 'imagetools', 'inspect', tag], definitive=tag_missing,
                      backoff=REGISTRY_BACKOFF, env=env, capture_output=True, text=True)
    if result.returncode == 0:
        return True
    if tag_missing(result):
        return False
    raise SystemExit('Cannot determine whether %s exists remotely:\n%s' % (tag, result.stderr))


def containerd_store():
    info = json.loads(subprocess.check_output(['docker', 'info', '--format', '{{json .DriverStatus}}'], text=True))
    return ['driver-type', 'io.containerd.snapshotter.v1'] in info


def builder_args(name):
    """Name an explicit builder, else use the default one if the daemon can push an index itself."""
    if name:
        return ['--builder', name]
    if containerd_store():
        return []
    name = 'py313-runtime-builder'
    if subprocess.run(['docker', 'buildx', 'inspect', name], capture_output=True).returncode:
        subprocess.run(['docker', 'buildx', 'create', '--name', name, '--driver', 'docker-container',
                        '--bootstrap'], check=True)
    return ['--builder', name]


def parse_index(raw):
    """Return (index digest, {platform: child manifest digest}) from a raw OCI image index."""
    index = json.loads(raw)
    if index.get('mediaType') != IMAGE_INDEX_MEDIA_TYPE:
        raise SystemExit('Pushed tag is %r, not an OCI image index' % index.get('mediaType'))
    platforms = {}
    for manifest in index.get('manifests', []):
        platform = manifest.get('platform') or {}
        if platform.get('os') == 'unknown':
            raise SystemExit('Unexpected attestation manifest; build with --provenance=false --sbom=false')
        # Docker reports arm64 with or without the v8 variant depending on the producer.
        key = '%s/%s' % (platform.get('os'), platform.get('architecture'))
        if key in platforms:
            raise SystemExit('Duplicate platform in image index: ' + key)
        platforms[key] = manifest['digest']
    if set(platforms) != set(PLATFORMS):
        raise SystemExit('Image index platforms %s differ from %s' % (sorted(platforms), list(PLATFORMS)))
    return 'sha256:' + hashlib.sha256(raw).hexdigest(), platforms


def lock_record(tag, index_digest, platforms, commit, built_on):
    return validate_runtime_lock({
        'schema_version': 1, 'repository': RUNTIME_REPOSITORY, 'tag': tag.partition(':')[2], 'stage': STAGE,
        'registry_manifest_type': IMAGE_INDEX_MEDIA_TYPE, 'index_digest': index_digest, 'platforms': platforms,
        'devstack_commit': commit, 'built_on': built_on})


def pushed_index(tag, env):
    raw = retrying(['docker', 'buildx', 'imagetools', 'inspect', '--raw', tag], backoff=REGISTRY_BACKOFF,
                   env=env, capture_output=True)
    if raw.returncode:
        raise SystemExit('Cannot inspect pushed ' + tag)
    return parse_index(raw.stdout)


def write_lock(path, tag, index_digest, platforms, commit):
    record = lock_record(tag, index_digest, platforms, commit, datetime.date.today().isoformat())
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    print('Pushed %s@%s from %s' % (RUNTIME_REPOSITORY, index_digest, commit))
    for platform, digest in sorted(platforms.items()):
        print('  %s %s' % (platform, digest))
    print('Wrote %s; commit it in a follow-up commit.' % path)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--tag', required=True, help='new tag, e.g. %s:py313-devstack-YYYYMMDD' % RUNTIME_REPOSITORY)
    parser.add_argument('--context', type=Path, help='new directory, kept for build audit (required to build)')
    parser.add_argument('--builder', help='buildx builder (default: the current one if it can push an index)')
    parser.add_argument('--build-arg', action='append', default=[], metavar='NAME=VALUE',
                        help='mirror override, one of ' + ', '.join(sorted(BUILD_ARG_NAMES)))
    parser.add_argument('--registry-proxy', metavar='URL',
                        help='HTTP CONNECT proxy for client-side registry reads (tag check, index inspect)')
    parser.add_argument('--lock', type=Path, default=RUNTIME_LOCK_PATH, help='lock file to write')
    parser.add_argument('--lock-only', action='store_true',
                        help='record an already pushed tag (recovery after a failed inspect); needs --source-commit')
    parser.add_argument('--source-commit', help='commit the pushed image was built from (with --lock-only)')
    args = parser.parse_args(argv)
    validate_tag(args.tag)
    registry_env = registry_environment(args.registry_proxy)
    if args.lock_only:
        if not args.source_commit or not re.fullmatch(r'[0-9a-f]{40}', args.source_commit):
            raise SystemExit('--lock-only requires the full --source-commit the image was built from')
        write_lock(args.lock, args.tag, *pushed_index(args.tag, registry_env), args.source_commit)
        return
    if not args.context:
        raise SystemExit('--context is required to build')
    build_args = []
    for item in args.build_arg:
        name, _, value = item.partition('=')
        if name not in BUILD_ARG_NAMES or not value:
            raise SystemExit('--build-arg must be NAME=VALUE with NAME in ' + ', '.join(sorted(BUILD_ARG_NAMES)))
        build_args += ['--build-arg', item]
    root = Path(__file__).resolve().parents[2]
    dirty = git(root, 'status', '--porcelain', '--untracked-files=all', capture_output=True, text=True).stdout
    if dirty.strip():
        raise SystemExit('Refusing to build from a dirty tree:\n' + dirty)
    sha = git(root, 'rev-parse', 'HEAD', capture_output=True, text=True).stdout.strip()
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise SystemExit('Cannot resolve HEAD')
    if tag_exists(args.tag, registry_env):
        raise SystemExit('%s already exists remotely; choose a new tag (e.g. a "b" suffix)' % args.tag)
    args.context.mkdir(mode=0o700, parents=False)
    with tempfile.TemporaryFile() as stream:
        git(root, 'archive', sha, *BUILD_INPUTS, stdout=stream)
        stream.seek(0)
        with tarfile.open(fileobj=stream) as archive:
            archive.extractall(args.context, filter='data')
    context = args.context / 'docker/py313'
    # --provenance/--sbom off: attestation manifests would add unknown/unknown entries to the index.
    command = ['docker', 'buildx', 'build', *builder_args(args.builder), '--platform', ','.join(PLATFORMS),
               '--target', STAGE, '--provenance=false', '--sbom=false', *build_args,
               '-f', str(context / 'Dockerfile'), '-t', args.tag, '--push', str(context)]
    if retrying(command).returncode:
        raise SystemExit('Build or push failed')
    try:
        index = pushed_index(args.tag, registry_env)
    except SystemExit:
        print('Push succeeded but the index could not be read; record it with: --lock-only --tag %s '
              '--source-commit %s' % (args.tag, sha), file=sys.stderr)
        raise
    write_lock(args.lock, args.tag, *index, sha)


if __name__ == '__main__':
    main()
