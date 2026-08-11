"""Regression coverage for V1 production security configuration."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

BACKEND = Path(__file__).resolve().parents[1]


def _load_origins(environment: str, cors_origins: str | None) -> list[str]:
    env = os.environ.copy()
    env.update({
        "ENVIRONMENT": environment,
        "MONGO_URL": env.get("MONGO_URL", "mongodb://127.0.0.1:27017"),
        "DB_NAME": env.get("DB_NAME", "lakeview_test"),
        "ADMIN_PASSWORD": env.get("ADMIN_PASSWORD", "test-only-password"),
    })
    if cors_origins is None:
        env.pop("CORS_ORIGINS", None)
    else:
        env["CORS_ORIGINS"] = cors_origins

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, config; print(json.dumps(config.ALLOWED_ORIGINS))",
        ],
        cwd=BACKEND,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_production_missing_cors_origins_fails_closed():
    assert _load_origins("production", None) == []


def test_production_blank_cors_origins_fails_closed():
    assert _load_origins("production", "   ") == []


def test_production_explicit_origins_are_trimmed_and_preserved():
    assert _load_origins(
        "production",
        "https://lakeview.example, https://admin.lakeview.example ",
    ) == ["https://lakeview.example", "https://admin.lakeview.example"]


def test_nonproduction_unset_cors_retains_dev_wildcard():
    assert _load_origins("development", None) == ["*"]


def test_photo_flyer_router_remains_unmounted():
    server_source = (BACKEND / "server.py").read_text()
    assert "photo_flyer" not in server_source
