# Python 3.13 delivery entry point

Use the paired manifest at
`/Users/noahwang/docs/hawthorn/py313-delivery-checkpoint-2026-10-27.json`.
It fixes the platform and devstack commits, Python 3.13, Docker/Compose
requirements, the local runtime image digest, and the six infrastructure image
index digests. The compose file uses those immutable service references; the
runtime image is built from the digest-pinned Python base in `Dockerfile`.

From this directory, the explicit local sequence is:

```bash
make env
make build
make up
make shell PLATFORM_DIR=/absolute/path/to/platform-worktree
```

`make env` creates only a new mode-600 local `.env`; `make build` builds local
runtime/dev images; `make up` is the command that starts services. No command in
this delivery removes existing databases, volumes, images or Docker resources.
The older `make destroy` and `make venv-reset` targets are intentionally outside
the verification path.

The read-only verification entry point is:

```bash
python3.13 verify-delivery.py \
  --manifest /Users/noahwang/docs/hawthorn/py313-delivery-checkpoint-2026-10-27.json \
  --platform-dir /absolute/path/to/platform-worktree
```

It checks both full SHAs, clean worktrees, `docker compose config`, and exact
compose-to-lock image references. It does not pull, build, start, stop, or
clean containers. The bounded verification set also includes
`python3.13 -m unittest docker/py313/probe/startup-20261024-run01/replay/test_core.py`
for lock/config guard behavior and the platform helper mock tests recorded in
the manifest. These are mock/static/isolated checks, not a complete platform or
integrated service suite. Mongo-backed tests and the complete dependency
resolver remain open because of the documented opaque-keys/completion/PyMongo
2.9.1 blockers.

The local architecture support claim is native `linux/arm64` and `linux/amd64`
for the six multi-platform service indexes and the runtime build; host Docker
must provide one of those architectures. No production service, real IdP,
external ORA2 checkout, or existing production database is contacted.
