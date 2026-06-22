/**
 * Sprint 15B.4 regression test — RecentDesignsRail over-fetch loop.
 *
 * Verifies the three contracts of the rail's data layer:
 *   1. usingPrefetch=true + no refreshKey change → ZERO /jobs/recent calls
 *      even if `onRetryJobs` identity flips multiple times (mimics the
 *      staggered boot orchestrator which causes 4 parent re-renders).
 *   2. usingPrefetch=true + refreshKey increments by 1 → exactly ONE call to
 *      the parent's onRetryJobs handler.
 *   3. usingPrefetch=false → exactly ONE /jobs/recent call on mount and one
 *      more whenever refreshKey changes.
 *
 * Pure logic test — replicates the two useEffects from the component without
 * a JSX renderer so we can run it under plain Node.
 */

/* eslint-disable no-console */

// ----- Mock React hooks (single-component, sequential) ---------------------

let stateSlots = [];
let stateIndex = 0;
let effects = [];           // queued effects per render
let effectDeps = new Map(); // last-seen deps keyed by effect identity
let refs = [];
let refIndex = 0;
let callbacks = [];
let callbackIndex = 0;

function useState(initial) {
  const i = stateIndex++;
  if (!(i in stateSlots)) stateSlots[i] = initial;
  const setter = (next) => {
    stateSlots[i] = typeof next === "function" ? next(stateSlots[i]) : next;
  };
  return [stateSlots[i], setter];
}

function useRef(initial) {
  const i = refIndex++;
  if (!(i in refs)) refs[i] = { current: initial };
  return refs[i];
}

function useCallback(fn, deps) {
  const i = callbackIndex++;
  const slot = callbacks[i];
  if (!slot) {
    callbacks[i] = { fn, deps };
    return fn;
  }
  const same =
    slot.deps.length === deps.length &&
    slot.deps.every((d, k) => Object.is(d, deps[k]));
  if (!same) callbacks[i] = { fn, deps };
  return callbacks[i].fn;
}

function useEffect(fn, deps) {
  effects.push({ fn, deps });
}

function resetHookState() {
  stateSlots = [];
  refs = [];
  callbacks = [];
  effectDeps = new Map();
}

function beginRender() {
  stateIndex = 0;
  refIndex = 0;
  callbackIndex = 0;
  effects = [];
}

function runEffects() {
  effects.forEach((e, idx) => {
    const prev = effectDeps.get(idx);
    const changed =
      !prev ||
      prev.length !== e.deps.length ||
      prev.some((d, k) => !Object.is(d, e.deps[k]));
    if (changed) {
      effectDeps.set(idx, e.deps.slice());
      e.fn();
    }
  });
}

// ----- Mock axios ----------------------------------------------------------

let fetchCount = 0;
const mockAxios = {
  get: () => {
    fetchCount += 1;
    return Promise.resolve({ data: { jobs: [] } });
  },
};

// ----- Component-under-test (the two useEffects from RecentDesignsRail) ---

let onRetryCalls = 0;

function renderRail({ usingPrefetch, refreshKey, onRetryJobs, getAuthHeader }) {
  beginRender();

  const reload = useCallback(
    () => {
      if (usingPrefetch) {
        if (onRetryJobs) onRetryJobs();
        return;
      }
      mockAxios.get("/api/ai-designer/jobs/recent?limit=5", {
        headers: getAuthHeader(),
      });
    },
    [getAuthHeader, usingPrefetch, onRetryJobs],
  );

  // Legacy auto-fetch effect.
  useEffect(
    () => {
      if (usingPrefetch) return;
      reload();
    },
    [reload, refreshKey, usingPrefetch],
  );

  // Prefetch refreshKey effect.
  const lastRefreshKeyRef = useRef(refreshKey);
  useEffect(
    () => {
      if (!usingPrefetch) return;
      if (lastRefreshKeyRef.current === refreshKey) return;
      lastRefreshKeyRef.current = refreshKey;
      if (onRetryJobs) onRetryJobs();
    },
    [refreshKey, usingPrefetch],
  );

  runEffects();
  return { reload };
}

// ----- Helpers -------------------------------------------------------------

function assert(label, condition, detail) {
  if (condition) {
    console.log(`  PASS  ${label}`);
  } else {
    console.error(`  FAIL  ${label}${detail ? `\n        ${detail}` : ""}`);
    process.exitCode = 1;
  }
}

function reset() {
  resetHookState();
  fetchCount = 0;
  onRetryCalls = 0;
}

const stableAuthHeader = () => ({ Authorization: "Bearer test" });
const incOnRetry = () => {
  onRetryCalls += 1;
};

// ----- Tests ---------------------------------------------------------------

console.log("Sprint 15B.4 — RecentDesignsRail over-fetch regression");

// Test 1: prefetch=true + 4 re-renders with new onRetryJobs identities (mimics
// boot orchestrator emitting 4 staggered ingest callbacks). Expected: 0 fetches
// and 0 onRetryJobs calls.
console.log("\nTest 1: prefetch=true, boot-sequence re-renders → no fetches");
{
  reset();
  for (let i = 0; i < 4; i += 1) {
    renderRail({
      usingPrefetch: true,
      refreshKey: 0,
      onRetryJobs: () => incOnRetry(), // new identity each render
      getAuthHeader: stableAuthHeader,
    });
  }
  assert(
    "zero /jobs/recent network calls",
    fetchCount === 0,
    `got ${fetchCount}`,
  );
  assert(
    "zero onRetryJobs invocations",
    onRetryCalls === 0,
    `got ${onRetryCalls}`,
  );
}

// Test 2: prefetch=true, refreshKey bumps from 0 → 1. Expected: exactly one
// onRetryJobs call, zero direct fetches.
console.log("\nTest 2: prefetch=true, refreshKey increments → 1 retry call");
{
  reset();
  renderRail({
    usingPrefetch: true,
    refreshKey: 0,
    onRetryJobs: incOnRetry,
    getAuthHeader: stableAuthHeader,
  });
  renderRail({
    usingPrefetch: true,
    refreshKey: 1,
    onRetryJobs: incOnRetry,
    getAuthHeader: stableAuthHeader,
  });
  assert("zero direct fetches", fetchCount === 0, `got ${fetchCount}`);
  assert(
    "exactly one onRetryJobs invocation",
    onRetryCalls === 1,
    `got ${onRetryCalls}`,
  );
}

// Test 3: prefetch=false → mount triggers one fetch; refreshKey++ triggers
// another.
console.log("\nTest 3: prefetch=false (legacy) → fetch on mount + on refresh");
{
  reset();
  renderRail({
    usingPrefetch: false,
    refreshKey: 0,
    onRetryJobs: undefined,
    getAuthHeader: stableAuthHeader,
  });
  assert("one fetch on mount", fetchCount === 1, `got ${fetchCount}`);
  renderRail({
    usingPrefetch: false,
    refreshKey: 1,
    onRetryJobs: undefined,
    getAuthHeader: stableAuthHeader,
  });
  assert(
    "two fetches after refreshKey bump",
    fetchCount === 2,
    `got ${fetchCount}`,
  );
}

// Test 4: prefetch=true, multiple refreshKey bumps with parent re-renders
// in between. Expected: exactly one onRetryJobs call per refreshKey change.
console.log("\nTest 4: prefetch=true, mixed re-renders + key bumps");
{
  reset();
  renderRail({
    usingPrefetch: true,
    refreshKey: 0,
    onRetryJobs: incOnRetry,
    getAuthHeader: stableAuthHeader,
  });
  // 3 cosmetic re-renders (e.g. boot ingest of other streams) — should be silent.
  for (let i = 0; i < 3; i += 1) {
    renderRail({
      usingPrefetch: true,
      refreshKey: 0,
      onRetryJobs: () => incOnRetry(),
      getAuthHeader: stableAuthHeader,
    });
  }
  renderRail({
    usingPrefetch: true,
    refreshKey: 1,
    onRetryJobs: incOnRetry,
    getAuthHeader: stableAuthHeader,
  });
  renderRail({
    usingPrefetch: true,
    refreshKey: 2,
    onRetryJobs: incOnRetry,
    getAuthHeader: stableAuthHeader,
  });
  assert("zero direct fetches", fetchCount === 0, `got ${fetchCount}`);
  assert(
    "two onRetryJobs invocations (one per key bump)",
    onRetryCalls === 2,
    `got ${onRetryCalls}`,
  );
}

if (process.exitCode) {
  console.error("\nFAILED — see above");
} else {
  console.log("\nAll 8 assertions passed.");
}
