/**
 * Video Studio — script + storyboard + production notes (Phase 2 concepts).
 * Actual video rendering wired later by implementing providers.generate_video().
 */
import React from "react";
import { Video } from "lucide-react";
import { Section, CopyableItem } from "./shared";
import { BriefForm, useSpecialtyRunner, OutputPanel, SaveBtn } from "./BriefForm";

const renderList = (items, prefix) => {
  const out = [];
  for (let i = 0; i < (items || []).length; i += 1) {
    out.push(<CopyableItem key={i} text={items[i]} testId={`${prefix}-${i}`} />);
  }
  return out;
};

const SceneItem = ({ scene, idx }) => {
  const sname = scene.scene || `Scene ${idx + 1}`;
  const dur = scene.duration_seconds;
  const visual = scene.visual || "";
  const audio = scene.audio || "";
  return (
    <CopyableItem
      text={`${sname} (${dur}s)\nVisual: ${visual}\nAudio: ${audio}`}
      testId={`ai-video-scene-${idx}`}
    />
  );
};

const renderScenes = (scenes) => {
  const out = [];
  for (let i = 0; i < (scenes || []).length; i += 1) {
    out.push(<SceneItem key={i} scene={scenes[i]} idx={i} />);
  }
  return out;
};

const Result = ({ output, savedJustNow, onSave }) => {
  if (!output) return null;
  return (
    <Section
      title={`${output.duration_seconds || ""}-second Video`}
      icon={Video}
      testId="ai-video-result"
      action={<SaveBtn savedJustNow={savedJustNow} onSave={onSave} testId="ai-video-save" />}
    >
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Script (Voiceover)</p>
      <CopyableItem text={output.script || ""} testId="ai-video-script" />
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">VO Direction</p>
      <CopyableItem text={output.voiceover || ""} testId="ai-video-vo" />
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Shot List</p>
      {renderList(output.shot_list, "ai-video-shot")}
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Scene List</p>
      {renderScenes(output.scene_list)}
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Storyboard</p>
      {renderList(output.storyboard, "ai-video-board")}
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">On-Screen Text</p>
      {renderList(output.on_screen_text, "ai-video-ost")}
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Production Notes</p>
      <CopyableItem text={output.production_notes || ""} testId="ai-video-notes" />
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1">Generation Prompt (Sora / Runway / Veo / Kling)</p>
      <CopyableItem text={output.generation_prompt || ""} testId="ai-video-genprompt" />
      <p className="text-xs text-muted-foreground italic mt-2">
        Video rendering is a future step. Connect a provider in ai_engine/providers.py to enable in-app generation.
      </p>
    </Section>
  );
};

export const VideoStudio = ({ catalog, getAuthHeader, onSavedCount }) => {
  const { output, busy, error, savedJustNow, run, saveAsAsset, lastBrief } = useSpecialtyRunner("video_concept", getAuthHeader, onSavedCount);

  const onSave = () => {
    const title = `Video · ${(lastBrief && lastBrief.duration_seconds) || ""}s · ${(lastBrief && lastBrief.name) || "Untitled"}`;
    saveAsAsset("video_concept", title, output, null);
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1">
        <BriefForm
          catalog={catalog}
          onSubmit={run}
          busy={busy}
          submitLabel="Generate Video Brief"
          testIdPrefix="ai-video"
          briefIcon={Video}
          showPlatform={false}
          showDuration
        />
      </div>
      <div className="lg:col-span-2">
        {error && <p data-testid="ai-video-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-sm p-3 mb-3">{error}</p>}
        <OutputPanel
          busy={busy}
          EmptyIcon={Video}
          emptyTitle="Generate video concepts"
          emptyBody="Choose duration. You'll get script, voiceover, shot list, scene breakdown, storyboard, on-screen text and production notes."
        >
          {output ? <Result output={output} savedJustNow={savedJustNow} onSave={onSave} /> : null}
        </OutputPanel>
      </div>
    </div>
  );
};

export default VideoStudio;
