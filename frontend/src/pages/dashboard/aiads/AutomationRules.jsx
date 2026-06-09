/**
 * Automation Rules — create simple recurring AI generation rules.
 *
 * Example: "Every Friday at 9am — Generate Seafood Special".
 * The backend stores the rule; a future cron/worker tick will trigger the
 * actual generation. For now this UI shows the CRUD; the execution worker
 * is a TODO (the scheduler loop is already in server.py and easy to extend).
 */
import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Repeat, Plus, Trash2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API, Section } from "./shared";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const DEFAULT_RULE = {
  name: "",
  frequency: "weekly",
  day_of_week: 4, // Friday
  day_of_month: 1,
  hour: 9,
  minute: 0,
  plugin_id: "restaurant",
  template_id: "seafood_special",
  context: {},
  action_ids: null,
  auto_publish: false,
  auto_publish_provider: "facebook",
  is_active: true,
};

const RuleForm = (props) => {
  const { templates, onCreate } = props;
  const [rule, setRule] = useState(DEFAULT_RULE);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    try {
      await onCreate(rule);
      setRule(DEFAULT_RULE);
    } finally {
      setBusy(false);
    }
  };

  const tplOpts = [];
  for (let i = 0; i < templates.length; i += 1) {
    tplOpts.push(<option key={templates[i].id} value={templates[i].id}>{templates[i].label}</option>);
  }
  return (
    <div className="rounded-lg border-2 border-navy/10 bg-card p-4 space-y-3" data-testid="automation-rule-form">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Rule Name</label>
          <Input
            value={rule.name}
            onChange={(e) => setRule({ ...rule, name: e.target.value })}
            placeholder="e.g. Friday Seafood Special"
            className="border-navy/20 text-sm"
            data-testid="automation-name"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Frequency</label>
          <select
            value={rule.frequency}
            onChange={(e) => setRule({ ...rule, frequency: e.target.value })}
            className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm"
            data-testid="automation-frequency"
          >
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="monthly">Monthly</option>
          </select>
        </div>
        {rule.frequency === "weekly" ? (
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Day of Week</label>
            <select
              value={rule.day_of_week}
              onChange={(e) => setRule({ ...rule, day_of_week: Number(e.target.value) })}
              className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm"
              data-testid="automation-dow"
            >
              {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
            </select>
          </div>
        ) : null}
        {rule.frequency === "monthly" ? (
          <div>
            <label className="block text-xs text-muted-foreground mb-1">Day of Month</label>
            <Input
              type="number" min={1} max={31}
              value={rule.day_of_month}
              onChange={(e) => setRule({ ...rule, day_of_month: Number(e.target.value) })}
              className="border-navy/20 text-sm"
              data-testid="automation-dom"
            />
          </div>
        ) : null}
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Hour (UTC)</label>
          <Input
            type="number" min={0} max={23}
            value={rule.hour}
            onChange={(e) => setRule({ ...rule, hour: Number(e.target.value) })}
            className="border-navy/20 text-sm"
            data-testid="automation-hour"
          />
        </div>
        <div>
          <label className="block text-xs text-muted-foreground mb-1">Template</label>
          <select
            value={rule.template_id}
            onChange={(e) => setRule({ ...rule, template_id: e.target.value })}
            className="w-full px-2 py-2 border border-navy/20 rounded-sm text-sm"
            data-testid="automation-template"
          >
            {tplOpts}
          </select>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <label className="flex items-center gap-2 text-sm text-navy">
          <input
            type="checkbox"
            checked={rule.auto_publish}
            onChange={(e) => setRule({ ...rule, auto_publish: e.target.checked })}
            data-testid="automation-autopublish"
          />
          Auto-publish on generation (to {rule.auto_publish_provider})
        </label>
        <Button onClick={submit} disabled={busy || !rule.name} className="bg-gold text-navy hover:bg-gold/90" data-testid="automation-save">
          <Plus className="w-3.5 h-3.5 mr-1" /> Create Rule
        </Button>
      </div>
    </div>
  );
};

const RuleRow = (props) => {
  const { rule, onDelete, onToggle } = props;
  const cadence = rule.frequency === "daily"
    ? `Daily at ${String(rule.hour).padStart(2, "0")}:00 UTC`
    : rule.frequency === "weekly"
      ? `Every ${DAYS[rule.day_of_week]} at ${String(rule.hour).padStart(2, "0")}:00 UTC`
      : `Day ${rule.day_of_month} of each month at ${String(rule.hour).padStart(2, "0")}:00 UTC`;
  return (
    <div className="p-3 bg-background border border-navy/10 rounded-sm flex flex-wrap items-center gap-3" data-testid={`automation-rule-${rule.id}`}>
      <div className="flex-1 min-w-[200px]">
        <p className="font-semibold text-navy text-sm">{rule.name}</p>
        <p className="text-xs text-muted-foreground">{cadence} · {rule.template_id}{rule.auto_publish ? ` · → ${rule.auto_publish_provider}` : ""}</p>
      </div>
      <label className="text-xs text-navy flex items-center gap-1">
        <input
          type="checkbox"
          checked={!!rule.is_active}
          onChange={() => onToggle(rule)}
          data-testid={`automation-toggle-${rule.id}`}
        />
        Active
      </label>
      <Button size="sm" variant="outline" onClick={() => onDelete(rule.id)} className="border-destructive text-destructive" data-testid={`automation-delete-${rule.id}`}>
        <Trash2 className="w-3 h-3" />
      </Button>
    </div>
  );
};

export const AutomationRules = (props) => {
  const { getAuthHeader } = props;
  const [rules, setRules] = useState([]);
  const [templates, setTemplates] = useState([]);

  const load = useCallback(async () => {
    try {
      const [rRes, pRes] = await Promise.all([
        axios.get(`${API}/ai-ads/automations`, { headers: getAuthHeader() }),
        axios.get(`${API}/ai-ads/plugins/restaurant`, { headers: getAuthHeader() }),
      ]);
      setRules(rRes.data.rules || []);
      setTemplates((pRes.data.templates || []));
    } catch (e) {
      console.error("automations load:", e);
    }
  }, [getAuthHeader]);

  useEffect(() => { load(); }, [load]);

  const create = async (rule) => {
    await axios.post(`${API}/ai-ads/automations`, rule, { headers: getAuthHeader() });
    load();
  };
  const del = async (id) => {
    if (!window.confirm("Delete this automation rule?")) return;
    await axios.delete(`${API}/ai-ads/automations/${id}`, { headers: getAuthHeader() });
    load();
  };
  const toggle = async (rule) => {
    await axios.put(`${API}/ai-ads/automations/${rule.id}`, { ...rule, is_active: !rule.is_active }, { headers: getAuthHeader() });
    load();
  };

  const rows = [];
  for (let i = 0; i < rules.length; i += 1) {
    rows.push(<RuleRow key={rules[i].id} rule={rules[i]} onDelete={del} onToggle={toggle} />);
  }

  return (
    <div className="space-y-4">
      <Section title="New Automation Rule" icon={Plus} testId="ai-automation-new">
        <RuleForm templates={templates} onCreate={create} />
      </Section>
      <Section title={`Active Rules (${rules.length})`} icon={Repeat} testId="ai-automation-list">
        {rows.length === 0 ? (
          <p className="text-sm text-muted-foreground italic text-center py-6">No automation rules yet.</p>
        ) : (
          <div className="space-y-2">{rows}</div>
        )}
      </Section>
    </div>
  );
};

export default AutomationRules;
