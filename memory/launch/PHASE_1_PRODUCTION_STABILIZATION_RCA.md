# Phase 1 — Production Stabilization: Code-Side RCA

**Date**: Feb 24, 2026
**Auditor**: E1 (preview environment)
**Status**: Ready for Emergent Support handoff

---

## TL;DR

Authentication is **deterministic and correct in code**. There is no bug in
the auth path. The production failure is one of **two possible causes**, both
on the Emergent platform side:

1. **Production pod is running an older container image** where
   `ADMIN_PASSWORD` was a different value.
2. **Production pod's `ADMIN_PASSWORD` env var did not propagate from the
   Secrets UI** to the running container (the historical "env var propagation
   bug" already escalated to Support).

Both manifest identically: **old password works, new password doesn't.**
The only way to discriminate between them is to read the running container's
env (`/proc/1/environ` or platform UI showing live env), which requires
Support access.

---

## 1. Complete Auth Code Path (every env-var touchpoint)

```
ENV VAR        WHERE READ                      USED FOR
─────────────  ──────────────────────────────  ────────────────────────────────
ADMIN_PASSWORD config.py:18                    Bcrypt-hashed at module import
MONGO_URL      config.py:12                    Motor client → admin_sessions
DB_NAME        config.py:14                    Same client.db handle
CORS_ORIGINS   config.py:31                    FastAPI CORSMiddleware
ENVIRONMENT    ai_image.py:63                  Variation cap (preview=4, prod=1)
                scripts/media_orphans.py:240   Refuses to mutate prod
```

### Auth flow (deterministic, no LRU caches, no module-state mutation post-import)

**`backend/config.py` (lines 1–27)** — runs ONCE at process import:
```python
_ADMIN_PASSWORD_PLAIN = os.environ['ADMIN_PASSWORD']        # KeyError if missing
_ADMIN_PASSWORD_HASH  = bcrypt.hashpw(_ADMIN_PASSWORD_PLAIN.encode(), bcrypt.gensalt())

def verify_admin_password(candidate: str) -> bool:
    return bcrypt.checkpw(candidate.encode(), _ADMIN_PASSWORD_HASH)
```

**`backend/auth.py::login` (lines 56–80)** — runs per request:
```python
@router.post("/login")
@limiter.limit("5/15 minutes")
async def login(request, data: LoginRequest, response):
    if not verify_admin_password(data.password):
        raise HTTPException(401, "Invalid password")
    session_token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(hours=24)
    await db.admin_sessions.insert_one({...})
    response.set_cookie("session_token", ...)
    return {"token": session_token}
```

**Key properties**:
- Password hash is computed **exactly once** when `config.py` is imported
  (i.e., when the FastAPI process starts).
- Hash is stored in process-local memory (`_ADMIN_PASSWORD_HASH`).
- A live process whose `os.environ['ADMIN_PASSWORD']` is `"foo"` will
  **continue to accept "foo"** until the process is restarted, regardless
  of what the platform UI shows.
- There is **no fallback password**, **no hardcoded value**, **no default**.
  If `ADMIN_PASSWORD` is missing from env, the process crashes on import
  with `KeyError: 'ADMIN_PASSWORD'` and the supervisor will not bring it up.
- Login responses are deterministic: bcrypt match → 200 + token. No match →
  401. `slowapi.limiter` adds a `5/15min` rate limit per real client IP
  (forwarded via `X-Forwarded-For` in `rate_limit.py`).

---

## 2. Preview vs Production Configuration (as expected)

| Variable           | Preview (verified)              | Production (expected)            |
|--------------------|---------------------------------|-----------------------------------|
| `ADMIN_PASSWORD`   | sha256[:8] = `2f599703`, len 32 | Same value set via Secrets UI     |
| `ENVIRONMENT`      | `preview`                       | `production`                      |
| `MONGO_URL`        | local mongo                     | platform-managed mongo (different DB) |
| `DB_NAME`          | `test_database`                 | `lakeview_prod` (or similar)      |
| `EMERGENT_LLM_KEY` | present                         | present (required)                |
| `CORS_ORIGINS`     | `*`                             | (whatever was set)                |

The active **preview** admin password sha256[:8] is `2f599703` — Support
can hash `[REDACTED-scrubbed during V1 release-blocker remediation]` and confirm match.

---

## 3. Reproduction Steps for Support

### A. Confirm the symptom on production

```bash
PROD="https://lakeview-grill.emergent.host"

# Expected: 200 (since the new password was set in Secrets UI)
# Actually seeing: 401
curl -s -o /dev/null -w "new_password=%{http_code}\n" \
  -X POST "$PROD/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"password":"[REDACTED-scrubbed during V1 release-blocker remediation]"}'

# Expected: 401 (the old password should no longer work)
# Actually seeing: 200  ← THE BUG
curl -s -o /dev/null -w "old_password=%{http_code}\n" \
  -X POST "$PROD/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"password":"<OLD_PASSWORD_VALUE>"}'
```

### B. Diagnose from inside the prod container (Support action)

Pick ONE of these — any of the three definitively proves which case it is:

```bash
# (1) Read the running process's actual environment
cat /proc/1/environ | tr '\0' '\n' | grep ADMIN_PASSWORD

# (2) Have the live process print its own hash
python -c "
import bcrypt, os
pw = os.environ['ADMIN_PASSWORD']
import hashlib
print('sha256[:8] =', hashlib.sha256(pw.encode()).hexdigest()[:8])
print('len =', len(pw))
"

# (3) Read the deployment manifest the platform actually injected
kubectl get pod -o jsonpath='{.spec.containers[0].env}' | python -m json.tool
```

If sha256[:8] of `ADMIN_PASSWORD` inside the container is **NOT** `2f599703`,
then the env var did not propagate from the Secrets UI to the container
(case 2). If sha256[:8] **IS** `2f599703` but old password still works,
then the container is running stale code that has a different hash baked
in (case 1).

### C. Verify the fix after Support action

After Support corrects the env injection / forces a rolling restart:

```bash
# Old password must now return 401
curl -s -o /dev/null -w "%{http_code}\n" -X POST "$PROD/api/auth/login" \
  -H "Content-Type: application/json" -d '{"password":"<OLD>"}'   # → 401

# New password must return 200 + token
curl -s -X POST "$PROD/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"password":"[REDACTED-scrubbed during V1 release-blocker remediation]"}' | python -m json.tool
# → { "message": "Login successful", "token": "..." }
```

---

## 4. Why this is NOT a code bug

| Hypothesis                          | Verdict | Why ruled out                          |
|-------------------------------------|---------|----------------------------------------|
| Hardcoded fallback password         | ❌      | `config.py:18` uses `os.environ['ADMIN_PASSWORD']` (KeyError on miss — no fallback). `tests/test_cleanup_p0_p1.py` regression-locks this. |
| Cached old hash in memory after restart | ❌  | Hash is re-derived on every process start. A supervisor restart picks up new env. |
| Session token from old password still valid | ⚠️  | Possible side-effect: a session minted under the old password remains valid for 24 h. Not the bug, but worth `db.admin_sessions.deleteMany({})` post-fix. |
| `os.environ.get` with default       | ❌      | All references use `os.environ[...]` (subscript) for the auth-critical var. |
| Bcrypt collision / non-deterministic hash | ❌ | bcrypt is a one-way function. Same input → matchable hash. |
| Multiple `ADMIN_PASSWORD` env declarations | ❌ | Single source (`backend/.env`). No `.env.local`, `.env.production`, override files. |
| Worker forked before env update     | ✅ (likely root cause)| Pre-fork uvicorn workers inherit env at master startup. New env in Secrets UI requires a full process restart, not a SIGHUP. |

**Most likely cause**: the production pod was redeployed with new env values
in the manifest, but the running container's process was not fully restarted.
Either supervisor's "restart" reused the same Python interpreter, or the
deployment "rolling update" never actually replaced the pod.

---

## 5. One-Paragraph Handoff to Emergent Support

> The Lakeview Burgers production deployment (`lakeview-grill.emergent.host`)
> is rejecting the current `ADMIN_PASSWORD` value set in the platform Secrets
> UI and still accepting an earlier value. Backend code reads
> `os.environ['ADMIN_PASSWORD']` exactly once at process import and stores a
> bcrypt hash in memory (see `backend/config.py:18`). There is no fallback
> or default. Preview verifies correctly with sha256[:8]=`2f599703` (len 32).
> Please (a) confirm the value injected into the running production container
> matches what's in the Secrets UI by reading `/proc/1/environ` in the pod,
> and (b) force a full pod replacement (not a process SIGHUP) so the new env
> is picked up. After (b), please run
> `db.admin_sessions.deleteMany({})` against the prod Mongo to invalidate
> any sessions minted under the old password.

---

**Status**: Auth code is launch-ready. Production unblock is a platform
operation, not a code change.
