import os
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

import httpx
import pytest
from playwright.sync_api import sync_playwright

from system_tests.support import ARTIFACTS, BACKEND
from system_tests.support import test_environment as server_env


@pytest.fixture
def web_server(postgres_url, seeded_engine, request):
    assert (BACKEND.parent / "frontend/dist/index.html").is_file(), "Build frontend before E2E tests"
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}"
    artifacts = ARTIFACTS / request.node.name
    artifacts.mkdir(parents=True, exist_ok=True)
    with (artifacts / "server.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "system_tests.e2e_server", "--port", str(port)],
            cwd=BACKEND, env=server_env(postgres_url), stdout=log, stderr=log,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        try:
            deadline = time.monotonic() + 45
            with httpx.Client(base_url=base_url, timeout=1, trust_env=False) as client:
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        pytest.fail(f"E2E server exited; inspect {artifacts / 'server.log'}")
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.2)
                else:
                    pytest.fail(f"E2E server readiness timed out; inspect {artifacts / 'server.log'}")
            yield base_url
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(headless=True)
        yield instance
        instance.close()


@pytest.fixture
def page(browser, web_server, request):
    context = browser.new_context(base_url=web_server, viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    # Keep tests offline except for this test server. Never visit source forums.
    context.route("**/*", lambda route: route.continue_()
                  if urlparse(route.request.url).netloc == urlparse(web_server).netloc else route.abort())
    context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page = context.new_page()
    page.set_default_timeout(15000)
    errors, server_errors = [], []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("response", lambda response: server_errors.append(f"{response.status} {response.url}")
            if response.status >= 500 else None)
    try:
        yield page
        assert not errors, errors
        assert not server_errors, server_errors
    finally:
        report = getattr(request.node, "rep_call", None)
        failed = not report or report.failed or errors or server_errors
        if failed:
            target = ARTIFACTS / request.node.name
            target.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(target / "failure.png"), full_page=True)
            context.tracing.stop(path=str(target / "trace.zip"))
        else:
            context.tracing.stop()
        context.close()
