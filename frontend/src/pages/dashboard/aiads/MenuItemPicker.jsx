/**
 * Sprint 17A — MenuItemPicker
 *
 * Searchable, category-grouped dropdown of menu items. Reads the live
 * /api/menu (no new endpoint). When the owner picks an item we compute
 * the canonical `item_key` (mirrors backend services/menu_matcher.py).
 *
 * Props:
 *   getAuthHeader  – () => { Authorization: 'Bearer …' }
 *   value          – current selected item_key (string | "")
 *   onSelect(item) – called with `{ item_key, name, price, features, category }`
 *                    when the user picks a menu item.
 *   onClear()      – called when the owner clears the selection.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { Search, ChevronDown, X, BookOpen } from "lucide-react";
import { API } from "./shared";

// Mirror backend services/menu_matcher.py::_item_key
const slugify = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
const computeItemKey = (cat, name) => `${slugify(cat || "menu")}::${slugify(name)}`;

const flattenMenu = (categories) => {
  const out = [];
  for (const cat of categories || []) {
    const catLabel = cat.display_name || cat.name || cat.slug || "Menu";
    for (const it of cat.items || []) {
      if (!it || !it.name) continue;
      // Try features → fallback to description-derived list (comma split)
      let features = it.features || [];
      if ((!features || features.length === 0) && it.description) {
        features = String(it.description)
          .split(/[,;|·•]/)
          .map((s) => s.trim())
          .filter(Boolean)
          .slice(0, 4);
      }
      out.push({
        item_key: it.item_key || computeItemKey(catLabel, it.name),
        name: it.name,
        price: it.price || "",
        features,
        category: catLabel,
      });
    }
  }
  return out;
};

const MenuItemPicker = ({ getAuthHeader, value, onSelect, onClear }) => {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState(0);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);
  const wrapRef = useRef(null);

  // Load menu once per mount.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    axios.get(`${API}/menu`, { headers: getAuthHeader(), timeout: 15000 })
      .then((r) => { if (!cancelled) setItems(flattenMenu(r.data)); })
      .catch(() => { /* non-fatal */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [getAuthHeader]);

  // Close on click-outside.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  const selected = useMemo(
    () => items.find((it) => it.item_key === value) || null,
    [items, value]
  );

  // Search filter + grouping
  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = q
      ? items.filter((it) =>
          (it.name + " " + it.category + " " + (it.features || []).join(" "))
            .toLowerCase()
            .includes(q))
      : items;
    const byCat = new Map();
    for (const it of filtered) {
      if (!byCat.has(it.category)) byCat.set(it.category, []);
      byCat.get(it.category).push(it);
    }
    return Array.from(byCat.entries()); // [[cat, items[]], ...]
  }, [items, query]);

  // Flat list of items for keyboard nav
  const flat = useMemo(() => grouped.flatMap(([_, list]) => list), [grouped]);

  const pick = (it) => {
    onSelect(it);
    setOpen(false);
    setQuery("");
    setHighlight(0);
  };

  const onKeyDown = (e) => {
    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter") setOpen(true);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlight((h) => Math.min(flat.length - 1, h + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlight((h) => Math.max(0, h - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (flat[highlight]) pick(flat[highlight]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="relative" ref={wrapRef} data-testid="menu-item-picker">
      <label className="text-[11px] font-semibold uppercase tracking-wider text-navy/70 mb-1 flex items-center gap-1.5">
        <BookOpen className="w-3 h-3" />
        Pick a menu item (optional)
      </label>
      {selected ? (
        <div
          className="flex items-center justify-between rounded-md border border-gold/40 bg-gold/10 px-2.5 py-1.5"
          data-testid="menu-picker-selected"
        >
          <div className="min-w-0">
            <p className="text-sm font-semibold text-navy truncate">
              {selected.name}
              {selected.price ? (
                <span className="ml-2 text-gold font-semibold">{selected.price}</span>
              ) : null}
            </p>
            <p className="text-[11px] text-navy/60 truncate">{selected.category}</p>
          </div>
          <button
            type="button"
            onClick={() => { onClear?.(); setOpen(true); setTimeout(() => inputRef.current?.focus(), 0); }}
            className="text-navy/60 hover:text-navy"
            aria-label="Clear menu item"
            data-testid="menu-picker-clear"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <button
          type="button"
          className="w-full text-left flex items-center justify-between rounded-md border border-navy/20 bg-white px-2.5 py-1.5 text-sm hover:border-gold/50"
          onClick={() => { setOpen((v) => !v); setTimeout(() => inputRef.current?.focus(), 0); }}
          data-testid="menu-picker-trigger"
        >
          <span className="text-navy/60">
            {loading ? "Loading menu…" : "Search menu items…"}
          </span>
          <ChevronDown className="w-4 h-4 text-navy/40" />
        </button>
      )}

      {open ? (
        <div
          className="absolute z-30 mt-1 w-full rounded-md border border-navy/20 bg-white shadow-lg"
          data-testid="menu-picker-popover"
        >
          <div className="flex items-center gap-2 border-b border-navy/10 px-2.5 py-1.5">
            <Search className="w-3.5 h-3.5 text-navy/40" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setHighlight(0); }}
              onKeyDown={onKeyDown}
              placeholder="Type to filter…"
              className="w-full bg-transparent text-sm outline-none"
              data-testid="menu-picker-search-input"
            />
          </div>
          <div className="max-h-72 overflow-y-auto" data-testid="menu-picker-results">
            {grouped.length === 0 ? (
              <p className="px-3 py-4 text-xs text-navy/50">No matches.</p>
            ) : null}
            {grouped.map(([cat, list]) => (
              <div key={cat}>
                <p className="sticky top-0 px-2.5 py-1 text-[10px] uppercase tracking-wider font-semibold text-navy/60 bg-navy/5">
                  {cat}
                </p>
                {list.map((it) => {
                  const idx = flat.indexOf(it);
                  const active = idx === highlight;
                  return (
                    <button
                      key={it.item_key}
                      type="button"
                      onClick={() => pick(it)}
                      onMouseEnter={() => setHighlight(idx)}
                      className={`w-full text-left px-2.5 py-1.5 text-sm flex items-center justify-between ${
                        active ? "bg-gold/15 text-navy" : "text-navy/90 hover:bg-navy/5"
                      }`}
                      data-testid={`menu-picker-item-${it.item_key}`}
                    >
                      <span className="truncate">{it.name}</span>
                      {it.price ? (
                        <span className="text-[11px] text-gold font-semibold ml-2 shrink-0">
                          {it.price}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
};

export { computeItemKey };
export default MenuItemPicker;
