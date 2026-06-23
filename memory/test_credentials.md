# Test Credentials

## Admin Dashboard
- **Login URL**: /login
- **Password**: 83CeLOZJQbOcopK0yYmNtdRQg4VPii8o
- **Auth Method**: JWT Bearer token (stored in localStorage as `admin_token`)

## Notes (Sprint 15B.5 — Auth Hardening, Feb 2026)
- Rotated from `Lakeview872` to 32-char `secrets.token_urlsafe(24)` value.
- `/api/auth/login` rate-limited to **5 attempts / 15 minutes per IP** (was 10/min).
- After 5 failures within 15 min, IP receives HTTP 429 until the rolling window expires.
- bcrypt-hashed at module import; constant-time check via `bcrypt.checkpw`.
- Session token: 32-byte `secrets.token_urlsafe`, 24 h expiry, TTL index `as_ttl` on `admin_sessions.expires_at`.
