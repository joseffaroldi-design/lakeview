"""Shared configuration and fail-fast production validation."""
import os
import bcrypt
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')


def _required(name: str) -> str:
    value = (os.environ.get(name) or '').strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


# MongoDB connection
mongo_url = _required('MONGO_URL')
client = AsyncIOMotorClient(mongo_url)
db = client[_required('DB_NAME')]

# Admin credentials — load plain password from env, hash once on startup
# (bcrypt verification is timing-safe by design)
_ADMIN_PASSWORD_PLAIN = _required('ADMIN_PASSWORD')
_ADMIN_PASSWORD_HASH = bcrypt.hashpw(_ADMIN_PASSWORD_PLAIN.encode('utf-8'), bcrypt.gensalt())


def verify_admin_password(candidate: str) -> bool:
    """Timing-safe bcrypt comparison of a candidate password."""
    try:
        return bcrypt.checkpw(candidate.encode('utf-8'), _ADMIN_PASSWORD_HASH)
    except (ValueError, TypeError):
        return False


# CORS
# In production, refuse to fall back to wildcard credentialed CORS: the
# combination `allow_credentials=True` + `allow_origins=["*"]` is
# invalid per the CORS spec and unsafe. If ENVIRONMENT=production and
# CORS_ORIGINS is unset or blank, we default to an empty list so no
# cross-origin request is admitted — the operator must configure the
# explicit production domain before browsers can talk to the API.
_env_name = (os.environ.get('ENVIRONMENT') or '').strip().lower()
_cors_raw = (os.environ.get('CORS_ORIGINS') or '').strip()
_IS_PROD = _env_name == 'production'

if _cors_raw and _cors_raw != '*':
    ALLOWED_ORIGINS = [o.strip() for o in _cors_raw.split(',') if o.strip()]
elif _IS_PROD:
    # Fail-safe: no credentialed wildcard in production.
    ALLOWED_ORIGINS = []
else:
    # Dev / preview convenience: allow all when explicitly requested via
    # `*` or when nothing is configured.
    ALLOWED_ORIGINS = ["*"]


def validate_runtime_config() -> None:
    """Reject unsafe/incomplete production configuration before serving traffic."""
    if not _IS_PROD:
        return

    problems = []
    if not ALLOWED_ORIGINS:
        problems.append('CORS_ORIGINS must list the production frontend origin')
    if any(origin == '*' for origin in ALLOWED_ORIGINS):
        problems.append('CORS_ORIGINS cannot contain * in production')
    if len(_ADMIN_PASSWORD_PLAIN) < 12:
        problems.append('ADMIN_PASSWORD must contain at least 12 characters')
    if (os.environ.get('STORAGE_BACKEND') or 's3').strip().lower() != 's3':
        problems.append('STORAGE_BACKEND must be s3 in production')
    for name in ('S3_ENDPOINT_URL', 'S3_ACCESS_KEY_ID', 'S3_SECRET_ACCESS_KEY', 'S3_BUCKET'):
        if not (os.environ.get(name) or '').strip():
            problems.append(f'{name} is required in production')

    if problems:
        raise RuntimeError('Unsafe production configuration: ' + '; '.join(problems))

