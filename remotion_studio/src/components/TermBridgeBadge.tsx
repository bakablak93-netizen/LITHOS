import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { TermBridge } from "../types";

interface TermBridgeBadgeProps {
  bridge: TermBridge;
  delayFrames?: number;
}

export const TermBridgeBadge: React.FC<TermBridgeBadgeProps> = ({ bridge, delayFrames = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame: Math.max(0, frame - delayFrames),
    fps,
    config: { damping: 16, stiffness: 120 },
  });

  return (
    <div
      style={{
        opacity: progress,
        transform: `translateY(${(1 - progress) * 14}px)`,
        backgroundColor: "rgba(15, 23, 42, 0.92)",
        border: "1px solid rgba(56, 189, 248, 0.45)",
        borderRadius: 12,
        padding: "12px 16px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 14,
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      <div>
        <div style={{ fontSize: 12, color: "#F59E0B", fontWeight: 700, letterSpacing: 0.8 }}>
          ШКОЛА СНГ
        </div>
        <div style={{ fontSize: 20, color: "#F8FAFC", fontWeight: 700 }}>
          {bridge.ru_symbol}
        </div>
        <div style={{ fontSize: 14, color: "#CBD5E1" }}>{bridge.ru_term}</div>
      </div>

      <div style={{ fontSize: 22, color: "#38BDF8", fontWeight: 700 }}>↔</div>

      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 12, color: "#38BDF8", fontWeight: 700, letterSpacing: 0.8 }}>
          WESTERN EQUIVALENT
        </div>
        <div style={{ fontSize: 20, color: "#38BDF8", fontWeight: 700 }}>
          {bridge.en_symbol}
        </div>
        <div style={{ fontSize: 14, color: "#CBD5E1" }}>
          {bridge.en_term} {bridge.unit ? `(${bridge.unit})` : ""}
        </div>
      </div>
    </div>
  );
};
