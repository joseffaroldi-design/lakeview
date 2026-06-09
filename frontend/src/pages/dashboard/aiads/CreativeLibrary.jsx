/**
 * Creative Library — unified asset list with search, filters, bulk actions, export.
 *
 * Phase 2: search + per-row favorite/archive/duplicate/delete.
 * Phase 4: multi-select + bulk archive/delete/export (TXT/CSV/Clipboard).
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Star, Trash2, Archive, Library as LibraryIcon, Filter, Copy,
  Download, FileText, FileSpreadsheet, Square, CheckSquare, X,
  Calendar as CalendarIcon, Zap,
} from "lucide-react";
import { API, Section, EmptyState } from "./shared";
import SchedulePopover from "./SchedulePopover";

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

const flattenPayload = (payload) => {
  if (payload == null) return "";
  if (typeof payload === "string") return payload;
  if (Array.isArray(payload)) return payload.map((x) => flattenPayload(x)).join("\n");
  if (typeof payload === "object") {
    const out = [];
    for (const k of Object.keys(payload)) {
      out.push(`${k}: ${flattenPayload(payload[k])}`);
    }
    return out.join("\n");
  }
  return String(payload);
};

const AssetRow = (props) => {
  const { asset, onToggleFavorite, onArchive, onDelete, onDuplicate, onSchedule, selected, onToggleSelect } = props;
  const fav = !!asset.is_favorite;
  const archived = asset.status === "archived";
  const kindLabel = KIND_LABELS[asset.kind] || asset.kind;
  const date = new Date(asset.created_at).toLocaleDateString();
  return (
    <div
      data-testid={`ai-asset-${asset.id}`}
      className={`flex flex-wrap items-center gap-2 p-3 bg-background border border-navy/5 rounded-sm hover:border-gold/40 ${archived ? "opacity-60" : ""} ${selected ? "ring-2 ring-gold/60" : ""}`}
    >
      <button
        type="button"
        onClick={() => onToggleSelect(asset.id)}
        className="text-navy hover:text-gold"
        data-testid={`ai-asset-${asset.id}-select`}
        aria-label="Select"
      >
        {selected ? <CheckSquare className="w-4 h-4 text-gold" /> : <Square className="w-4 h-4 text-navy/40" />}
      </button>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[10px] font-sans px-2 py-0.5 rounded-full bg-gold/15 text-navy uppercase tracking-wider">{kindLabel}</span>
          {asset.platform ? <span className="text-[10px] text-muted-foreground">{asset.platform}</span> : null}
          {archived ? <span className="text-[10px] font-sans px-2 py-0.5 rounded-full bg-navy/10 uppercase">archived</span> : null}
          {asset.status === "draft" ? <span className="text-[10px] font-sans px-2 py-0.5 rounded-full bg-forest/15 text-forest uppercase">draft</span> : null}
        </div>
        <p className="font-semibold text-navy text-sm mt-1 truncate">{asset.title}</p>
        <p className="text-xs text-muted-foreground">{date}</p>
      </div>
      <div className="flex gap-1.5">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onSchedule(asset)}
          className="border-navy/20 text-gold"
          title="Schedule / Publish"
          data-testid={`ai-asset-${asset.id}-schedule`}
        >
          <CalendarIcon className="w-3.5 h-3.5" />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onToggleFavorite(asset)}
          className={`border-navy/20 ${fav ? "text-gold" : "text-navy"}`}
          title="Favorite"
          data-testid={`ai-asset-${asset.id}-favorite`}
        >
          <Star className="w-3.5 h-3.5" fill={fav ? "currentColor" : "none"} />
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => onArchive(asset)}
          className="border-navy/20"
          title={archived ? "Restore" : "Archive"}
          data-testid={`ai-asset-${asset.id}-archive`}
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
          data-testid={`ai-asset-${asset.id}-delete`}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
};

export const CreativeLibrary = (props) => {
  const { getAuthHeader } = props;
  const [assets, setAssets] = useState([]);
  const [busy, setBusy] = useState(false);
  const [filters, setFilters] = useState({
    q: "", kind: "", platform: "", status: "", is_favorite: "",
    date_from: "", date_to: "",
  });
  const [selectedIds, setSelectedIds] = useState([]);
  const [scheduling, setScheduling] = useState(null);

  const load = useCallback(async (f) => {
    try {
      const params = {};
      if (f.q) params.q = f.q;
      if (f.kind) params.kind = f.kind;
      if (f.platform) params.platform = f.platform;
      if (f.status) params.status = f.status;
      if (f.is_favorite) params.is_favorite = f.is_favorite === "true";
      if (f.date_from) params.date_from = f.date_from;
      if (f.date_to) params.date_to = f.date_to;
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
    setSelectedIds((prev) => prev.filter((x) => x !== id));
    refresh();
  };
  const duplicate = async (a) => {
    await axios.post(`${API}/ai-ads/assets/${a.id}/duplicate`, {}, { headers: getAuthHeader() });
    refresh();
  };
  const openSchedule = (a) => setScheduling(a);

  const toggleSelect = (id) => {
    setSelectedIds((prev) => (prev.indexOf(id) === -1 ? [...prev, id] : prev.filter((x) => x !== id)));
  };
  const selectAllVisible = () => {
    const ids = assets.map((a) => a.id);
    setSelectedIds(selectedIds.length === ids.length ? [] : ids);
  };
  const clearSelection = () => setSelectedIds([]);

  const bulkAction = async (action) => {
    if (selectedIds.length === 0) return;
    if (action === "delete" && !window.confirm(`Delete ${selectedIds.length} selected assets?`)) return;
    await axios.post(
      `${API}/ai-ads/assets/bulk`,
      { ids: selectedIds, action },
      { headers: getAuthHeader() }
    );
    clearSelection();
    refresh();
  };

  const downloadBlob = (data, filename, mime) => {
    const blob = new Blob([data], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportSelected = async (format) => {
    if (selectedIds.length === 0) return;
    const res = await axios.post(
      `${API}/ai-ads/assets/export`,
      { ids: selectedIds, format },
      { headers: getAuthHeader() }
    );
    const data = res.data.data;
    const stamp = new Date().toISOString().slice(0, 10);
    if (format === "clipboard") {
      try {
        await navigator.clipboard.writeText(typeof data === "string" ? data : JSON.stringify(data, null, 2));
        window.alert(`Copied ${selectedIds.length} assets to clipboard.`);
      } catch (_) {
        window.alert("Clipboard blocked by browser.");
      }
      return;
    }
    if (format === "csv") downloadBlob(data, `ai-assets-${stamp}.csv`, "text/csv");
    else if (format === "txt") downloadBlob(data, `ai-assets-${stamp}.txt`, "text/plain");
    else downloadBlob(JSON.stringify(data, null, 2), `ai-assets-${stamp}.json`, "application/json");
  };

  const copySelectedToClipboard = async () => {
    if (selectedIds.length === 0) return;
    const selectedAssets = assets.filter((a) => selectedIds.indexOf(a.id) !== -1);
    const text = selectedAssets.map((a) => `### ${a.title}\n${flattenPayload(a.payload)}`).join("\n\n---\n\n");
    try {
      await navigator.clipboard.writeText(text);
      window.alert(`Copied ${selectedAssets.length} assets to clipboard.`);
    } catch (_) {
      window.alert("Clipboard blocked.");
    }
  };

  const rows = [];
  for (let i = 0; i < assets.length; i += 1) {
    const a = assets[i];
    rows.push(
      <AssetRow
        key={a.id}
        asset={a}
        onToggleFavorite={toggleFavorite}
        onArchive={archive}
        onDelete={del}
        onDuplicate={duplicate}
        onSchedule={openSchedule}
        selected={selectedIds.indexOf(a.id) !== -1}
        onToggleSelect={toggleSelect}
      />
    );
  }

  const allVisibleSelected = selectedIds.length === assets.length && assets.length > 0;
  const hasSelection = selectedIds.length > 0;

  return (
    <div className="space-y-4">
      <Section title="Filters" icon={Filter} testId="ai-library-filters">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
          <Input
            data-testid="ai-library-q"
            placeholder="Search title or tags…"
            value={filters.q}
            onChange={(e) => setFilters({ ...filters, q: e.target.value })}
            className="border-navy/20 text-sm md:col-span-2"
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
            <option>Google Business</option>
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
            <option value="scheduled">Scheduled</option>
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
          <Input
            data-testid="ai-library-date-from"
            type="date"
            value={filters.date_from}
            onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
            className="border-navy/20 text-sm"
            title="Date from"
          />
          <Input
            data-testid="ai-library-date-to"
            type="date"
            value={filters.date_to}
            onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
            className="border-navy/20 text-sm"
            title="Date to"
          />
        </div>
      </Section>

      {hasSelection ? (
        <div
          data-testid="ai-library-bulk-bar"
          className="sticky top-0 z-10 rounded-lg border-2 border-gold bg-gold/10 px-4 py-3 flex flex-wrap items-center gap-2"
        >
          <span className="text-sm font-semibold text-navy">{selectedIds.length} selected</span>
          <Button variant="outline" size="sm" onClick={clearSelection} className="border-navy/20" data-testid="ai-bulk-clear">
            <X className="w-3.5 h-3.5 mr-1" /> Clear
          </Button>
          <div className="flex-1" />
          <Button variant="outline" size="sm" onClick={() => bulkAction("archive")} className="border-navy/20" data-testid="ai-bulk-archive">
            <Archive className="w-3.5 h-3.5 mr-1" /> Archive
          </Button>
          <Button variant="outline" size="sm" onClick={() => bulkAction("favorite")} className="border-navy/20" data-testid="ai-bulk-favorite">
            <Star className="w-3.5 h-3.5 mr-1" /> Favorite
          </Button>
          <Button variant="outline" size="sm" onClick={copySelectedToClipboard} className="border-navy/20" data-testid="ai-bulk-clipboard">
            <Copy className="w-3.5 h-3.5 mr-1" /> Copy
          </Button>
          <Button variant="outline" size="sm" onClick={() => exportSelected("txt")} className="border-navy/20" data-testid="ai-bulk-export-txt">
            <FileText className="w-3.5 h-3.5 mr-1" /> TXT
          </Button>
          <Button variant="outline" size="sm" onClick={() => exportSelected("csv")} className="border-navy/20" data-testid="ai-bulk-export-csv">
            <FileSpreadsheet className="w-3.5 h-3.5 mr-1" /> CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => exportSelected("json")} className="border-navy/20" data-testid="ai-bulk-export-json">
            <Download className="w-3.5 h-3.5 mr-1" /> JSON
          </Button>
          <Button size="sm" onClick={() => bulkAction("delete")} className="bg-destructive text-white hover:bg-destructive/90" data-testid="ai-bulk-delete">
            <Trash2 className="w-3.5 h-3.5 mr-1" /> Delete
          </Button>
        </div>
      ) : null}

      <Section
        title={`Assets (${assets.length})`}
        icon={LibraryIcon}
        testId="ai-library-list"
        action={
          assets.length > 0 ? (
            <Button
              variant="outline"
              size="sm"
              onClick={selectAllVisible}
              className="border-navy/20"
              data-testid="ai-library-select-all"
            >
              {allVisibleSelected ? <CheckSquare className="w-3.5 h-3.5 mr-1" /> : <Square className="w-3.5 h-3.5 mr-1" />}
              {allVisibleSelected ? "Deselect all" : "Select all"}
            </Button>
          ) : null
        }
      >
        {busy ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
        {!busy && rows.length === 0 ? (
          <EmptyState
            icon={LibraryIcon}
            title="No assets yet"
            body="Generate ads, social posts, emails, SMS, or concepts — then click 'Save to Library' to collect them here."
            testId="ai-library-empty"
          />
        ) : (
          <div className="space-y-2">{rows}</div>
        )}
      </Section>
      {scheduling ? (
        <SchedulePopover
          asset={scheduling}
          getAuthHeader={getAuthHeader}
          onClose={() => setScheduling(null)}
          onScheduled={() => { setScheduling(null); refresh(); }}
        />
      ) : null}
    </div>
  );
};

export default CreativeLibrary;
