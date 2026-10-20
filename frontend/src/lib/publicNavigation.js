export const hasActiveSpecials = (specials) =>
  Array.isArray(specials) && specials.length > 0;

export const getHashTargetId = (hash) => {
  const rawId = String(hash || "").replace(/^#/, "");
  if (!rawId) return "";

  try {
    return decodeURIComponent(rawId);
  } catch (_) {
    return rawId;
  }
};

export const scrollToHashTarget = (hash, options = {}) => {
  if (typeof document === "undefined") return false;

  const targetId = getHashTargetId(hash);
  if (!targetId) return false;

  const target = document.getElementById(targetId);
  if (!target) return false;

  target.scrollIntoView({ block: "start", behavior: "auto", ...options });
  return true;
};
