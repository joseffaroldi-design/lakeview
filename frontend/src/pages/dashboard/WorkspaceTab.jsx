import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Briefcase, Image as ImageIcon, Video, MessageSquare, Star,
  ChevronRight, Sparkles, ArrowLeft, Megaphone,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BACKEND = process.env.REACT_APP_BACKEND_URL;

// Sprint 20A Phase 4 — Marketing Workspace tab.
// Lists every menu item as a marketing project; click into one for the
// 6-tab detail view. Auto-backfills on first load.

export default function WorkspaceTab({ getAuthHeader, onPromote }) {
  const [projects, setProjects] = useState(null);
  const [featuredId, setFeaturedId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeKey, setActiveKey] = useState(null);   // open project detail
  const [filter, setFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    axios.get(`${API}/workspace/projects?backfill=true`, { headers: getAuthHeader() })
      .then((r) => {
        if (cancelled) return;
        setProjects(r.data?.projects || []);
        setFeaturedId(r.data?.featured_asset_id || null);
      })
      .catch((e) => { if (!cancelled) setError(e?.message || "Failed to load projects"); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [getAuthHeader]);

  const filtered = (projects || []).filter((p) => {
    if (!filter) return true;
    const q = filter.toLowerCase();
    return (
      p.item_name.toLowerCase().includes(q)
      || (p.category || "").toLowerCase().includes(q)
    );
  });

  if (activeKey) {
    return (
      <ProjectDetail
        itemKey={activeKey}
        getAuthHeader={getAuthHeader}
        onBack={() => setActiveKey(null)}
        onPromote={onPromote}
      />
    );
  }

  return (
    <section data-testid="workspace-tab">
      <div className="flex items-center justify-between mb-2">
        <h2 className="font-serif text-2xl text-navy font-bold flex items-center gap-2">
          <Briefcase className="w-6 h-6 text-gold" /> Marketing Workspace
        </h2>
        <div className="text-xs text-navy/60" data-testid="workspace-count">
          {projects ? `${projects.length} projects` : ""}
        </div>
      </div>
      <p className="text-sm text-muted-foreground mb-6">
        Every menu item gets a marketing project. Open one to see its flyers,
        videos, captions, and campaign history.
      </p>

      <div className="mb-4">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search items or categories…"
          data-testid="workspace-filter"
          className="w-full md:w-96 px-4 py-2 rounded-lg border border-navy/20 focus:border-gold focus:outline-none bg-white text-sm"
        />
      </div>

      {loading && (
        <div className="text-center py-12 text-navy/60" data-testid="workspace-loading">
          Loading projects…
        </div>
      )}
      {error && (
        <div className="text-rose-500 text-sm py-2" data-testid="workspace-error">
          {error}
        </div>
      )}

      {!loading && !error && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtered.map((p) => (
            <ProjectCard
              key={p.item_key}
              project={p}
              featuredId={featuredId}
              onOpen={() => setActiveKey(p.item_key)}
              onPromote={onPromote}
            />
          ))}
          {filtered.length === 0 && (
            <div className="text-navy/40 col-span-full text-center py-12">
              No projects match “{filter}”.
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function ProjectCard({ project, featuredId, onOpen, onPromote }) {
  const hero = project.hero_asset_id
    ? `${BACKEND}/api/media/file/${project.hero_asset_id}`
    : null;
  const isFeatured = project.is_featured_today;
  return (
    <Card
      data-testid={`workspace-card-${project.item_key}`}
      className="p-0 overflow-hidden border-navy/10 hover:border-gold hover:shadow-lg transition cursor-pointer group"
      onClick={onOpen}
    >
      <div className="relative aspect-square bg-navy/5 overflow-hidden">
        {hero ? (
          <img
            src={hero}
            alt={project.item_name}
            loading="lazy"
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            data-testid="workspace-card-hero"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-navy/30">
            <ImageIcon className="w-12 h-12" />
          </div>
        )}
        {isFeatured && (
          <div className="absolute top-3 left-3 bg-gold text-navy text-[10px] font-bold tracking-widest uppercase px-2 py-1 rounded-full shadow flex items-center gap-1" data-testid="featured-badge">
            <Star className="w-3 h-3 fill-navy" /> Featured Today
          </div>
        )}
        <div className="absolute top-3 right-3 bg-navy/80 text-cream text-[10px] font-semibold uppercase tracking-wider px-2 py-1 rounded-full">
          {project.category}
        </div>
      </div>
      <div className="p-4">
        <h3 className="font-serif text-lg font-bold text-navy leading-tight truncate" title={project.item_name}>
          {project.item_name}
        </h3>
        <div className="mt-1 text-sm text-gold font-semibold">{project.price || "—"}</div>
        <div className="mt-3 flex items-center gap-3 text-xs text-navy/60">
          <span className="flex items-center gap-1" title="Flyers">
            <ImageIcon className="w-3.5 h-3.5" />{project.flyer_count}
          </span>
          <span className="flex items-center gap-1" title="Videos">
            <Video className="w-3.5 h-3.5" />{project.video_count}
          </span>
          <span className="flex items-center gap-1" title="Captions">
            <MessageSquare className="w-3.5 h-3.5" />{project.caption_count}
          </span>
          {project.favorite_theme && (
            <span className="ml-auto px-2 py-0.5 rounded-full bg-navy/5 text-navy/70 text-[10px] uppercase tracking-wider">
              {project.favorite_theme}
            </span>
          )}
        </div>
        <div className="mt-4 flex items-center gap-2 pt-3 border-t border-navy/5">
          <Button
            size="sm"
            variant="ghost"
            data-testid="workspace-open-btn"
            className="flex-1 text-navy hover:text-gold text-xs"
            onClick={(e) => { e.stopPropagation(); onOpen(); }}
          >
            Open <ChevronRight className="w-3.5 h-3.5 ml-0.5" />
          </Button>
          {onPromote && (
            <Button
              size="sm"
              variant="ghost"
              data-testid="workspace-promote-btn"
              className="text-gold hover:bg-gold/10 text-xs"
              onClick={(e) => {
                e.stopPropagation();
                onPromote({ name: project.item_name, description: "", price: project.price },
                          { slug: project.category_slug, display_name: project.category });
              }}
            >
              <Megaphone className="w-3.5 h-3.5 mr-1" /> Promote
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}

// ----------------------------------------------------------- Detail view

// Launch Cleanup Sprint — Schedule + Insights "Soon" tabs removed from
// the per-project detail view until the real features land (Sprint 20B / 20E).
const DETAIL_TABS = [
  { id: "overview", label: "Overview", icon: Sparkles },
  { id: "designs",  label: "Designs",  icon: ImageIcon },
  { id: "videos",   label: "Videos",   icon: Video },
  { id: "captions", label: "Captions", icon: MessageSquare },
];

function ProjectDetail({ itemKey, getAuthHeader, onBack, onPromote }) {
  const [proj, setProj] = useState(null);
  const [tab, setTab] = useState("overview");
  const [tabData, setTabData] = useState({});      // { designs: [...], videos: [...], captions: [...] }
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    axios.get(`${API}/workspace/projects/${itemKey}`, { headers: getAuthHeader() })
      .then((r) => { if (!cancelled) setProj(r.data); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [itemKey, getAuthHeader]);

  const loadTab = useCallback((tabId) => {
    if (tabData[tabId] !== undefined) return;
    if (!["designs", "videos", "captions"].includes(tabId)) return;
    axios.get(`${API}/workspace/projects/${itemKey}/${tabId}`, { headers: getAuthHeader() })
      .then((r) => setTabData((s) => ({ ...s, [tabId]: r.data })))
      .catch(() => setTabData((s) => ({ ...s, [tabId]: { error: true } })));
  }, [itemKey, getAuthHeader, tabData]);

  useEffect(() => { loadTab(tab); }, [tab, loadTab]);

  if (loading) {
    return <div className="py-12 text-center text-navy/60">Loading…</div>;
  }
  if (!proj) {
    return <div className="py-12 text-center text-rose-500">Project not found.</div>;
  }

  const heroUrl = proj.hero_asset_id
    ? `${BACKEND}/api/media/file/${proj.hero_asset_id}`
    : null;

  return (
    <section data-testid="workspace-detail">
      <div className="flex items-center justify-between mb-4">
        <Button variant="ghost" size="sm" onClick={onBack} data-testid="workspace-detail-back" className="text-navy hover:text-gold">
          <ArrowLeft className="w-4 h-4 mr-1" /> Back to Workspace
        </Button>
        {proj.is_featured_today && (
          <span className="text-[11px] uppercase tracking-widest text-gold font-bold flex items-center gap-1">
            <Star className="w-4 h-4 fill-gold" /> Featured Today
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-8 mb-6 items-start">
        <div className="rounded-2xl overflow-hidden bg-navy/5 border border-navy/10 aspect-square">
          {heroUrl ? (
            <img src={heroUrl} alt={proj.item_name} className="w-full h-full object-cover" data-testid="workspace-detail-hero" />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-navy/30">
              <ImageIcon className="w-12 h-12" />
            </div>
          )}
        </div>
        <div>
          <div className="text-xs uppercase tracking-widest text-gold mb-1">{proj.category}</div>
          <h2 className="font-serif text-3xl md:text-4xl font-bold text-navy" data-testid="workspace-detail-name">
            {proj.item_name}
          </h2>
          <div className="text-xl text-gold font-semibold mt-1">{proj.price || "—"}</div>

          <div className="grid grid-cols-3 gap-3 mt-6 max-w-md">
            <Stat icon={ImageIcon} label="Flyers"   value={proj.flyer_count} />
            <Stat icon={Video}     label="Videos"   value={proj.video_count} />
            <Stat icon={MessageSquare} label="Captions" value={proj.caption_count} />
          </div>

          <div className="mt-6 flex gap-2 flex-wrap">
            {onPromote && (
              <Button onClick={() => onPromote({ name: proj.item_name, description: "", price: proj.price },
                                               { slug: proj.category_slug, display_name: proj.category })}
                      data-testid="workspace-detail-promote"
                      className="bg-gold text-navy hover:bg-gold/90">
                <Megaphone className="w-4 h-4 mr-1" /> Promote this item
              </Button>
            )}
          </div>
        </div>
      </div>

      {/* Detail tabs */}
      <div className="flex flex-wrap gap-1 border-b border-navy/10 mb-6" data-testid="workspace-detail-tabs">
        {DETAIL_TABS.map((t) => (
          <button
            key={t.id}
            data-testid={`workspace-detail-tab-${t.id}`}
            onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium transition border-b-2 -mb-px ${
              tab === t.id
                ? "border-gold text-navy"
                : "border-transparent text-navy/50 hover:text-navy"
            }`}
          >
            <span className="inline-flex items-center gap-1.5">
              <t.icon className="w-4 h-4" />
              {t.label}
            </span>
          </button>
        ))}
      </div>

      {tab === "overview" && <OverviewPane proj={proj} />}
      {tab === "designs"  && <AssetGrid title="Designs"  data={tabData.designs}  kind="image" />}
      {tab === "videos"   && <AssetGrid title="Videos"   data={tabData.videos}   kind="video" />}
      {tab === "captions" && <CaptionList data={tabData.captions} />}
    </section>
  );
}

function Stat({ icon: Icon, label, value }) {
  return (
    <div className="bg-navy/5 rounded-lg p-3">
      <div className="text-xs text-navy/60 mb-1 flex items-center gap-1">
        <Icon className="w-3.5 h-3.5" /> {label}
      </div>
      <div className="text-2xl font-bold text-navy">{value}</div>
    </div>
  );
}

function OverviewPane({ proj }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <KV label="Favorite theme"      value={proj.favorite_theme || "—"} />
      <KV label="Favorite design"     value={proj.favorite_flyer_id ? proj.favorite_flyer_id.slice(0,8) : "—"} />
      <KV label="Last promoted"       value={fmtDate(proj.last_promoted_at)} />
      <KV label="Last generated"      value={fmtDate(proj.last_generated_at)} />
      <KV label="Active status"       value={proj.active ? "Active" : "Inactive"} />
      <KV label="Project created"     value={fmtDate(proj.created_at)} />
    </div>
  );
}

function KV({ label, value }) {
  return (
    <div className="bg-white border border-navy/10 rounded-lg p-4">
      <div className="text-[11px] uppercase tracking-widest text-navy/50 mb-1">{label}</div>
      <div className="text-sm text-navy font-medium">{value}</div>
    </div>
  );
}

function fmtDate(s) {
  if (!s) return "—";
  try { return new Date(s).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); }
  catch { return s; }
}

function AssetGrid({ title, data, kind }) {
  if (!data) return <div className="text-navy/50 text-sm py-8">Loading {title.toLowerCase()}…</div>;
  if (data.error) return <div className="text-rose-500 text-sm py-8">Failed to load {title.toLowerCase()}.</div>;
  const items = data.designs || data.videos || [];
  if (!items.length) return <div className="text-navy/40 text-sm py-12 text-center">No {title.toLowerCase()} yet.</div>;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3" data-testid={`asset-grid-${kind}`}>
      {items.map((a) => (
        <a
          key={a.id}
          href={`${BACKEND}/api/media/file/${a.id}`}
          target="_blank"
          rel="noopener noreferrer"
          className="aspect-square bg-navy/5 rounded-lg overflow-hidden border border-navy/10 hover:border-gold hover:shadow transition group"
        >
          {kind === "image" ? (
            <img src={`${BACKEND}/api/media/file/${a.id}`} alt={a.filename || a.item_name || ""}
                 loading="lazy" className="w-full h-full object-cover group-hover:scale-105 transition" />
          ) : (
            <video src={`${BACKEND}/api/media/file/${a.id}`} className="w-full h-full object-cover" muted />
          )}
        </a>
      ))}
    </div>
  );
}

function CaptionList({ data }) {
  if (!data) return <div className="text-navy/50 text-sm py-8">Loading captions…</div>;
  if (data.error) return <div className="text-rose-500 text-sm py-8">Failed to load captions.</div>;
  const caps = data.captions || [];
  if (!caps.length) return <div className="text-navy/40 text-sm py-12 text-center">No captions yet. Generate a marketing pack from Promote.</div>;
  return (
    <div className="space-y-3" data-testid="captions-list">
      {caps.map((c, i) => (
        <div key={i} className="bg-white border border-navy/10 rounded-lg p-4">
          <div className="text-[11px] uppercase tracking-widest text-gold mb-2">{c.channel}</div>
          <div className="text-sm text-navy whitespace-pre-line leading-relaxed">
            {typeof c.text === "string" ? c.text : JSON.stringify(c.text)}
          </div>
        </div>
      ))}
    </div>
  );
}
