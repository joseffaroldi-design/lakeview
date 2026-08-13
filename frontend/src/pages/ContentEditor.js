import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { ChevronDown, ChevronUp, Plus, Save, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

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
      await axios.put(
        `${API}/menu/${cat.id}`,
        {
          display_name: cat.display_name,
          subtitle: cat.subtitle,
          columns: cat.columns,
          items: cat.items,
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

                <div className="space-y-2">
                  {(cat.items || []).map((item, itemIdx) => (
                    <div
                      key={`${cat.id}-${itemIdx}`}
                      className="grid grid-cols-1 sm:grid-cols-12 gap-2 p-3 bg-background rounded-sm border border-navy/5"
                    >
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
                  ))}
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
    </div>
  );
};
