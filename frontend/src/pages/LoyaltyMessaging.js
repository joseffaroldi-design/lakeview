import React, { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CreditCard, Plus, Award, Send, History } from "lucide-react";
import axios from "axios";

const API_BASE = process.env.REACT_APP_BACKEND_URL + "/api";

const PunchDots = ({ visits }) => {
  const items = [];
  for (let i = 0; i < 10; i += 1) {
    const filled = i < visits;
    items.push(
      <div
        key={i}
        className={`w-6 h-6 rounded-full border flex items-center justify-center text-xs ${
          filled ? "bg-gold border-gold" : "border-navy/20"
        }`}
        style={{ fontSize: "10px" }}
      >
        {i + 1}
      </div>
    );
  }
  return <div className="flex gap-1 flex-wrap">{items}</div>;
};

const LoyaltyMemberRow = ({ member, onStamp, onClaim }) => {
  const id = member.id;
  const name = member.name;
  const phone = member.phone;
  const visits = member.visits;
  const rewardEarned = member.reward_earned;
  const rewardClaimed = member.reward_claimed;

  return (
    <div
      className="p-4 bg-background rounded-sm border border-navy/5"
      data-testid={`loyalty-member-${id}`}
    >
      <div className="flex items-center justify-between mb-2">
        <div>
          <span className="font-semibold text-navy">{name}</span>
          <span className="text-muted-foreground text-sm ml-2">{phone}</span>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            onClick={() => onStamp(id)}
            className="bg-forest text-cream hover:bg-forest/90 text-xs"
            data-testid={`stamp-${id}`}
          >
            <Plus className="w-3 h-3 mr-1" />
            Stamp Visit
          </Button>
          {rewardEarned && !rewardClaimed && (
            <Button
              size="sm"
              onClick={() => onClaim(id)}
              className="bg-gold text-navy hover:bg-gold/90 text-xs"
              data-testid={`claim-reward-${id}`}
            >
              <Award className="w-3 h-3 mr-1" />
              Give Free Meal
            </Button>
          )}
        </div>
      </div>
      <PunchDots visits={visits} />
      {rewardEarned && (
        <p className="text-sm font-semibold text-gold mt-2 flex items-center gap-1">
          <Award className="w-4 h-4" />
          FREE MEAL EARNED!
        </p>
      )}
    </div>
  );
};

export function LoyaltyManager({ getAuthHeader }) {
  const [members, setMembers] = useState([]);
  const [search, setSearch] = useState("");

  const load = useCallback(() => {
    axios
      .get(`${API_BASE}/loyalty/members`, { headers: getAuthHeader() })
      .then((r) => setMembers(r.data.members || []))
      .catch(console.error);
  }, [getAuthHeader]);

  useEffect(() => { load(); }, [load]);

  const stamp = (id) => {
    axios
      .put(`${API_BASE}/loyalty/members/${id}/stamp`, {}, { headers: getAuthHeader() })
      .then(load)
      .catch(console.error);
  };

  const claimReward = (id) => {
    axios
      .put(`${API_BASE}/loyalty/members/${id}/claim`, {}, { headers: getAuthHeader() })
      .then(load)
      .catch(console.error);
  };

  const q = search.toLowerCase();
  const filtered = members.filter(
    (m) => !q || m.name.toLowerCase().includes(q) || m.phone.includes(q)
  );

  return (
    <div className="space-y-6" data-testid="loyalty-manager">
      <Card className="bg-card border-2 border-navy/10">
        <CardHeader>
          <CardTitle className="font-serif text-navy flex items-center gap-2">
            <CreditCard className="w-5 h-5 text-gold" /> Loyalty Members ({members.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Input
            data-testid="loyalty-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by name or phone..."
            className="border-navy/20 mb-4"
          />
          {filtered.length === 0 ? (
            <p className="text-muted-foreground text-center py-6">No loyalty members yet.</p>
          ) : (
            <div className="space-y-3 max-h-[500px] overflow-y-auto">
              {filtered.map((member) => (
                <LoyaltyMemberRow
                  key={member.id}
                  member={member}
                  onStamp={stamp}
                  onClaim={claimReward}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const INIT_MSG_FORM = { subject: "", body: "", channel: "email", recipient_group: "newsletter" };

const ResultBanner = ({ result }) => {
  const errors = result.errors || [];
  const hasErrors = errors.length > 0;
  return (
    <div
      className={`p-3 rounded-sm text-sm ${
        hasErrors
          ? "bg-yellow-50 border border-yellow-200"
          : "bg-green-50 border border-green-200"
      }`}
      data-testid="msg-result"
    >
      <p className="font-semibold">{result.message}</p>
      {hasErrors && (
        <ul className="mt-1 text-xs text-muted-foreground">
          {errors.map((err, i) => (
            <li key={i}>{err}</li>
          ))}
        </ul>
      )}
    </div>
  );
};

const BlastHistoryRow = ({ blast }) => {
  const subject = blast.subject || "(No subject)";
  const body = blast.body;
  const preview = body.length > 100 ? body.substring(0, 100) + "..." : body;
  const sentAt = new Date(blast.sent_at).toLocaleDateString();
  return (
    <div className="p-3 bg-background rounded-sm border border-navy/5">
      <div className="flex justify-between items-start">
        <div>
          <p className="font-semibold text-navy text-sm">{subject}</p>
          <p className="text-xs text-muted-foreground mt-1">{preview}</p>
        </div>
        <span className="text-xs text-muted-foreground flex-shrink-0">{sentAt}</span>
      </div>
      <div className="flex gap-3 mt-2 text-xs text-muted-foreground">
        <span>Channel: {blast.channel}</span>
        <span>Emails: {blast.email_count}/{blast.total_emails}</span>
        <span>SMS: {blast.sms_count}/{blast.total_phones}</span>
      </div>
    </div>
  );
};

export function MessagingDashboard({ getAuthHeader }) {
  const [form, setForm] = useState(INIT_MSG_FORM);
  const [sending, setSending] = useState(false);
  const [lastResult, setLastResult] = useState(null);
  const [history, setHistory] = useState([]);

  const loadHistory = useCallback(() => {
    axios
      .get(`${API_BASE}/messages/history`, { headers: getAuthHeader() })
      .then((r) => setHistory(r.data.blasts || []))
      .catch(console.error);
  }, [getAuthHeader]);

  useEffect(() => { loadHistory(); }, [loadHistory]);

  const sendBlast = (e) => {
    e.preventDefault();
    setSending(true);
    setLastResult(null);
    axios
      .post(`${API_BASE}/messages/send`, form, { headers: getAuthHeader() })
      .then((r) => {
        setLastResult(r.data);
        setForm(INIT_MSG_FORM);
        loadHistory();
      })
      .catch((err) => {
        const detail = (err.response && err.response.data && err.response.data.detail) || "Error";
        setLastResult({ message: `Failed: ${detail}` });
      })
      .finally(() => setSending(false));
  };

  return (
    <div className="space-y-6" data-testid="messaging-dashboard">
      <Card className="bg-card border-2 border-navy/10">
        <CardHeader>
          <CardTitle className="font-serif text-navy flex items-center gap-2">
            <Send className="w-5 h-5 text-gold" /> Send Message Blast
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={sendBlast} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block font-sans text-sm text-muted-foreground mb-1">
                  Channel
                </label>
                <select
                  data-testid="msg-channel"
                  value={form.channel}
                  onChange={(e) => setForm({ ...form, channel: e.target.value })}
                  className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                >
                  <option value="email">Email Only</option>
                  <option value="sms">SMS Only</option>
                  <option value="both">Email + SMS</option>
                </select>
              </div>
              <div>
                <label className="block font-sans text-sm text-muted-foreground mb-1">
                  Recipients
                </label>
                <select
                  data-testid="msg-recipients"
                  value={form.recipient_group}
                  onChange={(e) => setForm({ ...form, recipient_group: e.target.value })}
                  className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-gold"
                >
                  <option value="all">All Contacts</option>
                  <option value="newsletter">Newsletter Subscribers</option>
                  <option value="giveaway">Giveaway Entrants</option>
                  <option value="loyalty">Loyalty Members</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">
                Subject (for email)
              </label>
              <Input
                data-testid="msg-subject"
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                placeholder="e.g., This Weekend at Lakeview!"
                className="border-navy/20"
              />
            </div>

            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">
                Message Body
              </label>
              <textarea
                data-testid="msg-body"
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                required
                rows={4}
                placeholder="Write your message here..."
                className="w-full px-3 py-2 border border-navy/20 rounded-sm text-sm focus:outline-none focus:ring-2 focus:ring-gold resize-none"
              />
            </div>

            {lastResult && <ResultBanner result={lastResult} />}

            <Button
              data-testid="msg-send-btn"
              type="submit"
              disabled={sending || !form.body.trim()}
              className="bg-gold text-navy hover:bg-gold/90"
            >
              <Send className="w-4 h-4 mr-2" />
              {sending ? "Sending..." : "Send Blast"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {history.length > 0 && (
        <Card className="bg-card border-2 border-navy/10">
          <CardHeader>
            <CardTitle className="font-serif text-navy flex items-center gap-2">
              <History className="w-5 h-5 text-gold" /> Message History
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {history.map((blast) => (
                <BlastHistoryRow key={blast.id} blast={blast} />
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
