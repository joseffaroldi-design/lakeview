import React, { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Save, Gift, CheckCircle } from "lucide-react";
import axios from "axios";

const API_BASE = process.env.REACT_APP_BACKEND_URL + "/api";

const PrizeRow = ({ prize, idx, onChange }) => {
  const color = prize.color;
  const label = prize.label;
  const weight = prize.weight;
  return (
    <div className="flex items-center gap-2 p-2 bg-background rounded-sm border border-navy/5">
      <div className="w-5 h-5 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
      <Input
        value={label}
        onChange={(e) => onChange(idx, "label", e.target.value)}
        className="border-navy/20 flex-1 text-sm"
      />
      <Input
        type="number"
        value={weight}
        onChange={(e) => onChange(idx, "weight", e.target.value)}
        className="border-navy/20 w-20 text-sm"
      />
    </div>
  );
};

const EntryRow = ({ entry, onClaim }) => {
  const id = entry.id;
  const name = entry.name;
  const prize = entry.prize;
  const email = entry.email;
  const enteredAt = new Date(entry.entered_at).toLocaleDateString();
  const claimed = entry.claimed;
  const canClaim = !claimed && prize !== "Try Again";
  return (
    <div className="flex items-center justify-between p-3 bg-background rounded-sm border border-navy/5">
      <div>
        <div className="flex items-center gap-2">
          <span className="font-semibold text-navy">{name}</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-gold/20 text-gold">{prize}</span>
          {claimed && <CheckCircle className="w-4 h-4 text-green-500" />}
        </div>
        <p className="text-xs text-muted-foreground">{email} | {enteredAt}</p>
      </div>
      {canClaim && (
        <Button size="sm" variant="outline" onClick={() => onClaim(id)} className="text-xs">
          Claimed
        </Button>
      )}
    </div>
  );
};

export function GiveawayManager({ getAuthHeader }) {
  const [data, setData] = useState(null);
  const [entries, setEntries] = useState([]);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    axios.get(`${API_BASE}/giveaway/settings`).then((r) => setData(r.data));
    axios
      .get(`${API_BASE}/giveaway/entries`, { headers: getAuthHeader() })
      .then((r) => setEntries(r.data.entries || []))
      .catch(() => {});
  }, [getAuthHeader]);

  useEffect(() => { load(); }, [load]);

  const toggle = () => {
    if (!data) return;
    axios
      .put(`${API_BASE}/giveaway/settings`, { is_active: !data.is_active }, { headers: getAuthHeader() })
      .then((r) => setData(r.data));
  };

  const save = () => {
    setSaving(true);
    axios
      .put(`${API_BASE}/giveaway/settings`, data, { headers: getAuthHeader() })
      .then(() => setTimeout(() => setSaving(false), 1500));
  };

  const claim = (id) => {
    axios
      .put(`${API_BASE}/giveaway/entries/${id}/claim`, {}, { headers: getAuthHeader() })
      .then(load);
  };

  const setPrizeField = (i, key, value) => {
    const next = data.prizes.slice();
    next[i] = { ...next[i], [key]: key === "weight" ? (parseInt(value) || 0) : value };
    setData({ ...data, prizes: next });
  };

  const setField = (key, value) => setData({ ...data, [key]: value });

  if (!data) return <p>Loading...</p>;

  const prizes = data.prizes || [];

  return (
    <div className="space-y-6" data-testid="giveaway-manager">
      <Card className="border-2 border-navy/10">
        <CardContent className="py-6">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-serif text-xl text-navy font-bold">
                {data.is_active ? "Giveaway is LIVE" : "Giveaway is OFF"}
              </h3>
              <p className="font-sans text-sm text-muted-foreground">
                {data.is_active ? "Visitors can see the Spin wheel." : "Activate when ready."}
              </p>
            </div>
            <Button
              data-testid="giveaway-toggle-btn"
              onClick={toggle}
              className={
                data.is_active
                  ? "bg-red-500 text-white hover:bg-red-600"
                  : "bg-green-600 text-white hover:bg-green-700"
              }
            >
              {data.is_active ? "Deactivate" : "Activate"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="bg-card border-2 border-navy/10">
        <CardHeader>
          <CardTitle className="font-serif text-navy flex items-center gap-2">
            <Gift className="w-5 h-5 text-gold" /> Settings
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">Title</label>
              <Input
                data-testid="giveaway-title-input"
                value={data.title || ""}
                onChange={(e) => setField("title", e.target.value)}
                className="border-navy/20"
              />
            </div>
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">Subtitle</label>
              <Input
                value={data.subtitle || ""}
                onChange={(e) => setField("subtitle", e.target.value)}
                className="border-navy/20"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">Start Date</label>
              <Input
                type="date"
                value={data.start_date || ""}
                onChange={(e) => setField("start_date", e.target.value)}
                className="border-navy/20"
              />
            </div>
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">End Date</label>
              <Input
                type="date"
                value={data.end_date || ""}
                onChange={(e) => setField("end_date", e.target.value)}
                className="border-navy/20"
              />
            </div>
          </div>

          <div>
            <label className="block font-sans text-sm font-semibold text-navy mb-2">Prizes</label>
            <div className="space-y-2">
              {prizes.map((prize, idx) => (
                <PrizeRow key={idx} prize={prize} idx={idx} onChange={setPrizeField} />
              ))}
            </div>
          </div>

          <Button
            data-testid="save-giveaway-btn"
            onClick={save}
            disabled={saving}
            className="bg-gold text-navy hover:bg-gold/90"
          >
            <Save className="w-4 h-4 mr-2" />
            {saving ? "Saved!" : "Save Settings"}
          </Button>
        </CardContent>
      </Card>

      <Card className="bg-card border-2 border-navy/10">
        <CardHeader>
          <CardTitle className="font-serif text-navy">
            Entries ({entries.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {entries.length === 0 ? (
            <p className="text-muted-foreground text-center py-6">No entries yet.</p>
          ) : (
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {entries.map((entry) => (
                <EntryRow key={entry.id} entry={entry} onClaim={claim} />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
