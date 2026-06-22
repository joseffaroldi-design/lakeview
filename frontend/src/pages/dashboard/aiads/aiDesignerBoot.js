/**
 * AI Designer Boot Orchestrator — Sprint 15B.2
 *
 * Problem: On AI Designer mount, the parent and children fire 4 API calls in
 * parallel:
 *   - /ai-designer/templates       (parent)
 *   - /ai-designer/jobs/recent     (RecentDesignsRail)
 *   - /ai-designer/themes          (Designer, on step 2)
 *   - /media/assets                (PickPhoto, when library opens)
 *
 * On a cold-started production pod this 4-way burst causes Cloudflare 520s
 * because the origin can't keep up with the simultaneous load.
 *
 * Solution: serialize the 4 calls with a 200ms stagger, in priority order:
 *   1. themes        (needed for step 2)
 *   2. jobs/recent   (rail visible immediately on step 1)
 *   3. templates     (parent state)
 *   4. media/assets  (only needed when user clicks "Pick from Library")
 *
 * Each call uses its own retry-once-on-5xx logic (mirroring the global
 * interceptor in src/index.js) but on a *silent* axios instance so failures
 * do not pop the global red toast. Children surface failures via inline
 * retry buttons instead.
 *
 * The global axios interceptor is left UNCHANGED.
 */
import axios from "axios";
import { API } from "./shared";

export const BOOT_STAGGER_MS = 200;
const BOOT_RETRY_STATUSES = new Set([500, 502, 503, 504, 520, 522, 524]);
const BOOT_RETRY_DELAY_MS = 1000;

// Silent client — no interceptors, no toasts on failure.
const silentClient = axios.create();

/**
 * Single-shot GET with one auto-retry on transient infra/proxy failures.
 * Returns { data, error, status, attempts, durationMs }.
 */
async function silentGet(url, headers) {
  const start = Date.now();
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    try {
      const res = await silentClient.get(url, { headers, timeout: 20000 });
      return {
        data: res.data,
        error: null,
        status: res.status,
        attempts: attempt,
        durationMs: Date.now() - start,
      };
    } catch (e) {
      const status = e.response && e.response.status;
      const isLast = attempt === 2;
      const transient = !status || BOOT_RETRY_STATUSES.has(status);
      if (!transient || isLast) {
        return {
          data: null,
          error: e,
          status: status || 0,
          attempts: attempt,
          durationMs: Date.now() - start,
        };
      }
      // wait then retry once
      await new Promise((r) => setTimeout(r, BOOT_RETRY_DELAY_MS));
    }
  }
  // Unreachable, but TS-style safety
  return { data: null, error: new Error("unknown"), status: 0, attempts: 2, durationMs: Date.now() - start };
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * Fire a Sprint 14B.1A-style analytics event. Silent on failure — we don't
 * want analytics dropping to ever interfere with the UI.
 */
async function fireBootAnalytics(event, metadata, getAuthHeader) {
  try {
    await silentClient.post(
      `${API}/todays-pick/analytics`,
      { event, metadata: metadata || {} },
      { headers: getAuthHeader(), timeout: 5000 }
    );
  } catch (_) {
    /* swallow */
  }
}

/**
 * Orchestrate the staggered boot sequence.
 *
 * The 4 callbacks (`onThemes`, `onRecentJobs`, `onTemplates`, `onMediaAssets`)
 * each receive `{ data, error, status, attempts, durationMs, retry }`. The
 * `retry` field is a function the caller can wire to a button to re-fetch.
 *
 * Order: themes → recent jobs → templates → media assets, with 200ms gap.
 * The returned promise resolves when all 4 have settled (success OR failure);
 * children can render partial UI as each callback fires.
 *
 * @returns {{cancel: () => void, complete: Promise<void>}}
 */
export function bootAiDesigner({
  getAuthHeader,
  onThemes,
  onRecentJobs,
  onTemplates,
  onMediaAssets,
  staggerMs = BOOT_STAGGER_MS,
}) {
  let cancelled = false;

  const callOnce = async (url, key, callback) => {
    const result = await silentGet(`${API}${url}`, getAuthHeader());
    if (cancelled) return;
    if (result.error) {
      await fireBootAnalytics("ai_designer_boot_call_failed", {
        endpoint: key,
        status: result.status,
        attempts: result.attempts,
        duration_ms: result.durationMs,
      }, getAuthHeader);
    } else {
      await fireBootAnalytics("ai_designer_boot_call_success", {
        endpoint: key,
        status: result.status,
        attempts: result.attempts,
        duration_ms: result.durationMs,
      }, getAuthHeader);
    }
    // Provide a `retry` callback that fires the same endpoint once more.
    const retry = () => callOnce(url, key, callback);
    callback({ ...result, retry });
  };

  const complete = (async () => {
    await fireBootAnalytics("ai_designer_boot_start", { stagger_ms: staggerMs }, getAuthHeader);

    const start = Date.now();
    // 1. themes
    await callOnce("/ai-designer/themes", "themes", onThemes);
    if (cancelled) return;
    await wait(staggerMs);
    if (cancelled) return;
    // 2. recent jobs
    await callOnce("/ai-designer/jobs/recent?limit=5", "jobs_recent", onRecentJobs);
    if (cancelled) return;
    await wait(staggerMs);
    if (cancelled) return;
    // 3. templates
    await callOnce("/ai-designer/templates", "templates", onTemplates);
    if (cancelled) return;
    await wait(staggerMs);
    if (cancelled) return;
    // 4. media assets (only needed when user clicks "Pick from Library", but we
    //    prefetch so the button is instant on a warm pod)
    await callOnce("/media/assets?kind=image&limit=24", "media_assets", onMediaAssets);

    if (cancelled) return;
    await fireBootAnalytics("ai_designer_boot_complete", {
      total_duration_ms: Date.now() - start,
    }, getAuthHeader);
  })();

  return {
    cancel: () => { cancelled = true; },
    complete,
  };
}
