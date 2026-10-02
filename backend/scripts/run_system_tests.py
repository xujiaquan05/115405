"""Run real PostgreSQL/browser tests, optionally with an isolated local PG cluster."""

import argparse
import os
import shutil
import socket
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

BACKEND = Path(__file__).resolve().parents[1]
ARTIFACTS = BACKEND / ".test-artifacts"
HIDDEN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


@contextmanager
def local_postgres():
    initdb, pg_ctl = shutil.which("initdb"), shutil.which("pg_ctl")
    if not initdb or not pg_ctl:
        raise RuntimeError("Put PostgreSQL bin on PATH, or provide TEST_POSTGRES_URL without --local-postgres")
    root = (ARTIFACTS / ("postgres-" + uuid4().hex)).resolve()
    root.mkdir(parents=True)
    data = root / "data"
    port = free_port()
    started = False
    try:
        subprocess.run([initdb, "-D", str(data), "-U", "postgres", "--auth=trust", "--encoding=UTF8", "--locale=C"],
                       check=True, capture_output=True, creationflags=HIDDEN)
        subprocess.run([pg_ctl, "-D", str(data), "-l", str(root / "server.log"),
                        "-o", f"-h 127.0.0.1 -p {port} -F", "-w", "start"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=45, creationflags=HIDDEN)
        started = True
        yield f"postgresql://postgres@127.0.0.1:{port}/postgres"
    finally:
        stopped = not started
        if started or (data / "postmaster.pid").exists():
            result = subprocess.run([pg_ctl, "-D", str(data), "-m", "fast", "-w", "stop"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=45, creationflags=HIDDEN)
            stopped = result.returncode == 0
        # Verify the exact deletion target stays inside our generated artifact directory.
        if stopped and data.exists() and data.resolve().is_relative_to(ARTIFACTS.resolve()):
            shutil.rmtree(data)


def run(suite, admin_url, extra):
    if not admin_url:
        raise RuntimeError("Set TEST_POSTGRES_URL explicitly or pass --local-postgres; DATABASE_URL is never used")
    env = {**os.environ, "TEST_POSTGRES_URL": admin_url, "PYTHONIOENCODING": "utf-8",
           "GOOGLE_API_KEY": "", "PYTHON_DOTENV_DISABLED": "1",
           "JWT_SECRET": "isolated-system-tests-only-5948-not-for-production", "PBKDF2_ITERATIONS": "1000"}
    if suite in ("all", "e2e"):
        npm = "npm.cmd" if os.name == "nt" else "npm"
        subprocess.run([npm, "run", "build"], cwd=BACKEND.parent / "frontend", env=env, check=True)
    targets = []
    if suite in ("all", "postgres"):
        targets.append("system_tests/test_postgres.py")
    if suite in ("all", "e2e"):
        targets.append("system_tests/e2e")
    ARTIFACTS.mkdir(exist_ok=True)
    # Use a fresh workspace directory instead of Windows' potentially inaccessible
    # shared pytest temp root. A UUID prevents pytest from clearing another run.
    temp_root = ARTIFACTS / ("pytest-" + uuid4().hex)
    return subprocess.run([sys.executable, "-m", "pytest", *targets, "-q", "--tb=short",
                           f"--basetemp={temp_root}",
                           f"--junitxml={ARTIFACTS / (suite + '-results.xml')}", *extra],
                          cwd=BACKEND, env=env).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["all", "postgres", "e2e"], default="all")
    parser.add_argument("--local-postgres", action="store_true")
    args, extra = parser.parse_known_args()
    if args.local_postgres:
        with local_postgres() as url:
            return run(args.suite, url, extra)
    return run(args.suite, os.environ.get("TEST_POSTGRES_URL"), extra)


if __name__ == "__main__":
    raise SystemExit(main())
