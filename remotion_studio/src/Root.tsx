import React from "react";
import { Composition } from "remotion";
import { CourseVideo } from "./CourseVideo";
import { CourseManifestProps } from "./types";

const defaultProps: CourseManifestProps = {
  course_id: "demo_preview",
  module_type: "latyshova_gis",
  book_title: "Латышова М.Г. — Практическое руководство по интерпретации диаграмм ГИС (1991)",
  chapter_title: "Глава I & V — Уравнение Арчи и выделение коллекторов",
  total_duration_sec: 14,
  fps: 30,
  baseAssetUrl: "http://127.0.0.1:8000",
  scenes: [
    {
      scene_id: "preview_1",
      order: 1,
      title: "Уравнение Арчи–Дахнова и выделение коллекторов",
      narration: "Удельное сопротивление водоносной породы пропорционально сопротивлению поровой воды.",
      duration_sec: 14,
      fps: 30,
      visual_backend: "remotion_split",
      subtitles: [
        {
          index: 1,
          start_sec: 0.2,
          end_sec: 5.0,
          text: "Удельное сопротивление породы пропорционально ρ_в.",
        },
        {
          index: 2,
          start_sec: 5.2,
          end_sec: 11.0,
          text: "Терминологический мост: P_п (СНГ) ↔ F (West).",
        },
      ],
      formulas: [
        {
          latex: "P_п = a_m / K_п^m,   P_н = ρ_п / ρ_вп = a_n / K_в^n",
          western_latex: "F = a / φ^m,   I = R_t / R_0 = b / S_w^n",
          title: "Уравнения пористости и насыщения",
          variables: {
            "K_п": "Коэффициент пористости, д.е.",
            "P_п": "Параметр пористости",
            "P_н": "Параметр насыщения",
          },
          source_ref: "Латышова (1991), Глава I, ф. (2)-(3)",
        },
      ],
      term_bridges: [
        {
          ru_symbol: "K_п",
          ru_term: "Коэффициент пористости",
          en_symbol: "φ",
          en_term: "Porosity",
          unit: "%",
        },
        {
          ru_symbol: "ρ_п",
          ru_term: "Сопротивление пласта",
          en_symbol: "R_t",
          en_term: "True formation resistivity",
          unit: "Ом·м",
        },
      ],
      key_takeaways: [
        "100% детерминированная графика на базе physics_engine",
        "Автоматический терминологический мост СНГ ↔ Запад",
      ],
    },
  ],
};

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="CourseVideo"
      component={CourseVideo}
      durationInFrames={420}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={defaultProps}
      calculateMetadata={({ props }) => {
        const fps = props.fps || 30;
        const totalSec = props.scenes.reduce((acc, s) => acc + Math.max(2, s.duration_sec || 10), 0);
        return {
          durationInFrames: Math.max(60, Math.round(totalSec * fps)),
          fps,
        };
      }}
    />
  );
};
