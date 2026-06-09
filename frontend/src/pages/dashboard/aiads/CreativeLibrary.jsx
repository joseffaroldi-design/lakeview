/**
 * Creative Library — unified asset list with search + filter + favorite/archive/delete.
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Star, Trash2, Archive, Library as LibraryIcon, Filter, Copy } from "lucide-react";
import { API, Section, EmptyState } from "./shared";

const KIND_LABELS = {
  ad_copy: "Ad Copy",
  social_post: "Social Post",
  email: "Email",
  sms: "SMS",
  image_concept: "Image Concept",
  video_concept: "Video Concept",
  image_file: "Image",
  video_file: "Video",
};

const AssetRow = ({ asset, onToggleFavorite, onArchive, onDelete, onDuplicate }) => {
  const fav = !!asset.is_favorite;
  const archived = asset.status === "archived";
  const kindLabel = KIND_LABELS[asset.kind] || asset.kind;
  const date = new Date(asset.created_at).toLocaleDateString();
  return (
    <div
      data-testid={`ai-asset-${asset.id}`}
      className={`flex flex-wrap items-center gap-2 p-3 bg-background border border-navy/5 rounded-sm hover:border-gold/40 ${archived ? "opacity-60" : ""}`}
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-sans px-2 py-0.5 rounded-full bg-gold/15 text-navy uppercase tracking-wider">{kindLabel}</span>
          {asset.platform && <span className="text-[10px] text-muted-foreground">{asset.platform}</span>}
          {archived && <span className="text-[10px] font-sans px-2 py-0.5 rounded-full bg-navy/10 uppercase">archived</span>}
        </div>
        <p className="font-semibold text-navy text-sm mt-1 truncate">{asset.title}</p>
        <p className="text-xs text-muted-foreground">{date}</p>
      </div>
      <div className="flex gap-1.5">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onToggleFavorite(asset)}
          className={`border-navy/20 ${fav ? "text-gold" : "text-navy"}`}
          title="Favorite"
        >
          <Star className="w-3.5 h-3.5" fill={fav ? "currentColor" : "none"} />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onArchive(asset)}
          className="border-navy/20"
          title={archived ? "Restore" : "Archive"}
        >
          <Archive className="w-3.5 h-3.5" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onDuplicate(asset)}
          className="border-navy/20"
          title="Duplicate"
          data-testid={`ai-asset-${asset.id}-duplicate`}
        >
          <Copy className="w-3.5 h-3.5" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onDelete(asset.id)}
          className="border-destructive text-destructive hover:bg-destructive hover:text-white"
          title="Delete"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
};

export const CreativeLibrary = ({ getAuthHeader }) => {
  const [assets, setAssets] = useState([]);
  const [busy, setBusy] = useState(false);
  const [filters, setFilters] = useState({ q: "", kind: "", platform: "", status: "", is_favorite: "" });

  const load = useCallback(async (f) => {
    try {
      const params = {};
      if (f.q) params.q = f.q;
      if (f.kind) params.kind = f.kind;
      if (f.platform) params.platform = f.platform;
      if (f.status) params.status = f.status;
      if (f.is_favorite) params.is_favorite = f.is_favorite === "true";
      const res = await axios.get(`${API}/ai-ads/assets`, { params, headers: getAuthHeader() });
      return res.data.assets || [];
    } catch (e) {
      console.error("library load:", e);
      return [];
    }
  }, [getAuthHeader]);

  useEffect(() => {
    let mounted = true;
    setBusy(true);
    load(filters).then((items) => {
      if (!mounted) return;
      setAssets(items);
      setBusy(false);
    });
    return () => { mounted = false; };
  }, [load, filters]);

  const refresh = useCallback(async () => {
    const items = await load(filters);
    setAssets(items);
  }, [load, filters]);

  const toggleFavorite = async (a) => {
    await axios.put(`${API}/ai-ads/assets/${a.id}`, { is_favorite: !a.is_favorite }, { headers: getAuthHeader() });
    refresh();
  };
  const archive = async (a) => {
    const newStatus = a.status === "archived" ? "active" : "archived";
    await axios.put(`${API}/ai-ads/assets/${a.id}`, { status: newStatus }, { headers: getAuthHeader() });
    refresh();
  };
  const del = async (id) => {
    if (!window.confirm("Delete this asset?")) return;
    await axios.delete(`${API}/ai-ads/assets/${id}`, { headers: getAuthHeader() });
    refresh();
  };
  const duplicate = async (a) => {
    await axios.post(`${API}/ai-ads/assets/${a.id}/duplicate`, {}, { headers: getAuthHeader() });
    refresh();
  };

  const rows = [];
  for (let i = 0; i < assets.length; i += 1) {
    rows.push(
      <AssetRow
        key={assets[i].id}
        asset={assets[i]}
        onToggleFavorite={toggleFavorite}
        onArchive={archive}
        onDelete={del}
        onDuplicate={duplicate}
      />
    );
  }

  return (
    <div className="space-y-4">
      <Section title="Filters" icon={Filter} testId="ai-library-filters">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          <Input
            data-testid="ai-library-q"
            placeholder="Search title or tags..."
            value={filters.q}
            onChange={(e) => setFilters({ ...filters, q: e.target.value })}
            className="border-navy/20 text-sm"
          />
          <select
            data-testid="ai-library-kind"
            value={filters.kind}
            onChange={(e) => setFilters({ ...filters, kind: e.target.value })}
            className="px-2 py-2 border border-navy/20 rounded-sm text-sm"
          >
            <option value="">All types</option>
            <option value="ad_copy">Ad Copy</option>
            <option value="social_post">Social Post</option>
            <option value="email">Email</option>
            <option value="sms">SMS</option>
            <option value="image_concept">Image Concept</option>
            <option value="video_concept">Video Concept</option>
          </select>
          <select
            data-testid="ai-library-platform"
            value={filters.platform}
            onChange={(e) => setFilters({ ...filters, platform: e.target.value })}
            className="px-2 py-2 border border-navy/20 rounded-sm text-sm"
          >
            <option value="">All platforms</option>
            <option>Facebook</option>
            <option>Instagram</option>
            <option>TikTok</option>
            <option>Google</option>
            <option>Email</option>
            <option>SMS</option>
          </select>
          <select
            data-testid="ai-library-status"
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className="px-2 py-2 border border-navy/20 rounded-sm text-sm"
          >
            <option value="">Any status</option>
            <option value="active">Active</option>
            <option value="draft">Draft</option>
            <option value="archived">Archived</option>
          </select>
          <select
            data-testid="ai-library-fav"
            value={filters.is_favorite}
            onChange={(e) => setFilters({ ...filters, is_favorite: e.target.value })}
            className="px-2 py-2 border border-navy/20 rounded-sm text-sm"
          >
            <option value="">All</option>
            <option value="true">Favorites only</option>
          </select>
        </div>
      </Section>

      <Section title={`Assets (${assets.length})`} icon={LibraryIcon} testId="ai-library-list">
        {busy && <p className="text-sm text-muted-foreground">Loading…</p>}
        {!busy && rows.length === 0 ? (
          <EmptyState icon={LibraryIcon} title="No assets yet" body="Generate ads, social posts, emails, SMS, or concepts — then click 'Save to Library' to collect them here." testId="ai-library-empty" />
        ) : (
          <div className="space-y-2">{rows}</div>
        )}
      </Section>
    </div>
  );
};

export default CreativeLibrary;
