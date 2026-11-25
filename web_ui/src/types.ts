export interface ChapterInfo {
  index: number;
  title: string;
  start_line: number;
  end_line: number;
  char_count: number;
  has_nomograms: boolean;
  formula_count: number;
}

export interface BookInfo {
  book_file: string;
  passport_file: string | null;
  title: string;
  authors: string[];
  year: number | null;
  domain: string;
  school: string;
  is_control: boolean;
  recommended_module: "latyshova_gis" | "basniev_hydro" | "generic_chapter";
  chapters: ChapterInfo[];
}

export interface TermBridge {
  ru_symbol: string;
  ru_term: string;
  en_symbol: string;
  en_term: string;
  unit: string;
  note: string;
}

export interface FormulaSpec {
  latex: string;
  title: string;
  western_latex: string;
  variables: Record<string, string>;
  source_ref: string;
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
  manim_scene_class: string;
  manim_video_path: string | null;
  audio_path: string | null;
  subtitles: SubtitleCue[];
  formulas: FormulaSpec[];
  term_bridges: TermBridge[];
  lab_preset: Record<string, unknown>;
  key_takeaways: string[];
  methodology_only_nomogram: boolean;
}

export interface QACheck {
  check_id: string;
  category: string;
  status: "PASS" | "WARN" | "FIXED" | "FAIL";
  message: string;
  affected_scenes: string[];
}

export interface QAReport {
  passed: boolean;
  checks: QACheck[];
  warnings: string[];
  auto_fixes: string[];
  passport_warnings_applied: Record<string, string>;
}

export interface CourseManifest {
  course_id: string;
  module_type: "latyshova_gis" | "basniev_hydro" | "generic_chapter";
  book_file: string;
  passport_file: string | null;
  book_title: string;
  authors: string[];
  chapter_title: string;
  chapter_number: string;
  methodological_school: string;
  units_system: string;
  total_duration_sec: number;
  fps: number;
  resolution: string;
  voice: string;
  final_video_url: string | null;
  srt_url: string | null;
  scenes: SceneSpec[];
  physics_data: Record<string, any>;
  qa_report: QAReport;
}

export interface CourseJobStatus {
  job_id: string;
  course_id: string;
  status: "queued" | "running" | "completed" | "failed";
  stage: string;
  progress_pct: number;
  logs: string[];
  manifest_url: string | null;
  video_url: string | null;
  error: string | null;
}
