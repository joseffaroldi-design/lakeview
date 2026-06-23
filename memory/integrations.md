# Lakeview — Required Environment Variables

Single source of truth for env config. Verified against `backend/config.py` and `backend/storage.py` on **Sprint 15B.6 — Feb 22, 2026**.

## Required (backend WILL fail to start or operate without these)

| Variable | Loaded by | Consumed by | Failure mode if missing |
|---|---|---|---|
| `MONGO_URL` | `config.py:13` (`os.environ['MONGO_URL']`) | Every router | `KeyError` at import → backend cannot start |
| `DB_NAME` | `config.py:14` | Every router | `KeyError` at import → backend cannot start |
| `ADMIN_PASSWORD` | `config.py:18` | `auth.py` login | `KeyError` at import → backend cannot start |
| `EMERGENT_LLM_KEY` | `storage.py:51` + `ai_engine/client.py:37` | Object storage, all LLM-generated copy paths | Backend STARTS but: remote media returns 500 (45% of library), AI Designer cannot persist outputs, Marketing Pack crashes, Today's Pick falls back to defaults |

## Optional

| Variable | Loaded by | Default | Notes |
|---|---|---|---|
| `CORS_ORIGINS` | `config.py` | `*` | Comma-separated list. Preview uses `*`; production should restrict. |
| `STORAGE_APP_NAME` | `storage.py:23` | `lakeview` | Namespace prefix for object-storage paths. Do not change without migration plan. |
| `MEDIA_STORAGE_DIR` | `storage.py:33` | `/app/backend/media_storage` | Legacy local fallback. 346 of 625 assets still served from here. |
| `REMBG_PREWARM` | `server.py` startup hook | unset (disabled) | Set to `1` to pre-load `rembg` model at boot. Increases pod memory ~300–500 MB. Recommended for prod with `--workers 4` + 1–2 Gi RAM. |

## NOT to be set

| Variable | Why |
|---|---|
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` | Codebase exclusively uses `EMERGENT_LLM_KEY` via the emergentintegrations library. Setting these does nothing and creates a false sense of safety. |

## Verification probes

After any deploy, run these against the env:

```bash
# Probe 1 — storage health (must be initialized:true, reachable:true)
curl -s "$API_URL/api/media/health" -H "Authorization: Bearer $TOKEN" | jq .storage

# Probe 2 — confirm a remote-storage asset round-trips
curl -s -o /dev/null -w "%{http_code}\n" "$API_URL/api/media/thumb/<any-cloud-asset-id>"
# Expected: 200
```

## Historical incident

- **Feb 22, 2026 (Sprint 15B.6)**: `EMERGENT_LLM_KEY` was missing from preview `.env` for an extended period. 104 RuntimeErrors logged. 279/625 assets unreachable. Fixed by adding the line to `/app/backend/.env`; restored on backend restart.
