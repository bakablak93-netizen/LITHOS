import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { SubtitleCue } from "../types";

interface SubtitlesProps {
  cues: SubtitleCue[];
  fps: number;
}

export const Subtitles: React.FC<SubtitlesProps> = ({ cues, fps }) => {
  const frame = useCurrentFrame();
  const currentSec = frame / fps;

  const active = cues.find((c) => currentSec >= c.start_sec && currentSec <= c.end_sec);
  if (!active) return null;

  const fade = interpolate(
    currentSec,
    [active.start_sec, active.start_sec + 0.12, active.end_sec - 0.12, active.end_sec],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div
      style={{
        position: "absolute",
        bottom: 44,
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
        opacity: fade,
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(15, 23, 42, 0.94)",
          color: "#F8FAFC",
          padding: "14px 28px",
          borderRadius: 14,
          fontSize: 30,
          fontWeight: 600,
          maxWidth: 1320,
          textAlign: "center",
          boxShadow: "0 12px 32px rgba(0, 0, 0, 0.55)",
          border: "1px solid rgba(56, 189, 248, 0.4)",
          fontFamily: "Inter, system-ui, sans-serif",
          lineHeight: 1.3,
        }}
      >
        {active.text}
      </div>
    </div>
  );
};
