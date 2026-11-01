# Current py3-master isolated replay

Latest bounded result: [2026-11-02 repair and replay](current-replay-20261102.md).
Use its frozen candidate identities when interpreting that evidence; the example
below retains the historical R2 configuration and must be replaced for any new run.

Use [the exact configuration contract](README.md) and
[current-config.example.json](current-config.example.json). Replace all absolute
host paths, choose a new run ID and replace it in **every** resource/namespace,
then choose unused ports and a non-overlapping RFC1918 /24. Keep both full source
commits fixed; the example Devstack SHA is the executable adapter used for this
attempt, not a claim that every subsequent documentation HEAD was replayed.

Use independent clean Git worktrees. This adapter is based on Devstack
`e19e059cc7091d435dd5121b586da0d525a350c5`; Platform was fetched from py3-master
and frozen at `7dcbcca0651875f0b7748216847715e60f3af706`. Do not copy dirty
checkout changes or historical venvs/data/secrets/assets. Only the complete current
Platform installer is supported here; `install_internal_delivery.py install`
selects the historical upstream-only lock and must not be used for this profile.

## Prerequisites and images

The locally verified target is linux/arm64. Required cached application image:
`ltdps/edxapp@sha256:c73bb66928e12c9e5b1b4e3d1564226163409eb034c0bf123be17778f36dff63`.
Inspect it with `docker image inspect` and put its actual local image ID in
`images.runtime`; record RepoDigests and OS/architecture separately. The current
machine reports the same SHA for repository digest and local ID; these are distinct
identities. Cold pull and AMD64 application rebuild have not been verified.
The six service references must match `infrastructure-images.lock.json` exactly.
Docker/Compose, uv, Git, OpenSSL and package-index/pinned Git access are required.
Check disk, Docker memory, current resource inventory and host LAN/VPN routes first.
Do not free capacity by deleting historical environments.

## Commands

From the committed Devstack worktree, define absolute operator-selected paths:

```sh
REPLAY=docker/py313/probe/startup-20261024-run01/replay
CONFIG=/absolute/new-run/config.json
uv run --no-project --python 3.13 python -B -m unittest discover -s "$REPLAY" -p 'test_*.py' -v
```

Create a **new** parent directory for the config/outputs, and a new mode-700 private
subdirectory. Generate a new RSA private key with `openssl genrsa -out PATH 2048`
and chmod it 600; `PATH` must equal `jwt_file`. Never print or commit secrets.
Run these commands individually, stopping at any nonzero exit:

```sh
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" provision-secrets
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" provision-acceptance
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" preflight
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" prepare
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" create
uv run --no-project --python 3.13 python -B "$REPLAY/run.py" --config "$CONFIG" install
uv run --no-project --python 3.13 python -B "$REPLAY/replay_after_install.py" --config "$CONFIG" schema
uv run --no-project --python 3.13 python -B "$REPLAY/replay_after_install.py" --config "$CONFIG" assets
uv run --no-project --python 3.13 python -B "$REPLAY/replay_after_install.py" --config "$CONFIG" services
```

The original schema initializer synchronizes models in a fresh synthetic database;
it does not replay historical migrations. Asset execution is real npm-ci,
XModule/theme/static compilation, webpack for both systems, locale and collectstatic.
Service dispatch alone is not readiness: inspect run-owned HTTP/worker logs, loopback
responses and owned queue routing. Follow the browser/task/persistence checks in
the main replay README and capture the audit only after those prerequisites pass.
Never expose private authentication HTTP logs as evidence.

No resume/reset/cleanup/restart fallback is provided. Output labels are exclusive,
so a failure preserves evidence and cannot silently repeat a mutation. After an
executable adapter change, commit it and use a new run config/export/resources.
Application failures end dependent stages; record a focused follow-up instead of
patching installed sources or weakening checks. This is local development acceptance,
not old-data upgrade, external provider acceptance, production rollout or CI cutover.
