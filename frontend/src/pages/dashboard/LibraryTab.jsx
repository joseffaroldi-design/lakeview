/**
 * LibraryTab — flat asset grid + search, no folders, no sub-tabs.
 *
 * Sprint 12D introduced this as a top-level tab to replace the now-removed
 * MediaStudio folder browser.
 */
import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Search, Upload, Image as ImageIcon, Video, Loader2, Trash2, Pencil, Star } from "lucide-react";
import { Button } from "../../components/ui/button";
import { Input } from "../../components/ui/input";
import { Card } from "../../components/ui/card";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const LibraryTab = ({ getAuthHeader }) => {
  const [q, setQ] = useState("");
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const url = q ? `${API}/media/assets?q=${encodeURIComponent(q)}&limit=200`
                    : `${API}/media/assets?limit=200`;
      const r = await axios.get(url, { headers: getAuthHeader() });
      setAssets(r.data.assets || []);
    } catch (e) {
      toast.error("Couldn't load Library", { description: String(e.message) });
    } finally {
      setLoading(false);
    }
  }, [q, getAuthHeader]);

  useEffect(() => {
    const id = setTimeout(load, 250);
    return () => clearTimeout(id);
  }, [load]);

  const onUpload = async (files) => {
    if (!files || !files.length) return;
    setUploading(true);
    let ok = 0;
    for (const f of files) {
      const fd = new FormData();
      fd.append("file", f);
      fd.append("folder", "Custom");
      try {
        // Browser auto-sets Content-Type with boundary; do not override.
        await axios.post(`${API}/media/upload`, fd, { headers: getAuthHeader() });
        ok++;
      } catch (e) {
        toast.error(`Upload failed for ${f.name}`, { description: String(e?.response?.data?.detail || e.message) });
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
      await axios.patch(`${API}/media/assets/${a.id}`, { is_favorite: !a.is_favorite }, { headers: getAuthHeader() });
      load();
    } catch {/* ignore */}
  };

  const onDelete = async (a) => {
    if (!window.confirm(`Archive "${a.filename}"?`)) return;
    try {
      await axios.delete(`${API}/media/assets/${a.id}`, { headers: getAuthHeader() });
      toast.success("Archived");
      load();
    } catch (e) {
      toast.error("Could not archive", { description: String(e?.response?.data?.detail || e.message) });
    }
  };

  return (
    <div className="space-y-4" data-testid="library-tab">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by filename or tag…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="pl-9"
            data-testid="library-search"
          />
        </div>
        <label className="inline-flex items-center gap-2 cursor-pointer">
          <input
            type="file"
            multiple
            accept="image/*,video/*"
            className="hidden"
            onChange={(e) => onUpload(Array.from(e.target.files))}
            data-testid="library-upload-input"
          />
          <Button asChild className="bg-gold text-navy hover:bg-gold/90" data-testid="library-upload-btn">
            <span className="inline-flex items-center gap-2">
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
              Upload
            </span>
          </Button>
        </label>
      </div>

      {loading ? (
        <div className="text-center py-12 text-sm text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin inline mr-2" /> Loading assets…
        </div>
      ) : assets.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          {q ? `No assets match "${q}".` : "No assets yet — upload your first photo above."}
        </Card>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
          {assets.map((a) => (
            <Card key={a.id} className="overflow-hidden group" data-testid={`library-asset-${a.id}`}>
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
                >
                  <Star className={`h-3.5 w-3.5 ${a.is_favorite ? "fill-amber-400 text-amber-500" : "text-stone-400"}`} />
                </button>
              </div>
              <div className="p-2 text-xs">
                <div className="truncate font-medium">{a.filename}</div>
                <div className="flex items-center justify-between gap-1 mt-1">
                  <span className="text-muted-foreground capitalize">{a.kind}</span>
                  <div className="flex gap-1">
                    <button onClick={() => onDelete(a)} className="p-1 rounded hover:bg-stone-100" data-testid={`library-del-${a.id}`} title="Archive">
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
