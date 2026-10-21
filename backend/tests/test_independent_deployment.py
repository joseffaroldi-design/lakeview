from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import yaml

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"


def _python(code: str, extra_env: dict[str, str] | None = None):
    env = os.environ.copy()
    env.update({
        "ENVIRONMENT": "development",
        "MONGO_URL": "mongodb://127.0.0.1:27017",
        "DB_NAME": "lakeview_test",
        "ADMIN_PASSWORD": "test-only-password",
        "STORAGE_BACKEND": "local",
        "MEDIA_STORAGE_DIR": "/tmp/lakeview-test-media",
    })
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, env=env,
        text=True, capture_output=True,
    )


def test_active_route_surface_includes_public_health_checks():
    proc = _python(
        "import json, server; print(json.dumps(sorted(server.app.openapi()['paths'])))"
    )
    assert proc.returncode == 0, proc.stderr
    routes = json.loads(proc.stdout.strip().splitlines()[-1])
    assert "/api/health/live" in routes
    assert "/api/health/ready" in routes
    assert "/api/auth/login" in routes
    assert "/api/media/upload" in routes
    assert all(not route.startswith("/api/ai-") for route in routes)


def test_liveness_endpoint_responds_without_external_dependencies():
    proc = _python(
        """
import asyncio
import httpx
import server

async def check():
    transport = httpx.ASGITransport(app=server.app)
    async with httpx.AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/api/health/live')
        assert response.status_code == 200
        assert response.json() == {'service': 'lakeview-api', 'status': 'ok'}

asyncio.run(check())
print('ok')
"""
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().endswith("ok")


def test_production_validation_requires_remote_storage_and_explicit_cors():
    proc = _python(
        "import config; config.validate_runtime_config()",
        {"ENVIRONMENT": "production", "ADMIN_PASSWORD": "long-enough-test-password", "CORS_ORIGINS": ""},
    )
    assert proc.returncode != 0
    assert "CORS_ORIGINS" in proc.stderr
    assert "S3_ENDPOINT_URL" in proc.stderr


def test_production_validation_accepts_complete_safe_configuration():
    proc = _python(
        "import config; config.validate_runtime_config(); print('ok')",
        {
            "ENVIRONMENT": "production",
            "ADMIN_PASSWORD": "long-enough-test-password",
            "CORS_ORIGINS": "https://lakeview.example",
            "STORAGE_BACKEND": "s3",
            "S3_ENDPOINT_URL": "https://account.r2.cloudflarestorage.com",
            "S3_ACCESS_KEY_ID": "test",
            "S3_SECRET_ACCESS_KEY": "test",
            "S3_BUCKET": "lakeview-media",
        },
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().endswith("ok")


def test_render_blueprint_has_separate_static_and_api_services():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text())
    services = {service["name"]: service for service in blueprint["services"]}
    assert services["lakeview-api"]["runtime"] == "docker"
    assert services["lakeview-api"]["healthCheckPath"] == "/api/health/live"
    assert services["lakeview-web"]["runtime"] == "static"
    assert services["lakeview-web"]["staticPublishPath"] == "./build"
    assert any(route.get("destination") == "/index.html" for route in services["lakeview-web"]["routes"])


def test_production_requirements_exclude_dormant_vendor_ai_sdks():
    requirements = (BACKEND / "requirements-prod.txt").read_text().lower()
    assert "emergentintegrations" not in requirements
    assert "litellm" not in requirements
    assert "rembg" not in requirements
    for required in ("fastapi", "motor", "boto3", "playwright", "pillow"):
        assert required in requirements


def test_active_frontend_has_no_emergent_runtime_dependency():
    checked = [
        ROOT / "frontend/public/index.html",
        ROOT / "frontend/src/PublicSite.jsx",
        ROOT / "frontend/src/config/siteImages.js",
    ]
    assert all("emergent" not in path.read_text().lower() for path in checked)
