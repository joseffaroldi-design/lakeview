/**
 * StructuredErrorCard — single source of UX for ALL classified backend failures.
 *
 * Backend returns:
 *   { code, user_message, technical, status, retryable, retry_action, context? }
 *
 * We render:
 *   - A colored, iconified card
 *   - User-facing title + plain-English message
 *   - Optional "Show technical details" disclosure
 *   - A primary CTA button based on `retry_action`:
 *       retry / retry_render / retry_publish  → onRetry()
 *       add_balance                            → Universal Key deep link
 *       reconnect_provider / open_provider_connections → Provider Connections deep link (onOpenProviders)
 *       wait_and_retry                         → onRetry() with "Try again in 30s" hint
 *       edit_prompt / edit_post                → onEditSource()
 *       pick_assets                            → onPickAssets()
 *       restart_backend                        → static info
 *
 * Callers supply only the action handlers that make sense for their surface.
 */
import React, { useState } from "react";
import {
  AlertTriangle, Wallet, Key, Shield, Clock, Wifi, RefreshCcw,
  Pencil, Image as ImageIcon, ServerCrash, FileWarning, Plug,
} from "lucide-react";
import { Button } from "@/components/ui/button";

const CODE_TO_ICON = {
  budget_exhausted:    Wallet,
  key_invalid:         Key,
  key_missing:         Key,
  safety_reject:       Shield,
  rate_limited:        Clock,
  prompt_invalid:      AlertTriangle,
  provider_unavailable:Wifi,
  provider_empty:      AlertTriangle,
  timeout:             Clock,
  ffmpeg_missing:      ServerCrash,
  ffmpeg_failed:       ServerCrash,
  asset_missing:       FileWarning,
  asset_invalid:       FileWarning,
  provider_unregistered: Plug,
  not_connected:       Plug,
  permission_denied:   Shield,
  payload_too_large:   FileWarning,
  network:             Wifi,
  unknown:             AlertTriangle,
};

const CODE_TO_TITLE = {
  budget_exhausted:    "Out of AI credits",
  key_invalid:         "Provider key rejected",
  key_missing:         "Server not configured",
  safety_reject:       "Blocked by content policy",
  rate_limited:        "Rate limit hit",
  prompt_invalid:      "Input rejected",
  provider_unavailable:"Provider unreachable",
  provider_empty:      "Provider returned nothing",
  timeout:             "Timed out",
  ffmpeg_missing:      "Video renderer offline",
  ffmpeg_failed:       "Video renderer crashed",
  asset_missing:       "Media file not found",
  asset_invalid:       "Media file unreadable",
  provider_unregistered:"Provider not installed",
  not_connected:       "Provider not connected",
  permission_denied:   "Provider denied permission",
  payload_too_large:   "Asset too large",
  network:             "Network error",
  unknown:             "Unexpected error",
};

export const StructuredErrorCard = ({
  error,                          // { code, user_message, technical, retryable, retry_action, status }
  onRetry,                        // () => void
  onEditSource,                   // () => void  (for prompt_invalid / safety_reject)
  onPickAssets,                   // () => void  (for asset_missing)
  onOpenProviders,                // () => void  (for not_connected / permission_denied)
  className = "",
  compact = false,                // compact mode for inline cards (queue rows)
  testId = "error-card",
}) => {
  const [showTech, setShowTech] = useState(false);
  if (!error) return null;
  const code = error.code || "unknown";
  const Icon = CODE_TO_ICON[code] || AlertTriangle;
  const title = CODE_TO_TITLE[code] || "Error";
  const action = error.retry_action;

  const primary = (() => {
    if (action === "add_balance") {
      return (
        <a href="https://app.emergent.sh/profile" target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center px-3 h-8 text-xs bg-navy text-cream rounded hover:bg-navy/90"
          data-testid={`${testId}-action-add-balance`}>
          <Wallet className="w-3 h-3 mr-1" /> Add balance
        </a>
      );
    }
    if ((action === "reconnect_provider" || action === "open_provider_connections") && onOpenProviders) {
      return (
        <Button onClick={onOpenProviders} className="bg-navy text-cream hover:bg-navy/90 h-8 text-xs" data-testid={`${testId}-action-reconnect`}>
          <Plug className="w-3 h-3 mr-1" /> Open Provider Connections
        </Button>
      );
    }
    if ((action === "edit_prompt" || action === "edit_post") && onEditSource) {
      return (
        <Button onClick={onEditSource} className="bg-navy text-cream hover:bg-navy/90 h-8 text-xs" data-testid={`${testId}-action-edit`}>
          <Pencil className="w-3 h-3 mr-1" /> Edit and retry
        </Button>
      );
    }
    if (action === "pick_assets" && onPickAssets) {
      return (
        <Button onClick={onPickAssets} className="bg-navy text-cream hover:bg-navy/90 h-8 text-xs" data-testid={`${testId}-action-pick`}>
          <ImageIcon className="w-3 h-3 mr-1" /> Pick different assets
        </Button>
      );
    }
    if (error.retryable !== false && onRetry) {
      const label = action === "wait_and_retry" ? "Try again in 30s" : "Try again";
      return (
        <Button onClick={onRetry} className="bg-red-700 text-white hover:bg-red-800 h-8 text-xs" data-testid={`${testId}-action-retry`}>
          <RefreshCcw className="w-3 h-3 mr-1" /> {label}
        </Button>
      );
    }
    return null;
  })();

  if (compact) {
    return (
      <div className={`border border-red-300 bg-red-50 rounded p-2 ${className}`} data-testid={testId} data-error-code={code}>
        <div className="flex items-start gap-2">
          <Icon className="w-3.5 h-3.5 text-red-700 flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-[11px] font-semibold text-red-900">{title}</p>
            <p className="text-[10px] text-red-800">{error.user_message}</p>
            {error.technical ? (
              <button type="button" onClick={() => setShowTech((s) => !s)}
                className="text-[9px] text-red-700 hover:underline mt-0.5"
                data-testid={`${testId}-toggle`}>
                {showTech ? "Hide" : "Show"} technical details
              </button>
            ) : null}
            {showTech && error.technical ? (
              <pre className="text-[9px] text-red-900 bg-red-100 rounded p-1 mt-1 font-mono break-all whitespace-pre-wrap max-h-24 overflow-auto" data-testid={`${testId}-technical`}>{error.technical}</pre>
            ) : null}
            {primary ? <div className="mt-1.5">{primary}</div> : null}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`border-2 border-red-300 bg-red-50 rounded p-3 space-y-2 ${className}`} data-testid={testId} data-error-code={code}>
      <div className="flex items-start gap-2">
        <Icon className="w-4 h-4 text-red-700 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-red-900">{title}</p>
          <p className="text-xs text-red-800 mt-0.5">{error.user_message}</p>
          {error.technical ? (
            <button type="button" onClick={() => setShowTech((s) => !s)}
              className="text-[10px] text-red-700 hover:underline mt-1"
              data-testid={`${testId}-toggle`}>
              {showTech ? "Hide" : "Show"} technical details
            </button>
          ) : null}
          {showTech && error.technical ? (
            <pre className="text-[10px] text-red-900 bg-red-100 rounded p-1.5 mt-1 break-all whitespace-pre-wrap font-mono max-h-32 overflow-auto" data-testid={`${testId}-technical`}>{error.technical}</pre>
          ) : null}
        </div>
      </div>
      {primary ? <div className="flex gap-2 pt-1">{primary}</div> : null}
    </div>
  );
};

/** Parse an axios error (network/timeout/structured/unstructured) into the
 *  same shape the backend returns, so callers can pass it straight to
 *  StructuredErrorCard. */
export const parseAxiosError = (e) => {
  if (e.code === "ECONNABORTED" || (e.message || "").toLowerCase().includes("timeout")) {
    return {
      code: "timeout", retryable: true, retry_action: "retry",
      user_message: "The request timed out. Try again — if it keeps timing out, the server may be busy.",
      technical: e.message,
    };
  }
  if (!e.response) {
    return {
      code: "network", retryable: true, retry_action: "retry",
      user_message: "Couldn't reach the server. Check your internet connection.",
      technical: e.message,
    };
  }
  const d = e.response.data && e.response.data.detail;
  if (d && typeof d === "object" && d.code) return d;
  return {
    code: "unknown", retryable: true, retry_action: "retry",
    user_message: typeof d === "string" ? d : "Request failed.",
    technical: typeof d === "string" ? d : `HTTP ${e.response.status}`,
  };
};

export default StructuredErrorCard;
