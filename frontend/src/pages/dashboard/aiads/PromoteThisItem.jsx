import React from "react";
import PhotoToFlyer from "./PhotoToFlyer";

/**
 * Backward-compatible entry point for old "Promote this item" buttons.
 *
 * V1 intentionally has one marketing creation workflow now: Photo to Flyer.
 * The separate Marketing Pack/video generator was removed from the active UI
 * because it duplicated upload, item-entry, job polling, and download logic.
 */
export default function PromoteThisItem({ getAuthHeader, mode = "page", onClose }) {
  const body = (
    <div data-testid="promote-this-item">
      <PhotoToFlyer getAuthHeader={getAuthHeader} />
    </div>
  );

  if (mode !== "modal") return body;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-navy/60 backdrop-blur-sm overflow-y-auto p-4"
      data-testid="promote-modal"
      onClick={(e) => {
        if (e.target === e.currentTarget && onClose) onClose();
      }}
    >
      <div
        className="bg-cream w-full max-w-4xl rounded-lg shadow-2xl my-8 p-6 relative"
        onClick={(e) => e.stopPropagation()}
      >
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            className="absolute top-3 right-3 w-8 h-8 rounded-full bg-navy/10 hover:bg-navy/20 flex items-center justify-center text-navy z-10"
            data-testid="promote-modal-close"
            aria-label="Close"
          >
            ×
          </button>
        ) : null}
        {body}
      </div>
    </div>
  );
}
