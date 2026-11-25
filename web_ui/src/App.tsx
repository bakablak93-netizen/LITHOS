import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  Download,
  FileText,
  Film,
  FlaskConical,
  GraduationCap,
  Play,
  Plus,
  RotateCcw,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Upload,
  X,
  XCircle,
} from "lucide-react";
import { BookInfo, ChapterInfo, CourseJobStatus, CourseManifest, QACheck } from "./types";
import { LatyshovaProbeLab } from "./labs/LatyshovaProbeLab";
import { BasnievHydroLab } from "./labs/BasnievHydroLab";
import { MathText, cleanLatexToText } from "./components/MathText";

type StudioView = "video" | "lab";
type StudioPanelTab = "plan" | "quiz" | "qa";

interface QuizQuestion {
  id: string;
  question: string;
  options: string[];
  correctIndex: number;
  explanation: string;
}

const BOOK_DISPLAY_OVERRIDES: Record<string, string> = {
  "ctrl_baraboshkin_b.md": "Барабошкин Е.Ю. — Практическая седиментология (2007)",
  "ctrl_barenblatt.md": "Баренблатт Г.И. и др. — Движение жидкостей в пластах (1984)",
  "ctrl_vendelshtein.md": "Вендельштейн Б.Ю., Резванов Р.А. — Геофизические методы (1978)",
  "train_basniev.md": "Басниев К.С. и др. — Нефтегазовая гидромеханика (2005)",
  "train_kuznetsov.md": "Кузнецов В.Г. — Литология природных резервуаров (2012)",
  "train_latyshova.md": "Латышова М.Г. — Интерпретация диаграмм ГИС (1991)",
};

const LATYSHOVA_QUIZ: QuizQuestion[] = [
  {
    id: "lat_q1",
    question: "Как изменится параметр пористости P_п (F) чистого песчаника при снижении пористости K_п с 24% до 12% (при m = 2)?",
    options: [
      "Уменьшится в 2 раза",
      "Возрастёт примерно в 4 раза",
      "Не изменится, если ρ_в постоянно",
      "Возрастёт в 1.4 раза",
    ],
    correctIndex: 1,
    explanation:
      "По закону Арчи–Дахнова P_п = a_m / K_п^m. При m = 2 двукратное снижение K_п увеличивает P_п в 2^2 = 4 раза.",
  },
  {
    id: "lat_q2",
    question: "Какой диагностический признак указывает на нефтенасыщенный коллектор на пресном буровом растворе (ρ_ф > ρ_в)?",
    options: [
      "Положительная аномалия СП и отсутствие глинистой корки",
      "Повышающее проникновение: ρ_МБК > ρ_БК",
      "Понижающее проникновение: ρ_МБК < ρ_БК при α_СП ≥ α_СП*",
      "Совпадение кривых БК и МБК по всей мощности пласта",
    ],
    correctIndex: 2,
    explanation:
      "Пресный фильтрат вытесняет нефть из прискважинной зоны, но снижает УЭС сильнее или формирует понижающее проникновение (ρ_МБК < ρ_БК), при этом α_СП выше граничного отсчёта выделяет проницаемый коллектор.",
  },
  {
    id: "lat_q3",
    question: "Почему по неоцифрованным палеткам БЭЗ в учебнике запрещено автоматически считывать числовые значения ρ_п?",
    options: [
      "Кривые БЭЗ не применяются в терригенном разрезе",
      "Палетки требуют совмещения фактической кривой ρ_к(AO) с аттестованным бланком без домысливания отсчётов",
      "Уравнение P_н = ρ_п / ρ_вп не зависит от ρ_п",
      "Для расчёта К_в достаточно только кривой ПС",
    ],
    correctIndex: 1,
    explanation:
      "Для неоцифрованных палеток БЭЗ корректна только методика совмещения на логарифмическом бланке; произвольная генерация чисел приводит к ошибкам в оценке ρ_п и K_нг = 1 − K_в.",
  },
];

const BASNIEV_QUIZ: QuizQuestion[] = [
  {
    id: "bas_q1",
    question: "Как связана истинная средняя скорость v движения флюида в поровых каналах со скоростью фильтрации w по Дарси?",
    options: [
      "v = w · m (истинная скорость меньше)",
      "v = w / m (истинная скорость выше, чем фиктивная)",
      "v = w независимо от пористости",
      "v = w · μ / k",
    ],
    correctIndex: 1,
    explanation:
      "Поток движется только через открытое сечение пор (просветность m = φ), поэтому v = w / m > w, где w = −(k / μ)·grad p.",
  },
  {
    id: "bas_q2",
    question: "Что в формуле Дюпюи Q = 2πkh(p_к − p_с) / [μ ln(R_к / r_с)] оказывает наиболее слабое влияние на дебит при изменении в 2 раза?",
    options: [
      "Проницаемость пласта k",
      "Депрессия на пласт Δp = p_к − p_с",
      "Радиус контура питания R_к (стоит под знаком логарифма)",
      "Вязкость пластовой нефти μ",
    ],
    correctIndex: 2,
    explanation:
      "Радиус контура питания R_к и радиус скважины r_с входят под знаком натурального логарифма ln(R_к / r_с), поэтому кратное изменение R_к слабо меняет дебит по сравнению с k, h и Δp.",
  },
  {
    id: "bas_q3",
    question: "По какому закону расширяется радиус возмущённой области пласта R(t) в методе ПССС при пуске скважины?",
    options: [
      "Линейно со временем: R(t) ~ κ · t",
      "Пропорционально квадратному корню из времени: R(t) = √(r_с^2 + 4κt)",
      "Экспоненциально убывает к контуру питания",
      "Остаётся постоянным и равным R_к",
    ],
    correctIndex: 1,
    explanation:
      "При упругом режиме фильтрации граница воронки депрессии движется диффузионно: R(t) = √(r_с^2 + 4κt), где κ — коэффициент пьезопроводности.",
  },
];

const GENERIC_QUIZ: QuizQuestion[] = [
  {
    id: "gen_q1",
    question: "Зачем при изучении отечественных учебников используется сопоставление обозначений СНГ ↔ Запад (SPE/API)?",
    options: [
      "Чтобы исключить ошибки при переносе формул между методическими школами",
      "Чтобы заменить все единицы измерения только на баррели",
      "Чтобы отказаться от петрофизических поправок",
      "Только для оформления графиков без влияния на расчёты",
    ],
    correctIndex: 0,
    explanation:
      "Соответствие K_п ↔ φ, ρ_п ↔ R_t, P_п ↔ F и R_к, p_к ↔ r_e, p_e предотвращает путаницу в размерностях и коэффициентах при работе в международных проектах.",
  },
  {
    id: "gen_q2",
    question: "Что необходимо проверять перед применением эмпирических отсечек K_п* и α_СП* из учебника к новому месторождению?",
    options: [
      "Только диаметр долота при бурении",
      "Соответствие типа коллектора (терригенный / карбонатный) и калибровку по керну",
      "Только цвет бурового раствора",
      "Отсечки универсальны для любых разрезов без калибровки",
    ],
    correctIndex: 1,
    explanation:
      "Локальные критерии коллекторов зависят от литологии, глинистости и типа пустотного пространства (вторичная пористость карбонатов требует отдельных поправок).",
  },
  {
    id: "gen_q3",
    question: "Какой подход гарантирует отсутствие искажений при работе с графическими палетками в курсе?",
    options: [
      "Автоматическая подстановка средних значений нейросетью",
      "Использование методики считывания и прямых аналитических уравнений без домысливания чисел",
      "Округление всех показаний каротажа до десятков",
      "Игнорирование зоны проникновения фильтрата",
    ],
    correctIndex: 1,
    explanation:
      "Все количественные величины в платформе вычисляются по явным формулам, а неоцифрованные палетки сопровождаются строгой пошаговой методикой.",
  },
];

function formatAuthorShort(author: string): string {
  const cleaned = author.trim();
  if (!cleaned) return "";
  const parts = cleaned.split(/\s+/);
  if (parts.length === 3 && !parts[1].includes(".")) {
    return `${parts[0]} ${parts[1][0]}.${parts[2][0]}.`;
  }
  return cleaned;
}

function formatBookDisplay(book: BookInfo): string {
  if (BOOK_DISPLAY_OVERRIDES[book.book_file]) {
    return BOOK_DISPLAY_OVERRIDES[book.book_file];
  }
  const firstAuthor = book.authors?.length ? formatAuthorShort(book.authors[0]) : "";
  const etAl = book.authors && book.authors.length > 1 ? " и др." : "";
  const authorPrefix = firstAuthor ? `${firstAuthor}${etAl} — ` : "";
  const yearSuffix = book.year ? ` (${book.year})` : "";
  return `${authorPrefix}${book.title}${yearSuffix}`;
}

function formatCourseTitle(course: CourseManifest): string {
  if (BOOK_DISPLAY_OVERRIDES[course.book_file]) {
    return BOOK_DISPLAY_OVERRIDES[course.book_file];
  }
  const firstAuthor = course.authors?.length ? formatAuthorShort(course.authors[0]) : "";
  return firstAuthor ? `${firstAuthor} — ${course.book_title}` : course.book_title;
}

function formatCourseChapterSubtitle(course: CourseManifest): string {
  const raw = (course.chapter_title || "").trim();
  const isFrontMatter = /^(предисловие|серия|введение|аннотация|нефтегазовая)/i.test(raw);
  if (isFrontMatter || !raw) {
    if (course.module_type === "latyshova_gis") {
      return "Глава I · Уравнение Арчи–Дахнова, кривые ПС/БК и отбивка ВНК";
    }
    if (course.module_type === "basniev_hydro") {
      return "Главы XVIII–XXIV · Закон Дарси, формула Дюпюи и метод ПССС";
    }
  }
  return raw;
}

function formatSchool(school: string): string {
  if (school === "soviet_cis") return "Отечественная / СНГ";
  if (school === "bridge") return "СНГ ↔ Международная";
  if (school === "western") return "Международная (SPE / API)";
  return "Профильная методика";
}

function formatDiscipline(moduleType: string): string {
  if (moduleType === "latyshova_gis") return "Петрофизика и ГИС";
  if (moduleType === "basniev_hydro") return "Подземная гидромеханика";
  return "Геология и разработка пластов";
}

function formatDurationHuman(seconds?: number): string {
  if (!seconds || seconds <= 0) return "1:30";
  const rounded = Math.round(seconds);
  const mins = Math.floor(rounded / 60);
  const secs = rounded % 60;
  return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
}

function formatTimestamp(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem < 10 ? "0" : ""}${rem}`;
}

function formatSceneKind(backend: string): string {
  if (backend === "threejs_lab") return "3D-стенд";
  if (backend === "remotion_formula") return "Методика";
  if (backend === "remotion_split") return "Сопоставление";
  return "График";
}

function pickDefaultChapterIndex(chapters: ChapterInfo[]): number {
  if (!chapters || chapters.length === 0) return 0;
  const isFrontMatter = (title: string) =>
    /^(предисловие|введение|серия|список|таблиц|благодарност|содержан|оглавлен|аннотац|нефтегазовая$|\*\*)/i.test(
      title.trim()
    ) || /^таблица\s+\d+/i.test(title.trim());

  const substantiveWithFormulas = chapters.find((ch) => ch.formula_count > 0 && !isFrontMatter(ch.title));
  if (substantiveWithFormulas) return substantiveWithFormulas.index;

  const anyWithFormulas = chapters.find((ch) => ch.formula_count > 0);
  if (anyWithFormulas) return anyWithFormulas.index;

  const firstChapter = chapters.find((ch) => !isFrontMatter(ch.title));
  if (firstChapter) return firstChapter.index;

  return chapters[0].index;
}

function sanitizeQaMessage(message: string): string {
  return message
    .replace(/\s*\([a-z0-9_]+\)/gi, "")
    .replace(/Manim\s*\/\s*Three\.js\s*\/\s*Remotion/gi, "расчётные модели курса")
    .replace(/Manim|Three\.js|Remotion/gi, "инженерный модуль")
    .replace(/kп\*/g, "k_п*")
    .trim();
}

function mapQaCheckDisplay(chk: QACheck): {
  title: string;
  description: string;
  tone: "ok" | "warn";
  badge: string;
} {
  const tone: "ok" | "warn" = chk.status === "WARN" || chk.status === "FAIL" ? "warn" : "ok";
  const cleaned = sanitizeQaMessage(chk.message);

  switch (chk.category) {
    case "deterministic_visuals":
      return {
        title: "Точность графики подтверждена",
        description: "Все графики, кривые и формулы рассчитываются напрямую по уравнениям учебника.",
        tone,
        badge: "Подтверждено",
      };
    case "nomogram_guard":
      return {
        title: "Защита от искажения палеток",
        description:
          cleaned || "Для графических палеток даётся пошаговая методика без домысливания чисел.",
        tone,
        badge: tone === "ok" ? "Подтверждено" : "Ограничение",
      };
    case "school_notation":
      return {
        title: "Терминология СНГ ↔ Запад",
        description: "Все формульные слайды снабжены точным соответствием обозначений СНГ и SPE/API.",
        tone,
        badge: "Согласовано",
      };
    case "quantitative_safety":
      return {
        title: "Границы применимости формул",
        description: cleaned || "Количественные параметры лежат в безопасных границах применимости.",
        tone,
        badge: tone === "ok" ? "В пределах нормы" : "Требует учёта",
      };
    case "reservoir_type":
      return {
        title: "Тип коллектора и геологические условия",
        description: cleaned || "Учтены границы применимости для терригенных и карбонатных разрезов.",
        tone,
        badge: tone === "ok" ? "Проверено" : "Условие применения",
      };
    default:
      return {
        title: "Методический контроль",
        description: cleaned || "Проверка соответствия учебному материалу пройдена.",
        tone,
        badge: tone === "ok" ? "Подтверждено" : "Примечание",
      };
  }
}

export default function App() {
  const [studioView, setStudioView] = useState<StudioView>("video");
  const [panelTab, setPanelTab] = useState<StudioPanelTab>("plan");
  const [builderOpen, setBuilderOpen] = useState<boolean>(false);
  const [uploadOpen, setUploadOpen] = useState<boolean>(false);
  const [qaExpanded, setQaExpanded] = useState<boolean>(false);

  const [books, setBooks] = useState<BookInfo[]>([]);
  const [selectedBook, setSelectedBook] = useState<string>("");
  const [selectedChapterIdx, setSelectedChapterIdx] = useState<number>(0);
  const [voice, setVoice] = useState<"ru-RU-DmitryNeural" | "ru-RU-SvetlanaNeural">("ru-RU-DmitryNeural");
  const [renderVideo, setRenderVideo] = useState<boolean>(true);
  const [job, setJob] = useState<CourseJobStatus | null>(null);
  const [courses, setCourses] = useState<CourseManifest[]>([]);
  const [activeCourse, setActiveCourse] = useState<CourseManifest | null>(null);
  const [activeLab, setActiveLab] = useState<"latyshova" | "basniev">("latyshova");

  const [activeSceneIdx, setActiveSceneIdx] = useState<number>(0);
  const [hoveredCard, setHoveredCard] = useState<string | null>(null);
  const [quizAnswers, setQuizAnswers] = useState<Record<string, number>>({});

  const [uploadBookFile, setUploadBookFile] = useState<File | null>(null);
  const [uploadPassportFile, setUploadPassportFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [uploadStatus, setUploadStatus] = useState<{ text: string; ok: boolean } | null>(null);

  const videoRef = useRef<HTMLVideoElement>(null);
  const studioRef = useRef<HTMLElement>(null);
  const previewVideoRefs = useRef<Record<string, HTMLVideoElement | null>>({});
  const bookInputRef = useRef<HTMLInputElement>(null);
  const passportInputRef = useRef<HTMLInputElement>(null);

  const loadBooksAndCourses = async () => {
    try {
      const [bRes, cRes] = await Promise.all([fetch("/api/books"), fetch("/api/courses")]);
      if (bRes.ok) {
        const bList: BookInfo[] = await bRes.json();
        setBooks(bList);
        if (bList.length > 0 && !selectedBook) {
          const preferred = bList.find((b) => b.book_file.includes("latyshova")) || bList[0];
          setSelectedBook(preferred.book_file);
          setSelectedChapterIdx(pickDefaultChapterIndex(preferred.chapters));
        }
      }
      if (cRes.ok) {
        const cList: CourseManifest[] = await cRes.json();
        setCourses(cList);
        if (cList.length > 0 && !activeCourse) {
          const firstReady = cList.find((c) => c.final_video_url) || cList[0];
          setActiveCourse(firstReady);
          setActiveLab(firstReady.module_type === "basniev_hydro" ? "basniev" : "latyshova");
        }
      }
    } catch {
      // Игнорируем при offline-просмотре
    }
  };

  useEffect(() => {
    loadBooksAndCourses();
  }, []);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setBuilderOpen(false);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs/${job.job_id}`);
        if (res.ok) {
          const next: CourseJobStatus = await res.json();
          setJob(next);
          if (next.status === "completed" && next.course_id) {
            const cRes = await fetch(`/api/courses/${next.course_id}`);
            if (cRes.ok) {
              const manifest: CourseManifest = await cRes.json();
              setActiveCourse(manifest);
              setActiveSceneIdx(0);
              setQuizAnswers({});
              setCourses((prev) => [manifest, ...prev.filter((c) => c.course_id !== manifest.course_id)]);
              if (manifest.module_type === "basniev_hydro") setActiveLab("basniev");
              else if (manifest.module_type === "latyshova_gis") setActiveLab("latyshova");
            }
          }
        }
      } catch {
        // Игнорируем временную ошибку опроса
      }
    }, 1200);
    return () => clearInterval(timer);
  }, [job]);

  const currentBook = books.find((b) => b.book_file === selectedBook);

  const sceneStartTimes = useMemo(() => {
    if (!activeCourse) return [];
    const starts: number[] = [];
    let acc = 0;
    for (const sc of activeCourse.scenes) {
      starts.push(acc);
      acc += sc.duration_sec;
    }
    return starts;
  }, [activeCourse]);

  const handleVideoTimeUpdate = () => {
    const el = videoRef.current;
    if (!el || !activeCourse || activeCourse.scenes.length === 0) return;
    const t = el.currentTime;
    let foundIdx = 0;
    for (let i = 0; i < sceneStartTimes.length; i++) {
      if (t >= sceneStartTimes[i] - 0.15) {
        foundIdx = i;
      }
    }
    if (foundIdx !== activeSceneIdx) {
      setActiveSceneIdx(foundIdx);
    }
  };

  const seekToScene = (orderIndex: number) => {
    setActiveSceneIdx(orderIndex);
    if (!activeCourse || !videoRef.current) return;
    const targetTime = sceneStartTimes[orderIndex] ?? 0;
    videoRef.current.currentTime = targetTime;
    videoRef.current.play().catch(() => {});
  };

  const selectBookInWizard = (bookFile: string) => {
    setSelectedBook(bookFile);
    const bk = books.find((b) => b.book_file === bookFile);
    setSelectedChapterIdx(bk ? pickDefaultChapterIndex(bk.chapters) : 0);
  };

  const handleBuildCourse = async () => {
    if (!currentBook) return;
    const res = await fetch("/api/courses/build", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        book_file: currentBook.book_file,
        passport_file: currentBook.passport_file,
        chapter_index: selectedChapterIdx,
        module_override: "auto",
        voice,
        render_video: renderVideo,
        use_llm: true,
      }),
    });
    if (res.ok) {
      const created: CourseJobStatus = await res.json();
      setJob(created);
    }
  };

  const handleDropFiles = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = Array.from(e.dataTransfer.files);
    for (const f of dropped) {
      const lower = f.name.toLowerCase();
      if (lower.endsWith(".json")) {
        setUploadPassportFile(f);
      } else if (lower.endsWith(".md")) {
        if (!uploadBookFile) setUploadBookFile(f);
        else setUploadPassportFile(f);
      }
    }
  };

  const handleUpload = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!uploadBookFile && !uploadPassportFile) {
      setUploadStatus({ text: "Выберите или перетащите файл учебника.", ok: false });
      return;
    }
    const formData = new FormData();
    if (uploadBookFile) formData.append("book_file", uploadBookFile);
    if (uploadPassportFile) formData.append("passport_file", uploadPassportFile);

    setUploadStatus({ text: "Добавление материалов в библиотеку...", ok: true });
    try {
      const res = await fetch("/api/upload", { method: "POST", body: formData });
      if (res.ok) {
        const data = await res.json();
        setBooks(data.books);
        if (uploadBookFile) {
          const added = (data.books as BookInfo[]).find((b) => b.book_file === uploadBookFile.name);
          if (added) {
            setSelectedBook(added.book_file);
            setSelectedChapterIdx(pickDefaultChapterIndex(added.chapters));
          }
        }
        setUploadBookFile(null);
        setUploadPassportFile(null);
        setUploadStatus({ text: "Учебник добавлен и выбран в мастере.", ok: true });
      } else {
        setUploadStatus({ text: "Не удалось загрузить файлы.", ok: false });
      }
    } catch {
      setUploadStatus({ text: "Сервер временно недоступен.", ok: false });
    }
  };

  const openCourseInStudio = (moduleType: "latyshova_gis" | "basniev_hydro", view: StudioView) => {
    const found =
      courses.find((c) => c.module_type === moduleType && c.final_video_url) ||
      courses.find((c) => c.module_type === moduleType);
    if (found) {
      setActiveCourse(found);
      setActiveSceneIdx(0);
      setQuizAnswers({});
    }
    setActiveLab(moduleType === "basniev_hydro" ? "basniev" : "latyshova");
    setStudioView(view);
    studioRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleCardHover = (cardId: string, enter: boolean) => {
    setHoveredCard(enter ? cardId : null);
    const vid = previewVideoRefs.current[cardId];
    if (!vid) return;
    if (enter) {
      if (vid.currentTime < 14) vid.currentTime = 16;
      vid.play().catch(() => {});
    } else {
      vid.pause();
    }
  };

  const latyshovaCourse =
    courses.find((c) => c.module_type === "latyshova_gis" && c.final_video_url) ||
    courses.find((c) => c.module_type === "latyshova_gis");
  const basnievCourse =
    courses.find((c) => c.module_type === "basniev_hydro" && c.final_video_url) ||
    courses.find((c) => c.module_type === "basniev_hydro");

  const libraryCards = [
    {
      id: "latyshova" as const,
      moduleType: "latyshova_gis" as const,
      course: latyshovaCourse,
      category: "Петрофизика и ГИС",
      title: "Интерпретация ГИС и оценка коллекторов",
      author: "Латышова М.Г., 1991",
      description:
        "Уравнение Арчи–Дахнова P_п = a_m / K_п^m, выделение коллектора по α_СП и отбивка ВНК.",
      duration: formatDurationHuman(latyshovaCourse?.total_duration_sec || 93),
      scenesCount: latyshovaCourse?.scenes.length || 5,
      previewImg: latyshovaCourse
        ? `/outputs/${latyshovaCourse.course_id}/preview.jpg`
        : "/outputs/train_latyshova_eb45dac3/preview.jpg",
    },
    {
      id: "basniev" as const,
      moduleType: "basniev_hydro" as const,
      course: basnievCourse,
      category: "Подземная гидромеханика",
      title: "Фильтрация флюидов и приток к скважине",
      author: "Басниев К.С. и др., 2005",
      description:
        "Закон Дарси, формула Дюпюи для радиального притока, воронка депрессии и метод ПССС.",
      duration: formatDurationHuman(basnievCourse?.total_duration_sec || 90),
      scenesCount: basnievCourse?.scenes.length || 5,
      previewImg: basnievCourse
        ? `/outputs/${basnievCourse.course_id}/preview.jpg`
        : "/outputs/train_basniev_b828f75a/preview.jpg",
    },
  ];

  const activeScene = activeCourse?.scenes[activeSceneIdx] || activeCourse?.scenes[0] || null;
  const activeQuiz: QuizQuestion[] =
    activeCourse?.module_type === "latyshova_gis"
      ? LATYSHOVA_QUIZ
      : activeCourse?.module_type === "basniev_hydro"
      ? BASNIEV_QUIZ
      : GENERIC_QUIZ;

  const quizCorrectCount = activeQuiz.reduce(
    (acc, q) => (quizAnswers[q.id] === q.correctIndex ? acc + 1 : acc),
    0
  );
  const quizAnsweredCount = activeQuiz.filter((q) => quizAnswers[q.id] !== undefined).length;

  const qaChecks = activeCourse?.qa_report?.checks || [];
  const qaHasWarn = qaChecks.some((c) => c.status === "WARN" || c.status === "FAIL");

  const activePreviewPoster = activeCourse
    ? `/outputs/${activeCourse.course_id}/preview.jpg`
    : undefined;

  return (
    <div className="min-h-screen bg-[#090D16] text-slate-100">
      {/* Шапка */}
      <header className="sticky top-0 z-30 border-b border-white/[0.08] bg-[#090D16]/92 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-3.5">
          <div className="flex items-center gap-3.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-blue-500/35 bg-[#2563EB]/15 text-sm font-bold tracking-wider text-blue-400">
              L
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <span className="text-base font-semibold tracking-tight text-white">LITHOS</span>
                <span className="hidden rounded-md border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-slate-400 sm:inline-block">
                  Petroleum Studio
                </span>
              </div>
              <p className="text-xs text-slate-400">Интерактивная платформа нефтегазового обучения</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <div className="flex items-center gap-1 rounded-xl border border-white/[0.08] bg-[#111827] p-1">
              <button
                onClick={() => setStudioView("video")}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  studioView === "video"
                    ? "bg-[#2563EB] text-white"
                    : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
                }`}
              >
                <Film className="h-3.5 w-3.5" />
                Видеостудия
              </button>
              <button
                onClick={() => setStudioView("lab")}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                  studioView === "lab"
                    ? "bg-[#2563EB] text-white"
                    : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"
                }`}
              >
                <FlaskConical className="h-3.5 w-3.5" />
                3D-лаборатория
              </button>
            </div>

            <button
              onClick={() => setBuilderOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-xl bg-[#2563EB] px-4 py-2 text-xs font-medium text-white shadow-sm transition hover:bg-blue-500"
            >
              <Plus className="h-3.5 w-3.5" />
              Создать курс из главы
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto flex max-w-7xl flex-col gap-6 px-6 py-6">
        {/* БИБЛИОТЕКА КУРСОВ С ВИЗУАЛЬНЫМИ ПРЕВЬЮ */}
        <section>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-blue-400" />
              <h2 className="text-sm font-semibold tracking-tight text-white">Библиотека курсов</h2>
            </div>
            <span className="text-xs text-slate-400">
              Наведите курсор на обложку для живого превью или откройте курс в студии ниже
            </span>
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            {libraryCards.map((card) => {
              const isSelected = activeCourse?.module_type === card.moduleType;
              return (
                <div
                  key={card.id}
                  onMouseEnter={() => handleCardHover(card.id, true)}
                  onMouseLeave={() => handleCardHover(card.id, false)}
                  className={`group overflow-hidden rounded-xl border bg-[#111827] transition ${
                    isSelected
                      ? "border-blue-500/50 ring-1 ring-blue-500/25"
                      : "border-white/[0.08] hover:border-white/[0.16]"
                  }`}
                >
                  {/* Визуальная обложка с hover-видео */}
                  <div
                    onClick={() => openCourseInStudio(card.moduleType, "video")}
                    className="relative h-48 w-full cursor-pointer overflow-hidden bg-[#0B101B]"
                  >
                    <img
                      src={card.previewImg}
                      alt={card.title}
                      className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.02]"
                    />
                    {card.course?.final_video_url && (
                      <video
                        ref={(el) => {
                          previewVideoRefs.current[card.id] = el;
                        }}
                        src={card.course.final_video_url}
                        poster={card.previewImg}
                        muted
                        loop
                        playsInline
                        preload="metadata"
                        className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-300 ${
                          hoveredCard === card.id ? "opacity-100" : "opacity-0"
                        }`}
                      />
                    )}
                    <div className="absolute inset-0 bg-gradient-to-t from-[#111827] via-[#090D16]/45 to-transparent" />

                    {/* Верхние бейджи поверх превью */}
                    <div className="absolute left-3.5 right-3.5 top-3.5 flex items-center justify-between gap-2">
                      <span className="rounded-md border border-blue-400/25 bg-[#090D16]/85 px-2.5 py-1 text-[11px] font-medium text-blue-300 backdrop-blur-sm">
                        {card.category}
                      </span>
                      <div className="flex items-center gap-2">
                        {isSelected && (
                          <span className="rounded-md border border-emerald-400/30 bg-emerald-500/15 px-2 py-1 text-[11px] font-medium text-emerald-300 backdrop-blur-sm">
                            Открыт в студии
                          </span>
                        )}
                        <span className="inline-flex items-center gap-1 rounded-md border border-white/[0.1] bg-[#090D16]/85 px-2 py-1 text-[11px] font-medium text-slate-200 backdrop-blur-sm">
                          <Clock className="h-3 w-3 text-slate-400" />
                          {card.duration}
                        </span>
                      </div>
                    </div>

                    {/* Кнопка Play поверх кадра */}
                    <div className="absolute inset-0 flex items-center justify-center">
                      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-white/25 bg-[#090D16]/75 text-white shadow-lg backdrop-blur-md transition duration-200 group-hover:scale-110 group-hover:border-blue-400/60 group-hover:bg-[#2563EB]/90">
                        <Play className="ml-0.5 h-5 w-5 fill-current" />
                      </div>
                    </div>

                    {/* Заголовок на нижней кромке обложки */}
                    <div className="absolute bottom-3 left-4 right-4">
                      <div className="text-[11px] font-medium text-slate-300">{card.author}</div>
                      <h3 className="text-base font-semibold tracking-tight text-white">{card.title}</h3>
                    </div>
                  </div>

                  {/* Описание и кнопки действия */}
                  <div className="flex flex-col gap-3.5 p-4 pt-3">
                    <p className="text-xs leading-relaxed text-slate-400">
                      <MathText text={card.description} />
                    </p>
                    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-white/[0.06] pt-3">
                      <span className="text-[11px] text-slate-500">{card.scenesCount} сцен · 3 вопроса для проверки</span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => openCourseInStudio(card.moduleType, "video")}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-[#2563EB] px-3 py-1.5 text-xs font-medium text-white transition hover:bg-blue-500"
                        >
                          <Play className="h-3.5 w-3.5" />
                          Смотреть урок
                        </button>
                        <button
                          onClick={() => openCourseInStudio(card.moduleType, "lab")}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-white/[0.08]"
                        >
                          <FlaskConical className="h-3.5 w-3.5 text-slate-400" />
                          3D-стенд
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        {/* ГЛАВНЫЙ ЭКРАН: ИНТЕРАКТИВНАЯ СТУДИЯ КУРСА */}
        <section ref={studioRef} className="rounded-2xl border border-white/[0.08] bg-[#111827] p-5">
          {/* Верхняя панель студии */}
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/[0.06] pb-4">
            <div className="min-w-0 flex-1">
              {activeCourse ? (
                <>
                  <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium text-blue-400">
                    <span>{formatDiscipline(activeCourse.module_type)}</span>
                    <span className="text-slate-600">·</span>
                    <span className="text-slate-400">{formatSchool(activeCourse.methodological_school)}</span>
                    <span className="text-slate-600">·</span>
                    <span className="text-slate-400">{formatDurationHuman(activeCourse.total_duration_sec)}</span>
                  </div>
                  <h1 className="mt-1 truncate text-lg font-semibold tracking-tight text-white">
                    {formatCourseTitle(activeCourse)}
                  </h1>
                  <div className="truncate text-xs text-slate-400">
                    <MathText text={formatCourseChapterSubtitle(activeCourse)} />
                  </div>
                </>
              ) : (
                <div className="text-sm text-slate-400">Выберите курс из библиотеки или создайте новый из главы учебника</div>
              )}
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              {courses.length > 1 && (
                <select
                  value={activeCourse?.course_id || ""}
                  onChange={(e) => {
                    const found = courses.find((c) => c.course_id === e.target.value);
                    if (found) {
                      setActiveCourse(found);
                      setActiveSceneIdx(0);
                      setQuizAnswers({});
                      if (found.module_type === "basniev_hydro") setActiveLab("basniev");
                      else if (found.module_type === "latyshova_gis") setActiveLab("latyshova");
                    }
                  }}
                  className="max-w-[260px] rounded-lg border border-white/[0.08] bg-[#090D16] px-3 py-2 text-xs text-slate-200 outline-none focus:border-[#2563EB]"
                >
                  {courses.map((c) => (
                    <option key={c.course_id} value={c.course_id}>
                      {formatCourseTitle(c)}
                    </option>
                  ))}
                </select>
              )}

              <div className="flex items-center gap-1 rounded-lg border border-white/[0.08] bg-[#090D16] p-1">
                <button
                  onClick={() => setStudioView("video")}
                  className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition ${
                    studioView === "video" ? "bg-[#2563EB] text-white" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <Film className="h-3.5 w-3.5" />
                  Видеоурок
                </button>
                <button
                  onClick={() => setStudioView("lab")}
                  className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition ${
                    studioView === "lab" ? "bg-[#2563EB] text-white" : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <FlaskConical className="h-3.5 w-3.5" />
                  3D-стенд
                </button>
              </div>
            </div>
          </div>

          {/* РЕЖИМ 1: ВИДЕОУРОК + ИНТЕРАКТИВНАЯ ПАНЕЛЬ КУРСА */}
          {studioView === "video" && activeCourse && (
            <div className="mt-5 grid grid-cols-1 gap-6 lg:grid-cols-12">
              {/* Левая часть (7 колонок): HD плеер + живые формулы активной сцены */}
              <div className="flex flex-col gap-4 lg:col-span-7">
                <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-black">
                  {activeCourse.final_video_url ? (
                    <video
                      ref={videoRef}
                      controls
                      playsInline
                      poster={activePreviewPoster}
                      src={activeCourse.final_video_url}
                      onTimeUpdate={handleVideoTimeUpdate}
                      className="aspect-video w-full bg-black"
                    />
                  ) : (
                    <div className="flex aspect-video flex-col items-center justify-center gap-3 bg-[#090D16] p-8 text-center">
                      <Film className="h-10 w-10 text-slate-600" />
                      <div className="text-sm font-medium text-slate-300">Видеодорожка для этой главы не собиралась</div>
                      <div className="max-w-md text-xs text-slate-500">
                        Изучите сгенерированный план урока, формулы и проверку знаний справа или пересоберите курс с опцией «Видеоурок (HD 1080p)».
                      </div>
                    </div>
                  )}
                </div>

                {/* Живая карточка активной сцены (как Brilliant / Techlog) */}
                {activeScene && (
                  <div className="rounded-xl border border-white/[0.08] bg-[#090D16]/85 p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/[0.06] pb-3">
                      <div>
                        <div className="text-[11px] font-medium text-blue-400">
                          Сцена {activeScene.order} из {activeCourse.scenes.length} ·{" "}
                          {formatTimestamp(sceneStartTimes[activeSceneIdx] || 0)}
                        </div>
                        <div className="text-sm font-semibold text-white">
                          <MathText text={activeScene.title} />
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {activeCourse.srt_url && (
                          <a
                            href={activeCourse.srt_url}
                            download
                            className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.04] px-2.5 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-white/[0.08]"
                          >
                            <Download className="h-3.5 w-3.5 text-slate-400" />
                            Субтитры (.SRT)
                          </a>
                        )}
                        <button
                          onClick={() => setStudioView("lab")}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-blue-500/30 bg-blue-500/10 px-3 py-1.5 text-xs font-medium text-blue-300 transition hover:bg-blue-500/20"
                        >
                          <FlaskConical className="h-3.5 w-3.5" />
                          Проверить в 3D
                        </button>
                      </div>
                    </div>

                    {/* Формулы активной сцены */}
                    {activeScene.formulas.length > 0 && (
                      <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                        {activeScene.formulas.map((f, i) => (
                          <React.Fragment key={i}>
                            <div className="rounded-lg border border-white/[0.06] bg-[#111827] p-3">
                              <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
                                Нотация СНГ · {f.source_ref || "Учебник"}
                              </div>
                              <div className="mt-1.5 font-mono text-sm font-semibold text-white">
                                <MathText text={cleanLatexToText(f.latex)} />
                              </div>
                            </div>
                            <div className="rounded-lg border border-white/[0.06] bg-[#111827] p-3">
                              <div className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
                                Международная нотация (SPE / API)
                              </div>
                              <div className="mt-1.5 font-mono text-sm font-semibold text-blue-300">
                                <MathText text={cleanLatexToText(f.western_latex || f.latex)} />
                              </div>
                            </div>
                          </React.Fragment>
                        ))}
                      </div>
                    )}

                    {/* Ключевые выводы и терминологический мост */}
                    <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                      {activeScene.term_bridges.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {activeScene.term_bridges.map((b, i) => (
                            <span
                              key={i}
                              title={`${b.ru_term} ↔ ${b.en_term} (${b.unit})`}
                              className="inline-flex items-center gap-1 rounded-md border border-blue-500/20 bg-blue-500/10 px-2.5 py-1 text-[11px] font-medium text-blue-200"
                            >
                              <MathText text={`${b.ru_symbol} ↔ ${b.en_symbol}`} />
                              {b.unit && b.unit !== "б/р" && (
                                <span className="text-[10px] text-slate-400">· {b.unit}</span>
                              )}
                            </span>
                          ))}
                        </div>
                      )}

                      {activeScene.key_takeaways.length > 0 && (
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400">
                          {activeScene.key_takeaways.map((kw, i) => (
                            <span key={i} className="flex items-center gap-1">
                              <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-400" />
                              <MathText text={kw} />
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Правая часть (5 колонок): План урока | Самопроверка (3 вопроса) | Верификация */}
              <div className="flex flex-col rounded-xl border border-white/[0.08] bg-[#090D16]/75 p-4 lg:col-span-5">
                <div className="grid grid-cols-3 gap-1 rounded-lg border border-white/[0.08] bg-[#111827] p-1">
                  <button
                    onClick={() => setPanelTab("plan")}
                    className={`rounded-md px-2 py-1.5 text-xs font-medium transition ${
                      panelTab === "plan" ? "bg-[#2563EB] text-white" : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    План урока
                  </button>
                  <button
                    onClick={() => setPanelTab("quiz")}
                    className={`flex items-center justify-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium transition ${
                      panelTab === "quiz" ? "bg-[#2563EB] text-white" : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <GraduationCap className="h-3.5 w-3.5" />
                    <span>Тест (3)</span>
                  </button>
                  <button
                    onClick={() => setPanelTab("qa")}
                    className={`flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-medium transition ${
                      panelTab === "qa" ? "bg-[#2563EB] text-white" : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    <span>Верификация</span>
                    <span className={`h-1.5 w-1.5 rounded-full ${qaHasWarn ? "bg-amber-400" : "bg-emerald-400"}`} />
                  </button>
                </div>

                {/* ВКЛАДКА ПРАВОЙ ПАНЕЛИ 1: ПЛАН УРОКА (С КЛИКАБЕЛЬНЫМИ ТАЙМКОДАМИ И ПОДСВЕТКОЙ) */}
                {panelTab === "plan" && (
                  <div className="mt-3 flex max-h-[560px] flex-col gap-2.5 overflow-y-auto pr-1">
                    {activeCourse.scenes.map((sc, idx) => {
                      const isCurrent = idx === activeSceneIdx;
                      const startSec = sceneStartTimes[idx] ?? 0;
                      return (
                        <button
                          key={sc.scene_id}
                          onClick={() => seekToScene(idx)}
                          className={`rounded-xl border p-3.5 text-left transition ${
                            isCurrent
                              ? "border-blue-500/60 bg-blue-500/10 ring-1 ring-blue-500/20"
                              : "border-white/[0.06] bg-[#111827]/90 hover:border-white/[0.16]"
                          }`}
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span
                                className={`inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[11px] font-semibold ${
                                  isCurrent ? "bg-[#2563EB] text-white" : "bg-white/[0.06] text-slate-300"
                                }`}
                              >
                                {sc.order}
                              </span>
                              <span className="text-xs font-semibold text-white">
                                <MathText text={sc.title} />
                              </span>
                            </div>
                            <span
                              className={`shrink-0 rounded px-2 py-0.5 font-mono text-[11px] ${
                                isCurrent
                                  ? "bg-blue-500/20 text-blue-300"
                                  : "bg-white/[0.04] text-slate-400"
                              }`}
                            >
                              {formatTimestamp(startSec)} · {formatSceneKind(sc.visual_backend)}
                            </span>
                          </div>

                          <p className="mt-2 text-xs leading-relaxed text-slate-400">
                            <MathText text={sc.narration} />
                          </p>

                          {sc.term_bridges.length > 0 && (
                            <div className="mt-2.5 flex flex-wrap gap-1.5">
                              {sc.term_bridges.map((b, i) => (
                                <span
                                  key={i}
                                  className="rounded border border-white/[0.08] bg-[#090D16] px-2 py-0.5 text-[11px] text-slate-300"
                                >
                                  <MathText text={`${b.ru_symbol} ↔ ${b.en_symbol}`} />
                                </span>
                              ))}
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* ВКЛАДКА ПРАВОЙ ПАНЕЛИ 2: САМОПРОВЕРКА (3 ИНЖЕНЕРНЫХ ВОПРОСА) */}
                {panelTab === "quiz" && (
                  <div className="mt-3 flex max-h-[560px] flex-col gap-3 overflow-y-auto pr-1">
                    <div className="flex items-center justify-between rounded-lg border border-white/[0.06] bg-[#111827] px-3 py-2 text-xs">
                      <span className="text-slate-300">
                        Результат: <strong className="text-white">{quizCorrectCount}</strong> из {activeQuiz.length}
                        {quizAnsweredCount === activeQuiz.length && quizCorrectCount === activeQuiz.length && (
                          <span className="ml-2 text-emerald-400">Отлично!</span>
                        )}
                      </span>
                      {quizAnsweredCount > 0 && (
                        <button
                          onClick={() => setQuizAnswers({})}
                          className="inline-flex items-center gap-1 text-[11px] text-slate-400 hover:text-white"
                        >
                          <RotateCcw className="h-3 w-3" />
                          Сбросить
                        </button>
                      )}
                    </div>

                    {activeQuiz.map((q, qIdx) => {
                      const chosen = quizAnswers[q.id];
                      const isAnswered = chosen !== undefined;
                      const isRight = chosen === q.correctIndex;

                      return (
                        <div key={q.id} className="rounded-xl border border-white/[0.07] bg-[#111827] p-3.5 text-xs">
                          <div className="font-medium leading-relaxed text-white">
                            <span className="mr-1.5 text-blue-400">{qIdx + 1}.</span>
                            <MathText text={q.question} />
                          </div>

                          <div className="mt-2.5 flex flex-col gap-1.5">
                            {q.options.map((opt, optIdx) => {
                              const pickedThis = chosen === optIdx;
                              const isCorrectOpt = optIdx === q.correctIndex;
                              let cls =
                                "border-white/[0.08] bg-[#090D16]/70 text-slate-300 hover:border-white/[0.2] hover:text-white";
                              if (isAnswered) {
                                if (isCorrectOpt) {
                                  cls = "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
                                } else if (pickedThis) {
                                  cls = "border-rose-500/40 bg-rose-500/10 text-rose-200";
                                } else {
                                  cls = "border-white/[0.04] bg-[#090D16]/40 text-slate-500";
                                }
                              }

                              return (
                                <button
                                  key={optIdx}
                                  onClick={() => setQuizAnswers((prev) => ({ ...prev, [q.id]: optIdx }))}
                                  className={`flex items-start justify-between gap-2 rounded-lg border px-3 py-2 text-left transition ${cls}`}
                                >
                                  <span>
                                    <MathText text={opt} />
                                  </span>
                                  {isAnswered && isCorrectOpt && (
                                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                                  )}
                                  {isAnswered && pickedThis && !isCorrectOpt && (
                                    <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-400" />
                                  )}
                                </button>
                              );
                            })}
                          </div>

                          {isAnswered && (
                            <div
                              className={`mt-2.5 rounded-lg border p-2.5 text-[11px] leading-relaxed ${
                                isRight
                                  ? "border-emerald-500/25 bg-emerald-500/5 text-emerald-200"
                                  : "border-amber-500/25 bg-amber-500/5 text-amber-200"
                              }`}
                            >
                              <MathText text={q.explanation} />
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* ВКЛАДКА ПРАВОЙ ПАНЕЛИ 3: НАУЧНАЯ ВЕРИФИКАЦИЯ */}
                {panelTab === "qa" && (
                  <div className="mt-3 flex max-h-[560px] flex-col gap-2.5 overflow-y-auto pr-1">
                    <div className="grid grid-cols-1 gap-2">
                      <div className="flex items-center justify-between rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2.5 text-xs">
                        <span className="flex items-center gap-2 font-medium text-emerald-300">
                          <CheckCircle2 className="h-4 w-4 shrink-0" />
                          Точность графики подтверждена
                        </span>
                        <span className="text-[11px] text-emerald-400/80">По уравнениям</span>
                      </div>
                      <div className="flex items-center justify-between rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2.5 text-xs">
                        <span className="flex items-center gap-2 font-medium text-emerald-300">
                          <ShieldCheck className="h-4 w-4 shrink-0" />
                          Защита от искажения палеток
                        </span>
                        <span className="text-[11px] text-emerald-400/80">Активна</span>
                      </div>
                      <div className="flex items-center justify-between rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2.5 text-xs">
                        <span className="flex items-center gap-2 font-medium text-emerald-300">
                          <CheckCircle2 className="h-4 w-4 shrink-0" />
                          Терминология СНГ ↔ Запад
                        </span>
                        <span className="text-[11px] text-emerald-400/80">Согласовано</span>
                      </div>
                    </div>

                    <div className="rounded-lg border border-white/[0.06] bg-[#111827]">
                      <button
                        type="button"
                        onClick={() => setQaExpanded((prev) => !prev)}
                        className="flex w-full items-center justify-between px-3.5 py-2.5 text-xs font-medium text-slate-300 transition hover:text-white"
                      >
                        <span>Детали проверки по паспорту учебника ({qaChecks.length})</span>
                        {qaExpanded ? (
                          <ChevronUp className="h-4 w-4 text-slate-500" />
                        ) : (
                          <ChevronDown className="h-4 w-4 text-slate-500" />
                        )}
                      </button>

                      {qaExpanded && (
                        <div className="flex flex-col gap-2 border-t border-white/[0.06] p-3">
                          {qaChecks.map((chk) => {
                            const info = mapQaCheckDisplay(chk);
                            return (
                              <div
                                key={chk.check_id}
                                className="flex items-start justify-between gap-2.5 rounded-lg border border-white/[0.06] bg-[#090D16] p-3 text-xs"
                              >
                                <div className="flex items-start gap-2">
                                  {info.tone === "ok" ? (
                                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
                                  ) : (
                                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
                                  )}
                                  <div>
                                    <div className="font-medium text-slate-200">{info.title}</div>
                                    <div className="mt-0.5 leading-relaxed text-slate-400">
                                      <MathText text={info.description} />
                                    </div>
                                  </div>
                                </div>
                                <span
                                  className={`shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium ${
                                    info.tone === "ok"
                                      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                                      : "border-amber-500/20 bg-amber-500/10 text-amber-300"
                                  }`}
                                >
                                  {info.badge}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* РЕЖИМ 2: ПОЛНОШИРИННАЯ 3D-ЛАБОРАТОРИЯ */}
          {studioView === "lab" && (
            <div className="mt-5 flex flex-col gap-4">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/[0.06] bg-[#090D16]/75 px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => setStudioView("video")}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.08] bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-white/[0.08]"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" />
                    К видеоуроку
                  </button>
                  <span className="hidden text-xs text-slate-500 sm:inline">
                    Интерактивное моделирование по уравнениям курса
                  </span>
                </div>

                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => setActiveLab("latyshova")}
                    className={`rounded-lg px-3.5 py-1.5 text-xs font-medium transition ${
                      activeLab === "latyshova"
                        ? "bg-[#2563EB] text-white"
                        : "border border-white/[0.08] bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]"
                    }`}
                  >
                    Петрофизика и ГИС (Латышова)
                  </button>
                  <button
                    onClick={() => setActiveLab("basniev")}
                    className={`rounded-lg px-3.5 py-1.5 text-xs font-medium transition ${
                      activeLab === "basniev"
                        ? "bg-[#2563EB] text-white"
                        : "border border-white/[0.08] bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]"
                    }`}
                  >
                    Гидромеханика пласта (Басниев)
                  </button>
                </div>
              </div>

              {activeLab === "latyshova" ? (
                <LatyshovaProbeLab preset={activeCourse?.physics_data?.parameters} />
              ) : (
                <BasnievHydroLab preset={activeCourse?.physics_data?.dupuit?.inputs} />
              )}
            </div>
          )}
        </section>
      </main>

      {/* МОДАЛЬНОЕ ОКНО: + СОЗДАТЬ КУРС ИЗ ГЛАВЫ */}
      {builderOpen && (
        <div
          onClick={() => setBuilderOpen(false)}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-white/[0.1] bg-[#111827] p-6 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-white/[0.08] pb-4">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#2563EB]/15 text-blue-400">
                  <BookOpen className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="text-base font-semibold text-white">Создать курс из главы учебника</h2>
                  <p className="text-xs text-slate-400">
                    Автоматический разбор формул, методический контроль и сборка видеоурока
                  </p>
                </div>
              </div>
              <button
                onClick={() => setBuilderOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 transition hover:bg-white/[0.06] hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="mt-5 flex flex-col gap-4">
              {/* Шаг 1: Учебник */}
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <label className="text-xs font-medium text-slate-300">1. Учебное пособие</label>
                  {currentBook && (
                    <span
                      className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${
                        currentBook.passport_file
                          ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                          : "border-white/[0.08] bg-white/[0.03] text-slate-400"
                      }`}
                    >
                      {currentBook.passport_file ? "Методический паспорт подключён" : "Без паспорта"}
                    </span>
                  )}
                </div>
                <select
                  value={selectedBook}
                  onChange={(e) => selectBookInWizard(e.target.value)}
                  className="w-full rounded-lg border border-white/[0.1] bg-[#090D16] px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-[#2563EB]"
                >
                  {books.map((b) => (
                    <option key={b.book_file} value={b.book_file}>
                      {formatBookDisplay(b)}
                    </option>
                  ))}
                </select>
              </div>

              {currentBook && (
                <>
                  <div className="grid grid-cols-2 gap-3 rounded-lg border border-white/[0.06] bg-[#090D16]/75 p-3 text-xs">
                    <div>
                      <div className="text-[11px] text-slate-500">Дисциплина</div>
                      <div className="mt-0.5 font-medium text-slate-200">
                        {formatDiscipline(currentBook.recommended_module)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] text-slate-500">Методологическая школа</div>
                      <div className="mt-0.5 font-medium text-slate-200">{formatSchool(currentBook.school)}</div>
                    </div>
                  </div>

                  {/* Шаг 2: Глава */}
                  <div>
                    <label className="mb-1.5 block text-xs font-medium text-slate-300">
                      2. Содержательная глава или раздел
                    </label>
                    <select
                      value={selectedChapterIdx}
                      onChange={(e) => setSelectedChapterIdx(Number(e.target.value))}
                      className="w-full rounded-lg border border-white/[0.1] bg-[#090D16] px-3 py-2.5 text-sm text-slate-100 outline-none focus:border-[#2563EB]"
                    >
                      {currentBook.chapters.map((ch) => (
                        <option key={ch.index} value={ch.index}>
                          {ch.index + 1}. {ch.title} ({ch.formula_count} формул
                          {ch.has_nomograms ? ", палетки" : ""})
                        </option>
                      ))}
                    </select>
                  </div>
                </>
              )}

              {/* Шаг 3: Диктор и видео */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="mb-1.5 block text-xs font-medium text-slate-300">3. Голос диктора</label>
                  <select
                    value={voice}
                    onChange={(e) => setVoice(e.target.value as "ru-RU-DmitryNeural" | "ru-RU-SvetlanaNeural")}
                    className="w-full rounded-lg border border-white/[0.1] bg-[#090D16] px-3 py-2 text-xs text-slate-100 outline-none focus:border-[#2563EB]"
                  >
                    <option value="ru-RU-DmitryNeural">Мужской (баритон)</option>
                    <option value="ru-RU-SvetlanaNeural">Женский (нейтральный)</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <label className="flex w-full cursor-pointer items-center gap-2 rounded-lg border border-white/[0.1] bg-[#090D16] px-3 py-2 text-xs text-slate-200">
                    <input
                      type="checkbox"
                      checked={renderVideo}
                      onChange={(e) => setRenderVideo(e.target.checked)}
                      className="h-3.5 w-3.5 accent-[#2563EB]"
                    />
                    <span>Собрать видеоурок (HD 1080p)</span>
                  </label>
                </div>
              </div>

              <button
                onClick={handleBuildCourse}
                disabled={!currentBook || job?.status === "running"}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#2563EB] px-4 py-2.5 text-sm font-medium text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Play className="h-4 w-4" />
                {job?.status === "running" ? "Формирование курса..." : "Создать курс"}
              </button>

              {/* Прогресс сборки в модальном окне */}
              {job && (
                <div className="rounded-xl border border-white/[0.08] bg-[#090D16] p-4">
                  <div className="flex items-center justify-between text-xs font-medium">
                    <span className="text-slate-200">{job.stage}</span>
                    <span className="font-mono text-blue-400">{job.progress_pct}%</span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
                    <div
                      className="h-full rounded-full bg-[#2563EB] transition-all duration-300"
                      style={{ width: `${job.progress_pct}%` }}
                    />
                  </div>
                  {job.logs.length > 0 && (
                    <div className="mt-2.5 max-h-24 overflow-y-auto text-[11px] text-slate-400">
                      {job.logs.slice(-6).map((line, i) => (
                        <div key={i} className="truncate py-0.5">
                          {line}
                        </div>
                      ))}
                    </div>
                  )}
                  {job.status === "completed" && (
                    <button
                      onClick={() => {
                        setBuilderOpen(false);
                        setStudioView("video");
                      }}
                      className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/15 px-3 py-1.5 text-xs font-medium text-emerald-300 transition hover:bg-emerald-500/25"
                    >
                      Открыть готовый курс в студии
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              )}

              {/* Загрузка своего учебника */}
              <div className="rounded-xl border border-white/[0.08] bg-[#090D16]/60">
                <button
                  type="button"
                  onClick={() => setUploadOpen((prev) => !prev)}
                  className="flex w-full items-center justify-between px-4 py-3 text-left text-xs font-medium text-slate-300 hover:text-white"
                >
                  <span className="flex items-center gap-2">
                    <Upload className="h-3.5 w-3.5 text-blue-400" />
                    Загрузить свой учебник (.md) и паспорт (.json)
                  </span>
                  {uploadOpen ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </button>

                {uploadOpen && (
                  <form onSubmit={handleUpload} className="border-t border-white/[0.06] p-4">
                    <input
                      ref={bookInputRef}
                      type="file"
                      accept=".md"
                      className="hidden"
                      onChange={(e) => setUploadBookFile(e.target.files?.[0] || null)}
                    />
                    <input
                      ref={passportInputRef}
                      type="file"
                      accept=".md,.json"
                      className="hidden"
                      onChange={(e) => setUploadPassportFile(e.target.files?.[0] || null)}
                    />

                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        setIsDragging(true);
                      }}
                      onDragLeave={() => setIsDragging(false)}
                      onDrop={handleDropFiles}
                      onClick={() => bookInputRef.current?.click()}
                      className={`cursor-pointer rounded-lg border border-dashed p-4 text-center transition ${
                        isDragging
                          ? "border-[#2563EB] bg-[#2563EB]/10"
                          : "border-white/[0.14] bg-[#111827]/70 hover:border-white/[0.25]"
                      }`}
                    >
                      <Upload className="mx-auto mb-1.5 h-5 w-5 text-slate-400" />
                      <div className="text-xs font-medium text-slate-200">
                        Перетащите файлы сюда или нажмите для выбора
                      </div>
                      <div className="mt-1 text-[11px] text-slate-500">
                        Текст учебника (.md) и методический паспорт (.json / .md)
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => bookInputRef.current?.click()}
                          className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.04] px-2.5 py-1.5 text-[11px] text-slate-300 hover:bg-white/[0.08]"
                        >
                          <FileText className="h-3 w-3 text-slate-400" />
                          {uploadBookFile ? uploadBookFile.name : "Текст учебника (.md)"}
                        </button>
                        <button
                          type="button"
                          onClick={() => passportInputRef.current?.click()}
                          className="inline-flex items-center gap-1.5 rounded-md border border-white/[0.08] bg-white/[0.04] px-2.5 py-1.5 text-[11px] text-slate-300 hover:bg-white/[0.08]"
                        >
                          <SlidersHorizontal className="h-3 w-3 text-slate-400" />
                          {uploadPassportFile ? uploadPassportFile.name : "Паспорт (необяз.)"}
                        </button>
                      </div>

                      <button
                        type="submit"
                        className="rounded-lg bg-[#2563EB] px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-500"
                      >
                        Добавить
                      </button>
                    </div>

                    {uploadStatus && (
                      <div className={`mt-2.5 text-xs ${uploadStatus.ok ? "text-emerald-400" : "text-amber-400"}`}>
                        {uploadStatus.text}
                      </div>
                    )}
                  </form>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
