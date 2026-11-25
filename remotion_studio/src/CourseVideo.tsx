import React from "react";
import { AbsoluteFill, Audio, Series, useVideoConfig } from "remotion";
import { CourseManifestProps } from "./types";
import { SplitScreen } from "./components/SplitScreen";
import { Subtitles } from "./components/Subtitles";

export const CourseVideo: React.FC<CourseManifestProps> = ({
  book_title,
  module_type,
  baseAssetUrl,
  scenes,
  physics_data,
}) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: "#0B1120" }}>
      <Series>
        {scenes.map((scene) => {
          const frames = Math.max(60, Math.round((scene.duration_sec || 10) * fps));
          const audioSrc =
            scene.audio_path && baseAssetUrl
              ? `${baseAssetUrl}${scene.audio_path}`
              : scene.audio_path || null;

          return (
            <Series.Sequence key={scene.scene_id} durationInFrames={frames}>
              <AbsoluteFill>
                {audioSrc && <Audio src={audioSrc} />}
                <SplitScreen
                  scene={scene}
                  bookTitle={book_title}
                  moduleType={module_type}
                  baseAssetUrl={baseAssetUrl}
                  physicsData={physics_data}
                />
                <Subtitles cues={scene.subtitles || []} fps={fps} />
              </AbsoluteFill>
            </Series.Sequence>
          );
        })}
      </Series>
    </AbsoluteFill>
  );
};
