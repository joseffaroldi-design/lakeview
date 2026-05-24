"""Shared rate limiter using slowapi (per real client IP via X-Forwarded-For)."""
from slowapi import Limiter
from slowapi.util import get_remote_address


def get_client_ip(request) -> str:
    """Return the original client IP. Honors X-Forwarded-For when present
    (Kubernetes ingress forwards the real client IP this way)."""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        # X-Forwarded-For: client, proxy1, proxy2 -> take the first
        return fwd.split(",")[0].strip()
    return get_remote_address(request)


# Per-IP limiter using forwarded client IP
limiter = Limiter(key_func=get_client_ip)
