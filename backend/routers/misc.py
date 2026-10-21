"""Public liveness and dependency-readiness endpoints."""
import asyncio

from fastapi import APIRouter, Response, status

from config import db
import storage as objstore

router = APIRouter()


@router.get("/")
async def root():
    return {"service": "lakeview-api", "status": "ok"}


@router.get("/health/live")
async def liveness():
    """Process-only health check used by Render; performs no external writes."""
    return {"service": "lakeview-api", "status": "ok"}


@router.get("/health/ready")
async def readiness(response: Response):
    """Read-only MongoDB and object-storage dependency check for operators."""
    storage_health = await asyncio.to_thread(objstore.health)
    public_storage_health = {
        "backend": storage_health.get("backend"),
        "configured": storage_health.get("configured", False),
        "reachable": storage_health.get("reachable", False),
        "error": "unavailable" if storage_health.get("error") else None,
    }
    checks = {
        "mongodb": {"reachable": False, "error": None},
        "storage": public_storage_health,
    }
    try:
        await asyncio.wait_for(db.command("ping"), timeout=5)
        checks["mongodb"]["reachable"] = True
    except Exception as exc:  # noqa: BLE001
        checks["mongodb"]["error"] = type(exc).__name__

    ready = checks["mongodb"]["reachable"] and checks["storage"].get("reachable", False)
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"service": "lakeview-api", "status": "ready" if ready else "degraded", "checks": checks}
