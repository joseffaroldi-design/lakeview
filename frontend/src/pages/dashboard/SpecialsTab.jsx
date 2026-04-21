import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Plus, Trash2, Edit2, Eye, EyeOff, Image as ImageIcon, Save, X, Upload,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const SpecialsTab = ({ getAuthHeader }) => {
  const [specials, setSpecials] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingSpecial, setEditingSpecial] = useState(null);
  const [formData, setFormData] = useState({ title: "", description: "", price: "", image_url: "" });
  const [uploading, setUploading] = useState(false);

  const fetchSpecials = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/specials`);
      setSpecials(res.data);
    } catch (err) {
      console.error("Error fetching specials:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchSpecials(); }, [fetchSpecials]);

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await axios.post(`${API}/upload-image`, fd, {
        headers: { "Content-Type": "multipart/form-data", ...getAuthHeader() },
      });
      setFormData((prev) => ({ ...prev, image_url: res.data.image_url }));
    } catch (err) {
      console.error("Error uploading image:", err);
      alert("Failed to upload image");
    } finally {
      setUploading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editingSpecial) {
        await axios.put(`${API}/specials/${editingSpecial.id}`, formData, { headers: getAuthHeader() });
      } else {
        await axios.post(`${API}/specials`, formData, { headers: getAuthHeader() });
      }
      setShowForm(false);
      setEditingSpecial(null);
      setFormData({ title: "", description: "", price: "", image_url: "" });
      fetchSpecials();
    } catch (err) {
      console.error("Error saving special:", err);
      alert("Failed to save special");
    }
  };

  const handleEdit = (special) => {
    setEditingSpecial(special);
    setFormData({
      title: special.title,
      description: special.description,
      price: special.price || "",
      image_url: special.image_url || "",
    });
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this special?")) return;
    try {
      await axios.delete(`${API}/specials/${id}`, { headers: getAuthHeader() });
      fetchSpecials();
    } catch (err) {
      console.error("Error deleting special:", err);
    }
  };

  const toggleActive = async (special) => {
    try {
      await axios.put(`${API}/specials/${special.id}`, { is_active: !special.is_active }, { headers: getAuthHeader() });
      fetchSpecials();
    } catch (err) {
      console.error("Error toggling special:", err);
    }
  };

  if (loading) {
    return <p className="text-muted-foreground">Loading specials…</p>;
  }

  return (
    <section>
      <div className="flex items-center justify-between mb-6">
        <h2 className="font-serif text-2xl text-navy font-bold flex items-center gap-2">
          <ImageIcon className="w-6 h-6 text-gold" />
          Manage Specials
        </h2>
        <Button
          data-testid="add-special-btn"
          onClick={() => {
            setEditingSpecial(null);
            setFormData({ title: "", description: "", price: "", image_url: "" });
            setShowForm(true);
          }}
          className="bg-forest text-cream hover:bg-forest/90"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Special
        </Button>
      </div>

      {showForm && (
        <Card className="mb-8 bg-card border-2 border-gold" data-testid="special-form">
          <CardHeader>
            <CardTitle className="font-serif text-navy">
              {editingSpecial ? "Edit Special" : "Add New Special"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block font-sans text-sm text-muted-foreground mb-1">Title *</label>
                <Input
                  data-testid="special-title-input"
                  value={formData.title}
                  onChange={(e) => setFormData((p) => ({ ...p, title: e.target.value }))}
                  placeholder="e.g., Friday Fish Fry"
                  required
                  className="border-navy/20"
                />
              </div>

              <div>
                <label className="block font-sans text-sm text-muted-foreground mb-1">Description *</label>
                <textarea
                  data-testid="special-description-input"
                  value={formData.description}
                  onChange={(e) => setFormData((p) => ({ ...p, description: e.target.value }))}
                  placeholder="Describe the special..."
                  required
                  className="w-full px-3 py-2 border border-navy/20 rounded-sm focus:outline-none focus:ring-2 focus:ring-gold"
                  rows={3}
                />
              </div>

              <div>
                <label className="block font-sans text-sm text-muted-foreground mb-1">Price (optional)</label>
                <Input
                  data-testid="special-price-input"
                  value={formData.price}
                  onChange={(e) => setFormData((p) => ({ ...p, price: e.target.value }))}
                  placeholder="e.g., $14.99"
                  className="border-navy/20"
                />
              </div>

              <div>
                <label className="block font-sans text-sm text-muted-foreground mb-1">Image</label>
                <div className="flex gap-4 items-start">
                  <div className="flex-1">
                    <label className="flex items-center justify-center w-full h-32 border-2 border-dashed border-navy/20 rounded-sm cursor-pointer hover:border-gold transition-colors">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleImageUpload}
                        className="hidden"
                        data-testid="special-image-upload"
                      />
                      <div className="text-center">
                        {uploading ? (
                          <span className="text-muted-foreground">Uploading...</span>
                        ) : (
                          <>
                            <Upload className="w-8 h-8 mx-auto text-muted-foreground mb-2" />
                            <span className="text-sm text-muted-foreground">Click to upload image</span>
                          </>
                        )}
                      </div>
                    </label>
                  </div>
                  {formData.image_url && (
                    <div className="w-32 h-32 border border-navy/20 rounded-sm overflow-hidden">
                      <img src={formData.image_url} alt="Preview" className="w-full h-full object-cover" />
                    </div>
                  )}
                </div>
              </div>

              <div className="flex gap-3 pt-4">
                <Button type="submit" data-testid="save-special-btn" className="bg-gold text-navy hover:bg-gold/90">
                  <Save className="w-4 h-4 mr-2" />
                  {editingSpecial ? "Update Special" : "Save Special"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  data-testid="cancel-special-btn"
                  onClick={() => {
                    setShowForm(false);
                    setEditingSpecial(null);
                  }}
                  className="border-navy/20"
                >
                  <X className="w-4 h-4 mr-2" />
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {specials.length === 0 ? (
        <Card className="bg-card border-2 border-navy/10">
          <CardContent className="py-12 text-center">
            <ImageIcon className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
            <p className="font-sans text-muted-foreground">No specials yet. Add your first special!</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {specials.map((special) => (
            <Card
              key={special.id}
              className={`bg-card border-2 ${special.is_active ? "border-forest/30" : "border-navy/10 opacity-60"}`}
              data-testid={`special-card-${special.id}`}
            >
              {special.image_url && (
                <div className="h-48 overflow-hidden">
                  <img src={special.image_url} alt={special.title} className="w-full h-full object-cover" />
                </div>
              )}
              <CardHeader>
                <div className="flex items-start justify-between">
                  <CardTitle className="font-serif text-navy text-lg">{special.title}</CardTitle>
                  {special.price && <span className="font-sans font-bold text-forest">{special.price}</span>}
                </div>
              </CardHeader>
              <CardContent>
                <p className="font-sans text-sm text-muted-foreground mb-4">{special.description}</p>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => toggleActive(special)}
                    className="border-navy/20"
                    data-testid={`toggle-special-${special.id}`}
                  >
                    {special.is_active ? (
                      <><EyeOff className="w-4 h-4 mr-1" /> Hide</>
                    ) : (
                      <><Eye className="w-4 h-4 mr-1" /> Show</>
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleEdit(special)}
                    className="border-navy/20"
                    data-testid={`edit-special-${special.id}`}
                  >
                    <Edit2 className="w-4 h-4" />
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleDelete(special.id)}
                    className="border-destructive text-destructive hover:bg-destructive hover:text-white"
                    data-testid={`delete-special-${special.id}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </section>
  );
};

export default SpecialsTab;
