export interface TermBridge {
  ru_symbol: string;
  ru_term: string;
  en_symbol: string;
  en_term: string;
  unit?: string;
  note?: string;
}

export interface FormulaSpec {
  latex: string;
  title: string;
  western_latex?: string;
  variables?: Record<string, string>;
  source_ref?: string;
}

export interface SubtitleCue {
  index: number;
  start_sec: number;
  end_sec: number;
  text: string;
}

export interface SceneSpec {
  scene_id: string;
  order: number;
  title: string;
  narration: string;
  duration_sec: number;
  fps: number;
  visual_backend: "manim" | "threejs_lab" | "remotion_split" | "remotion_formula";
  manim_scene_class?: string;
  manim_video_path?: string | null;
  audio_path?: string | null;
  subtitles: SubtitleCue[];
  formulas: FormulaSpec[];
  term_bridges: TermBridge[];
  key_takeaways: string[];
  methodology_only_nomogram?: boolean;
}

export interface CourseManifestProps {
  course_id: string;
  module_type: "latyshova_gis" | "basniev_hydro" | "generic_chapter";
  book_title: string;
  chapter_title: string;
  total_duration_sec: number;
  fps: number;
  baseAssetUrl?: string;
  scenes: SceneSpec[];
  physics_data?: Record<string, any>;
}
