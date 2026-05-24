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
cors_origins = os.environ.get('CORS_ORIGINS', '*')
ALLOWED_ORIGINS = ["*"] if cors_origins == '*' else cors_origins.split(',')
