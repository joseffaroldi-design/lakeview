import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Save, Gift, CheckCircle } from "lucide-react";
import axios from "axios";

const API_BASE = process.env.REACT_APP_BACKEND_URL + "/api";

export function GiveawayManager({ getAuthHeader }) {
  const [data, setData] = useState(null);
  const [entries, setEntries] = useState([]);
  const [saving, setSaving] = useState(false);

  function load() {
    axios.get(API_BASE + "/giveaway/settings").then(r => setData(r.data));
    axios.get(API_BASE + "/giveaway/entries", { headers: getAuthHeader() }).then(r => setEntries(r.data.entries || [])).catch(() => {});
  }

  useEffect(load, []);

  function toggle() {
    if (!data) return;
    axios.put(API_BASE + "/giveaway/settings", { is_active: !data.is_active }, { headers: getAuthHeader() }).then(r => setData(r.data));
  }

  function save() {
    setSaving(true);
    axios.put(API_BASE + "/giveaway/settings", data, { headers: getAuthHeader() }).then(() => setTimeout(() => setSaving(false), 1500));
  }

  function claim(id) {
    axios.put(API_BASE + "/giveaway/entries/" + id + "/claim", {}, { headers: getAuthHeader() }).then(load);
  }

  function setPrizeField(i, k, v) {
    var p = data.prizes.slice();
    p[i] = Object.assign({}, p[i]);
    p[i][k] = k === "weight" ? (parseInt(v) || 0) : v;
    setData(Object.assign({}, data, { prizes: p }));
  }

  function setField(k, v) {
    setData(Object.assign({}, data, { [k]: v }));
  }

  if (!data) return React.createElement("p", null, "Loading...");

  return React.createElement("div", { className: "space-y-6", "data-testid": "giveaway-manager" },
    React.createElement(Card, { className: "border-2 border-navy/10" },
      React.createElement(CardContent, { className: "py-6" },
        React.createElement("div", { className: "flex items-center justify-between" },
          React.createElement("div", null,
            React.createElement("h3", { className: "font-serif text-xl text-navy font-bold" }, data.is_active ? "Giveaway is LIVE" : "Giveaway is OFF"),
            React.createElement("p", { className: "font-sans text-sm text-muted-foreground" }, data.is_active ? "Visitors can see the Spin wheel." : "Activate when ready.")
          ),
          React.createElement(Button, {
            "data-testid": "giveaway-toggle-btn",
            onClick: toggle,
            className: data.is_active ? "bg-red-500 text-white hover:bg-red-600" : "bg-green-600 text-white hover:bg-green-700"
          }, data.is_active ? "Deactivate" : "Activate")
        )
      )
    ),
    React.createElement(Card, { className: "bg-card border-2 border-navy/10" },
      React.createElement(CardHeader, null,
        React.createElement(CardTitle, { className: "font-serif text-navy flex items-center gap-2" },
          React.createElement(Gift, { className: "w-5 h-5 text-gold" }), " Settings"
        )
      ),
      React.createElement(CardContent, { className: "space-y-4" },
        React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4" },
          React.createElement("div", null,
            React.createElement("label", { className: "block font-sans text-sm text-muted-foreground mb-1" }, "Title"),
            React.createElement(Input, { "data-testid": "giveaway-title-input", value: data.title || "", onChange: function(e) { setField("title", e.target.value); }, className: "border-navy/20" })
          ),
          React.createElement("div", null,
            React.createElement("label", { className: "block font-sans text-sm text-muted-foreground mb-1" }, "Subtitle"),
            React.createElement(Input, { value: data.subtitle || "", onChange: function(e) { setField("subtitle", e.target.value); }, className: "border-navy/20" })
          )
        ),
        React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4" },
          React.createElement("div", null,
            React.createElement("label", { className: "block font-sans text-sm text-muted-foreground mb-1" }, "Start Date"),
            React.createElement(Input, { type: "date", value: data.start_date || "", onChange: function(e) { setField("start_date", e.target.value); }, className: "border-navy/20" })
          ),
          React.createElement("div", null,
            React.createElement("label", { className: "block font-sans text-sm text-muted-foreground mb-1" }, "End Date"),
            React.createElement(Input, { type: "date", value: data.end_date || "", onChange: function(e) { setField("end_date", e.target.value); }, className: "border-navy/20" })
          )
        ),
        React.createElement("div", null,
          React.createElement("label", { className: "block font-sans text-sm font-semibold text-navy mb-2" }, "Prizes"),
          React.createElement("div", { className: "space-y-2" },
            (data.prizes || []).map(function(prize, idx) {
              return React.createElement("div", { key: idx, className: "flex items-center gap-2 p-2 bg-background rounded-sm border border-navy/5" },
                React.createElement("div", { className: "w-5 h-5 rounded-full flex-shrink-0", style: { backgroundColor: prize.color } }),
                React.createElement(Input, { value: prize.label, onChange: function(e) { setPrizeField(idx, "label", e.target.value); }, className: "border-navy/20 flex-1 text-sm" }),
                React.createElement(Input, { type: "number", value: prize.weight, onChange: function(e) { setPrizeField(idx, "weight", e.target.value); }, className: "border-navy/20 w-20 text-sm" })
              );
            })
          )
        ),
        React.createElement(Button, { "data-testid": "save-giveaway-btn", onClick: save, disabled: saving, className: "bg-gold text-navy hover:bg-gold/90" },
          React.createElement(Save, { className: "w-4 h-4 mr-2" }), saving ? "Saved!" : "Save Settings"
        )
      )
    ),
    React.createElement(Card, { className: "bg-card border-2 border-navy/10" },
      React.createElement(CardHeader, null,
        React.createElement(CardTitle, { className: "font-serif text-navy" }, "Entries (" + entries.length + ")")
      ),
      React.createElement(CardContent, null,
        entries.length === 0
          ? React.createElement("p", { className: "text-muted-foreground text-center py-6" }, "No entries yet.")
          : React.createElement("div", { className: "space-y-2 max-h-96 overflow-y-auto" },
              entries.map(function(entry) {
                return React.createElement("div", { key: entry.id, className: "flex items-center justify-between p-3 bg-background rounded-sm border border-navy/5" },
                  React.createElement("div", null,
                    React.createElement("div", { className: "flex items-center gap-2" },
                      React.createElement("span", { className: "font-semibold text-navy" }, entry.name),
                      React.createElement("span", { className: "text-xs px-2 py-0.5 rounded-full bg-gold/20 text-gold" }, entry.prize),
                      entry.claimed && React.createElement(CheckCircle, { className: "w-4 h-4 text-green-500" })
                    ),
                    React.createElement("p", { className: "text-xs text-muted-foreground" }, entry.email + " | " + new Date(entry.entered_at).toLocaleDateString())
                  ),
                  !entry.claimed && entry.prize !== "Try Again" && React.createElement(Button, { size: "sm", variant: "outline", onClick: function() { claim(entry.id); }, className: "text-xs" }, "Claimed")
                );
              })
            )
      )
    )
  );
}
