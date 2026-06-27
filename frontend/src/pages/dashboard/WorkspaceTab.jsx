import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import {
  Image as ImageIcon, Video, MessageSquare, Star,
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
    <section data-testid="workspace-tab" className="ds-fade">
      <header className="mb-8 flex items-end justify-between gap-4 flex-wrap">
        <div>
          <p className="ds-eyebrow mb-1">Workspace</p>
          <h2 className="ds-display text-3xl sm:text-4xl">Marketing projects</h2>
          <p className="text-sm text-navy/60 mt-2 max-w-md">
            Every menu item gets its own project. Open one to see its flyers,
            videos, captions, and campaign history.
          </p>
        </div>
        <div className="ds-stat" data-testid="workspace-count">
          {projects ? `${projects.length} projects` : "—"}
        </div>
      </header>

      <div className="mb-6">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Search items or categories…"
          data-testid="workspace-filter"
          className="ds-input md:max-w-md"
        />
      </div>

      {loading && (
        <div className="ds-empty" data-testid="workspace-loading">
          <p className="text-sm text-navy/55">Loading projects…</p>
        </div>
      )}
      {error && (
        <div className="ds-card p-4 text-rose-600 text-sm" data-testid="workspace-error">
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
            <div className="ds-empty col-span-full">
              <p className="text-sm text-navy/55">No projects match &ldquo;{filter}&rdquo;.</p>
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
    <div
      data-testid={`workspace-card-${project.item_key}`}
      className="ds-card ds-card-interactive overflow-hidden group ds-fade"
      onClick={onOpen}
    >
      <div className="relative aspect-square ds-thumb !rounded-none">
        {hero ? (
          <img
            src={hero}
            alt={project.item_name}
            loading="lazy"
            data-testid="workspace-card-hero"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-navy/25 bg-gradient-to-br from-navy/5 to-navy/0">
            <ImageIcon className="w-14 h-14" />
          </div>
        )}
        {isFeatured && (
          <div className="absolute top-3 left-3 ds-badge-gold shadow-md" data-testid="featured-badge">
            <Star className="w-3 h-3 fill-white" /> Featured Today
          </div>
        )}
        <div className="absolute top-3 right-3 bg-navy/85 backdrop-blur text-cream text-[10px] font-semibold uppercase tracking-wider px-2.5 py-1 rounded-full">
          {project.category}
        </div>
      </div>
      <div className="p-5">
        <h3 className="ds-display text-lg leading-tight truncate" title={project.item_name}>
          {project.item_name}
        </h3>
        <div className="mt-1 text-sm font-semibold text-gold">{project.price || "—"}</div>

        <div className="mt-4 flex items-center gap-1.5 flex-wrap">
          <span className="ds-stat" title="Flyers">
            <ImageIcon className="w-3 h-3" /> {project.flyer_count}
          </span>
          <span className="ds-stat" title="Videos">
            <Video className="w-3 h-3" /> {project.video_count}
          </span>
          <span className="ds-stat" title="Captions">
            <MessageSquare className="w-3 h-3" /> {project.caption_count}
          </span>
          {project.favorite_theme && (
            <span className="ds-stat ds-stat-gold ml-auto" title="Favourite theme">
              {project.favorite_theme}
            </span>
          )}
        </div>

        <div className="mt-5 flex items-center gap-2 pt-4 border-t border-navy/8">
          <button
            data-testid="workspace-open-btn"
            className="flex-1 text-xs font-semibold text-navy hover:text-gold transition-colors flex items-center justify-center gap-1 py-1"
            onClick={(e) => { e.stopPropagation(); onOpen(); }}
          >
            Open project <ChevronRight className="w-3.5 h-3.5" />
          </button>
          {onPromote && (
            <button
              data-testid="workspace-promote-btn"
              className="ds-btn-gold !py-1.5 !px-3 text-xs"
              onClick={(e) => {
                e.stopPropagation();
                onPromote({ name: project.item_name, description: "", price: project.price },
                          { slug: project.category_slug, display_name: project.category });
              }}
            >
              <Megaphone className="w-3.5 h-3.5" /> Promote
            </button>
          )}
        </div>
      </div>
    </div>
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
    return (
      <div className="ds-empty" data-testid="workspace-detail-loading">
        <p className="text-sm text-navy/55">Loading project…</p>
      </div>
    );
  }
  if (!proj) {
    return <div className="py-12 text-center text-rose-500">Project not found.</div>;
  }

  const heroUrl = proj.hero_asset_id
    ? `${BACKEND}/api/media/file/${proj.hero_asset_id}`
    : null;

  return (
    <section data-testid="workspace-detail" className="ds-fade">
      <div className="flex items-center justify-between mb-6">
        <button onClick={onBack} data-testid="workspace-detail-back"
          className="ds-btn-secondary !py-1.5 !px-3 text-xs">
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Workspace
        </button>
        {proj.is_featured_today && (
          <span className="ds-badge-gold">
            <Star className="w-3 h-3 fill-white" /> Featured Today
          </span>
        )}
      </div>

      <div className="ds-hero p-6 sm:p-8 mb-8">
        <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-8 items-start">
          <div className="ds-thumb aspect-square">
            {heroUrl ? (
              <img src={heroUrl} alt={proj.item_name} data-testid="workspace-detail-hero" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-navy/25 bg-gradient-to-br from-navy/5 to-transparent">
                <ImageIcon className="w-16 h-16" />
              </div>
            )}
          </div>
          <div>
            <p className="ds-eyebrow mb-2">{proj.category}</p>
            <h2 className="ds-display text-3xl md:text-4xl leading-tight" data-testid="workspace-detail-name">
              {proj.item_name}
            </h2>
            <div className="text-xl text-gold font-semibold mt-2" style={{ fontFamily: 'Outfit, system-ui, sans-serif' }}>
              {proj.price || "—"}
            </div>

            <div className="grid grid-cols-3 gap-3 mt-6 max-w-md">
              <DetailStat icon={ImageIcon} label="Flyers"   value={proj.flyer_count} />
              <DetailStat icon={Video}     label="Videos"   value={proj.video_count} />
              <DetailStat icon={MessageSquare} label="Captions" value={proj.caption_count} />
            </div>

            <div className="mt-6">
              {onPromote && (
                <button onClick={() => onPromote({ name: proj.item_name, description: "", price: proj.price },
                                                 { slug: proj.category_slug, display_name: proj.category })}
                        data-testid="workspace-detail-promote"
                        className="ds-btn-gold">
                  <Megaphone className="w-4 h-4" /> Promote this item
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Detail tabs */}
      <div className="flex flex-wrap gap-1 mb-6 ds-nav-scroll overflow-x-auto" data-testid="workspace-detail-tabs">
        {DETAIL_TABS.map((t) => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              data-testid={`workspace-detail-tab-${t.id}`}
              onClick={() => setTab(t.id)}
              className={`ds-tab whitespace-nowrap ${active ? "is-active" : ""}`}
            >
              <t.icon className="w-4 h-4" />
              {t.label}
            </button>
          );
        })}
      </div>

      {tab === "overview" && <OverviewPane proj={proj} />}
      {tab === "designs"  && <AssetGrid title="Designs"  data={tabData.designs}  kind="image" />}
      {tab === "videos"   && <AssetGrid title="Videos"   data={tabData.videos}   kind="video" />}
      {tab === "captions" && <CaptionList data={tabData.captions} />}
    </section>
  );
}

function DetailStat({ icon: Icon, label, value }) {
  return (
    <div className="ds-card p-3">
      <div className="text-[10px] text-navy/55 mb-1 flex items-center gap-1 uppercase tracking-wider font-semibold">
        <Icon className="w-3 h-3" /> {label}
      </div>
      <div className="text-2xl font-semibold text-navy" style={{ fontFamily: 'Outfit, system-ui, sans-serif' }}>{value}</div>
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
