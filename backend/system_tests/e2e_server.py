"""Test-only server entry point. Never imported by the production application."""

import argparse

import uvicorn
from sqlalchemy.engine import make_url

from system_tests.support import fake_generate_json


def main():
    import os

    # Refuse to start this fake-provider server on an ordinary application DB.
    database = make_url(os.environ["DATABASE_URL"]).database or ""
    if not database.startswith("mebod_test_") or not os.environ.get("TEST_POSTGRES_URL"):
        raise RuntimeError("E2E server requires a disposable test database")

    from app.services import llm_client

    llm_client.generate_json_response = fake_generate_json
    from app.main import app

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
