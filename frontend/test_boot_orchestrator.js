/**
 * Sprint 15B.2 — AI Designer Boot Orchestrator unit tests (Node-only mirror)
 *
 * Replicates the exact logic of `aiDesignerBoot.js` against a mock HTTP server.
 * Run with: cd /app/frontend && node test_boot_orchestrator.js
 */
const axios = require("axios");
const http = require("http");

// ----- Mirror of aiDesignerBoot.js -----
const BOOT_STAGGER_MS = 200;
const BOOT_RETRY_STATUSES = new Set([500, 502, 503, 504, 520, 522, 524]);
const BOOT_RETRY_DELAY_MS = 1000;
let API; // set per test

function makeBoot() {
  const silentClient = axios.create();

  async function silentGet(url, headers) {
    const start = Date.now();
    for (let attempt = 1; attempt <= 2; attempt += 1) {
      try {
        const res = await silentClient.get(url, { headers, timeout: 20000 });
        return { data: res.data, error: null, status: res.status, attempts: attempt, durationMs: Date.now() - start };
      } catch (e) {
        const status = e.response && e.response.status;
        const isLast = attempt === 2;
        const transient = !status || BOOT_RETRY_STATUSES.has(status);
        if (!transient || isLast) {
          return { data: null, error: e, status: status || 0, attempts: attempt, durationMs: Date.now() - start };
        }
        await new Promise((r) => setTimeout(r, BOOT_RETRY_DELAY_MS));
      }
    }
    return { data: null, error: new Error("unknown"), status: 0, attempts: 2, durationMs: Date.now() - start };
  }

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  async function fireBootAnalytics(event, metadata, getAuthHeader) {
    try {
      await silentClient.post(`${API}/todays-pick/analytics`, { event, metadata: metadata || {} },
        { headers: getAuthHeader(), timeout: 5000 });
    } catch (_) { /* swallow */ }
  }

  function bootAiDesigner({ getAuthHeader, onThemes, onRecentJobs, onTemplates, onMediaAssets, staggerMs = BOOT_STAGGER_MS }) {
    let cancelled = false;
    const callOnce = async (url, key, callback) => {
      const result = await silentGet(`${API}${url}`, getAuthHeader());
      if (cancelled) return;
      const evt = result.error ? "ai_designer_boot_call_failed" : "ai_designer_boot_call_success";
      await fireBootAnalytics(evt, { endpoint: key, status: result.status, attempts: result.attempts, duration_ms: result.durationMs }, getAuthHeader);
      const retry = () => callOnce(url, key, callback);
      callback({ ...result, retry });
    };
    const complete = (async () => {
      await fireBootAnalytics("ai_designer_boot_start", { stagger_ms: staggerMs }, getAuthHeader);
      const start = Date.now();
      await callOnce("/ai-designer/themes", "themes", onThemes);
      if (cancelled) return;
      await wait(staggerMs); if (cancelled) return;
      await callOnce("/ai-designer/jobs/recent?limit=5", "jobs_recent", onRecentJobs);
      if (cancelled) return;
      await wait(staggerMs); if (cancelled) return;
      await callOnce("/ai-designer/templates", "templates", onTemplates);
      if (cancelled) return;
      await wait(staggerMs); if (cancelled) return;
      await callOnce("/media/assets?kind=image&limit=24", "media_assets", onMediaAssets);
      if (cancelled) return;
      await fireBootAnalytics("ai_designer_boot_complete", { total_duration_ms: Date.now() - start }, getAuthHeader);
    })();
    return { cancel: () => { cancelled = true; }, complete };
  }

  return bootAiDesigner;
}

// ----- Mock HTTP server -----
const PORT = 39872;
let endpointPlan = {};
let callLog = [];
let analyticsBodies = [];

function startServer() {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      let body = "";
      req.on("data", (c) => { body += c; });
      req.on("end", () => {
        callLog.push({ url: req.url, time: Date.now() });
        if (req.url.startsWith("/api/todays-pick/analytics")) {
          try { analyticsBodies.push(JSON.parse(body)); } catch (_) {}
        }
        const key = Object.keys(endpointPlan).find((k) => req.url.startsWith(k));
        if (!key) { res.writeHead(404); res.end(); return; }
        const seq = endpointPlan[key];
        const idx = Math.min(callLog.filter((c) => c.url.startsWith(key)).length - 1, seq.length - 1);
        const status = seq[idx];
        res.writeHead(status, { "Content-Type": "application/json" });
        res.end('{"ok":true}');
      });
    });
    srv.listen(PORT, () => { API = `http://127.0.0.1:${PORT}/api`; resolve(srv); });
  });
}

function resetState() { endpointPlan = {}; callLog = []; analyticsBodies = []; }

async function test1_happy() {
  console.log("\n=== TEST 1 — Happy path: all 4 succeed, in order with stagger ===");
  resetState();
  endpointPlan = {
    "/api/ai-designer/themes": [200],
    "/api/ai-designer/jobs/recent": [200],
    "/api/ai-designer/templates": [200],
    "/api/media/assets": [200],
    "/api/todays-pick/analytics": Array(10).fill(200),
  };
  const bootAiDesigner = makeBoot();
  const got = {};
  const t0 = Date.now();
  const handle = bootAiDesigner({
    getAuthHeader: () => ({}),
    onThemes: (r) => { got.themes = r.status; },
    onRecentJobs: (r) => { got.recent = r.status; },
    onTemplates: (r) => { got.templates = r.status; },
    onMediaAssets: (r) => { got.assets = r.status; },
    staggerMs: 50,
  });
  await handle.complete;
  const elapsed = Date.now() - t0;
  const apiCalls = callLog.filter((c) => !c.url.includes("analytics"));
  const order = apiCalls.map((c) => c.url);
  const expected = [
    "/api/ai-designer/themes",
    "/api/ai-designer/jobs/recent?limit=5",
    "/api/ai-designer/templates",
    "/api/media/assets?kind=image&limit=24",
  ];
  const orderOk = JSON.stringify(order) === JSON.stringify(expected);
  const allOk = got.themes === 200 && got.recent === 200 && got.templates === 200 && got.assets === 200;
  const analyticsCount = analyticsBodies.length;
  console.log("  Statuses:", got);
  console.log("  Order matches:", orderOk);
  console.log("  Stagger respected (>=150ms for 3x50ms gaps):", elapsed >= 150);
  console.log("  Analytics fired:", analyticsCount, "(expected 6 = 1 start + 4 success + 1 complete)");
  const pass = allOk && orderOk && analyticsCount === 6 && elapsed >= 150;
  console.log(pass ? "PASS" : "FAIL");
  return pass;
}

async function test2_transient_retry() {
  console.log("\n=== TEST 2 — Themes 520→200: silent retry recovers ===");
  resetState();
  endpointPlan = {
    "/api/ai-designer/themes": [520, 200],
    "/api/ai-designer/jobs/recent": [200],
    "/api/ai-designer/templates": [200],
    "/api/media/assets": [200],
    "/api/todays-pick/analytics": Array(10).fill(200),
  };
  const bootAiDesigner = makeBoot();
  let themesResult = null;
  const handle = bootAiDesigner({
    getAuthHeader: () => ({}),
    onThemes: (r) => { themesResult = r; },
    onRecentJobs: () => {}, onTemplates: () => {}, onMediaAssets: () => {},
    staggerMs: 20,
  });
  await handle.complete;
  const themesCalls = callLog.filter((c) => c.url.startsWith("/api/ai-designer/themes"));
  const pass = themesResult.status === 200 && themesResult.attempts === 2 && !themesResult.error && themesCalls.length === 2;
  console.log("  themesResult:", { status: themesResult.status, attempts: themesResult.attempts, error: !!themesResult.error });
  console.log("  Themes call count:", themesCalls.length, "(expected 2)");
  console.log(pass ? "PASS" : "FAIL");
  return pass;
}

async function test3_one_fails_others_succeed() {
  console.log("\n=== TEST 3 — Jobs/recent persistently 520: others still succeed ===");
  resetState();
  endpointPlan = {
    "/api/ai-designer/themes": [200],
    "/api/ai-designer/jobs/recent": [520, 520],
    "/api/ai-designer/templates": [200],
    "/api/media/assets": [200],
    "/api/todays-pick/analytics": Array(10).fill(200),
  };
  const bootAiDesigner = makeBoot();
  const results = {};
  const handle = bootAiDesigner({
    getAuthHeader: () => ({}),
    onThemes: (r) => { results.themes = r; },
    onRecentJobs: (r) => { results.recent = r; },
    onTemplates: (r) => { results.templates = r; },
    onMediaAssets: (r) => { results.assets = r; },
    staggerMs: 20,
  });
  await handle.complete;
  const pass = results.themes.status === 200 && !results.themes.error
    && results.recent.error && results.recent.attempts === 2
    && results.templates.status === 200 && !results.templates.error
    && results.assets.status === 200 && !results.assets.error
    && typeof results.recent.retry === "function";
  console.log("  themes:", results.themes.status === 200 ? "OK" : "FAIL");
  console.log("  recent (expected failure):", results.recent.error ? "FAILED as expected" : "FAIL");
  console.log("  templates:", results.templates.status === 200 ? "OK" : "FAIL");
  console.log("  media assets:", results.assets.status === 200 ? "OK" : "FAIL");
  console.log("  retry callback present on failed call:", typeof results.recent.retry === "function");
  console.log(pass ? "PASS" : "FAIL");
  return pass;
}

async function test4_analytics_events() {
  console.log("\n=== TEST 4 — Analytics events fired with right names ===");
  resetState();
  endpointPlan = {
    "/api/ai-designer/themes": [200],
    "/api/ai-designer/jobs/recent": [520, 520], // 1 failure to also get _failed event
    "/api/ai-designer/templates": [200],
    "/api/media/assets": [200],
    "/api/todays-pick/analytics": Array(20).fill(200),
  };
  const bootAiDesigner = makeBoot();
  const handle = bootAiDesigner({
    getAuthHeader: () => ({}),
    onThemes: () => {}, onRecentJobs: () => {}, onTemplates: () => {}, onMediaAssets: () => {},
    staggerMs: 20,
  });
  await handle.complete;
  const events = analyticsBodies.map((b) => b.event);
  const has = (e) => events.includes(e);
  const hasStart = has("ai_designer_boot_start");
  const hasComplete = has("ai_designer_boot_complete");
  const hasSuccess = has("ai_designer_boot_call_success");
  const hasFailed = has("ai_designer_boot_call_failed");
  console.log("  Events:", events);
  const pass = hasStart && hasComplete && hasSuccess && hasFailed;
  console.log(pass ? "PASS" : "FAIL");
  return pass;
}

async function test5_cancel() {
  console.log("\n=== TEST 5 — cancel() stops remaining calls ===");
  resetState();
  endpointPlan = {
    "/api/ai-designer/themes": [200],
    "/api/ai-designer/jobs/recent": [200],
    "/api/ai-designer/templates": [200],
    "/api/media/assets": [200],
    "/api/todays-pick/analytics": Array(20).fill(200),
  };
  const bootAiDesigner = makeBoot();
  let callbackCount = 0;
  const handle = bootAiDesigner({
    getAuthHeader: () => ({}),
    onThemes: () => { callbackCount += 1; },
    onRecentJobs: () => { callbackCount += 1; },
    onTemplates: () => { callbackCount += 1; },
    onMediaAssets: () => { callbackCount += 1; },
    staggerMs: 200,
  });
  setTimeout(() => handle.cancel(), 100);
  await handle.complete;
  console.log("  Callbacks fired after cancel:", callbackCount, "(expected 1)");
  const pass = callbackCount === 1;
  console.log(pass ? "PASS" : "FAIL");
  return pass;
}

async function test6_retry_via_callback() {
  console.log("\n=== TEST 6 — retry() callback re-fires the failed endpoint ===");
  resetState();
  endpointPlan = {
    "/api/ai-designer/themes": [200],
    "/api/ai-designer/jobs/recent": [520, 520, 200], // fail twice, succeed on user retry
    "/api/ai-designer/templates": [200],
    "/api/media/assets": [200],
    "/api/todays-pick/analytics": Array(20).fill(200),
  };
  const bootAiDesigner = makeBoot();
  let recentResults = [];
  const handle = bootAiDesigner({
    getAuthHeader: () => ({}),
    onThemes: () => {}, onTemplates: () => {}, onMediaAssets: () => {},
    onRecentJobs: (r) => { recentResults.push(r); },
    staggerMs: 20,
  });
  await handle.complete;
  // First boot failed
  const firstFailed = recentResults.length === 1 && recentResults[0].error;
  // User clicks "Try again"
  await recentResults[0].retry();
  const secondSucceeded = recentResults.length === 2 && recentResults[1].status === 200 && !recentResults[1].error;
  console.log("  First load failed:", firstFailed);
  console.log("  Retry succeeded:", secondSucceeded);
  const pass = firstFailed && secondSucceeded;
  console.log(pass ? "PASS" : "FAIL");
  return pass;
}

(async () => {
  const srv = await startServer();
  let allPass = true;
  try {
    allPass = (await test1_happy()) && allPass;
    allPass = (await test2_transient_retry()) && allPass;
    allPass = (await test3_one_fails_others_succeed()) && allPass;
    allPass = (await test4_analytics_events()) && allPass;
    allPass = (await test5_cancel()) && allPass;
    allPass = (await test6_retry_via_callback()) && allPass;
    console.log(`\n${allPass ? "✅ ALL TESTS PASSED" : "❌ SOME TESTS FAILED"}`);
    process.exit(allPass ? 0 : 1);
  } finally {
    srv.close();
  }
})();
