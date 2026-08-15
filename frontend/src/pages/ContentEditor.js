import React, { useCallback, useEffect, useMemo, useState } from "react";
import axios from "axios";
import { ChevronDown, ChevronUp, GripVertical, ImagePlus, Plus, Save, Star, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { AssetPicker } from "@/components/dashboard/AssetPicker";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const Field = ({ label, children }) => (
  <div>
    <label className="block font-sans text-sm text-muted-foreground mb-1">{label}</label>
    {children}
  </div>
);

export const ContentEditor = ({ getAuthHeader, onSaved }) => {
  const [content, setContent] = useState(null);
  const [saving, setSaving] = useState(null);
  const [saved, setSaved] = useState(null);

  useEffect(() => {
    axios.get(`${API}/content`).then((res) => setContent(res.data)).catch(console.error);
  }, []);

  const updateField = (section, field, value) => {
    setContent((prev) => ({
      ...prev,
      [section]: { ...prev?.[section], [field]: value },
    }));
  };

  const saveSection = async (section) => {
    setSaving(section);
    setSaved(null);
    try {
      const res = await axios.put(`${API}/content/${section}`, content[section], {
        headers: getAuthHeader(),
      });
      setContent(res.data);
      setSaved(section);
      onSaved?.();
      window.setTimeout(() => setSaved(null), 1800);
    } catch (err) {
      console.error(err);
      alert("Could not save this section.");
    } finally {
      setSaving(null);
    }
  };

  if (!content) {
    return <p className="text-muted-foreground">Loading website content...</p>;
  }

  const sectionButton = (section, label) => (
    <Button
      onClick={() => saveSection(section)}
      disabled={saving === section}
      className="bg-gold text-navy hover:bg-gold/90"
      data-testid={`save-${section}-btn`}
    >
      <Save className="w-4 h-4 mr-2" />
      {saving === section ? "Saving..." : saved === section ? "Saved" : label}
    </Button>
  );

  return (
    <div className="space-y-5" data-testid="content-editor">
      <Card className="bg-card border border-navy/10">
        <CardHeader>
          <CardTitle className="font-serif text-navy">Homepage headline</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label="Tagline">
            <Input
              value={content.hero?.tagline || ""}
              onChange={(e) => updateField("hero", "tagline", e.target.value)}
              className="border-navy/20"
            />
          </Field>
          <Field label="Subtitle">
            <textarea
              value={content.hero?.subtitle || ""}
              onChange={(e) => updateField("hero", "subtitle", e.target.value)}
              rows={3}
              className="w-full px-3 py-2 border border-navy/20 rounded-sm focus:outline-none focus:ring-2 focus:ring-gold font-sans text-sm"
            />
          </Field>
          {sectionButton("hero", "Save homepage")}
        </CardContent>
      </Card>

      <Card className="bg-card border border-navy/10">
        <CardHeader>
          <CardTitle className="font-serif text-navy">Our story</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Accent text">
              <Input
                value={content.about?.accent_text || ""}
                onChange={(e) => updateField("about", "accent_text", e.target.value)}
                className="border-navy/20"
              />
            </Field>
            <Field label="Heading">
              <Input
                value={content.about?.heading || ""}
                onChange={(e) => updateField("about", "heading", e.target.value)}
                className="border-navy/20"
              />
            </Field>
          </div>
          {["paragraph1", "paragraph2", "paragraph3"].map((field, index) => (
            <Field key={field} label={`Paragraph ${index + 1}`}>
              <textarea
                value={content.about?.[field] || ""}
                onChange={(e) => updateField("about", field, e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-navy/20 rounded-sm focus:outline-none focus:ring-2 focus:ring-gold font-sans text-sm"
              />
            </Field>
          ))}
          {sectionButton("about", "Save story")}
        </CardContent>
      </Card>

      <Card className="bg-card border border-navy/10">
        <CardHeader>
          <CardTitle className="font-serif text-navy">Contact & hours</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Address">
              <Input
                value={content.contact?.address_line1 || ""}
                onChange={(e) => updateField("contact", "address_line1", e.target.value)}
                className="border-navy/20"
              />
            </Field>
            <Field label="City / State / ZIP">
              <Input
                value={content.contact?.address_line2 || ""}
                onChange={(e) => updateField("contact", "address_line2", e.target.value)}
                className="border-navy/20"
              />
            </Field>
            <Field label="Monday–Saturday hours">
              <Input
                value={content.contact?.hours_weekday || ""}
                onChange={(e) => updateField("contact", "hours_weekday", e.target.value)}
                className="border-navy/20"
              />
            </Field>
            <Field label="Sunday hours">
              <Input
                value={content.contact?.hours_weekend || ""}
                onChange={(e) => updateField("contact", "hours_weekend", e.target.value)}
                className="border-navy/20"
              />
            </Field>
            <Field label="Phone">
              <Input
                value={content.contact?.phone || ""}
                onChange={(e) => updateField("contact", "phone", e.target.value)}
                className="border-navy/20"
              />
            </Field>
            <Field label="Email">
              <Input
                value={content.contact?.email || ""}
                onChange={(e) => updateField("contact", "email", e.target.value)}
                className="border-navy/20"
              />
            </Field>
          </div>
          {sectionButton("contact", "Save contact info")}
        </CardContent>
      </Card>
    </div>
  );
};

export const MenuEditor = ({ getAuthHeader, onSaved }) => {
  const [categories, setCategories] = useState([]);
  const [expandedCat, setExpandedCat] = useState(null);
  const [saving, setSaving] = useState(null);

  const fetchMenu = useCallback(() => {
    axios.get(`${API}/menu`).then((res) => setCategories(res.data)).catch(console.error);
  }, []);

  useEffect(() => {
    fetchMenu();
  }, [fetchMenu]);

  const updateCategory = (catIdx, field, value) => {
    setCategories((prev) =>
      prev.map((cat, index) => (index === catIdx ? { ...cat, [field]: value } : cat)),
    );
  };

  const updateItem = (catIdx, itemIdx, field, value) => {
    setCategories((prev) =>
      prev.map((cat, index) => {
        if (index !== catIdx) return cat;
        const items = [...(cat.items || [])];
        items[itemIdx] = { ...items[itemIdx], [field]: value };
        return { ...cat, items };
      }),
    );
  };

  const addItem = (catIdx) => {
    setCategories((prev) =>
      prev.map((cat, index) =>
        index === catIdx
          ? { ...cat, items: [...(cat.items || []), { name: "", description: "", price: "" }] }
          : cat,
      ),
    );
  };

  const removeItem = (catIdx, itemIdx) => {
    setCategories((prev) =>
      prev.map((cat, index) =>
        index === catIdx
          ? { ...cat, items: (cat.items || []).filter((_, itemIndex) => itemIndex !== itemIdx) }
          : cat,
      ),
    );
  };

  const saveCategory = async (cat) => {
    setSaving(cat.id);
    try {
      // Ensure photos are persisted as string[] (asset_id list) — the
      // backend accepts arbitrary shape on menu items so any missing field
      // stays missing.
      const items = (cat.items || []).map((it) => ({
        ...it,
        photos: Array.isArray(it.photos) ? it.photos.filter(Boolean) : [],
      }));
      await axios.put(
        `${API}/menu/${cat.id}`,
        {
          display_name: cat.display_name,
          subtitle: cat.subtitle,
          columns: cat.columns,
          items,
        },
        { headers: getAuthHeader() },
      );
      onSaved?.();
    } catch (err) {
      console.error(err);
      alert("Could not save this menu category.");
    } finally {
      setSaving(null);
    }
  };

  // --- Menu-item photo gallery helpers ---
  const setItemPhotos = (catIdx, itemIdx, updater) => {
    setCategories((prev) =>
      prev.map((cat, index) => {
        if (index !== catIdx) return cat;
        const items = [...(cat.items || [])];
        const current = Array.isArray(items[itemIdx]?.photos) ? items[itemIdx].photos : [];
        const next = typeof updater === "function" ? updater(current) : updater;
        items[itemIdx] = { ...items[itemIdx], photos: next };
        return { ...cat, items };
      }),
    );
  };

  const addPhotos = (catIdx, itemIdx, newIds) => {
    setItemPhotos(catIdx, itemIdx, (prev) => {
      const dedup = [...prev];
      for (const id of newIds) if (!dedup.includes(id)) dedup.push(id);
      return dedup;
    });
  };

  const removePhoto = (catIdx, itemIdx, photoId) =>
    setItemPhotos(catIdx, itemIdx, (prev) => prev.filter((p) => p !== photoId));

  const setPrimary = (catIdx, itemIdx, photoId) =>
    setItemPhotos(catIdx, itemIdx, (prev) => [photoId, ...prev.filter((p) => p !== photoId)]);

  const movePhoto = (catIdx, itemIdx, photoId, direction) =>
    setItemPhotos(catIdx, itemIdx, (prev) => {
      const idx = prev.indexOf(photoId);
      if (idx < 0) return prev;
      const target = direction === "left" ? idx - 1 : idx + 1;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[target]] = [next[target], next[idx]];
      return next;
    });

  // Track which item currently has the photo picker open (as "catIdx:itemIdx").
  const [pickerFor, setPickerFor] = useState(null);
  const openPicker = (catIdx, itemIdx) => setPickerFor(`${catIdx}:${itemIdx}`);
  const closePicker = () => setPickerFor(null);
  const pickerTarget = pickerFor
    ? pickerFor.split(":").map((n) => Number(n))
    : null;
  const currentPickerPhotos = useMemo(() => {
    if (!pickerTarget) return [];
    const [ci, ii] = pickerTarget;
    return categories?.[ci]?.items?.[ii]?.photos || [];
  }, [pickerTarget, categories]);

  const handlePickerAssign = async (ids) => {
    if (!pickerTarget) return;
    const [ci, ii] = pickerTarget;
    addPhotos(ci, ii, ids);
  };

  return (
    <div className="space-y-4" data-testid="menu-editor">
      {categories.map((cat, catIdx) => {
        const expanded = expandedCat === cat.id;
        return (
          <Card key={cat.id} className="bg-card border border-navy/10" data-testid={`menu-cat-${cat.slug}`}>
            <CardHeader
              className="cursor-pointer select-none"
              onClick={() => setExpandedCat(expanded ? null : cat.id)}
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <CardTitle className="font-serif text-navy">{cat.display_name}</CardTitle>
                  <p className="text-xs text-muted-foreground mt-1">{cat.items?.length || 0} items</p>
                </div>
                {expanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
              </div>
            </CardHeader>

            {expanded && (
              <CardContent className="space-y-5 border-t border-navy/10 pt-5">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <Field label="Category name">
                    <Input
                      value={cat.display_name || ""}
                      onChange={(e) => updateCategory(catIdx, "display_name", e.target.value)}
                      className="border-navy/20"
                    />
                  </Field>
                  <Field label="Subtitle">
                    <Input
                      value={cat.subtitle || ""}
                      onChange={(e) => updateCategory(catIdx, "subtitle", e.target.value || null)}
                      className="border-navy/20"
                    />
                  </Field>
                  <Field label="Columns">
                    <Input
                      type="number"
                      min={2}
                      max={4}
                      value={cat.columns || 2}
                      onChange={(e) => updateCategory(catIdx, "columns", Number(e.target.value) || 2)}
                      className="border-navy/20"
                    />
                  </Field>
                </div>

                <div className="space-y-3">
                  {(cat.items || []).map((item, itemIdx) => {
                    const photos = Array.isArray(item.photos) ? item.photos : [];
                    return (
                    <div
                      key={`${cat.id}-${itemIdx}`}
                      className="p-3 bg-background rounded-sm border border-navy/5 space-y-3"
                      data-testid={`menu-item-${cat.slug}-${itemIdx}`}
                    >
                      <div className="grid grid-cols-1 sm:grid-cols-12 gap-2">
                        <Input
                          value={item.name || ""}
                          onChange={(e) => updateItem(catIdx, itemIdx, "name", e.target.value)}
                          placeholder="Item name"
                          className="border-navy/20 sm:col-span-4"
                        />
                        <Input
                          value={item.description || ""}
                          onChange={(e) => updateItem(catIdx, itemIdx, "description", e.target.value)}
                          placeholder="Description"
                          className="border-navy/20 sm:col-span-5"
                        />
                        <Input
                          value={item.price || ""}
                          onChange={(e) => updateItem(catIdx, itemIdx, "price", e.target.value)}
                          placeholder="Price"
                          className="border-navy/20 sm:col-span-2"
                        />
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => removeItem(catIdx, itemIdx)}
                          className="text-destructive hover:text-destructive sm:col-span-1"
                          aria-label={`Remove ${item.name || "menu item"}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>

                      <div className="flex items-start gap-3 flex-wrap pt-1 border-t border-navy/8">
                        <div className="pt-3 min-w-0">
                          <p className="text-[10px] uppercase tracking-wider font-semibold text-navy/55 mb-2">
                            Photos {photos.length > 0 ? `· ${photos.length}` : ""}
                          </p>
                          <div className="flex items-center gap-2 flex-wrap">
                            {photos.map((photoId, pIdx) => (
                              <div
                                key={photoId}
                                className={`relative group w-20 h-20 rounded-lg overflow-hidden border-2 ${pIdx === 0 ? "border-gold" : "border-navy/10"}`}
                                data-testid={`menu-item-photo-${cat.slug}-${itemIdx}-${pIdx}`}
                              >
                                <img
                                  src={`${API}/media/file/${photoId}`}
                                  alt=""
                                  loading="lazy"
                                  className="w-full h-full object-cover"
                                  onError={(e) => { e.currentTarget.style.opacity = "0.25"; }}
                                />
                                {pIdx === 0 ? (
                                  <span className="absolute top-1 left-1 text-[9px] font-bold uppercase bg-gold text-navy px-1.5 py-0.5 rounded-full flex items-center gap-0.5">
                                    <Star className="w-2.5 h-2.5" fill="currentColor" />
                                    Primary
                                  </span>
                                ) : null}
                                <div className="absolute inset-0 bg-navy/0 group-hover:bg-navy/60 transition-colors flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100">
                                  {pIdx !== 0 ? (
                                    <button
                                      type="button"
                                      title="Make primary"
                                      onClick={() => setPrimary(catIdx, itemIdx, photoId)}
                                      className="w-6 h-6 rounded-full bg-gold text-navy flex items-center justify-center"
                                    >
                                      <Star className="w-3 h-3" fill="currentColor" />
                                    </button>
                                  ) : null}
                                  <button
                                    type="button"
                                    title="Move left"
                                    onClick={() => movePhoto(catIdx, itemIdx, photoId, "left")}
                                    disabled={pIdx === 0}
                                    className="w-6 h-6 rounded-full bg-cream text-navy flex items-center justify-center disabled:opacity-30"
                                  >
                                    <GripVertical className="w-3 h-3 rotate-90" />
                                  </button>
                                  <button
                                    type="button"
                                    title="Move right"
                                    onClick={() => movePhoto(catIdx, itemIdx, photoId, "right")}
                                    disabled={pIdx === photos.length - 1}
                                    className="w-6 h-6 rounded-full bg-cream text-navy flex items-center justify-center disabled:opacity-30"
                                  >
                                    <GripVertical className="w-3 h-3 -rotate-90" />
                                  </button>
                                  <button
                                    type="button"
                                    title="Remove photo"
                                    onClick={() => removePhoto(catIdx, itemIdx, photoId)}
                                    className="w-6 h-6 rounded-full bg-red-600 text-white flex items-center justify-center"
                                    data-testid={`menu-item-photo-remove-${cat.slug}-${itemIdx}-${pIdx}`}
                                  >
                                    <X className="w-3 h-3" />
                                  </button>
                                </div>
                              </div>
                            ))}
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => openPicker(catIdx, itemIdx)}
                              className="h-20 w-20 flex-col gap-1 border-dashed border-navy/25 text-navy/60 hover:text-navy hover:border-navy/50"
                              data-testid={`menu-item-add-photos-${cat.slug}-${itemIdx}`}
                            >
                              <ImagePlus className="w-4 h-4" />
                              <span className="text-[10px] uppercase tracking-wider">Add Photos</span>
                            </Button>
                          </div>
                          {photos.length > 5 ? (
                            <p className="text-[11px] text-navy/50 mt-2">
                              {photos.length} photos on this item · tip: 1–5 is usually plenty.
                            </p>
                          ) : (
                            <p className="text-[11px] text-navy/40 mt-2">
                              First photo is the primary thumbnail used on the public menu.
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                    );
                  })}
                </div>

                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => addItem(catIdx)} className="border-navy/20">
                    <Plus className="w-4 h-4 mr-1" /> Add item
                  </Button>
                  <Button
                    onClick={() => saveCategory(cat)}
                    disabled={saving === cat.id}
                    className="bg-gold text-navy hover:bg-gold/90"
                  >
                    <Save className="w-4 h-4 mr-2" />
                    {saving === cat.id ? "Saving..." : "Save category"}
                  </Button>
                </div>
              </CardContent>
            )}
          </Card>
        );
      })}

      <AssetPicker
        open={Boolean(pickerFor)}
        onClose={closePicker}
        getAuthHeader={getAuthHeader}
        title="Add photos to menu item"
        subtitle="Pick one or more photos from your Library, or upload new ones. First photo becomes the primary."
        mode="multiple"
        disabledIds={currentPickerPhotos}
        onAssign={handlePickerAssign}
      />
    </div>
  );
};
