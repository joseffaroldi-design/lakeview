# 🚀 SPRINT 14B.2: AI DESIGNER PROGRESS & CLARITY — IMPLEMENTATION PLAN

**Date**: 2026-06-22  
**Status**: READY FOR IMPLEMENTATION  
**Goal**: Eliminate abandonment during 60-90 second AI Designer generation

---

## CURRENT PROBLEM

Owner clicks "Generate" and sees:
```
[Spinner] 0 of 3 ready · elapsed 0s
Each design takes about 30–90 seconds. Hang tight.
[Progress bar: 5%]
```

**Issues**:
1. ❌ No indication of *what* step is running
2. ❌ No estimated time remaining
3. ❌ Cannot leave page (will lose work)
4. ❌ No visibility into recent jobs
5. ❌ Vague "30-90 seconds" range
6. ❌ "Hang tight" feels dismissive

**Result**: High abandonment rate. Owner thinks it froze.

---

## SOLUTION DESIGN

### 1. Real-Time Progress Tracker with Steps

**Backend Changes** (minimal):
Add `current_step` field to job document:
```python
# In _run_design_job():
await update(current_step="Preparing design")
await update(current_step="Creating variation A")
await update(current_step="Creating variation B")
await update(current_step="Creating variation C")
if auto_copy:
    await update(current_step="Generating marketing copy")
await update(current_step="Complete", status="completed")
```

**Frontend Display**:
```jsx
<div className="space-y-2">
  {/* Active Step */}
  <div className="flex items-center gap-3">
    <Loader2 className="w-5 h-5 animate-spin text-gold" />
    <div className="flex-1">
      <p className="text-sm font-semibold text-navy">
        {job.current_step || "Starting..."}
      </p>
      <p className="text-xs text-muted-foreground">
        {getEstimatedTimeRemaining(job)} remaining
      </p>
    </div>
  </div>

  {/* Step Checklist */}
  <div className="space-y-1 text-xs">
    <Step completed={true} label="Upload Complete" />
    <Step completed={true} label="Preparing Design" />
    <Step completed={completed >= 1} active={current_step.includes("A")} label="Creating Variation A" />
    <Step completed={completed >= 2} active={current_step.includes("B")} label="Creating Variation B" />
    <Step completed={completed >= 3} active={current_step.includes("C")} label="Creating Variation C" />
    {autoCopy && (
      <Step completed={job.copy_pack} active={current_step.includes("copy")} label="Generating Marketing Copy" />
    )}
    <Step completed={job.status === "completed"} label="Complete" />
  </div>
</div>
```

**Step Component**:
```jsx
const Step = ({ completed, active, label }) => (
  <div className={`flex items-center gap-2 ${active ? 'text-gold' : completed ? 'text-forest' : 'text-muted-foreground'}`}>
    {completed ? (
      <CheckCircle2 className="w-4 h-4" />
    ) : active ? (
      <Loader2 className="w-4 h-4 animate-spin" />
    ) : (
      <div className="w-4 h-4 rounded-full border-2 border-current" />
    )}
    <span>{label}</span>
  </div>
);
```

---

### 2. Estimated Time Remaining

**Logic**:
```javascript
const getEstimatedTimeRemaining = (job) => {
  const elapsed = Math.floor((Date.now() - startTime) / 1000);
  const completed = job.variations?.filter(v => v.status === "completed").length || 0;
  
  // Each variation takes ~25-30 seconds
  const remainingVariations = 3 - completed;
  const copyTime = job.auto_copy && !job.copy_pack ? 10 : 0;
  
  const estimated = (remainingVariations * 27) + copyTime;
  
  if (estimated < 10) return "Less than 10 seconds";
  if (estimated < 30) return "About 20 seconds";
  if (estimated < 60) return `About ${Math.round(estimated / 10) * 10} seconds`;
  return `About ${Math.round(estimated / 60)} minute`;
};
```

**Display**:
```jsx
<p className="text-xs text-muted-foreground">
  {getEstimatedTimeRemaining(job)} remaining
</p>
```

**Key**: Never show fake percentages. Always base on actual completed steps.

---

### 3. Background-Safe Generation

**Implementation**:

**A. Store active job in localStorage**:
```javascript
// When generation starts
localStorage.setItem('ai_designer_active_job', JSON.stringify({
  job_id,
  item_name,
  started_at: Date.now()
}));

// Clear when complete
localStorage.removeItem('ai_designer_active_job');
```

**B. Check on component mount**:
```javascript
useEffect(() => {
  const activeJob = localStorage.getItem('ai_designer_active_job');
  if (activeJob) {
    const { job_id, item_name, started_at } = JSON.parse(activeJob);
    const elapsed = Date.now() - started_at;
    
    if (elapsed < 10 * 60 * 1000) { // Less than 10 minutes
      // Show "You have a generation in progress" banner
      setResumeJob({ job_id, item_name });
    } else {
      // Too old, clear it
      localStorage.removeItem('ai_designer_active_job');
    }
  }
}, []);
```

**C. Resume Banner**:
```jsx
{resumeJob && (
  <div className="bg-gold/10 border-2 border-gold/30 rounded-lg p-4 mb-6">
    <div className="flex items-center justify-between">
      <div>
        <p className="font-semibold text-navy">
          Your "{resumeJob.item_name}" design is still generating
        </p>
        <p className="text-xs text-muted-foreground">
          Started {formatDistanceToNow(resumeJob.started_at)} ago
        </p>
      </div>
      <div className="flex gap-2">
        <Button onClick={() => loadJob(resumeJob.job_id)}>
          View Progress
        </Button>
        <Button variant="outline" onClick={() => setResumeJob(null)}>
          Dismiss
        </Button>
      </div>
    </div>
  </div>
)}
```

**D. Allow navigation during generation**:
- Owner can click Home, Customers, Analytics
- Polling continues in background (via localStorage flag)
- Check on Home screen load if generation complete → show notification

---

### 4. Recent Jobs Widget

**Location**: Above AI Designer form

**Design**:
```jsx
const RecentJobs = ({ getAuthHeader, onJobClick }) => {
  const [jobs, setJobs] = useState([]);
  
  useEffect(() => {
    loadRecentJobs();
  }, []);
  
  const loadRecentJobs = async () => {
    const res = await axios.get(`${API}/ai-designer/jobs/recent?limit=3`, {
      headers: getAuthHeader()
    });
    setJobs(res.data.jobs || []);
  };
  
  if (jobs.length === 0) return null;
  
  return (
    <div className="bg-cream border-2 border-navy/10 rounded-lg p-4 mb-6">
      <h3 className="text-sm font-semibold text-navy mb-3 flex items-center gap-2">
        <Folder className="w-4 h-4" />
        Recent Designs
      </h3>
      <div className="space-y-2">
        {jobs.map(job => (
          <button
            key={job.id}
            onClick={() => onJobClick(job.id)}
            className="w-full flex items-center justify-between p-2 hover:bg-white rounded border border-transparent hover:border-gold/30 transition-colors text-left"
          >
            <div className="flex items-center gap-3">
              {job.status === "completed" ? (
                <CheckCircle2 className="w-4 h-4 text-forest" />
              ) : job.status === "generating" ? (
                <Loader2 className="w-4 h-4 animate-spin text-gold" />
              ) : (
                <div className="w-4 h-4 rounded-full border-2 border-navy/20" />
              )}
              <div>
                <p className="text-sm font-medium text-navy">{job.item_name}</p>
                <p className="text-xs text-muted-foreground">
                  {job.status === "completed" ? "Complete" : job.status === "generating" ? "In progress..." : "Pending"}
                </p>
              </div>
            </div>
            <span className="text-xs text-muted-foreground">
              {formatDistance(new Date(job.created_at), new Date(), { addSuffix: true })}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
};
```

---

### 5. Improve Form Labels

**Before**:
```jsx
<label>Features</label>
<textarea />
```

**After**:
```jsx
<label className="text-sm font-semibold text-navy mb-1 block">
  Features
  <span className="text-xs font-normal text-muted-foreground ml-2">
    (Example: Fresh Gulf Shrimp, Andouille Sausage, Homemade Roux)
  </span>
</label>
<textarea 
  placeholder="Enter 3-5 key features or ingredients"
  className="..."
/>
```

**Price Field**:
```jsx
<label className="text-sm font-semibold text-navy mb-1 block">
  Price
</label>
<Input 
  type="text" 
  placeholder="12.99"
  helperText="Example: 12.99 (no $ symbol needed)"
/>
```

---

### 6. Theme Preview Cards

**Backend**: Add preview images
```python
# In /ai-designer/themes endpoint:
THEME_STYLES: Dict[str, Dict[str, Any]] = {
    "luxury": {
        "label": "Luxury Black & Gold",
        "description": "Upscale restaurant advertisement",
        "preview_url": "/static/theme-previews/luxury.jpg",
        "bg_color": (16, 16, 16),
        ...
    },
    "modern": {
        "label": "Modern Restaurant",
        "description": "Clean social media style",
        "preview_url": "/static/theme-previews/modern.jpg",
        ...
    },
    ...
}
```

**Frontend**: Card-based theme selector
```jsx
<div className="grid grid-cols-2 md:grid-cols-3 gap-3">
  {themes.map(theme => (
    <button
      key={theme.id}
      onClick={() => setSelectedTheme(theme.id)}
      className={`border-2 rounded-lg overflow-hidden transition-all ${
        selectedTheme === theme.id
          ? 'border-gold shadow-lg scale-105'
          : 'border-navy/20 hover:border-gold/50'
      }`}
    >
      {/* Preview Image */}
      <div className="aspect-video bg-cream relative">
        {theme.preview_url ? (
          <img 
            src={theme.preview_url} 
            alt={theme.label}
            className="w-full h-full object-cover"
          />
        ) : (
          <div 
            className="w-full h-full"
            style={{ backgroundColor: theme.preview_color }}
          />
        )}
        {selectedTheme === theme.id && (
          <div className="absolute top-2 right-2 bg-gold rounded-full p-1">
            <Check className="w-3 h-3 text-navy" />
          </div>
        )}
      </div>
      
      {/* Info */}
      <div className="p-3 text-left">
        <p className="text-sm font-semibold text-navy">{theme.label}</p>
        <p className="text-xs text-muted-foreground">{theme.description}</p>
      </div>
    </button>
  ))}
</div>
```

---

## IMPLEMENTATION CHECKLIST

### Backend Changes (30 minutes)

- [ ] Add `current_step` field to AI Designer job schema
- [ ] Update `_run_design_job()` to set `current_step` at each stage:
  - `await update(current_step="Preparing design")`
  - `await update(current_step="Creating variation A")`
  - `await update(current_step="Creating variation B")`
  - `await update(current_step="Creating variation C")`
  - `await update(current_step="Generating marketing copy")`  (if auto_copy)
  - `await update(current_step="Complete")`
- [ ] Add theme descriptions to `/ai-designer/themes` response
- [ ] *Optional*: Generate tiny preview images for each theme

**File**: `/app/backend/routers/ai_designer.py`

---

### Frontend Changes (2-3 hours)

**1. Enhanced Progress Tracker** (45 min)
- [ ] Create `<ProgressStep>` component (checkbox + label)
- [ ] Update `<Progress>` component to show step-by-step checklist
- [ ] Add `getEstimatedTimeRemaining()` function
- [ ] Display dynamic time estimate

**2. Background-Safe Generation** (45 min)
- [ ] Add localStorage persistence for active jobs
- [ ] Check localStorage on mount → show resume banner
- [ ] Add resume banner UI
- [ ] Allow navigation during generation (remove blocking)

**3. Recent Jobs Widget** (30 min)
- [ ] Create `<RecentJobs>` component
- [ ] Fetch `/ai-designer/jobs/recent?limit=3`
- [ ] Display job status (Complete / In Progress / Pending)
- [ ] Click to load job results

**4. Improved Form Labels** (15 min)
- [ ] Add example text to "Features" label
- [ ] Add helper text under price field
- [ ] Update placeholders

**5. Theme Preview Cards** (30 min)
- [ ] Convert theme selector from radio buttons to cards
- [ ] Add preview image/color block
- [ ] Add theme description
- [ ] Add selected state (border + checkmark)

**File**: `/app/frontend/src/pages/dashboard/aiads/AiDesigner.jsx`

---

## SUCCESS CRITERIA

### Before Sprint 14B.2
```
[Spinner] 0 of 3 ready · elapsed 0s
Each design takes about 30–90 seconds. Hang tight.
[Progress bar: 5%]
```

**Problems**:
- Owner doesn't know what's happening ❌
- "30-90 seconds" is too vague ❌
- Cannot leave page ❌
- No visibility into recent work ❌

---

### After Sprint 14B.2
```
✓ Upload Complete
✓ Preparing Design
⟳ Creating Variation A
  Creating Variation B
  Creating Variation C
  Generating Marketing Copy
  Complete

About 45 seconds remaining

[3 thumbnail previews showing as completed]

[Banner above form:]
Recent Designs
• Seafood Gumbo — Complete (2 min ago) [Click to view]
• Chicken Wings — Complete (1 hour ago)
• Shrimp Po-Boy — Generating... [View progress]
```

**Solutions**:
- Owner sees exact step ✅
- Realistic time estimate ✅
- Can navigate away ✅
- Can see and resume recent jobs ✅

---

## ESTIMATED IMPACT

### Time Saved
- **Before**: Owner stares at screen for 60-90s, unsure if working
- **After**: Owner sees progress, leaves to do other work, returns when notified

**Psychological Impact**: More important than time saved
- "Is it working?" → **YES, I can see it's on variation B**
- "Can I leave?" → **YES, I'll get notified**
- "Did I lose my work?" → **NO, I can resume from where I left off**

### Abandonment Rate
- **Current**: Estimated 30-40% (based on friction report)
- **Target**: < 10%
- **How**: Transparency + ability to multitask

---

## ANALYTICS TRACKING

Add events:
```javascript
// When generation starts
trackEvent("ai_designer_generation_started", {
  theme,
  auto_copy,
  source: "new_upload" | "library" | "template"
});

// When owner navigates away during generation
trackEvent("ai_designer_navigated_away", {
  elapsed_seconds,
  completed_variations
});

// When owner returns
trackEvent("ai_designer_resumed", {
  elapsed_seconds,
  from_page
});

// When generation completes
trackEvent("ai_designer_generation_completed", {
  total_seconds,
  abandoned_and_returned: boolean
});
```

**30-Day Review**:
- Abandonment rate before/after
- Resume rate (how many navigate away and come back)
- Average time to completion perception

---

## FUTURE ENHANCEMENTS (NOT NOW)

### Browser Notifications
If owner leaves tab, send browser notification when complete:
```javascript
if (Notification.permission === "granted") {
  new Notification("Your design is ready!", {
    body: `Your ${item_name} design has finished generating.`,
    icon: "/logo.png"
  });
}
```

**Complexity**: Medium  
**ROI**: Medium (nice-to-have)  
**Decision**: Wait for 30-day analytics. Only add if abandonment still > 15%.

### Email Notification
Send email when generation completes (for very long jobs):
```
Subject: Your Seafood Gumbo design is ready

Hi there,

Your AI Designer run for "Seafood Gumbo" has finished generating.
3 variations are ready to review.

[View Designs →]
```

**Complexity**: Low (already have email infrastructure)  
**ROI**: Low (jobs finish in < 2 minutes usually)  
**Decision**: Skip unless jobs take > 5 minutes regularly.

---

## RECOMMENDATION

**Priority Order**:
1. ✅ **Enhanced Progress Tracker** (45 min) — Biggest impact
2. ✅ **Estimated Time Remaining** (15 min) — Low effort, high value
3. ✅ **Background-Safe Generation** (45 min) — Eliminates "stuck at screen" problem
4. ✅ **Recent Jobs Widget** (30 min) — Helps owner see work isn't lost
5. ⚠️ **Improved Form Labels** (15 min) — Nice polish
6. ⚠️ **Theme Preview Cards** (30 min) — Nice polish but lower priority

**Total Implementation Time**: ~3 hours  
**ROI**: EXTREME HIGH (prevents abandonment)

**Ship Order**:
1. Ship items 1-4 first (core abandonment fixes)
2. Ship items 5-6 as polish (can be separate deploy)

---

**Status**: READY FOR IMPLEMENTATION  
**Files to Modify**:
- `/app/backend/routers/ai_designer.py` (+20 LOC)
- `/app/frontend/src/pages/dashboard/aiads/AiDesigner.jsx` (+150 LOC)

**Estimated Time Savings for Owner**: Psychological relief (can multitask)  
**Estimated Abandonment Reduction**: 30-40% → < 10% ✅
