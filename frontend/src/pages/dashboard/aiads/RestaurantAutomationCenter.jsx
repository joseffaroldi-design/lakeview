/**
 * Restaurant Automation Center — production restaurant-marketing wizards.
 *
 * Four lanes, all powered by the existing /api/ai-ads/plugins/restaurant/promote
 * endpoint with restaurant-specific templates:
 *   • Daily Specials Automation  → pick a menu item + day(s) + channels
 *   • Google Review Automation   → SMS / Email / Follow-up
 *   • Loyalty Campaigns          → First Visit / Repeat / Birthday / Win-back / VIP
 *   • Catering Marketing         → Office / Corporate / School / Holiday / Family
 *
 * Each wizard generates content (saved to Library) and lets the operator
 * optionally schedule the bundle for a chosen date+provider.
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import {
  UtensilsCrossed, Star as StarIcon, Heart, Briefcase,
  Sparkles, Calendar as CalendarIcon, Send, CheckCircle2, Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API, Section, EmptyState } from "./shared";

const LANES = [
  {
    id: "specials",
    label: "Daily Specials",
    icon: UtensilsCrossed,
    color: "border-gold",
    templates: ["daily_special", "seafood_special", "burger_special", "happy_hour"],
    actions: ["facebook_ad", "instagram_caption", "sms_campaign"],
    requiresMenuItem: true,
    intro: "Pick a menu item, choose channels, generate the campaign. Optionally schedule for the days you want.",
  },
  {
    id: "reviews",
    label: "Google Review Requests",
    icon: StarIcon,
    color: "border-forest",
    templates: ["review_request_sms", "review_request_email", "review_followup"],
    actions: ["sms_campaign", "email_campaign"],
    requiresMenuItem: false,
    intro: "Generate the SMS / email copy that brings 5-star reviews. Send a follow-up if a guest doesn't respond.",
  },
  {
    id: "loyalty",
    label: "Loyalty Campaigns",
    icon: Heart,
    color: "border-red-500",
    templates: ["loyalty_first_visit", "loyalty_repeat", "loyalty_birthday", "loyalty_winback", "loyalty_vip"],
    actions: ["email_campaign", "sms_campaign"],
    requiresMenuItem: false,
    intro: "Templates for first-time, repeat, birthday, win-back, and VIP guests. Email + SMS.",
  },
  {
    id: "catering",
    label: "Catering Marketing",
    icon: Briefcase,
    color: "border-navy",
    templates: ["catering_office_lunch", "catering_corporate", "catering_school", "catering_holiday_party", "catering_family"],
    actions: ["facebook_ad", "instagram_caption", "email_campaign", "flyer_copy"],
    requiresMenuItem: false,
    intro: "Pitch catering to office lunches, corporate events, schools, holiday parties, and family gatherings.",
  },
];

const ChannelChip = (props) => {
  const { id, on, onToggle } = props;
  const labelMap = {
    facebook_ad: "Facebook",
    instagram_caption: "Instagram",
    tiktok_caption: "TikTok",
    google_business_post: "Google Business",
    email_campaign: "Email",
    sms_campaign: "SMS",
    flyer_copy: "Flyer",
    image_prompt: "Image Prompt",
    video_script_15: "15s Video",
  };
  return (
    <button
      type="button"
      onClick={() => onToggle(id)}
      data-testid={`automation-channel-${id}`}
      className={`px-3 py-1.5 rounded-sm text-xs border ${on ? "border-gold bg-gold/15 text-navy font-semibold" : "border-navy/15 text-navy/60"}`}
    >
      {labelMap[id] || id}
    </button>
  );
};

const ResultPanel = (props) => {
  const { results, onScheduleBundle, scheduling } = props;
  if (!results || results.length === 0) return null;
  const ok = results.filter((r) => !r.error && r.asset_id);
  const errored = results.filter((r) => r.error);
  return (
    <div className="mt-4 space-y-3" data-testid="automation-results">
      <div className="flex items-center gap-2 p-3 bg-forest/10 border border-forest/30 rounded-sm">
        <CheckCircle2 className="w-5 h-5 text-forest" />
        <p className="text-sm text-navy">
          <strong>{ok.length}</strong> assets saved to Creative Library. {errored.length > 0 ? `${errored.length} failed.` : ""}
        </p>
        {ok.length > 0 ? (
          <Button
            size="sm"
            onClick={() => onScheduleBundle(ok)}
            className="ml-auto bg-gold text-navy hover:bg-gold/90"
            disabled={scheduling}
            data-testid="automation-schedule-bundle"
          >
            {scheduling ? <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" /> : <CalendarIcon className="w-3.5 h-3.5 mr-1" />}
            Schedule This Bundle
          </Button>
        ) : null}
      </div>
      {errored.length > 0 ? (
        <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">
          {errored.map((e, i) => <p key={i}>{e.label}: {e.error}</p>)}
        </div>
      ) : null}
    </div>
  );
};

const ScheduleBundlePopover = (props) => {
  const { assets, onClose, onScheduled, getAuthHeader } = props;
  const pad = (n) => String(n).padStart(2, "0");
  const next = new Date(); next.setHours(next.getHours() + 1); next.setMinutes(0, 0, 0);
  const [whenLocal, setWhenLocal] = useState(
    `${next.getFullYear()}-${pad(next.getMonth() + 1)}-${pad(next.getDate())}T${pad(next.getHours())}:00`
  );
  const [stagger, setStagger] = useState(30);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);

  const submit = async () => {
    setBusy(true);
    try {
      // Bundle endpoint already supports per-asset provider override; map
      // each asset to its native platform.
      const platformToProvider = {
        Facebook: "facebook", Instagram: "instagram", TikTok: "tiktok",
        "Google Business": "google_business", Email: "email", SMS: "sms",
      };
      const overrides = {};
      for (const a of assets) {
        const provider = platformToProvider[a.platform] || (a.kind === "email" ? "email" : a.kind === "sms" ? "sms" : "facebook");
        overrides[a.asset_id] = { provider };
      }
      const res = await axios.post(`${API}/ai-ads/bundle-schedule`, {
        asset_ids: assets.map((a) => a.asset_id),
        overrides,
        default_provider: "facebook",
        default_scheduled_at: new Date(whenLocal).toISOString(),
        stagger_minutes: Number(stagger) || 0,
      }, { headers: getAuthHeader() });
      setDone(res.data);
      onScheduled(res.data);
    } catch (e) {
      setDone({ error: (e.response && e.response.data && e.response.data.detail) || "Failed to schedule" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-card rounded-lg max-w-md w-full p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-serif text-navy font-bold text-lg mb-3 flex items-center gap-2">
          <CalendarIcon className="w-5 h-5 text-gold" /> Schedule {assets.length} Assets
        </h3>
        <p className="text-xs text-muted-foreground mb-4">
          Each asset publishes to its native platform (FB Ad → Facebook, IG Caption → Instagram, etc.). Stagger spaces posts apart so they don't all fire at once.
        </p>
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-muted-foreground mb-1">First post at</label>
            <Input type="datetime-local" value={whenLocal} onChange={(e) => setWhenLocal(e.target.value)} className="border-navy/20 text-sm" data-testid="bundle-when" />
          </div>
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Stagger (minutes between posts)</label>
            <Input type="number" min={0} value={stagger} onChange={(e) => setStagger(e.target.value)} className="border-navy/20 text-sm" data-testid="bundle-stagger" />
          </div>
          {done && done.scheduled ? (
            <div className="text-xs text-forest bg-forest/10 border border-forest/30 rounded p-2">
              ✓ Scheduled {done.scheduled.length} posts. View them in Calendar / Queue.
            </div>
          ) : done && done.error ? (
            <div className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">{done.error}</div>
          ) : null}
          <div className="flex gap-2 pt-2">
            <Button onClick={submit} disabled={busy} className="bg-gold text-navy hover:bg-gold/90 flex-1" data-testid="bundle-submit">
              {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />} Schedule
            </Button>
            <Button variant="outline" onClick={onClose} className="border-navy/20">Close</Button>
          </div>
        </div>
      </div>
    </div>
  );
};

const Lane = (props) => {
  const { lane, menu, plugin, getAuthHeader, onLaneRun } = props;
  const [template, setTemplate] = useState(lane.templates[0]);
  const [channels, setChannels] = useState(lane.actions);
  const [menuItem, setMenuItem] = useState(null);
  const [busy, setBusy] = useState(false);
  const [results, setResults] = useState(null);
  const [scheduleAssets, setScheduleAssets] = useState(null);
  const [campaignName, setCampaignName] = useState("");

  const toggleChannel = (id) => {
    setChannels((prev) => (prev.indexOf(id) === -1 ? [...prev, id] : prev.filter((x) => x !== id)));
  };

  const allPluginActions = (plugin && plugin.actions) || [];
  const actionsForLane = allPluginActions.filter((a) => lane.actions.indexOf(a.id) !== -1);

  const tplOpts = [];
  const tpls = (plugin && plugin.templates) || [];
  for (let i = 0; i < tpls.length; i += 1) {
    if (lane.templates.indexOf(tpls[i].id) !== -1) {
      tplOpts.push(<option key={tpls[i].id} value={tpls[i].id}>{tpls[i].label}</option>);
    }
  }

  const menuOpts = [<option key="__none" value="">— Pick menu item (optional) —</option>];
  for (let ci = 0; ci < menu.length; ci += 1) {
    const cat = menu[ci];
    for (let ii = 0; ii < (cat.items || []).length; ii += 1) {
      const it = cat.items[ii];
      if (!it.name) continue;
      menuOpts.push(<option key={`${ci}-${ii}`} value={`${ci}-${ii}`}>{cat.display_name} · {it.name}</option>);
    }
  }

  const run = async () => {
    setBusy(true);
    setResults(null);
    const item = menuItem
      ? {
          name: menuItem.item.name,
          description: menuItem.item.description || "",
          category: menuItem.category,
          price: menuItem.item.price || "",
        }
      : { name: lane.label, description: "", category: lane.label };
    const payloadBase = {
      context: { item },
      template_id: template,
      save_to_library: true,
      campaign_name: campaignName || `${lane.label} · ${template}`,
    };
    try {
      // Fan out per-action — each gets its own 60s ingress budget.
      const settled = await Promise.allSettled(
        channels.map((id) =>
          axios.post(`${API}/ai-ads/plugins/restaurant/promote`,
            { ...payloadBase, action_ids: [id] },
            { headers: getAuthHeader(), timeout: 70000 })
        )
      );
      const merged = [];
      for (let i = 0; i < settled.length; i += 1) {
        const id = channels[i];
        const res = settled[i];
        if (res.status === "fulfilled") {
          const r = (res.value.data.results || [])[0];
          merged.push(r || { action_id: id, label: id, error: "Empty response" });
        } else {
          const d = res.reason && res.reason.response && res.reason.response.data && res.reason.response.data.detail;
          merged.push({ action_id: id, label: id, error: typeof d === "string" ? d : "Request failed" });
        }
      }
      setResults(merged);
      onLaneRun(lane.id, merged);
    } finally {
      setBusy(false);
    }
  };

  const chans = [];
  for (let i = 0; i < actionsForLane.length; i += 1) {
    const a = actionsForLane[i];
    chans.push(<ChannelChip key={a.id} id={a.id} on={channels.indexOf(a.id) !== -1} onToggle={toggleChannel} />);
  }

  return (
    <Section
      title={lane.label}
      icon={lane.icon}
      testId={`automation-lane-${lane.id}`}
    >
      <p className="text-xs text-muted-foreground mb-3">{lane.intro}</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Template</label>
          <select
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
            className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm"
            data-testid={`automation-${lane.id}-template`}
          >
            {tplOpts}
          </select>
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Campaign Name (optional)</label>
          <Input
            value={campaignName}
            onChange={(e) => setCampaignName(e.target.value)}
            placeholder={`${lane.label} – ${new Date().toLocaleDateString()}`}
            className="border-navy/20 text-sm"
            data-testid={`automation-${lane.id}-campaign-name`}
          />
        </div>
        {lane.requiresMenuItem || lane.id === "specials" ? (
          <div className="md:col-span-2">
            <label className="block text-xs text-muted-foreground mb-1">Menu item</label>
            <select
              value={menuItem ? `${menu.indexOf(menu.find((c) => c.display_name === menuItem.category))}-${menu.find((c) => c.display_name === menuItem.category).items.indexOf(menuItem.item)}` : ""}
              onChange={(e) => {
                if (!e.target.value) { setMenuItem(null); return; }
                const [ci, ii] = e.target.value.split("-").map(Number);
                setMenuItem({ category: menu[ci].display_name, item: menu[ci].items[ii] });
              }}
              className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm"
              data-testid={`automation-${lane.id}-menu-item`}
            >
              {menuOpts}
            </select>
          </div>
        ) : null}
      </div>
      <div className="mb-3">
        <p className="text-xs text-muted-foreground mb-1">Channels ({channels.length} selected)</p>
        <div className="flex flex-wrap gap-1">{chans}</div>
      </div>
      <Button
        onClick={run}
        disabled={busy || channels.length === 0}
        className="bg-gold text-navy hover:bg-gold/90"
        data-testid={`automation-${lane.id}-run`}
      >
        {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
        {busy ? `Generating ${channels.length} assets…` : `Generate ${channels.length} Assets`}
      </Button>
      <ResultPanel
        results={results}
        scheduling={false}
        onScheduleBundle={(assets) => setScheduleAssets(assets)}
      />
      {scheduleAssets ? (
        <ScheduleBundlePopover
          assets={scheduleAssets}
          onClose={() => setScheduleAssets(null)}
          onScheduled={() => setScheduleAssets(null)}
          getAuthHeader={getAuthHeader}
        />
      ) : null}
    </Section>
  );
};

export const RestaurantAutomationCenter = (props) => {
  const { getAuthHeader } = props;
  const [menu, setMenu] = useState([]);
  const [plugin, setPlugin] = useState(null);

  const load = useCallback(async () => {
    // Use allSettled so a single endpoint failure doesn't leave the page stuck on
    // "Loading automation center…" forever. Both calls now send auth headers so
    // they work in production envs where /api/menu is gated.
    const headers = getAuthHeader();
    const [m, p] = await Promise.allSettled([
      axios.get(`${API}/menu`, { headers }),
      axios.get(`${API}/ai-ads/plugins/restaurant`, { headers }),
    ]);
    if (m.status === "fulfilled") {
      // /api/menu returns either {categories:[...]} or a bare list, depending on caller.
      const data = m.value.data;
      setMenu(Array.isArray(data) ? data : (data.categories || []));
    } else {
      console.error("menu load failed:", m.reason);
      setMenu([]);
    }
    if (p.status === "fulfilled") {
      setPlugin(p.value.data);
    } else {
      console.error("plugin load failed:", p.reason);
      // Surface a minimal plugin shape so the UI exits the loading state.
      setPlugin({ id: "restaurant", label: "Restaurant", templates: [], error: String(p.reason).slice(0, 200) });
    }
  }, [getAuthHeader]);

  useEffect(() => { load(); }, [load]);

  if (!plugin) {
    return <p className="text-sm text-muted-foreground" data-testid="automation-loading">Loading automation center…</p>;
  }

  const lanes = [];
  for (let i = 0; i < LANES.length; i += 1) {
    lanes.push(
      <Lane
        key={LANES[i].id}
        lane={LANES[i]}
        menu={menu}
        plugin={plugin}
        getAuthHeader={getAuthHeader}
        onLaneRun={() => { /* hook for analytics */ }}
      />
    );
  }

  return (
    <div className="space-y-4" data-testid="restaurant-automation-center">
      <div className="rounded-lg bg-gradient-to-r from-gold/15 to-forest/10 border-2 border-gold/30 p-4">
        <h3 className="font-serif font-bold text-navy text-lg flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-gold" /> Restaurant Automation Center
        </h3>
        <p className="text-sm text-navy/80 mt-1">
          Four production wizards: <strong>Daily Specials</strong>, <strong>Google Reviews</strong>,{" "}
          <strong>Loyalty Campaigns</strong>, <strong>Catering Marketing</strong>. Each generates
          channel-ready content, saves it to your Library, and can schedule the bundle to publish on
          the right platforms at the right time.
        </p>
      </div>
      {lanes}
    </div>
  );
};

export default RestaurantAutomationCenter;
