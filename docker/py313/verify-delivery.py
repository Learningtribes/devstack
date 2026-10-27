#!/usr/bin/env python3
"""Verify the paired Python 3.13 checkpoint without starting Docker services."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path


SERVICES = ("mysql", "mongo", "rabbitmq", "memcached", "valkey", "elasticsearch")


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> str:
    return subprocess.check_output(args, cwd=cwd, env=env, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--platform-dir", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    manifest = json.loads(args.manifest.read_text())
    repo = root.parent.parent
    actual = run("git", "rev-parse", "HEAD", cwd=repo)
    if actual != manifest["devstack"]["sha"]:
        raise SystemExit(f"devstack HEAD differs from manifest: {actual}")
    if run("git", "status", "--short", cwd=repo):
        raise SystemExit("devstack worktree is not clean")
    platform_head = run("git", "-C", str(args.platform_dir), "rev-parse", "HEAD")
    if platform_head != manifest["platform"]["sha"]:
        raise SystemExit(f"platform HEAD differs from manifest: {platform_head}")
    lock = json.loads((root / "probe/startup-20261024-run01/replay/infrastructure-images.lock.json").read_text())
    expected = {name: lock["services"][name]["reference"] for name in SERVICES}
    env = os.environ.copy()
    for key in ("PY313_MYSQL_ROOT_PASSWORD", "PY313_MYSQL_PASSWORD", "PY313_MONGO_PASSWORD", "PY313_RABBITMQ_PASSWORD"):
        env.setdefault(key, "delivery-check")
    config = json.loads(run("docker", "compose", "--env-file", "/dev/null", "-f", str(root / "docker-compose.yml"), "config", "--format", "json", env=env))
    configured = {name: config["services"][name]["image"] for name in SERVICES}
    if configured != expected:
        raise SystemExit(f"compose image references differ from lock: {configured}")
    print(f"PASS paired SHAs platform={platform_head} devstack={actual}")
    print("PASS docker compose config and immutable image lock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
