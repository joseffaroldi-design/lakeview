"""Shared configuration: env loading, MongoDB client, admin password verification."""
import os
import bcrypt
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Admin credentials — load plain password from env, hash once on startup
# (bcrypt verification is timing-safe by design)
_ADMIN_PASSWORD_PLAIN = os.environ['ADMIN_PASSWORD']
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

