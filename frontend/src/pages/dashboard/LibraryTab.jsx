/**
 * LibraryTab — flat asset grid + search + Sprint 17B Smart Menu Workflow:
 *   - ⭐ Favorite toggle (existing)
 *   - 🔁 Remix → re-opens Photo→Flyer with the original photo + saved
 *     style + theme preloaded (sessionStorage handshake)
 *   - Filter by Menu Item / Theme / Date
 *   - Smart sort = favorites first → most-recently-used → rest
 */
import React, { useEffect, useState, useCallback, useMemo } from "react";
import axios from "axios";
import {
  Search, Upload, Video, Loader2, Trash2, Star,
  RotateCcw, Filter, X,
} from "lucide-react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Card } from "../../components/ui/card";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const REMIX_KEY = "lakeview.photo_flyer.remix";

// Quick date-range buckets for the simple "Filter by Date" pill.
const DATE_BUCKETS = [
  { key: "any",   label: "Any time", days: null },
  { key: "7d",    label: "Last 7 days", days: 7 },
  { key: "30d",   label: "Last 30 days", days: 30 },
  { key: "90d",   label: "Last 90 days", days: 90 },
];

const sinceFor = (key) => {
  const b = DATE_BUCKETS.find((x) => x.key === key);
  if (!b || !b.days) return undefined;
  const d = new Date();
  d.setDate(d.getDate() - b.days);
  return d.toISOString();
};

const LibraryTab = ({ getAuthHeader, onRequestNavigate }) => {
  const [q, setQ] = useState("");
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  // Sprint 17B — filter state
  const [filterMenuKey, setFilterMenuKey] = useState("");
  const [filterTheme, setFilterTheme] = useState("");
  const [filterDate, setFilterDate] = useState("any");
  const [showFavOnly, setShowFavOnly] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      params.set("limit", "200");
      if (filterMenuKey) params.set("item_key", filterMenuKey);
      if (filterTheme) params.set("theme", filterTheme);
      const since = sinceFor(filterDate);
      if (since) params.set("since", since);
      if (showFavOnly) params.set("is_favorite", "true");
      const r = await axios.get(`${API}/media/assets?${params.toString()}`,
        { headers: getAuthHeader() });
      setAssets(r.data.assets || []);
    } catch (e) {
      toast.error("Couldn't load Library", { description: String(e.message) });
    } finally {
      setLoading(false);
    }
  }, [q, filterMenuKey, filterTheme, filterDate, showFavOnly, getAuthHeader]);

  useEffect(() => {
    const id = setTimeout(load, 250);
    return () => clearTimeout(id);
  }, [load]);

  // Derive the filter options from the currently-loaded set so the
  // dropdowns only ever show values that actually exist on disk.
  // Sprint 17B: assets have `item_key`, `item_name`, `theme` top-level.
  const { menuOptions, themeOptions } = useMemo(() => {
    const menuMap = new Map();   // item_key -> item_name
    const themeMap = new Map();  // theme_id -> theme_id (label === id today)
    for (const a of assets) {
      if (a.item_key && a.item_name) menuMap.set(a.item_key, a.item_name);
      if (a.theme) themeMap.set(a.theme, a.theme);
      // Legacy tags
      for (const t of a.tags || []) {
        if (typeof t === "string" && t.startsWith("theme:") && !a.theme) {
          const tid = t.split(":", 2)[1];
          themeMap.set(tid, tid);
        }
      }
    }
    return {
      menuOptions: Array.from(menuMap.entries()).sort((a, b) => a[1].localeCompare(b[1])),
      themeOptions: Array.from(themeMap.keys()).sort(),
    };
  }, [assets]);

  const onUpload = async (files) => {
    if (!files || !files.length) return;
    setUploading(true);
    let ok = 0;
    for (const f of files) {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("folder", "Custom");
      try {
        await axios.post(`${API}/media/upload`, fd, { headers: getAuthHeader() });
        ok++;
      } catch (e) {
        toast.error(`Upload failed for ${f.name}`,
          { description: String(e?.response?.data?.detail || e.message) });
      }
    }
    setUploading(false);
    if (ok) {
      toast.success(`Uploaded ${ok} file${ok > 1 ? "s" : ""}`);
      load();
    }
  };

  const toggleFav = async (a) => {
    try {
      await axios.patch(`${API}/media/assets/${a.id}`,
        { is_favorite: !a.is_favorite }, { headers: getAuthHeader() });
      load();
    } catch { /* ignore */ }
  };

  const onDelete = async (a) => {
    if (!window.confirm(`Archive "${a.filename}"?`)) return;
    try {
      await axios.delete(`${API}/media/assets/${a.id}`, { headers: getAuthHeader() });
      toast.success("Archived");
      load();
    } catch (e) {
      toast.error("Could not archive",
        { description: String(e?.response?.data?.detail || e.message) });
    }
  };

  // Sprint 17B — Remix: stash original-photo + menu item + theme into
  // sessionStorage, then navigate to Photo→Flyer.
  const onRemix = async (a) => {
    if (!a.source_asset_id) {
      toast.error("Can't remix this asset",
        { description: "Original photo wasn't tracked. Try uploading + generating once more." });
      return;
    }
    const payload = {
      source_asset_id: a.source_asset_id,
      theme: a.theme || null,
      menu_item: a.item_key && a.item_name ? {
        item_key: a.item_key,
        name: a.item_name,
        price: "",
        features: [],
        category: "",
      } : null,
      food_type: a.item_name || "",
    };
    try { sessionStorage.setItem(REMIX_KEY, JSON.stringify(payload)); } catch { /* ignore */ }

    // Bump usage so smart-sort floats the remixed flyer.
    axios.post(`${API}/media/assets/${a.id}/used`, null,
      { headers: getAuthHeader(), timeout: 10000 }).catch(() => {});

    // Hand off to Photo→Flyer. We support two integration modes:
    //   (a) parent passed `onRequestNavigate("promote")` — clean tab switch
    //   (b) fallback — fire a CustomEvent that the dashboard listens for
    if (typeof onRequestNavigate === "function") {
      onRequestNavigate("promote");
    } else {
      window.dispatchEvent(new CustomEvent("lakeview.tab.navigate",
        { detail: { tab: "promote" } }));
    }
    toast.success(`Remixing "${a.item_name || a.filename}"…`);
  };

  const clearFilters = () => {
    setFilterMenuKey(""); setFilterTheme(""); setFilterDate("any"); setShowFavOnly(false);
  };
  const anyFilter = filterMenuKey || filterTheme || filterDate !== "any" || showFavOnly;

  return (
    <div className="space-y-4" data-testid="library-tab">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by filename, item or tag…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
            data-testid="library-search"
          />
        </div>
        <label className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="file" multiple accept="image/*,video/*"
            className="hidden"
            onChange={(e) => onUpload(Array.from(e.target.files))}
            data-testid="library-upload-input"
          />
          <Button asChild className="bg-gold text-navy hover:bg-gold/90"
                  data-testid="library-upload-btn">
            <span className="inline-flex items-center gap-2">
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              Upload
            </span>
          </Button>
        </label>
      </div>

      {/* Sprint 17B — Filter chips. Lightweight, no heavy filter modal. */}
      <div className="flex flex-wrap items-center gap-2" data-testid="library-filters">
        <Filter className="h-3.5 w-3.5 text-navy/50" />
        <select
          value={filterMenuKey}
          onChange={(e) => setFilterMenuKey(e.target.value)}
          className="text-xs border border-navy/20 rounded-md px-2 py-1 bg-white"
          data-testid="library-filter-menu"
        >
          <option value="">All menu items</option>
          {menuOptions.map(([key, name]) => (
            <option key={key} value={key}>{name}</option>
          ))}
        </select>
        <select
          value={filterTheme}
          onChange={(e) => setFilterTheme(e.target.value)}
          className="text-xs border border-navy/20 rounded-md px-2 py-1 bg-white"
          data-testid="library-filter-theme"
        >
          <option value="">All themes</option>
          {themeOptions.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select
          value={filterDate}
          onChange={(e) => setFilterDate(e.target.value)}
          className="text-xs border border-navy/20 rounded-md px-2 py-1 bg-white"
          data-testid="library-filter-date"
        >
          {DATE_BUCKETS.map((b) => (
            <option key={b.key} value={b.key}>{b.label}</option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => setShowFavOnly((v) => !v)}
          className={`text-xs inline-flex items-center gap-1 rounded-md px-2 py-1 border ${
            showFavOnly
              ? "bg-amber-100 border-amber-300 text-amber-800"
              : "bg-white border-navy/20 text-navy/70"
          }`}
          data-testid="library-filter-favorite"
        >
          <Star className={`h-3 w-3 ${showFavOnly ? "fill-amber-400 text-amber-500" : "text-navy/40"}`} />
          Favorites
        </button>
        {anyFilter ? (
          <button type="button" onClick={clearFilters}
            className="text-xs text-navy/60 hover:underline inline-flex items-center gap-1"
            data-testid="library-filter-clear">
            <X className="h-3 w-3" /> Clear
          </button>
        ) : null}
      </div>

      {loading ? (
        <div className="text-center py-12 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin inline mr-2" /> Loading assets…
        </div>
      ) : assets.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground"
              data-testid="library-empty">
          {q ? `No assets match "${q}".` :
            anyFilter ? "No assets match the current filters."
                      : "No assets yet — upload your first photo above."}
        </Card>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3"
             data-testid="library-grid">
          {assets.map((a) => (
            <Card key={a.id} className="overflow-hidden group"
                  data-testid={`library-asset-${a.id}`}>
              <div className="aspect-square relative bg-stone-100">
                {a.kind === "image" ? (
                  <img src={`${API}/media/thumb/${a.id}`} alt={a.filename}
                       className="w-full h-full object-cover" loading="lazy" />
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <Video className="h-10 w-10 text-stone-400" />
                  </div>
                )}
                <button
                  onClick={() => toggleFav(a)}
                  className="absolute top-1 right-1 p-1 rounded-full bg-white/80 hover:bg-white"
                  data-testid={`library-fav-${a.id}`}
                  title={a.is_favorite ? "Unfavorite" : "Favorite"}
                >
                  <Star className={`h-3.5 w-3.5 ${a.is_favorite ? "fill-amber-400 text-amber-500" : "text-stone-400"}`} />
                </button>
                {a.source_asset_id ? (
                  <button
                    onClick={() => onRemix(a)}
                    className="absolute top-1 left-1 p-1 rounded-full bg-white/80 hover:bg-white"
                    data-testid={`library-remix-${a.id}`}
                    title="Remix (open in Photo→Flyer)"
                  >
                    <RotateCcw className="h-3.5 w-3.5 text-gold" />
                  </button>
                ) : null}
              </div>
              <div className="p-2 text-xs">
                <div className="truncate font-medium" title={a.filename}>
                  {a.item_name || a.filename}
                </div>
                <div className="flex items-center justify-between gap-1 mt-1">
                  <span className="text-muted-foreground capitalize truncate">
                    {a.theme || a.kind}
                  </span>
                  <div className="flex gap-1">
                    <button onClick={() => onDelete(a)}
                      className="p-1 rounded hover:bg-stone-100"
                      data-testid={`library-del-${a.id}`} title="Archive">
                      <Trash2 className="h-3.5 w-3.5 text-stone-500" />
                    </button>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default LibraryTab;
