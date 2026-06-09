/**
 * Content Calendar — month / week / day views.
 *
 * Lightweight in-house calendar (no external lib). Renders scheduled_posts
 * pulled from GET /api/ai-ads/calendar. Color-coded by status:
 *   scheduled  → gold
 *   publishing → blue
 *   published  → forest green
 *   failed     → red
 *   cancelled  → muted gray
 *
 * Drag-and-drop reschedules via POST /api/ai-ads/reschedule/{id}.
 * Click an event to open a small detail popover with Cancel / Reschedule.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import {
  Calendar as CalendarIcon, ChevronLeft, ChevronRight, X,
  Trash2, Clock, Loader2, AlertTriangle, CheckCircle2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { API, Section } from "./shared";
import { StructuredErrorCard } from "./StructuredErrorCard";

const STATUS_COLOR = {
  scheduled: "bg-gold text-navy border-gold",
  publishing: "bg-blue-500 text-white border-blue-600",
  published: "bg-forest text-white border-forest",
  failed: "bg-red-500 text-white border-red-600",
  cancelled: "bg-navy/30 text-navy border-navy/30",
  draft: "bg-navy/10 text-navy border-navy/20",
};

const pad = (n) => String(n).padStart(2, "0");
const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const startOfMonth = (d) => new Date(d.getFullYear(), d.getMonth(), 1);
const endOfMonth = (d) => new Date(d.getFullYear(), d.getMonth() + 1, 0);
const startOfWeek = (d) => {
  const x = new Date(d);
  const day = x.getDay() === 0 ? 6 : x.getDay() - 1; // Mon as start
  x.setDate(x.getDate() - day);
  x.setHours(0, 0, 0, 0);
  return x;
};
const addDays = (d, n) => {
  const x = new Date(d);
  x.setDate(x.getDate() + n);
  return x;
};

const fmtMonth = (d) => d.toLocaleString(undefined, { month: "long", year: "numeric" });

const EventChip = (props) => {
  const { event, onClick, onDragStart } = props;
  const hhmm = event.scheduled_at ? event.scheduled_at.slice(11, 16) : "";
  return (
    <button
      type="button"
      draggable
      onDragStart={(e) => onDragStart(e, event)}
      onClick={() => onClick(event)}
      className={`w-full text-left px-1.5 py-0.5 rounded-sm text-[10px] font-semibold border ${STATUS_COLOR[event.status] || STATUS_COLOR.draft} truncate cursor-pointer hover:opacity-90`}
      data-testid={`calendar-event-${event.id}`}
      title={`${event.title} · ${event.provider} · ${event.status}`}
    >
      <span className="opacity-80">{hhmm}</span> · {event.title || event.kind}
    </button>
  );
};

const EventDetail = (props) => {
  const { event, onClose, onCancelEvent, onReschedule } = props;
  const [newAt, setNewAt] = useState(event.scheduled_at ? event.scheduled_at.slice(0, 16) : "");
  return (
    <div
      className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4"
      onClick={onClose}
      data-testid="calendar-event-detail"
    >
      <div className="bg-card rounded-lg max-w-md w-full p-5 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-serif text-navy font-bold text-lg">Scheduled Post</h3>
          <button onClick={onClose} aria-label="Close" data-testid="calendar-detail-close">
            <X className="w-4 h-4 text-navy" />
          </button>
        </div>
        <div className="space-y-2 text-sm">
          <p className="font-semibold text-navy">{event.title}</p>
          <p className="text-xs text-muted-foreground">
            {event.provider} · {event.kind}
          </p>
          <p className="text-xs">
            Status: <span className="font-mono font-semibold uppercase">{event.status}</span>
          </p>
          {event.error ? (
            <StructuredErrorCard error={event.error} testId={`calendar-event-${event.id}-error`} />
          ) : event.error_message ? (
            <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">{event.error_message}</p>
          ) : null}
          {event.published_at ? (
            <p className="text-xs text-forest">Published at {event.published_at.slice(0, 16).replace("T", " ")}</p>
          ) : null}
          {event.external_id ? (
            <p className="text-[10px] font-mono text-muted-foreground">ext id: {event.external_id}</p>
          ) : null}
        </div>
        {(event.status === "scheduled" || event.status === "failed") ? (
          <div className="mt-4 space-y-2">
            <label className="block text-xs text-muted-foreground">Reschedule to</label>
            <Input
              type="datetime-local"
              value={newAt}
              onChange={(e) => setNewAt(e.target.value)}
              className="border-navy/20 text-sm"
              data-testid="calendar-detail-reschedule-input"
            />
            <div className="flex gap-2">
              <Button
                size="sm"
                className="bg-gold text-navy hover:bg-gold/90"
                onClick={() => onReschedule(event, new Date(newAt).toISOString())}
                disabled={!newAt}
                data-testid="calendar-detail-reschedule-btn"
              >
                <Clock className="w-3.5 h-3.5 mr-1" /> Reschedule
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="border-destructive text-destructive"
                onClick={() => onCancelEvent(event)}
                data-testid="calendar-detail-cancel-btn"
              >
                <Trash2 className="w-3.5 h-3.5 mr-1" /> Cancel
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
};

const Legend = () => (
  <div className="flex flex-wrap gap-3 text-xs text-navy">
    {["scheduled", "publishing", "published", "failed", "cancelled"].map((s) => (
      <span key={s} className="inline-flex items-center gap-1">
        <span className={`inline-block w-3 h-3 rounded-sm border ${STATUS_COLOR[s]}`} />
        <span className="uppercase tracking-wider">{s}</span>
      </span>
    ))}
  </div>
);

export const ContentCalendar = (props) => {
  const { getAuthHeader } = props;
  const [cursor, setCursor] = useState(new Date());
  const [view, setView] = useState("month"); // month | week | day
  const [events, setEvents] = useState([]);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");  // all | draft | scheduled | publishing | published | failed

  const range = useMemo(() => {
    if (view === "month") return { start: startOfMonth(cursor), end: endOfMonth(cursor) };
    if (view === "week") return { start: startOfWeek(cursor), end: addDays(startOfWeek(cursor), 6) };
    return { start: new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate()),
             end: new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate(), 23, 59, 59) };
  }, [cursor, view]);

  const load = useCallback(async () => {
    setBusy(true);
    try {
      const res = await axios.get(`${API}/ai-ads/calendar`, {
        params: {
          start: new Date(range.start.getFullYear(), range.start.getMonth(), range.start.getDate()).toISOString(),
          end: new Date(range.end.getFullYear(), range.end.getMonth(), range.end.getDate(), 23, 59, 59).toISOString(),
        },
        headers: getAuthHeader(),
      });
      setEvents(res.data.events || []);
    } catch (e) {
      console.error("calendar load:", e);
    } finally {
      setBusy(false);
    }
  }, [range, getAuthHeader]);

  const calendarRefs = useRef({ load });
  useEffect(() => { calendarRefs.current = { load }; });
  useEffect(() => { calendarRefs.current.load(); }, [range]);

  const eventsByDay = useMemo(() => {
    const map = {};
    const filtered = statusFilter === "all" ? events : events.filter((e) => e.status === statusFilter);
    for (const ev of filtered) {
      const key = ev.scheduled_at ? ev.scheduled_at.slice(0, 10) : "";
      if (!key) continue;
      if (!map[key]) map[key] = [];
      map[key].push(ev);
    }
    for (const k of Object.keys(map)) {
      map[k].sort((a, b) => (a.scheduled_at < b.scheduled_at ? -1 : 1));
    }
    return map;
  }, [events]);

  const handleDragStart = (e, ev) => {
    e.dataTransfer.setData("text/plain", ev.id);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDropOnDay = async (e, day) => {
    e.preventDefault();
    const id = e.dataTransfer.getData("text/plain");
    if (!id) return;
    const ev = events.find((x) => x.id === id);
    if (!ev) return;
    // Preserve original hour/minute when moving across days
    const orig = new Date(ev.scheduled_at);
    const target = new Date(day);
    target.setHours(orig.getHours(), orig.getMinutes(), 0, 0);
    try {
      await axios.post(
        `${API}/ai-ads/reschedule/${id}`,
        { scheduled_at: target.toISOString() },
        { headers: getAuthHeader() }
      );
      load();
    } catch (err) {
      console.error("reschedule failed:", err);
    }
  };

  const handleCancel = async (ev) => {
    await axios.post(`${API}/ai-ads/cancel/${ev.id}`, {}, { headers: getAuthHeader() });
    setSelected(null);
    load();
  };

  const handleReschedule = async (ev, isoString) => {
    await axios.post(
      `${API}/ai-ads/reschedule/${ev.id}`,
      { scheduled_at: isoString },
      { headers: getAuthHeader() }
    );
    setSelected(null);
    load();
  };

  // ---------- View renderers ----------
  const renderMonth = () => {
    const first = startOfMonth(cursor);
    const last = endOfMonth(cursor);
    const gridStart = startOfWeek(first);
    const cells = [];
    let curDay = new Date(gridStart);
    while ((curDay <= last || curDay.getDay() !== 1) && cells.length < 42) {
      const nextCur = curDay;  // hoisted into block so React-Compiler immutability rule passes
      const key = ymd(nextCur);
      const inMonth = nextCur.getMonth() === cursor.getMonth();
      const todayCell = ymd(new Date()) === key;
      const dayEvents = eventsByDay[key] || [];
      const chips = [];
      for (let i = 0; i < Math.min(dayEvents.length, 4); i += 1) {
        chips.push(
          <EventChip
            key={dayEvents[i].id}
            event={dayEvents[i]}
            onClick={setSelected}
            onDragStart={handleDragStart}
          />
        );
      }
      cells.push(
        <div
          key={key}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => handleDropOnDay(e, new Date(nextCur))}
          className={`min-h-[110px] border border-navy/10 p-1 ${inMonth ? "bg-card" : "bg-background"} ${todayCell ? "ring-2 ring-gold" : ""}`}
          data-testid={`calendar-day-${key}`}
        >
          <p className={`text-[10px] font-mono mb-1 ${inMonth ? "text-navy" : "text-navy/30"}`}>
            {nextCur.getDate()}
          </p>
          <div className="space-y-1">{chips}</div>
          {dayEvents.length > 4 ? (
            <p className="text-[9px] text-muted-foreground mt-1">+{dayEvents.length - 4} more</p>
          ) : null}
        </div>
      );
      curDay = addDays(curDay, 1);
    }

    return (
      <div className="grid grid-cols-7 gap-0 border-t border-l border-navy/10 rounded-sm overflow-hidden">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
          <div key={d} className="text-[10px] text-navy uppercase tracking-wider font-semibold bg-navy/5 px-2 py-1 border-r border-b border-navy/10">{d}</div>
        ))}
        {cells}
      </div>
    );
  };

  const renderWeek = () => {
    const ws = startOfWeek(cursor);
    const days = [];
    for (let i = 0; i < 7; i += 1) {
      const d = addDays(ws, i);
      const key = ymd(d);
      const dayEvents = eventsByDay[key] || [];
      const chips = [];
      for (let j = 0; j < dayEvents.length; j += 1) {
        chips.push(<EventChip key={dayEvents[j].id} event={dayEvents[j]} onClick={setSelected} onDragStart={handleDragStart} />);
      }
      days.push(
        <div
          key={key}
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => handleDropOnDay(e, d)}
          className="flex-1 min-w-[140px] border border-navy/10 p-2 bg-card"
          data-testid={`calendar-week-day-${key}`}
        >
          <p className="text-xs font-semibold text-navy mb-2">
            {d.toLocaleDateString(undefined, { weekday: "short", day: "numeric" })}
          </p>
          <div className="space-y-1">{chips.length === 0 ? <p className="text-[10px] text-muted-foreground italic">No posts</p> : chips}</div>
        </div>
      );
    }
    return <div className="flex flex-wrap gap-1">{days}</div>;
  };

  const renderDay = () => {
    const key = ymd(cursor);
    const dayEvents = eventsByDay[key] || [];
    if (dayEvents.length === 0) {
      return <p className="text-sm text-muted-foreground py-8 text-center">No scheduled posts for {cursor.toDateString()}.</p>;
    }
    const rows = [];
    for (let i = 0; i < dayEvents.length; i += 1) {
      const ev = dayEvents[i];
      const time = ev.scheduled_at ? ev.scheduled_at.slice(11, 16) : "";
      rows.push(
        <div
          key={ev.id}
          onClick={() => setSelected(ev)}
          className={`p-3 rounded-sm border-l-4 cursor-pointer ${STATUS_COLOR[ev.status] || STATUS_COLOR.draft} bg-card text-navy`}
          data-testid={`calendar-day-row-${ev.id}`}
          style={{ borderLeftStyle: "solid" }}
        >
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs">{time}</span>
            <span className="text-[10px] uppercase tracking-wider font-semibold">{ev.status}</span>
          </div>
          <p className="font-semibold text-sm mt-1 truncate">{ev.title}</p>
          <p className="text-[10px] text-muted-foreground">{ev.provider} · {ev.kind}</p>
        </div>
      );
    }
    return <div className="space-y-2">{rows}</div>;
  };

  const navigatePrev = () => {
    const n = new Date(cursor);
    if (view === "month") n.setMonth(n.getMonth() - 1);
    else if (view === "week") n.setDate(n.getDate() - 7);
    else n.setDate(n.getDate() - 1);
    setCursor(n);
  };
  const navigateNext = () => {
    const n = new Date(cursor);
    if (view === "month") n.setMonth(n.getMonth() + 1);
    else if (view === "week") n.setDate(n.getDate() + 7);
    else n.setDate(n.getDate() + 1);
    setCursor(n);
  };

  return (
    <Section
      title={view === "month" ? fmtMonth(cursor) : view === "week" ? `Week of ${startOfWeek(cursor).toDateString()}` : cursor.toDateString()}
      icon={CalendarIcon}
      testId="ai-content-calendar"
      action={
        <div className="flex items-center gap-1">
          <Button size="sm" variant="outline" onClick={navigatePrev} className="border-navy/20" data-testid="calendar-prev">
            <ChevronLeft className="w-3.5 h-3.5" />
          </Button>
          <Button size="sm" variant="outline" onClick={() => setCursor(new Date())} className="border-navy/20" data-testid="calendar-today">
            Today
          </Button>
          <Button size="sm" variant="outline" onClick={navigateNext} className="border-navy/20" data-testid="calendar-next">
            <ChevronRight className="w-3.5 h-3.5" />
          </Button>
          <div className="ml-2 flex items-center border border-navy/20 rounded-sm overflow-hidden">
            {["month", "week", "day"].map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setView(v)}
                className={`text-xs px-3 py-1.5 ${view === v ? "bg-gold text-navy font-semibold" : "bg-card text-navy/70"}`}
                data-testid={`calendar-view-${v}`}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      }
    >
      <div className="mb-3"><Legend /></div>
      <div className="flex flex-wrap gap-1.5 mb-3" data-testid="calendar-status-filters">
        {["all", "draft", "scheduled", "publishing", "published", "failed"].map((s) => {
          const count = s === "all" ? events.length : events.filter((e) => e.status === s).length;
          const on = statusFilter === s;
          return (
            <button key={s} type="button" onClick={() => setStatusFilter(s)}
              className={`px-2.5 py-1 text-[11px] font-semibold rounded-full border transition-colors ${on ? "bg-navy text-cream border-navy" : "bg-card text-navy border-navy/20 hover:border-gold"}`}
              data-testid={`calendar-filter-${s}`}>
              {s.charAt(0).toUpperCase() + s.slice(1)} <span className="ml-1 opacity-70">({count})</span>
            </button>
          );
        })}
      </div>
      {busy ? <p className="text-sm text-muted-foreground">Loading calendar…</p> : null}
      {view === "month" && renderMonth()}
      {view === "week" && renderWeek()}
      {view === "day" && renderDay()}
      {selected ? (
        <EventDetail
          event={selected}
          onClose={() => setSelected(null)}
          onCancelEvent={handleCancel}
          onReschedule={handleReschedule}
        />
      ) : null}
    </Section>
  );
};

export default ContentCalendar;
