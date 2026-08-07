# Test Credentials

## Admin Dashboard
- **Login URL**: `/login`
- **Password**: _stored only in the backend `ADMIN_PASSWORD` environment variable — never committed to git_
- **Auth Method**: JWT Bearer token (stored in localStorage as `admin_token`)

### For local / preview development
Retrieve the current admin password by reading `ADMIN_PASSWORD` from `/app/backend/.env` on the running container:

```
grep '^ADMIN_PASSWORD=' /app/backend/.env
```

## For testing agents and automation
Do the same lookup at runtime — do not paste a password into this file.

## Notes (Sprint 15B.5 — Auth Hardening, Feb 2026)
- Password value rotated to a 32-char `secrets.token_urlsafe(24)`.
- `/api/auth/login` rate-limited to **5 attempts / 15 minutes per IP** (was 10/min).
- After 5 failures within 15 min, IP receives HTTP 429 until the rolling window expires.
- bcrypt-hashed at module import; constant-time check via `bcrypt.checkpw`.
- Session token: 32-byte `secrets.token_urlsafe`, 24 h expiry, TTL index `as_ttl` on `admin_sessions.expires_at`.

## V1 release-blocker remediation (Feb 2026)
The previously plaintext admin password in this tracked file was scrubbed
during the V1 release-blocker remediation pass. If the exposed value was
ever used against the production `ADMIN_PASSWORD`, **owner action is
required to rotate `ADMIN_PASSWORD` in the production environment before
deploy.** The remediation pass did not touch the running environment
variable.
