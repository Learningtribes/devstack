"""Contract test of the production application image sources (stdlib only, no Docker needed).

Run: uv run --no-project --python 3.13 python -B -m unittest -v test_app_image_contract   (from this directory)
"""
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASH = shutil.which("bash")
SYSTEM_PATH = "/usr/bin:/bin"


def logical_lines(path):
    """Dockerfile instructions with continuations joined and comments dropped."""
    lines, buffer = [], ""
    for raw in path.read_text().splitlines():
        stripped = raw.strip()
        if not buffer and (not stripped or stripped.startswith("#")):
            continue
        if stripped.startswith("#"):
            continue
        buffer += stripped[:-1] + " " if stripped.endswith("\\") else stripped
        if not stripped.endswith("\\"):
            lines.append(buffer)
            buffer = ""
    return lines


class DockerfileContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = logical_lines(HERE / "app.Dockerfile")
        cls.args = {}
        for line in cls.lines:
            m = re.match(r"ARG\s+(\w+)=(\S+)$", line)
            if m:
                cls.args.setdefault(m.group(1), m.group(2))
        starts = [i for i, line in enumerate(cls.lines) if line.startswith("FROM ")]
        cls.froms = [cls.lines[i] for i in starts]
        cls.final = cls.lines[starts[-1]:]

    def expand(self, value):
        return re.sub(r"\$\{(\w+)\}", lambda m: self.args[m.group(1)], value)

    def test_base_images_are_digest_pinned(self):
        stages = set()
        for line in self.froms:
            m = re.match(r"FROM\s+(\S+)(?:\s+AS\s+(\S+))?$", line)
            self.assertIsNotNone(m, line)
            image = self.expand(m.group(1))
            if image not in stages:
                self.assertRegex(image, r"@sha256:[0-9a-f]{64}$", f"base image not digest-pinned: {line}")
            if m.group(2):
                stages.add(m.group(2))

    def test_final_stage_runs_as_numeric_non_root(self):
        users = [line for line in self.final if line.startswith("USER ")]
        self.assertEqual(len(users), 1, users)
        user = self.expand(users[0].split(None, 1)[1])
        self.assertRegex(user, r"^[1-9][0-9]*:[1-9][0-9]*$")
        self.assertLess(self.final.index(users[0]), self.final.index(next(l for l in self.final if l.startswith("ENTRYPOINT"))))

    def test_exposed_ports(self):
        exposed = [line.split()[1:] for line in self.final if line.startswith("EXPOSE ")]
        self.assertEqual(exposed, [["8000", "8010"]])

    def test_entrypoint_is_tini_then_edxapp_entrypoint(self):
        entry = [line for line in self.final if line.startswith("ENTRYPOINT ")]
        self.assertEqual(len(entry), 1)
        self.assertEqual(json.loads(entry[0].split(None, 1)[1]), ["/usr/bin/tini", "--", "/usr/local/bin/edxapp-entrypoint"])
        self.assertTrue(any("tini" in l and l.startswith("RUN") for l in self.final), "tini must be installed in the final stage")
        self.assertTrue(any(l.startswith("COPY app-entrypoint.sh /usr/local/bin/edxapp-entrypoint") for l in self.final))

    def test_no_credentials_in_arg_or_env(self):
        secret_name = re.compile(r"(PASS(WORD)?|SECRET|TOKEN|CREDENTIAL|PRIVATE|API_?KEY|AUTH)", re.I)
        for line in self.lines:
            if not re.match(r"(ARG|ENV)\s", line):
                continue
            for name in re.findall(r"(\w+)=", line) or [line.split()[1]]:
                self.assertIsNone(secret_name.search(name), f"credential-like name in: {line}")
            self.assertIsNone(re.search(r"://[^/\s:@]+:[^/\s@]+@", line), f"URL with userinfo in: {line}")

    def test_no_runtime_path(self):
        # The final-stage guard greps the venv for the retired '/runtime/' prefix; that literal is the only allowed mention.
        text = "\n".join(self.lines).replace("grep -rIl '/runtime/'", "")
        self.assertIsNone(re.search(r"(?<![\w.-])/runtime\b", text))

    def test_labels_carry_both_commits(self):
        labels = " ".join(line for line in self.final if line.startswith("LABEL "))
        self.assertIn('org.opencontainers.image.revision="${PLATFORM_COMMIT}"', labels)
        self.assertIn('com.learningtribes.theme.revision="${THEME_COMMIT}"', labels)
        declared = " ".join(line for line in self.final if line.startswith("ARG "))
        self.assertIn("PLATFORM_COMMIT", declared)
        self.assertIn("THEME_COMMIT", declared)

    def test_no_latest_tag(self):
        self.assertNotRegex("\n".join(self.lines), r":latest\b")
        stages = set()
        for line in self.froms:
            m = re.match(r"FROM\s+(\S+)(?:\s+AS\s+(\S+))?$", line)
            self.assertIsNotNone(m, line)
            image = self.expand(m.group(1))
            if image not in stages:  # a reference to an earlier build stage is not a registry image
                tag = image.split("@", 1)[0].rsplit("/", 1)[-1]
                self.assertTrue(":" in tag or "@sha256:" in image, f"untagged base image resolves to :latest: {line}")
                self.assertNotEqual(tag.partition(":")[2], "latest", line)
            if m.group(2):
                stages.add(m.group(2))

    def test_inputs_env_pins_both_commits(self):
        values = dict(
            line.split("=", 1) for line in (HERE / "inputs.env").read_text().splitlines()
            if line and not line.startswith("#")
        )
        self.assertEqual(set(values), {"PLATFORM_COMMIT", "THEME_COMMIT"})
        for value in values.values():
            self.assertRegex(value, r"^[0-9a-f]{7,40}$")


class Workspace(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.tmp = Path(tempfile.mkdtemp(prefix="app-image-contract-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
        return path


class EntrypointBehaviour(Workspace):
    def setUp(self):
        super().setUp()
        self.home = self.tmp / "edxapp"
        (self.home / "edx-platform").mkdir(parents=True)
        self.config = self.tmp / "config"
        self.config.mkdir()
        self.record = self.tmp / "record"
        recorder = (
            f'{{ echo "pid=$$"; echo "variant=$SERVICE_VARIANT"; echo "settings=$DJANGO_SETTINGS_MODULE"; '
            f'echo "cwd=$(pwd)"; for a in "$@"; do echo "arg=$a"; done; }} > "{self.record}.tmp"\n'
            f'mv "{self.record}.tmp" "{self.record}"\n'
        )
        # Wait for SIGTERM so that the test can prove the signal reaches the exec'd process itself.
        waiter = "trap 'exit 0' TERM\nwhile :; do sleep 0.1; done\n"
        for name in ("gunicorn", "celery", "python"):
            self.stub(name, recorder + waiter)

    def write_config(self, system):
        for kind in ("env", "auth"):
            (self.config / f"{system}.{kind}.json").write_text("{}")

    def env(self, **extra):
        env = {"PATH": f"{self.bin}:{SYSTEM_PATH}", "EDXAPP_HOME": str(self.home), "CONFIG_ROOT": str(self.config)}
        env.update(extra)
        return env

    def run_entrypoint(self, *args, **extra_env):
        return subprocess.run([BASH, str(HERE / "app-entrypoint.sh"), *args], env=self.env(**extra_env),
                              capture_output=True, text=True, timeout=20)

    @staticmethod
    def reap(proc):
        try:
            os.killpg(proc.pid, signal.SIGKILL)  # also a wrapper shell's orphaned child, if exec was not used
        except ProcessLookupError:
            pass
        proc.communicate()

    def start(self, *args, **extra_env):
        proc = subprocess.Popen([BASH, str(HERE / "app-entrypoint.sh"), *args], env=self.env(**extra_env),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                start_new_session=True)
        self.addCleanup(self.reap, proc)
        deadline = time.monotonic() + 10
        while not self.record.exists():
            self.assertIsNone(proc.poll(), proc.stderr.read() if proc.poll() is not None else "")
            self.assertLess(time.monotonic(), deadline, "stub was never exec'd")
            time.sleep(0.02)
        pairs = [line.split("=", 1) for line in self.record.read_text().splitlines()]
        recorded = {"args": [v for k, v in pairs if k == "arg"]}
        recorded.update({k: v for k, v in pairs if k != "arg"})
        return proc, recorded

    def assert_sigterm_clean(self, proc, recorded):
        self.assertEqual(int(recorded["pid"]), proc.pid, "a shell wrapper is still PID of the process: exec was not used")
        proc.send_signal(signal.SIGTERM)
        self.assertEqual(proc.wait(timeout=10), 0)

    def test_missing_config_exits_78(self):
        for args in (["lms"], ["cms"], ["worker", "lms"], ["manage", "cms", "check"]):
            with self.subTest(args=args):
                result = self.run_entrypoint(*args)
                self.assertEqual(result.returncode, 78, result.stderr)
                self.assertIn(str(self.config), result.stderr)

    def test_unreadable_half_of_config_exits_78(self):
        (self.config / "lms.env.json").write_text("{}")
        self.assertEqual(self.run_entrypoint("lms").returncode, 78)

    def test_invalid_settings_exits_64(self):
        self.write_config("lms")
        for value in ("../aws", "Aws", "aws;id", "a b"):
            with self.subTest(settings=value):
                self.assertEqual(self.run_entrypoint("lms", EDXAPP_SETTINGS=value).returncode, 64)

    def test_wrong_system_exits_64(self):
        self.write_config("lms")
        for args in (["worker", "xyz"], ["worker"], ["manage"], ["manage", "studio", "check"]):
            with self.subTest(args=args):
                result = self.run_entrypoint(*args)
                self.assertEqual(result.returncode, 64, result.stderr)

    def test_lms_execs_gunicorn(self):
        self.write_config("lms")
        proc, rec = self.start("lms")
        self.assertEqual(rec["variant"], "lms")
        self.assertEqual(rec["settings"], "lms.envs.aws")
        self.assertEqual(Path(rec["cwd"]).resolve(), (self.home / "edx-platform").resolve())
        args = rec["args"]
        self.assertEqual(args[0], "lms.wsgi:application")
        for flag, value in (("--bind", "0.0.0.0:8000"), ("--workers", "2"), ("--timeout", "300"), ("--max-requests", "1000")):
            self.assertEqual(args[args.index(flag) + 1], value, flag)
        self.assert_sigterm_clean(proc, rec)

    def test_cms_execs_gunicorn(self):
        self.write_config("cms")
        proc, rec = self.start("cms")
        self.assertEqual(rec["settings"], "cms.envs.aws")
        args = rec["args"]
        self.assertEqual(args[0], "cms.wsgi:application")
        for flag, value in (("--bind", "0.0.0.0:8010"), ("--workers", "1"), ("--timeout", "300"), ("--max-requests", "2000")):
            self.assertEqual(args[args.index(flag) + 1], value, flag)
        self.assert_sigterm_clean(proc, rec)

    def test_gunicorn_env_overrides_and_extra_args(self):
        self.write_config("lms")
        proc, rec = self.start("lms", "--preload", PORT="9000", GUNICORN_WORKERS="7", GUNICORN_TIMEOUT="60",
                               GUNICORN_MAX_REQUESTS="5", EDXAPP_SETTINGS="devstack")
        args = rec["args"]
        self.assertEqual(rec["settings"], "lms.envs.devstack")
        for flag, value in (("--bind", "0.0.0.0:9000"), ("--workers", "7"), ("--timeout", "60"), ("--max-requests", "5")):
            self.assertEqual(args[args.index(flag) + 1], value, flag)
        self.assertEqual(args[-1], "--preload")
        self.assert_sigterm_clean(proc, rec)

    def test_default_command_is_lms(self):
        self.write_config("lms")
        proc, rec = self.start()
        self.assertEqual(rec["args"][0], "lms.wsgi:application")
        self.assert_sigterm_clean(proc, rec)

    def test_worker_execs_celery(self):
        self.write_config("lms")
        proc, rec = self.start("worker", "lms", "--queues=edx.lms.core.default", "--concurrency=1")
        self.assertEqual(rec["variant"], "lms")
        self.assertEqual(rec["settings"], "lms.envs.aws")
        self.assertEqual(rec["args"], ["-A", "lms.celery:APP", "worker", "--queues=edx.lms.core.default", "--concurrency=1"])
        self.assert_sigterm_clean(proc, rec)

    def test_manage_execs_python(self):
        self.write_config("cms")
        proc, rec = self.start("manage", "cms", "check", "--deploy")
        self.assertEqual(rec["args"], ["manage.py", "cms", "--settings=aws", "check", "--deploy"])
        self.assert_sigterm_clean(proc, rec)

    def test_passthrough_needs_no_config(self):
        self.stub("hello", 'echo "hello $*"\n')
        result = self.run_entrypoint("hello", "a", "b")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "hello a b"))


class BuildScriptPolicy(Workspace):
    def setUp(self):
        super().setUp()
        self.log = self.tmp / "docker.log"
        self.build_dir = self.tmp / "out"
        self.repos = {}
        for name in ("platform", "theme"):
            repo = self.tmp / name
            repo.mkdir()
            (repo / "file").write_text(name)
            git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid"]
            subprocess.run([*git[:3], "init", "-q"], check=True)
            subprocess.run([*git, "add", "file"], check=True)
            subprocess.run([*git, "commit", "-q", "-m", "x"], check=True)
            self.repos[name] = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True,
                                              capture_output=True, text=True).stdout.strip()
        # `docker image inspect <tag>` succeeds only for EXISTING_TAG; the --format forms answer for the built image.
        self.stub("docker", f'''echo "$*" >> "{self.log}"
case "$1 $2" in
  "image inspect")
    for last; do :; done
    case "$*" in
      *Architecture*) echo arm64; exit 0 ;;
      *--format*) echo sha256:abc123; exit 0 ;;
    esac
    [ "${{EXISTING_TAG:-}}" = "$last" ] ;;
  "buildx build")
    touch "{self.tmp}/built"
    while [ $# -gt 0 ]; do [ "$1" = --metadata-file ] && printf '{{\\n  "containerimage.digest": "sha256:feed"\\n}}\\n' > "$2"; shift; done ;;
esac
''')

    def run_build(self, *args, **extra):
        env = {"PATH": f"{self.bin}:{SYSTEM_PATH}", "PLATFORM_REPO": str(self.tmp / "platform"),
               "THEME_REPO": str(self.tmp / "theme"), "PLATFORM_COMMIT": self.repos["platform"],
               "THEME_COMMIT": self.repos["theme"], "BUILD_DIR": str(self.build_dir), "HOME": str(self.tmp)}
        env.update(extra)
        return subprocess.run([BASH, str(HERE / "build.sh"), *args], env=env, capture_output=True, text=True, timeout=30)

    def test_refuses_latest_and_unversioned_tags(self):
        for tag in ("latest", "edxapp", "edxapp:latest", "registry.example/team/edxapp", "registry.example:5000/edxapp"):
            with self.subTest(tag=tag):
                self.assertEqual(self.run_build(tag).returncode, 2)
        self.assertFalse(self.log.exists(), "docker must not run for a refused tag")

    def test_refuses_existing_tag_unless_forced(self):
        refused = self.run_build("edxapp:v1", EXISTING_TAG="edxapp:v1")
        self.assertEqual(refused.returncode, 2)
        self.assertIn("already exists", refused.stderr)
        self.assertFalse((self.tmp / "built").exists())
        self.assertEqual(self.run_build("edxapp:v1", EXISTING_TAG="edxapp:v1", FORCE="1").returncode, 0)

    def test_requires_repositories(self):
        for var in ("PLATFORM_REPO", "THEME_REPO"):
            with self.subTest(var=var):
                result = self.run_build("edxapp:v1", **{var: ""})
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(var, result.stderr)

    def test_old_positional_form_is_rejected(self):
        result = self.run_build("/p", "abcdef1", "/t", "abcdef1", "edxapp:v1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("removed", result.stderr)

    def test_native_build_writes_lock_with_resolved_shas(self):
        result = self.run_build("edxapp:v1")
        self.assertEqual(result.returncode, 0, result.stderr)
        call = next(l for l in self.log.read_text().splitlines() if l.startswith("buildx build"))
        self.assertRegex(call, r"--platform linux/(arm64|amd64) ")
        self.assertIn(f"PLATFORM_COMMIT={self.repos['platform']}", call)
        self.assertIn(f"THEME_COMMIT={self.repos['theme']}", call)
        self.assertIn("--load", call)
        lock = json.loads((self.build_dir / "image.lock.json").read_text())
        self.assertEqual(lock, {"tag": "edxapp:v1", "image_id": "sha256:abc123", "architecture": "arm64",
                                "platform_sha": self.repos["platform"], "theme_sha": self.repos["theme"],
                                "build_date": lock["build_date"], "index_digest": None})
        self.assertRegex(lock["build_date"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_amd64_only_on_request_and_index_digest_when_pushed(self):
        result = self.run_build("registry.example/edxapp:v1", "amd64", BUILDX_FLAGS="--push")
        self.assertEqual(result.returncode, 0, result.stderr)
        call = next(l for l in self.log.read_text().splitlines() if l.startswith("buildx build"))
        self.assertIn("--platform linux/amd64 ", call)
        self.assertNotIn("--load", call)
        self.assertEqual(json.loads((self.build_dir / "image.lock.json").read_text())["index_digest"], "sha256:feed")

    def test_commit_override_must_exist(self):
        result = self.run_build("edxapp:v1", PLATFORM_COMMIT="deadbeef")
        self.assertEqual(result.returncode, 2)
        self.assertIn("not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
