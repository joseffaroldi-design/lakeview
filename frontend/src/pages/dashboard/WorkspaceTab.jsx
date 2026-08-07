import React, { useEffect, useState } from "react";
import axios from "axios";
import { Download, Image as ImageIcon, RefreshCw } from "lucide-react";
import { PageHeader, EmptyState, LoadingState } from "@/components/dashboard/primitives";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * V1 Marketing Library.
 *
 * The old Workspace project abstraction duplicated the menu, media library,
 * design memory and campaign systems. For V1 this tab is intentionally a
 * straightforward view of generated image assets.
 */
export default function WorkspaceTab({ getAuthHeader }) {
  const [assets, setAssets] = useState(null);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setAssets(null);
    setError(null);
    axios.get(`${API}/media/assets?kind=image&limit=100`, { headers: getAuthHeader() })
      .then((r) => {
        if (cancelled) return;
        const rows = r.data?.assets || r.data || [];
        const marketing = rows.filter((a) => {
          const tags = a.tags || [];
          const source = a.source || "";
          return tags.includes("flyer") || tags.includes("ai-designer") || source === "ai_designer";
        });
        setAssets(marketing);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message || "Failed to load marketing files");
      });
    return () => { cancelled = true; };
  }, [getAuthHeader, refreshKey]);

  return (
    <section data-testid="workspace-tab" className="ds-fade">
      <PageHeader
        eyebrow="Library"
        title="Marketing files"
        subtitle="Your generated flyers in one place. No projects, campaigns, or extra setup required."
        actions={
          <button
            type="button"
            className="ds-btn-secondary"
            onClick={() => setRefreshKey((n) => n + 1)}
            data-testid="workspace-refresh"
          >
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        }
      />

      {assets === null && !error ? (
        <LoadingState message="Loading marketing files…" testId="workspace-loading" />
      ) : null}

      {error ? (
        <div className="ds-card p-4 text-rose-600 text-sm" data-testid="workspace-error">
          {error}
        </div>
      ) : null}

      {assets && assets.length === 0 ? (
        <EmptyState message="No generated flyers yet. Use Photo to Flyer to make your first one." />
      ) : null}

      {assets && assets.length > 0 ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {assets.map((asset) => (
            <article key={asset.id} className="ds-card overflow-hidden" data-testid={`workspace-asset-${asset.id}`}>
              <div className="aspect-square bg-navy/5">
                <img
                  src={`${API}/media/thumb/${asset.id}`}
                  alt={asset.item_name || asset.filename || "Generated flyer"}
                  className="w-full h-full object-cover"
                  loading="lazy"
                />
              </div>
              <div className="p-3">
                <div className="flex items-start gap-2">
                  <ImageIcon className="w-4 h-4 text-gold mt-0.5 shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-navy truncate">
                      {asset.item_name || asset.filename || "Flyer"}
                    </p>
                    <p className="text-[11px] text-navy/50 truncate">
                      {asset.theme ? `Style: ${asset.theme}` : "Generated flyer"}
                    </p>
                  </div>
                </div>
                <a
                  href={`${API}/media/file/${asset.id}`}
                  download
                  className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-gold hover:underline"
                  data-testid="workspace-download"
                >
                  <Download className="w-3.5 h-3.5" /> Download
                </a>
              </div>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
