"""Shared configuration: env loading, MongoDB client, admin hash."""
import os
import hashlib
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Admin credentials — required, no fallback
ADMIN_PASSWORD = os.environ['ADMIN_PASSWORD']
ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()

# CORS
cors_origins = os.environ.get('CORS_ORIGINS', '*')
ALLOWED_ORIGINS = ["*"] if cors_origins == '*' else cors_origins.split(',')
