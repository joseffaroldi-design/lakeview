/**
 * Sprint 15B.1 — Retry interceptor unit test
 *
 * Validates the exact retry logic from src/index.js by replicating it onto
 * an isolated axios instance and exercising 5 scenarios with a mock server.
 *
 * Run with: cd /app/frontend && node test_retry_interceptor.js
 */
const axios = require("axios");
const http = require("http");

// ----- Replica of the retry logic from src/index.js -----
const RETRY_STATUSES = new Set([500, 502, 503, 504, 520, 522, 524]);
const RETRY_DELAY_MS = 1000;

let toastCount = 0;
const fakeToast = { error: () => { toastCount += 1; } };

const isAdminRoute = () => true; // simulate /dashboard

function installInterceptor(client) {
  client.interceptors.response.use(
    (r) => r,
    async (error) => {
      const status = error.response && error.response.status;
      const config = error.config || {};
      const path = config.url || "";
      const isAuthEndpoint = path.includes("/auth/login");
      if (!isAdminRoute()) return Promise.reject(error);

      if (RETRY_STATUSES.has(status) && !config.__retried) {
        config.__retried = true;
        console.log(`  [retry] ${status} on ${path} — retrying once after ${RETRY_DELAY_MS}ms`);
        await new Promise((r) => setTimeout(r, RETRY_DELAY_MS));
        try {
          return await client.request(config);
        } catch (retryError) {
          return Promise.reject(retryError);
        }
      }
      const finalStatus = status;
      if (finalStatus === 401 && !isAuthEndpoint) fakeToast.error("Session expired");
      else if (finalStatus === 403 && !isAuthEndpoint) fakeToast.error("Access denied");
      else if (finalStatus >= 500) fakeToast.error(`Server error ${finalStatus}`);
      return Promise.reject(error);
    }
  );
}

// ----- Mock HTTP server -----
let serverState = {};
const PORT = 39871;

function startServer() {
  return new Promise((resolve) => {
    const srv = http.createServer((req, res) => {
      const url = req.url;
      // /seq/<status1>/<status2>/<status3>... — returns next status in sequence per requestId
      const m = url.match(/^\/seq\/([\d/]+)/);
      if (m) {
        const seq = m[1].split("/").filter(Boolean).map(Number);
        const key = url;
        serverState[key] = (serverState[key] || 0) + 1;
        const idx = Math.min(serverState[key] - 1, seq.length - 1);
        const status = seq[idx];
        res.writeHead(status, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ status, call: serverState[key] }));
        return;
      }
      res.writeHead(404); res.end();
    });
    srv.listen(PORT, () => resolve(srv));
  });
}

async function runTest(name, url, expect) {
  toastCount = 0;
  const before = Object.keys(serverState).filter(k => k === url).length ? serverState[url] : 0;
  const client = axios.create({ baseURL: `http://127.0.0.1:${PORT}` });
  installInterceptor(client);
  let err = null, res = null;
  try { res = await client.get(url); }
  catch (e) { err = e; }
  const calls = (serverState[`${url}`] || 0) - before;
  const status = (res && res.status) || (err && err.response && err.response.status);
  const passed =
    calls === expect.calls &&
    status === expect.status &&
    toastCount === expect.toasts;
  console.log(
    `${passed ? "PASS" : "FAIL"} | ${name}`
    + `\n  calls=${calls} (expected ${expect.calls})`
    + `, status=${status} (expected ${expect.status})`
    + `, toasts=${toastCount} (expected ${expect.toasts})`
  );
  return passed;
}

(async () => {
  const srv = await startServer();
  let allPassed = true;
  try {
    // TEST 1: 503 then 200 — retry succeeds, no toast
    allPassed &= await runTest(
      "TEST 1 — 503→200: retry succeeds, no toast",
      "/seq/503/200",
      { calls: 2, status: 200, toasts: 0 }
    );

    // TEST 2: 503 then 503 — both fail, toast appears
    allPassed &= await runTest(
      "TEST 2 — 503→503: retry fails, toast shown",
      "/seq/503/503",
      { calls: 2, status: 503, toasts: 1 }
    );

    // TEST 3: 404 — no retry, no toast (404 not in retry set or toast set)
    allPassed &= await runTest(
      "TEST 3 — 404: no retry, no toast",
      "/seq/404",
      { calls: 1, status: 404, toasts: 0 }
    );

    // TEST 4: 520 then 200 — the actual prod scenario from user
    allPassed &= await runTest(
      "TEST 4 — 520→200: prod deploy-window scenario, no toast",
      "/seq/520/200",
      { calls: 2, status: 200, toasts: 0 }
    );

    // TEST 5: 422 — no retry, no toast
    allPassed &= await runTest(
      "TEST 5 — 422: no retry, no toast",
      "/seq/422",
      { calls: 1, status: 422, toasts: 0 }
    );

    // TEST 6: 502 then 502 — toast text should contain 502
    allPassed &= await runTest(
      "TEST 6 — 502→502: retry fails, toast",
      "/seq/502/502",
      { calls: 2, status: 502, toasts: 1 }
    );

    // TEST 7: 524 then 200 (Cloudflare timeout)
    allPassed &= await runTest(
      "TEST 7 — 524→200: gateway timeout recovers, no toast",
      "/seq/524/200",
      { calls: 2, status: 200, toasts: 0 }
    );

    // TEST 8: 401 — no retry, but toast shown
    allPassed &= await runTest(
      "TEST 8 — 401: no retry, session-expired toast",
      "/seq/401",
      { calls: 1, status: 401, toasts: 1 }
    );

    // TEST 9: 500 then 500 — retry fails, toast
    allPassed &= await runTest(
      "TEST 9 — 500→500: retry fails, toast",
      "/seq/500/500",
      { calls: 2, status: 500, toasts: 1 }
    );

    console.log(`\n${allPassed ? "✅ ALL TESTS PASSED" : "❌ SOME TESTS FAILED"}`);
    process.exit(allPassed ? 0 : 1);
  } finally {
    srv.close();
  }
})();
