import React from "react";
import { OffthreadVideo } from "remotion";
import { SceneSpec } from "../types";
import { FormulaCard } from "./FormulaCard";
import { TermBridgeBadge } from "./TermBridgeBadge";

interface SplitScreenProps {
  scene: SceneSpec;
  bookTitle: string;
  moduleType: string;
  baseAssetUrl?: string;
  physicsData?: Record<string, any>;
}

const DeterministicPhysicsPreview: React.FC<{
  moduleType: string;
  physicsData?: Record<string, any>;
  scene: SceneSpec;
}> = ({ moduleType, physicsData, scene }) => {
  // Детерминированный SVG-график из physics_engine на случай, если Manim MP4 не приложен к сцене
  if (moduleType === "latyshova_gis" && physicsData?.logs) {
    const depths: number[] = physicsData.logs.depth_m || [];
    const bk: number[] = physicsData.logs.rho_bk_ohmm || [];
    const sp: number[] = physicsData.logs.alpha_sp || [];
    const pointsBk = depths
      .map((d, i) => {
        const x = 140 + Math.min(260, Math.log10(Math.max(bk[i] || 1, 0.5)) * 115);
        const y = 40 + ((d - 2400) / 50) * 520;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
    const pointsSp = depths
      .map((d, i) => {
        const x = 40 + (sp[i] || 0) * 85;
        const y = 40 + ((d - 2400) / 50) * 520;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");

    return (
      <svg viewBox="0 0 460 600" style={{ width: "100%", height: "100%" }}>
        <rect width="460" height="600" rx="16" fill="#0F172A" stroke="#1E293B" />
        <text x="24" y="28" fill="#38BDF8" fontSize="15" fontWeight="bold">
          α_СП (слева) и ρ_БК Ом·м (справа)
        </text>
        <line x1="80" y1="40" x2="80" y2="560" stroke="#F43F5E" strokeDasharray="5 5" />
        <line x1="24" y1="300" x2="436" y2="300" stroke="#EF4444" strokeDasharray="6 4" />
        <text x="310" y="292" fill="#EF4444" fontSize="13">
          ВНК (OWC)
        </text>
        <polyline fill="none" stroke="#38BDF8" strokeWidth="3" points={pointsSp} />
        <polyline fill="none" stroke="#10B981" strokeWidth="3" points={pointsBk} />
      </svg>
    );
  }

  if (moduleType === "basniev_hydro" && physicsData?.dupuit?.radial_profile) {
    const r: number[] = physicsData.dupuit.radial_profile.r_m || [];
    const p: number[] = physicsData.dupuit.radial_profile.p_mpa || [];
    const maxR = Math.max(...r, 250);
    const minP = Math.min(...p, 10);
    const maxP = Math.max(...p, 25);
    const pts = r
      .map((rv, i) => {
        const x = 50 + (rv / maxR) * 440;
        const y = 500 - ((p[i] - minP) / Math.max(maxP - minP, 1)) * 410;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");

    return (
      <svg viewBox="0 0 540 560" style={{ width: "100%", height: "100%" }}>
        <rect width="540" height="560" rx="16" fill="#0F172A" stroke="#1E293B" />
        <text x="30" y="34" fill="#38BDF8" fontSize="16" fontWeight="bold">
          Воронка депрессии p(r) — формула Дюпюи
        </text>
        <line x1="50" y1="500" x2="500" y2="500" stroke="#475569" strokeWidth="2" />
        <line x1="50" y1="60" x2="50" y2="500" stroke="#475569" strokeWidth="2" />
        <polyline fill="none" stroke="#F59E0B" strokeWidth="4" points={pts} />
        <text x="380" y="530" fill="#94A3B8" fontSize="14">
          Радиус r, м
        </text>
      </svg>
    );
  }

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        borderRadius: 16,
        backgroundColor: "#0F172A",
        border: "1px solid #1E293B",
        padding: 36,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        gap: 18,
      }}
    >
      <div style={{ fontSize: 16, color: "#38BDF8", fontWeight: 700, textTransform: "uppercase" }}>
        {scene.methodology_only_nomogram
          ? "МЕТОДИКА СЧИТЫВАНИЯ ПАЛЕТКИ (БЕЗ ВЫДУМАННЫХ ЧИСЕЛ)"
          : "ДЕТЕРМИНИРОВАННЫЙ СЛАЙД КУРСА"}
      </div>
      <div style={{ fontSize: 34, color: "#F8FAFC", fontWeight: 700, lineHeight: 1.25 }}>
        {scene.title}
      </div>
      <div style={{ fontSize: 20, color: "#CBD5E1", lineHeight: 1.5 }}>{scene.narration}</div>
    </div>
  );
};

export const SplitScreen: React.FC<SplitScreenProps> = ({
  scene,
  bookTitle,
  moduleType,
  baseAssetUrl,
  physicsData,
}) => {
  const videoSrc =
    scene.manim_video_path && baseAssetUrl
      ? `${baseAssetUrl}${scene.manim_video_path}`
      : scene.manim_video_path || null;

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: "#0B101B",
        backgroundImage:
          "linear-gradient(to right, rgba(30,41,59,0.35) 1px, transparent 1px), linear-gradient(to bottom, rgba(30,41,59,0.35) 1px, transparent 1px)",
        backgroundSize: "48px 48px",
        padding: "38px 46px 120px 46px",
        display: "flex",
        flexDirection: "column",
        gap: 22,
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      {/* Верхняя шапка */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 14, color: "#38BDF8", fontWeight: 700, letterSpacing: 1 }}>
            LITHOS · ГЛАВА → КУРС · {bookTitle}
          </div>
          <div style={{ fontSize: 30, color: "#F8FAFC", fontWeight: 700, marginTop: 4 }}>
            {scene.order}. {scene.title}
          </div>
        </div>
        {scene.methodology_only_nomogram && (
          <div
            style={{
              backgroundColor: "rgba(245, 158, 11, 0.16)",
              border: "1px solid #F59E0B",
              color: "#FCD34D",
              padding: "8px 14px",
              borderRadius: 10,
              fontSize: 14,
              fontWeight: 700,
            }}
          >
            Domain QA: Только методика (палетка не оцифрована)
          </div>
        )}
      </div>

      {/* Основной Split-Screen */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: "1.35fr 0.95fr", gap: 26, minHeight: 0 }}>
        {/* Левая панель: Manim MP4 или детерминированная графика */}
        <div
          style={{
            borderRadius: 18,
            overflow: "hidden",
            border: "1px solid #1E293B",
            backgroundColor: "#0F172A",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {videoSrc ? (
            <OffthreadVideo
              src={videoSrc}
              style={{ width: "100%", height: "100%", objectFit: "contain" }}
            />
          ) : (
            <DeterministicPhysicsPreview
              moduleType={moduleType}
              physicsData={physicsData}
              scene={scene}
            />
          )}
        </div>

        {/* Правая панель: формулы + терминологические мосты + выводы */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, overflow: "hidden" }}>
          {scene.formulas.map((f, idx) => (
            <FormulaCard key={idx} formula={f} />
          ))}

          {scene.term_bridges.map((b, idx) => (
            <TermBridgeBadge key={idx} bridge={b} delayFrames={idx * 8} />
          ))}

          {scene.key_takeaways.length > 0 && (
            <div
              style={{
                backgroundColor: "#111827",
                border: "1px solid #1E293B",
                borderRadius: 14,
                padding: "14px 18px",
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div style={{ fontSize: 13, color: "#10B981", fontWeight: 700, letterSpacing: 0.8 }}>
                КЛЮЧЕВЫЕ ВЫВОДЫ
              </div>
              {scene.key_takeaways.map((item, idx) => (
                <div key={idx} style={{ fontSize: 16, color: "#E2E8F0", lineHeight: 1.35 }}>
                  • {item}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
