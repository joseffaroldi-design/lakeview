import React, { useState, useEffect, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Save, Plus, Trash2, ChevronDown, ChevronUp, FileText, UtensilsCrossed, GripVertical } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Site Content Editor
export const ContentEditor = ({ getAuthHeader, onSaved }) => {
  const [content, setContent] = useState(null);
  const [saving, setSaving] = useState(null);
  const [saved, setSaved] = useState(null);

  useEffect(() => {
    axios.get(`${API}/content`).then(res => setContent(res.data)).catch(console.error);
  }, []);

  const saveSection = async (section) => {
    setSaving(section);
    setSaved(null);
    try {
      const res = await axios.put(`${API}/content/${section}`, content[section], { headers: getAuthHeader() });
      setContent(res.data);
      setSaved(section);
      if (onSaved) onSaved();
      setTimeout(() => setSaved(null), 2000);
    } catch (err) {
      console.error(err);
      alert("Failed to save");
    } finally {
      setSaving(null);
    }
  };

  const updateField = (section, field, value) => {
    setContent(prev => ({ ...prev, [section]: { ...prev[section], [field]: value } }));
  };

  if (!content) return <p className="text-muted-foreground">Loading content...</p>;

  return (
    <div className="space-y-8" data-testid="content-editor">
      {/* Hero */}
      <Card className="bg-card border-2 border-navy/10">
        <CardHeader>
          <CardTitle className="font-serif text-navy flex items-center gap-2">
            <FileText className="w-5 h-5 text-gold" /> Hero Section
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block font-sans text-sm text-muted-foreground mb-1">Tagline</label>
            <Input data-testid="edit-hero-tagline" value={content.hero?.tagline || ""} onChange={e => updateField("hero", "tagline", e.target.value)} className="border-navy/20" />
          </div>
          <div>
            <label className="block font-sans text-sm text-muted-foreground mb-1">Subtitle</label>
            <textarea data-testid="edit-hero-subtitle" value={content.hero?.subtitle || ""} onChange={e => updateField("hero", "subtitle", e.target.value)} rows={2} className="w-full px-3 py-2 border border-navy/20 rounded-sm focus:outline-none focus:ring-2 focus:ring-gold font-sans text-sm" />
          </div>
          <Button data-testid="save-hero-btn" onClick={() => saveSection("hero")} disabled={saving === "hero"} className="bg-gold text-navy hover:bg-gold/90">
            <Save className="w-4 h-4 mr-2" /> {saving === "hero" ? "Saving..." : saved === "hero" ? "Saved!" : "Save Hero"}
          </Button>
        </CardContent>
      </Card>

      {/* About */}
      <Card className="bg-card border-2 border-navy/10">
        <CardHeader>
          <CardTitle className="font-serif text-navy flex items-center gap-2">
            <FileText className="w-5 h-5 text-gold" /> About / Our Story
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">Accent Text</label>
              <Input data-testid="edit-about-accent" value={content.about?.accent_text || ""} onChange={e => updateField("about", "accent_text", e.target.value)} className="border-navy/20" />
            </div>
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">Heading</label>
              <Input data-testid="edit-about-heading" value={content.about?.heading || ""} onChange={e => updateField("about", "heading", e.target.value)} className="border-navy/20" />
            </div>
          </div>
          <div>
            <label className="block font-sans text-sm text-muted-foreground mb-1">Paragraph 1</label>
            <textarea data-testid="edit-about-p1" value={content.about?.paragraph1 || ""} onChange={e => updateField("about", "paragraph1", e.target.value)} rows={3} className="w-full px-3 py-2 border border-navy/20 rounded-sm focus:outline-none focus:ring-2 focus:ring-gold font-sans text-sm" />
          </div>
          <div>
            <label className="block font-sans text-sm text-muted-foreground mb-1">Paragraph 2</label>
            <textarea data-testid="edit-about-p2" value={content.about?.paragraph2 || ""} onChange={e => updateField("about", "paragraph2", e.target.value)} rows={3} className="w-full px-3 py-2 border border-navy/20 rounded-sm focus:outline-none focus:ring-2 focus:ring-gold font-sans text-sm" />
          </div>
          <div>
            <label className="block font-sans text-sm text-muted-foreground mb-1">Paragraph 3</label>
            <textarea data-testid="edit-about-p3" value={content.about?.paragraph3 || ""} onChange={e => updateField("about", "paragraph3", e.target.value)} rows={3} className="w-full px-3 py-2 border border-navy/20 rounded-sm focus:outline-none focus:ring-2 focus:ring-gold font-sans text-sm" />
          </div>
          <div>
            <label className="block font-sans text-sm text-muted-foreground mb-1">Established Text</label>
            <Input data-testid="edit-about-est" value={content.about?.established_text || ""} onChange={e => updateField("about", "established_text", e.target.value)} className="border-navy/20" />
          </div>
          <Button data-testid="save-about-btn" onClick={() => saveSection("about")} disabled={saving === "about"} className="bg-gold text-navy hover:bg-gold/90">
            <Save className="w-4 h-4 mr-2" /> {saving === "about" ? "Saving..." : saved === "about" ? "Saved!" : "Save About"}
          </Button>
        </CardContent>
      </Card>

      {/* Contact */}
      <Card className="bg-card border-2 border-navy/10">
        <CardHeader>
          <CardTitle className="font-serif text-navy flex items-center gap-2">
            <FileText className="w-5 h-5 text-gold" /> Contact Info
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">Address Line 1</label>
              <Input data-testid="edit-contact-addr1" value={content.contact?.address_line1 || ""} onChange={e => updateField("contact", "address_line1", e.target.value)} className="border-navy/20" />
            </div>
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">Address Line 2</label>
              <Input data-testid="edit-contact-addr2" value={content.contact?.address_line2 || ""} onChange={e => updateField("contact", "address_line2", e.target.value)} className="border-navy/20" />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">Hours (Weekday)</label>
              <Input data-testid="edit-contact-hours-wd" value={content.contact?.hours_weekday || ""} onChange={e => updateField("contact", "hours_weekday", e.target.value)} className="border-navy/20" />
            </div>
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">Hours (Weekend)</label>
              <Input data-testid="edit-contact-hours-we" value={content.contact?.hours_weekend || ""} onChange={e => updateField("contact", "hours_weekend", e.target.value)} className="border-navy/20" />
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">Phone</label>
              <Input data-testid="edit-contact-phone" value={content.contact?.phone || ""} onChange={e => updateField("contact", "phone", e.target.value)} className="border-navy/20" />
            </div>
            <div>
              <label className="block font-sans text-sm text-muted-foreground mb-1">Email</label>
              <Input data-testid="edit-contact-email" value={content.contact?.email || ""} onChange={e => updateField("contact", "email", e.target.value)} className="border-navy/20" />
            </div>
          </div>
          <div>
            <label className="block font-sans text-sm text-muted-foreground mb-1">Catering Text</label>
            <Input data-testid="edit-contact-catering" value={content.contact?.catering_text || ""} onChange={e => updateField("contact", "catering_text", e.target.value)} className="border-navy/20" />
          </div>
          <Button data-testid="save-contact-btn" onClick={() => saveSection("contact")} disabled={saving === "contact"} className="bg-gold text-navy hover:bg-gold/90">
            <Save className="w-4 h-4 mr-2" /> {saving === "contact" ? "Saving..." : saved === "contact" ? "Saved!" : "Save Contact"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

// Menu Editor
export const MenuEditor = ({ getAuthHeader, onSaved }) => {
  const [categories, setCategories] = useState([]);
  const [expandedCat, setExpandedCat] = useState(null);
  const [saving, setSaving] = useState(null);

  const fetchMenu = useCallback(() => {
    axios.get(`${API}/menu`).then(res => setCategories(res.data)).catch(console.error);
  }, []);

  useEffect(() => { fetchMenu(); }, [fetchMenu]);

  const saveCategory = async (cat) => {
    setSaving(cat.id);
    try {
      await axios.put(`${API}/menu/${cat.id}`, { display_name: cat.display_name, subtitle: cat.subtitle, columns: cat.columns, items: cat.items }, { headers: getAuthHeader() });
      if (onSaved) onSaved();
      setTimeout(() => setSaving(null), 1500);
    } catch (err) {
      console.error(err);
      alert("Failed to save");
      setSaving(null);
    }
  };

  const updateCategoryField = (catIdx, field, value) => {
    setCategories(prev => prev.map((c, i) => i === catIdx ? { ...c, [field]: value } : c));
  };

  const updateItem = (catIdx, itemIdx, field, value) => {
    setCategories(prev => prev.map((c, i) => {
      if (i !== catIdx) return c;
      const items = [...c.items];
      items[itemIdx] = { ...items[itemIdx], [field]: value };
      return { ...c, items };
    }));
  };

  const addItem = (catIdx) => {
    setCategories(prev => prev.map((c, i) => i === catIdx ? { ...c, items: [...c.items, { name: "", description: "", price: "" }] } : c));
  };

  const removeItem = (catIdx, itemIdx) => {
    setCategories(prev => prev.map((c, i) => {
      if (i !== catIdx) return c;
      return { ...c, items: c.items.filter((_, j) => j !== itemIdx) };
    }));
  };

  return (
    <div className="space-y-4" data-testid="menu-editor">
      {categories.map((cat, catIdx) => (
        <Card key={cat.id} className="bg-card border-2 border-navy/10" data-testid={`menu-cat-${cat.slug}`}>
          <CardHeader
            className="cursor-pointer select-none"
            onClick={() => setExpandedCat(expandedCat === cat.id ? null : cat.id)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="font-serif text-navy flex items-center gap-2">
                <UtensilsCrossed className="w-5 h-5 text-gold" />
                {cat.display_name}
                <span className="text-sm font-sans font-normal text-muted-foreground">({cat.items?.length || 0} items)</span>
              </CardTitle>
              {expandedCat === cat.id ? <ChevronUp className="w-5 h-5 text-muted-foreground" /> : <ChevronDown className="w-5 h-5 text-muted-foreground" />}
            </div>
          </CardHeader>

          {expandedCat === cat.id && (
            <CardContent className="space-y-4 border-t border-navy/10 pt-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div>
                  <label className="block font-sans text-xs text-muted-foreground mb-1">Category Name</label>
                  <Input value={cat.display_name} onChange={e => updateCategoryField(catIdx, "display_name", e.target.value)} className="border-navy/20" data-testid={`menu-cat-name-${cat.slug}`} />
                </div>
                <div>
                  <label className="block font-sans text-xs text-muted-foreground mb-1">Subtitle (optional)</label>
                  <Input value={cat.subtitle || ""} onChange={e => updateCategoryField(catIdx, "subtitle", e.target.value || null)} className="border-navy/20" />
                </div>
                <div>
                  <label className="block font-sans text-xs text-muted-foreground mb-1">Columns (2-4)</label>
                  <Input type="number" min={2} max={4} value={cat.columns} onChange={e => updateCategoryField(catIdx, "columns", parseInt(e.target.value) || 2)} className="border-navy/20" />
                </div>
              </div>

              <div className="space-y-2">
                <label className="block font-sans text-sm font-semibold text-navy">Menu Items</label>
                {(cat.items || []).map((item, itemIdx) => (
                  <div key={itemIdx} className="flex items-start gap-2 p-3 bg-background rounded-sm border border-navy/5" data-testid={`menu-item-${cat.slug}-${itemIdx}`}>
                    <GripVertical className="w-4 h-4 text-muted-foreground mt-2.5 flex-shrink-0" />
                    <div className="flex-1 grid grid-cols-1 sm:grid-cols-12 gap-2">
                      <Input
                        value={item.name}
                        onChange={e => updateItem(catIdx, itemIdx, "name", e.target.value)}
                        placeholder="Item name"
                        className="border-navy/20 sm:col-span-4 text-sm"
                      />
                      <Input
                        value={item.description || ""}
                        onChange={e => updateItem(catIdx, itemIdx, "description", e.target.value)}
                        placeholder="Description"
                        className="border-navy/20 sm:col-span-5 text-sm"
                      />
                      <Input
                        value={item.price}
                        onChange={e => updateItem(catIdx, itemIdx, "price", e.target.value)}
                        placeholder="Price"
                        className="border-navy/20 sm:col-span-2 text-sm"
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeItem(catIdx, itemIdx)}
                        className="text-destructive hover:text-destructive sm:col-span-1 h-9"
                        data-testid={`remove-item-${cat.slug}-${itemIdx}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
                <Button variant="outline" size="sm" onClick={() => addItem(catIdx)} className="border-navy/20" data-testid={`add-item-${cat.slug}`}>
                  <Plus className="w-4 h-4 mr-1" /> Add Item
                </Button>
              </div>

              <Button data-testid={`save-cat-${cat.slug}`} onClick={() => saveCategory(cat)} disabled={saving === cat.id} className="bg-gold text-navy hover:bg-gold/90">
                <Save className="w-4 h-4 mr-2" /> {saving === cat.id ? "Saved!" : "Save Category"}
              </Button>
            </CardContent>
          )}
        </Card>
      ))}
    </div>
  );
};
