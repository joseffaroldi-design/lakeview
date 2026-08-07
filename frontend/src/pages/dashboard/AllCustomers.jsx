/**
 * AllCustomers — unified customer directory.
 *
 * Merges `newsletter_subscribers` (email-only) and `loyalty_members`
 * (name + phone + visits) into a single searchable table. There is no
 * shared key between the two collections — each row shows what we know
 * about that person and a badge indicating the source channel(s).
 */
import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Mail, Phone, Users, Search } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const AllCustomers = ({ getAuthHeader }) => {
  const [subs, setSubs] = useState([]);
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [q, setQ] = useState("");

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [subsRes, memRes] = await Promise.all([
        axios.get(`${API}/newsletter/subscribers`, { headers: getAuthHeader() }),
        axios.get(`${API}/loyalty/members`,        { headers: getAuthHeader() }),
      ]);
      setSubs(subsRes.data.subscribers || []);
      setMembers(memRes.data.members || []);
    } catch (err) {
      console.error("Error fetching customers:", err);
    } finally {
      setLoading(false);
    }
  }, [getAuthHeader]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Merge into one row set. No shared key exists; we surface both sides
  // as separate rows tagged with the source channel(s).
  const rows = useMemo(() => {
    const out = [];
    for (const s of subs) {
      out.push({
        id: `sub:${s.id || s.email}`,
        name: "",
        email: s.email || "",
        phone: "",
        visits: null,
        channels: ["email"],
        joined_at: s.subscribed_at || null,
      });
    }
    for (const m of members) {
      out.push({
        id: `mem:${m.id}`,
        name: m.name || "",
        email: "",
        phone: m.phone || "",
        visits: m.visits ?? 0,
        channels: ["phone"],
        joined_at: m.joined_at || null,
      });
    }
    // Newest first
    out.sort((a, b) => (b.joined_at || "").localeCompare(a.joined_at || ""));
    return out;
  }, [subs, members]);

  const filtered = useMemo(() => {
    const query = q.trim().toLowerCase();
    if (!query) return rows;
    return rows.filter((r) =>
      (r.name || "").toLowerCase().includes(query) ||
      (r.email || "").toLowerCase().includes(query) ||
      (r.phone || "").includes(query)
    );
  }, [rows, q]);

  if (loading) return <p className="text-muted-foreground">Loading customers…</p>;

  return (
    <section data-testid="all-customers-section">
      <h2 className="font-serif text-2xl text-navy font-bold mb-6 flex items-center gap-2">
        <Users className="w-6 h-6 text-gold" />
        All Customers
        <span className="text-sm font-sans font-normal text-muted-foreground ml-2">
          ({rows.length} — {subs.length} email, {members.length} loyalty)
        </span>
      </h2>

      <div className="relative mb-4 max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-navy/40" />
        <Input
          data-testid="all-customers-search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search name, email, or phone…"
          className="pl-9"
        />
      </div>

      {filtered.length === 0 ? (
        <Card className="bg-card border-2 border-navy/10">
          <CardContent className="py-8 text-center">
            <Users className="w-10 h-10 mx-auto text-muted-foreground mb-3" />
            <p className="font-sans text-muted-foreground">
              {rows.length === 0 ? "No customers yet." : "No matches for that search."}
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="bg-card border-2 border-navy/10">
          <CardContent className="py-2">
            <div className="divide-y divide-navy/5">
              {filtered.map((r, idx) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between gap-4 py-3"
                  data-testid={`all-customer-row-${idx}`}
                >
                  <div className="flex-1 min-w-0">
                    {r.name ? (
                      <p className="font-sans text-navy font-medium truncate">{r.name}</p>
                    ) : null}
                    <div className="flex items-center gap-3 text-sm text-muted-foreground flex-wrap">
                      {r.email ? (
                        <span className="inline-flex items-center gap-1">
                          <Mail className="w-3.5 h-3.5" /> {r.email}
                        </span>
                      ) : null}
                      {r.phone ? (
                        <span className="inline-flex items-center gap-1">
                          <Phone className="w-3.5 h-3.5" /> {r.phone}
                        </span>
                      ) : null}
                      {r.visits != null ? (
                        <span className="inline-flex items-center gap-1 text-xs text-forest">
                          {r.visits}/10 visits{r.visits >= 10 ? " · reward earned" : ""}
                        </span>
                      ) : null}
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {r.channels.includes("email") ? (
                      <span
                        className="text-[10px] uppercase tracking-wider bg-gold/15 text-gold px-2 py-0.5 rounded-full"
                        data-testid={`all-customer-badge-email-${idx}`}
                      >Email</span>
                    ) : null}
                    {r.channels.includes("phone") ? (
                      <span
                        className="text-[10px] uppercase tracking-wider bg-forest/15 text-forest px-2 py-0.5 rounded-full"
                        data-testid={`all-customer-badge-phone-${idx}`}
                      >Loyalty</span>
                    ) : null}
                    <span className="font-sans text-xs text-muted-foreground hidden sm:inline">
                      {r.joined_at ? new Date(r.joined_at).toLocaleDateString() : ""}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </section>
  );
};

export default AllCustomers;
