"""Pytest bootstrap for backend tests.

Resolves the historical pain point where tests crashed during collection if
ADMIN_PASSWORD / REACT_APP_BACKEND_URL / MONGO_URL / DB_NAME were not exported
into the shell. We now:

1. Load `/app/backend/.env` and `/app/frontend/.env` if present.
2. Fall back to extracting ADMIN_PASSWORD from `/app/memory/test_credentials.md`
   so the same baseline works in CI, in the preview pod, and on a fresh
   developer machine.
3. Register the `slow` pytest mark so `@pytest.mark.slow` no longer emits
   warnings.

NO test logic changes — this is collection-time bootstrap only.
"""
from __future__ import annotations
import os
import re
from pathlib import Path


def _load_env_file(path: Path) -> None:
    """Cheap .env loader (no python-dotenv dep). Does not override existing vars."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _admin_password_from_credentials_file() -> str | None:
    f = Path("/app/memory/test_credentials.md")
    if not f.exists():
        return None
    m = re.search(r"Password\*?\*?\*?:\s*`?([^\s`*]+)", f.read_text())
    return m.group(1) if m else None


# 1. .env files (don't override real env)
_load_env_file(Path("/app/backend/.env"))
_load_env_file(Path("/app/frontend/.env"))

# 2. ADMIN_PASSWORD fallback for local pytest runs.
if not os.environ.get("ADMIN_PASSWORD"):
    pw = _admin_password_from_credentials_file()
    if pw:
        os.environ["ADMIN_PASSWORD"] = pw


def pytest_configure(config):
    """Register custom marks to silence PytestUnknownMarkWarning."""
    config.addinivalue_line(
        "markers",
        "slow: marks tests as slow / sandbox-incompatible (skip with -m 'not slow')",
    )
