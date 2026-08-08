import React, { useEffect, useState } from "react";
import axios from "axios";
import { Save, Settings as SettingsIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/dashboard/primitives";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const DAYS = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"];

const Input = ({ label, value, onChange, type="text", placeholder="" }) => (
  <label className="block space-y-1">
    <span className="text-xs font-semibold text-navy">{label}</span>
    <input type={type} value={value || ""} placeholder={placeholder} onChange={e => onChange(e.target.value)}
      className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm bg-white" />
  </label>
);

const SettingsTab = ({ getAuthHeader }) => {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    axios.get(`${API}/settings`, { headers: getAuthHeader() })
      .then(r => setData(r.data)).catch(() => setMessage("Could not load settings."));
  }, [getAuthHeader]);

  const patch = (key, value) => setData(prev => ({ ...prev, [key]: value }));
  const patchGroup = (group, key, value) => setData(prev => ({
    ...prev, [group]: { ...(prev?.[group] || {}), [key]: value }
  }));

  const save = async () => {
    setBusy(true); setMessage("");
    try {
      const r = await axios.put(`${API}/settings`, data, { headers: getAuthHeader() });
      setData(r.data); setMessage("Settings saved.");
    } catch { setMessage("Could not save settings."); }
    finally { setBusy(false); }
  };

  if (!data) return <div className="py-16 text-center text-sm text-navy/50">Loading settings…</div>;

  return <div className="ds-fade space-y-8" data-testid="settings-tab">
    <PageHeader eyebrow="Restaurant" title="Settings" subtitle="Change normal restaurant information here without editing code or redeploying." />

    <section className="bg-white border border-navy/10 rounded-lg p-5 space-y-4">
      <h3 className="font-serif text-xl text-navy">Restaurant profile</h3>
      <div className="grid md:grid-cols-2 gap-4">
        <Input label="Business name" value={data.business_name} onChange={v => patch("business_name", v)} />
        <Input label="Phone" value={data.phone} onChange={v => patch("phone", v)} />
        <Input label="Email" type="email" value={data.email} onChange={v => patch("email", v)} />
        <Input label="Address" value={data.address} onChange={v => patch("address", v)} />
      </div>
    </section>

    <section className="bg-white border border-navy/10 rounded-lg p-5 space-y-4">
      <h3 className="font-serif text-xl text-navy">Hours</h3>
      <div className="grid md:grid-cols-2 gap-3">
        {DAYS.map(day => <Input key={day} label={day[0].toUpperCase()+day.slice(1)} value={data.hours?.[day]} onChange={v => patchGroup("hours", day, v)} />)}
      </div>
    </section>

    <section className="bg-white border border-navy/10 rounded-lg p-5 space-y-4">
      <h3 className="font-serif text-xl text-navy">Homepage & marketing</h3>
      <div className="grid md:grid-cols-2 gap-4">
        <Input label="Homepage announcement" value={data.homepage?.announcement} onChange={v => patchGroup("homepage", "announcement", v)} />
        <Input label="Default call-to-action" value={data.homepage?.default_cta} onChange={v => patchGroup("homepage", "default_cta", v)} />
        <label className="block space-y-1">
          <span className="text-xs font-semibold text-navy">Default flyer template</span>
          <select value={data.marketing?.default_template || "luxury"} onChange={e => patchGroup("marketing", "default_template", e.target.value)} className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm bg-white">
            <option value="luxury">Luxury</option><option value="luxury_dark">Luxury Dark</option>
            <option value="cajun">Cajun</option><option value="cajun_blackened">Blackened Cajun</option>
            <option value="seafood">Seafood</option><option value="seafood_coastal">Coastal Seafood</option><option value="seafood_lagoon">Seafood Lagoon</option>
          </select>
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-semibold text-navy">Default flyer size</span>
          <select value={data.marketing?.default_platform || "instagram_square"} onChange={e => patchGroup("marketing", "default_platform", e.target.value)} className="w-full border border-navy/20 rounded-md px-3 py-2 text-sm bg-white">
            <option value="instagram_square">Instagram Square</option><option value="facebook_post">Facebook Post</option><option value="instagram_story">Story</option>
          </select>
        </label>
      </div>
    </section>

    <section className="bg-white border border-navy/10 rounded-lg p-5 space-y-4">
      <h3 className="font-serif text-xl text-navy">Loyalty</h3>
      <div className="grid md:grid-cols-2 gap-4">
        <Input label="Visits required for reward" type="number" value={data.loyalty?.visits_required} onChange={v => patchGroup("loyalty", "visits_required", Number(v))} />
        <Input label="Reward name" value={data.loyalty?.reward_label} onChange={v => patchGroup("loyalty", "reward_label", v)} />
      </div>
      <label className="flex items-center gap-2 text-sm text-navy">
        <input type="checkbox" checked={data.loyalty?.enabled !== false} onChange={e => patchGroup("loyalty", "enabled", e.target.checked)} /> Loyalty program enabled
      </label>
    </section>

    <section className="bg-white border border-navy/10 rounded-lg p-5 space-y-4">
      <h3 className="font-serif text-xl text-navy">Social & branding</h3>
      <div className="grid md:grid-cols-2 gap-4">
        <Input label="Facebook URL" value={data.social?.facebook} onChange={v => patchGroup("social", "facebook", v)} />
        <Input label="Instagram URL" value={data.social?.instagram} onChange={v => patchGroup("social", "instagram", v)} />
        <Input label="Logo URL" value={data.branding?.logo_url} onChange={v => patchGroup("branding", "logo_url", v)} />
      </div>
    </section>

    <div className="flex items-center gap-3 sticky bottom-4 bg-cream/95 p-3 border border-navy/10 rounded-lg shadow-sm">
      <Button onClick={save} disabled={busy} className="bg-gold text-navy hover:bg-gold/90"><Save className="w-4 h-4 mr-2" />{busy ? "Saving…" : "Save settings"}</Button>
      {message ? <span className="text-sm text-navy/70">{message}</span> : null}
      <SettingsIcon className="w-4 h-4 text-navy/30 ml-auto" />
    </div>
  </div>;
};

export default SettingsTab;
