import React, { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CreditCard, Plus, Award, CheckCircle, Send, History } from "lucide-react";
import axios from "axios";

const API_BASE = process.env.REACT_APP_BACKEND_URL + "/api";

export function LoyaltyManager({ getAuthHeader }) {
  const [members, setMembers] = useState([]);
  const [search, setSearch] = useState("");

  function load() {
    axios.get(API_BASE + "/loyalty/members", { headers: getAuthHeader() }).then(r => setMembers(r.data.members || [])).catch(console.error);
  }
  useEffect(load, []);

  function stamp(id) {
    axios.put(API_BASE + "/loyalty/members/" + id + "/stamp", {}, { headers: getAuthHeader() }).then(load).catch(console.error);
  }

  function claimReward(id) {
    axios.put(API_BASE + "/loyalty/members/" + id + "/claim", {}, { headers: getAuthHeader() }).then(load).catch(console.error);
  }

  var filtered = members.filter(function(m) {
    var q = search.toLowerCase();
    return !q || m.name.toLowerCase().includes(q) || m.phone.includes(q);
  });

  return React.createElement("div", { className: "space-y-6", "data-testid": "loyalty-manager" },
    React.createElement(Card, { className: "bg-card border-2 border-navy/10" },
      React.createElement(CardHeader, null,
        React.createElement(CardTitle, { className: "font-serif text-navy flex items-center gap-2" },
          React.createElement(CreditCard, { className: "w-5 h-5 text-gold" }),
          " Loyalty Members (" + members.length + ")"
        )
      ),
      React.createElement(CardContent, null,
        React.createElement(Input, {
          "data-testid": "loyalty-search",
          value: search,
          onChange: function(e) { setSearch(e.target.value); },
          placeholder: "Search by name or phone...",
          className: "border-navy/20 mb-4"
        }),
        filtered.length === 0
          ? React.createElement("p", { className: "text-muted-foreground text-center py-6" }, "No loyalty members yet.")
          : React.createElement("div", { className: "space-y-3 max-h-[500px] overflow-y-auto" },
              filtered.map(function(member) {
                var dots = [];
                for (var i = 0; i < 10; i++) {
                  dots.push(React.createElement("div", {
                    key: i,
                    className: "w-6 h-6 rounded-full border " + (i < member.visits ? "bg-gold border-gold" : "border-navy/20") + " flex items-center justify-center text-xs",
                    style: { fontSize: "10px" }
                  }, i + 1));
                }
                return React.createElement("div", {
                  key: member.id,
                  className: "p-4 bg-background rounded-sm border border-navy/5",
                  "data-testid": "loyalty-member-" + member.id
                },
                  React.createElement("div", { className: "flex items-center justify-between mb-2" },
                    React.createElement("div", null,
                      React.createElement("span", { className: "font-semibold text-navy" }, member.name),
                      React.createElement("span", { className: "text-muted-foreground text-sm ml-2" }, member.phone)
                    ),
                    React.createElement("div", { className: "flex gap-2" },
                      React.createElement(Button, {
                        size: "sm",
                        onClick: function() { stamp(member.id); },
                        className: "bg-forest text-cream hover:bg-forest/90 text-xs",
                        "data-testid": "stamp-" + member.id
                      }, React.createElement(Plus, { className: "w-3 h-3 mr-1" }), "Stamp Visit"),
                      member.reward_earned && !member.reward_claimed && React.createElement(Button, {
                        size: "sm",
                        onClick: function() { claimReward(member.id); },
                        className: "bg-gold text-navy hover:bg-gold/90 text-xs",
                        "data-testid": "claim-reward-" + member.id
                      }, React.createElement(Award, { className: "w-3 h-3 mr-1" }), "Give Free Meal")
                    )
                  ),
                  React.createElement("div", { className: "flex gap-1 flex-wrap" }, dots),
                  member.reward_earned && React.createElement("p", { className: "text-sm font-semibold text-gold mt-2 flex items-center gap-1" },
                    React.createElement(Award, { className: "w-4 h-4" }), "FREE MEAL EARNED!"
                  )
                );
              })
            )
      )
    )
  );
}

export function MessagingDashboard({ getAuthHeader }) {
  var initForm = { subject: "", body: "", channel: "email", recipient_group: "newsletter" };
  const [form, setForm] = useState(initForm);
  const [sending, setSending] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [history, setHistory] = useState([]);

  function loadHistory() {
    axios.get(API_BASE + "/messages/history", { headers: getAuthHeader() }).then(r => setHistory(r.data.blasts || [])).catch(console.error);
  }
  useEffect(loadHistory, []);

  function sendBlast(e) {
    e.preventDefault();
    setSending(true);
    setLastResult(null);
    axios.post(API_BASE + "/messages/send", form, { headers: getAuthHeader() })
      .then(function(r) { setLastResult(r.data); setForm(initForm); loadHistory(); })
      .catch(function(err) { setLastResult({ message: "Failed: " + (err.response?.data?.detail || "Error") }); })
      .finally(function() { setSending(false); });
  }

  return React.createElement("div", { className: "space-y-6", "data-testid": "messaging-dashboard" },
    React.createElement(Card, { className: "bg-card border-2 border-navy/10" },
      React.createElement(CardHeader, null,
        React.createElement(CardTitle, { className: "font-serif text-navy flex items-center gap-2" },
          React.createElement(Send, { className: "w-5 h-5 text-gold" }), " Send Message Blast"
        )
      ),
      React.createElement(CardContent, null,
        React.createElement("form", { onSubmit: sendBlast, className: "space-y-4" },
          React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-4" },
            React.createElement("div", null,
              React.createElement("label", { className: "block font-sans text-sm text-muted-foreground mb-1" }, "Channel"),
              React.createElement("select", {
                "data-testid": "msg-channel",
                value: form.channel,
                onChange: function(e) { setForm(Object.assign({}, form, { channel: e.target.value })); },
                className: "w-full px-3 py-2 border border-navy/20 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-gold"
              },
                React.createElement("option", { value: "email" }, "Email Only"),
                React.createElement("option", { value: "sms" }, "SMS Only"),
                React.createElement("option", { value: "both" }, "Email + SMS")
              )
            ),
            React.createElement("div", null,
              React.createElement("label", { className: "block font-sans text-sm text-muted-foreground mb-1" }, "Recipients"),
              React.createElement("select", {
                "data-testid": "msg-recipients",
                value: form.recipient_group,
                onChange: function(e) { setForm(Object.assign({}, form, { recipient_group: e.target.value })); },
                className: "w-full px-3 py-2 border border-navy/20 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-gold"
              },
                React.createElement("option", { value: "all" }, "All Contacts"),
                React.createElement("option", { value: "newsletter" }, "Newsletter Subscribers"),
                React.createElement("option", { value: "giveaway" }, "Giveaway Entrants"),
                React.createElement("option", { value: "loyalty" }, "Loyalty Members")
              )
            )
          ),
          React.createElement("div", null,
            React.createElement("label", { className: "block font-sans text-sm text-muted-foreground mb-1" }, "Subject (for email)"),
            React.createElement(Input, {
              "data-testid": "msg-subject",
              value: form.subject,
              onChange: function(e) { setForm(Object.assign({}, form, { subject: e.target.value })); },
              placeholder: "e.g., This Weekend at Lakeview!",
              className: "border-navy/20"
            })
          ),
          React.createElement("div", null,
            React.createElement("label", { className: "block font-sans text-sm text-muted-foreground mb-1" }, "Message Body"),
            React.createElement("textarea", {
              "data-testid": "msg-body",
              value: form.body,
              onChange: function(e) { setForm(Object.assign({}, form, { body: e.target.value })); },
              required: true,
              rows: 4,
              placeholder: "Write your message here...",
              className: "w-full px-3 py-2 border border-navy/20 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-gold resize-none"
            })
          ),
          lastResult && React.createElement("div", {
            className: "p-3 rounded-sm text-sm " + (lastResult.errors && lastResult.errors.length > 0 ? "bg-yellow-50 border border-yellow-200" : "bg-green-50 border border-green-200"),
            "data-testid": "msg-result"
          },
            React.createElement("p", { className: "font-semibold" }, lastResult.message),
            lastResult.errors && lastResult.errors.length > 0 && React.createElement("ul", { className: "mt-1 text-xs text-muted-foreground" },
              lastResult.errors.map(function(err, i) { return React.createElement("li", { key: i }, err); })
            )
          ),
          React.createElement(Button, {
            "data-testid": "msg-send-btn",
            type: "submit",
            disabled: sending || !form.body.trim(),
            className: "bg-gold text-navy hover:bg-gold/90"
          }, React.createElement(Send, { className: "w-4 h-4 mr-2" }), sending ? "Sending..." : "Send Blast")
        )
      )
    ),
    history.length > 0 && React.createElement(Card, { className: "bg-card border-2 border-navy/10" },
      React.createElement(CardHeader, null,
        React.createElement(CardTitle, { className: "font-serif text-navy flex items-center gap-2" },
          React.createElement(History, { className: "w-5 h-5 text-gold" }), " Message History"
        )
      ),
      React.createElement(CardContent, null,
        React.createElement("div", { className: "space-y-3 max-h-96 overflow-y-auto" },
          history.map(function(blast) {
            return React.createElement("div", {
              key: blast.id,
              className: "p-3 bg-background rounded-sm border border-navy/5"
            },
              React.createElement("div", { className: "flex justify-between items-start" },
                React.createElement("div", null,
                  React.createElement("p", { className: "font-semibold text-navy text-sm" }, blast.subject || "(No subject)"),
                  React.createElement("p", { className: "text-xs text-muted-foreground mt-1" }, blast.body.substring(0, 100) + (blast.body.length > 100 ? "..." : ""))
                ),
                React.createElement("span", { className: "text-xs text-muted-foreground flex-shrink-0" }, new Date(blast.sent_at).toLocaleDateString())
              ),
              React.createElement("div", { className: "flex gap-3 mt-2 text-xs text-muted-foreground" },
                React.createElement("span", null, "Channel: " + blast.channel),
                React.createElement("span", null, "Emails: " + blast.email_count + "/" + blast.total_emails),
                React.createElement("span", null, "SMS: " + blast.sms_count + "/" + blast.total_phones)
              )
            );
          })
        )
      )
    )
  );
}
