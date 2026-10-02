# PostgreSQL integration and browser tests

These tests run migrations and the real application against disposable PostgreSQL databases. Browser tests use Chromium, the built Vue application, FastAPI, cookie authentication and PostgreSQL together. Only the external language-model response is replaced with deterministic test data; scheduled crawlers are disabled. Live forum crawling and Gemini connectivity are outside this suite.

## Install dependencies

From the repository root in PowerShell:

```powershell
backend\venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
Push-Location frontend
npm ci
Pop-Location
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) 'backend/.test-artifacts/browsers'
backend\venv\Scripts\python.exe -m playwright install chromium
```

Python, Node.js/npm and PostgreSQL binaries are required. On Windows, add the PostgreSQL `bin` directory to PATH if necessary (for example `C:\Program Files\PostgreSQL\18\bin`). The browser installation and test run must use the same `PLAYWRIGHT_BROWSERS_PATH` value. On Linux, use `python -m playwright install --with-deps chromium` to install browser dependencies.

## Run with an isolated local PostgreSQL instance

```powershell
backend\venv\Scripts\python.exe backend/scripts/run_system_tests.py --local-postgres --suite all
```

The runner initializes a temporary cluster under `backend/.test-artifacts`, binds it to a free localhost port, builds the frontend, runs the tests, then stops its own cluster and removes its data directory. It leaves logs for diagnosis. It does not stop existing PostgreSQL services. The temporary local cluster uses trust authentication; use it only for these synthetic test fixtures.

Use `--suite postgres` for integration tests alone or `--suite e2e` for browser tests alone. Additional pytest arguments are accepted, for example `-x` or `-k quota`.

## Run against a dedicated test PostgreSQL server

Set `TEST_POSTGRES_URL` explicitly to a local or CI test server with a role allowed to create and drop databases, then omit `--local-postgres`:

```powershell
$env:TEST_POSTGRES_URL = 'postgresql://postgres:system-test-only@127.0.0.1:5432/postgres'
backend\venv\Scripts\python.exe backend/scripts/run_system_tests.py --suite all
```

The fixtures create a unique `mebod_test_<uuid>` database for each test and drop only that generated database afterward. They never migrate or seed the database named in the connection URL. The runner requires `TEST_POSTGRES_URL` explicitly and does not fall back to the application's `DATABASE_URL` or `.env`. Use a dedicated test server to keep test load separate from application traffic.

## Coverage and results

- PostgreSQL: upgrade from an empty database and the legacy `database/init.sql`, repeatable startup, migrated schema and foreign keys, preservation of existing articles, concurrent lock acquisition, dashboard filtering, JSON analysis/history ownership, XLSX contents, QA quotas and guest authorization.
- Chromium: incorrect and correct login, session persistence and logout, keyword search, platform filtering, article detail/comments, XLSX download, QA, history, report view, guest and free-plan restrictions.
- Browser fixtures reject external HTTP requests and fail on uncaught JavaScript exceptions or HTTP 5xx responses.

Results are written to `backend/.test-artifacts/<suite>-results.xml`. Pytest temporary files use a unique `pytest-<uuid>` directory inside the same artifact folder, avoiding permission conflicts with Windows' shared temporary directory. Browser failures additionally save `failure.png` and `trace.zip` beside the server log in a directory named after the test. Open a trace with:

```powershell
backend\venv\Scripts\python.exe -m playwright show-trace backend/.test-artifacts/<test-name>/trace.zip
```

The GitHub Actions `system-tests` job provisions PostgreSQL 18, installs Chromium, runs both suites and uploads test results and failure diagnostics. Adding this workflow does not imply that a remote CI run has completed.

The normal `python -m pytest tests` suite still uses SQLite and requires no PostgreSQL server. System tests live outside the default pytest test paths and must be requested explicitly.

## Baseline migration

The original Alembic baseline was empty and assumed tables already existed, so a fresh PostgreSQL installation failed in a later migration. The baseline now reads the frozen `backend/alembic/baseline_schema.sql` snapshot, creates missing original tables and fills the columns missing from the legacy SQL initializer. Later migrations remain responsible for subsequent schema changes. Already-stamped databases do not rerun the baseline. Do not regenerate this historical snapshot from future ORM models.
