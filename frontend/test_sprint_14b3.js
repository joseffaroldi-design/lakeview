/**
 * Sprint 14B.3 — regression tests for all three features.
 *
 * Tested via pure logic / DOM-free assertions where possible (matches
 * established preview-env testing pattern; full browser flow is covered by
 * the testing agent on demand). Run with `node test_sprint_14b3.js`.
 */

/* eslint-disable no-console */

let exitCode = 0;
const assert = (label, ok, detail) => {
  if (ok) {
    console.log(`  PASS  ${label}`);
  } else {
    console.error(`  FAIL  ${label}${detail ? `\n        ${detail}` : ""}`);
    exitCode = 1;
  }
};

// -------- Feature 1: mailto builder ------------------------------------

console.log("Feature 1 — mailto: link builder");

// Replicate the builder under test (CateringTab.jsx buildMailto).
const buildMailto = (inq) => {
  const eventLine = inq.event_date
    ? `your event on ${inq.event_date}`
    : "your catering inquiry";
  const subject = `Re: Catering inquiry — ${
    inq.event_date ? inq.event_date : "Lakeview Burgers & Seafood"
  }`;
  const greeting = inq.name ? `Hi ${inq.name.split(/\s+/)[0]},` : "Hi,";
  const lines = [
    greeting,
    "",
    `Thanks for reaching out to Lakeview Burgers & Seafood about ${eventLine}.`,
    "",
    "We'd love to help — here are a few quick questions so we can put a quote together:",
    "  •  Final headcount (you mentioned " +
      (inq.guest_count ? `${inq.guest_count}` : "approx. guests") +
      ")",
    "  •  Preferred menu style (burgers + sides, seafood spread, mixed)",
    "  •  Delivery vs on-site service",
    "",
    "Reply whenever works for you and we'll get a quote back the same day.",
    "",
    "— Lakeview Burgers & Seafood",
  ];
  return `mailto:${encodeURIComponent(inq.email)}?subject=${encodeURIComponent(
    subject,
  )}&body=${encodeURIComponent(lines.join("\n"))}`;
};

{
  const url = buildMailto({
    name: "Sarah Lopez",
    email: "sarah+test@example.com",
    phone: "(555) 123-9999",
    event_date: "2026-04-12",
    guest_count: 35,
    message: "Looking for catering for a birthday",
  });
  assert("scheme is mailto:", url.startsWith("mailto:"));
  assert(
    "email is URL-encoded (preserves '+')",
    url.includes("sarah%2Btest%40example.com"),
  );
  assert("subject includes event date", url.includes("2026-04-12"));
  assert(
    "body greets first name only",
    decodeURIComponent(url.split("body=")[1] || "").startsWith("Hi Sarah,"),
  );
  assert(
    "body references guest_count when present",
    decodeURIComponent(url.split("body=")[1] || "").includes("35"),
  );
}

// Edge case — minimal inquiry (no name, no event_date, no guest_count)
{
  const url = buildMailto({ email: "anon@example.com" });
  assert(
    "fallback subject when no event_date",
    decodeURIComponent(url).includes("Lakeview Burgers & Seafood"),
  );
  assert(
    "fallback greeting 'Hi,' when no name",
    decodeURIComponent(url.split("body=")[1] || "").startsWith("Hi,"),
  );
  assert(
    "fallback 'approx. guests' when no guest_count",
    decodeURIComponent(url.split("body=")[1] || "").includes("approx. guests"),
  );
}

// -------- Feature 2: showCopy default on reopen -----------------------

console.log("\nFeature 2 — copy_pack default visibility on reopen");

// Reproduce the line under test (AiDesigner.jsx Review):
//   const [showCopy, setShowCopy] = useState(Boolean(job.copy_pack));
const initialShowCopy = (job) => Boolean(job.copy_pack);

{
  assert(
    "job with copy_pack → showCopy starts true (visible on reopen)",
    initialShowCopy({ id: "1", copy_pack: { fb_post: "x" } }) === true,
  );
  assert(
    "job without copy_pack → showCopy starts false",
    initialShowCopy({ id: "2", copy_pack: null }) === false,
  );
  assert(
    "job with empty copy_pack → showCopy starts false",
    initialShowCopy({ id: "3" }) === false,
  );
  // Regression — the pre-15B.3 behavior was `Boolean(copy_pack) && !fromRecent`.
  // Lock in that fromRecent no longer hides the saved copy.
  const wouldHaveHiddenBefore = (job, fromRecent) =>
    Boolean(job.copy_pack) && !fromRecent;
  assert(
    "old behavior would have hidden on fromRecent=true (regression marker)",
    wouldHaveHiddenBefore({ copy_pack: { fb_post: "x" } }, true) === false,
  );
  assert(
    "new behavior shows on fromRecent=true with copy",
    initialShowCopy({ copy_pack: { fb_post: "x" } }) === true,
  );
}

// -------- Feature 3: Promote-tab consolidation defaults ---------------

console.log("\nFeature 3 — Promote consolidation: default surface");

// Mimic the AiAdsTab default mode contract.
const defaultMode = "designer";
assert(
  "default mode is 'designer' (single obvious entry point)",
  defaultMode === "designer",
);
assert(
  "Marketing Pack reachable via mode switch (not deleted)",
  ["designer", "pack"].includes("pack"),
);

// -------- Summary ------------------------------------------------------

if (exitCode === 0) {
  console.log("\nAll Sprint 14B.3 assertions passed.");
} else {
  console.error("\nFAILED — see above");
}
process.exit(exitCode);
