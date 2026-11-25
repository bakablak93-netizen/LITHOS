import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Compass,
  FlaskConical,
  Loader2,
  Play,
  Plus,
  Sparkles,
  Video,
} from "lucide-react";
import { LithosParticles, ParticleShapeMode } from "./components/LithosParticles";
import { CourseCoverSvg } from "./components/CourseCoverSvg";
import { CreateCourseWizard } from "./components/CreateCourseWizard";
import { CourseWorkspace, T3CoursePackage } from "./components/CourseWorkspace";
import { GuidedLabWrapper } from "./components/GuidedLabWrapper";

interface T3CourseSummary {
  course_id: string;
  book_file: string;
  pdf_file: string;
  book_title: string;
  chapter_title: string;
  is_training: boolean;
  is_custom?: boolean;
  steps_count: number;
  tasks_count: number;
  flashcards_count: number;
  registry_passed: boolean;
  registry_units_total: number;
  needs_model_steps: number;
  offline_html_url: string;
  offline_zip_url: string;
  offline_package_size_mb: number;
  media_passports_count: number;
}

interface LastCourseProgress {
  course_id: string;
  title: string;
  stepIdx: number;
  totalSteps: number;
}

type ViewMode = "home" | "labs";
type LibraryFilter = "all" | "video" | "custom";

const ACTIVE_JOB_KEY = "lithos_active_build_job_id";

export function App() {
  const [viewMode, setViewMode] = useState<ViewMode>("home");
  const [courses, setCourses] = useState<T3CourseSummary[]>([]);
  const [loadingList, setLoadingList] = useState<boolean>(true);
  const [listError, setListError] = useState<string | null>(null);

  const [activeCourse, setActiveCourse] = useState<T3CoursePackage | null>(null);
  const [openingCourseId, setOpeningCourseId] = useState<string | null>(null);
  const [openError, setOpenError] = useState<string | null>(null);

  const [wizardOpen, setWizardOpen] = useState<boolean>(() => {
    try {
      return Boolean(localStorage.getItem(ACTIVE_JOB_KEY));
    } catch {
      return false;
    }
  });

  const [particleMode, setParticleMode] = useState<ParticleShapeMode>("strata");
  const [filter, setFilter] = useState<LibraryFilter>("all");
  const [labChoice, setLabChoice] = useState<"latyshova" | "basniev">("latyshova");
  const [lastCourse, setLastCourse] = useState<LastCourseProgress | null>(null);

  const readLastCourse = useCallback(() => {
    try {
      const raw = localStorage.getItem("lithos_last_course");
      if (!raw) return;
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed.course_id === "string") {
        setLastCourse(parsed);
      }
    } catch {
      // ignore
    }
  }, []);

  const fetchCourses = useCallback(async () => {
    setLoadingList(true);
    setListError(null);
    try {
      const res = await fetch("/api/t3/courses");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: T3CourseSummary[] = await res.json();
      setCourses(data);
    } catch (e: unknown) {
      setListError(e instanceof Error ? e.message : "Не удалось загрузить библиотеку курсов.");
    } finally {
      setLoadingList(false);
    }
  }, []);

  useEffect(() => {
    fetchCourses();
    readLastCourse();
  }, [fetchCourses, readLastCourse]);

  const openCourse = useCallback(async (courseId: string) => {
    setOpeningCourseId(courseId);
    setOpenError(null);
    try {
      const res = await fetch(`/api/t3/courses/${encodeURIComponent(courseId)}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Ошибка загрузки курса (HTTP ${res.status})`);
      }
      const pkg: T3CoursePackage = await res.json();
      setActiveCourse(pkg);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e: unknown) {
      setOpenError(e instanceof Error ? e.message : "Не удалось открыть курс.");
    } finally {
      setOpeningCourseId(null);
    }
  }, []);

  const handleCloseCourse = () => {
    setActiveCourse(null);
    readLastCourse();
    fetchCourses();
  };

  const handleWizardCourseReady = async (courseId: string) => {
    setWizardOpen(false);
    await fetchCourses();
    await openCourse(courseId);
  };

  const libraryBooks = useMemo(
    () =>
      courses
        .filter((c) => !c.is_custom)
        .map((c) => ({
          book_file: c.book_file,
          title: `${c.book_title} — ${c.chapter_title}`,
        })),
    [courses]
  );

  const hasCustomCourses = useMemo(() => courses.some((c) => c.is_custom), [courses]);

  const filteredCourses = useMemo(() => {
    if (filter === "video") return courses.filter((c) => c.media_passports_count > 0);
    if (filter === "custom") return courses.filter((c) => c.is_custom);
    return courses;
  }, [courses, filter]);

  const handleCardHover = (courseId: string) => {
    const id = courseId.toLowerCase();
    if (id.includes("latyshova")) setParticleMode("wellbore");
    else if (id.includes("basniev")) setParticleMode("funnel");
    else setParticleMode("strata");
  };

  const particlesActive = !activeCourse && viewMode === "home" && !wizardOpen;

  return (
    <div className="min-h-screen overflow-x-hidden bg-[#0E1014] text-[#F4F1EA] selection:bg-[#D97736]/30 selection:text-[#F4F1EA]">
      <a href="#main-content" className="atlas-skip-link">
        Перейти к содержимому
      </a>

      {/* Компактная шапка без дублирования навигации */}
      <header className="sticky top-0 z-40 border-b border-white/[0.08] bg-[#0E1014]/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-6">
            <button
              type="button"
              onClick={() => {
                setActiveCourse(null);
                setViewMode("home");
                readLastCourse();
              }}
              className="flex items-center gap-2.5 text-left"
              aria-label="LITHOS — на главную"
            >
              <span className="h-2.5 w-2.5 rounded-full bg-[#D97736]" aria-hidden="true" />
              <span className="font-display text-lg font-bold tracking-tight text-[#F4F1EA]">
                LITHOS
              </span>
            </button>

            <nav aria-label="Основная навигация" className="hidden items-center gap-1 sm:flex">
              <button
                type="button"
                onClick={() => {
                  setActiveCourse(null);
                  setViewMode("home");
                }}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  !activeCourse && viewMode === "home"
                    ? "bg-white/[0.08] text-[#F4F1EA]"
                    : "text-[#A39E93] hover:text-[#F4F1EA]"
                }`}
              >
                Атлас
              </button>
              <button
                type="button"
                onClick={() => {
                  setActiveCourse(null);
                  setViewMode("labs");
                }}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  !activeCourse && viewMode === "labs"
                    ? "bg-white/[0.08] text-[#F4F1EA]"
                    : "text-[#A39E93] hover:text-[#F4F1EA]"
                }`}
              >
                <FlaskConical className="h-3.5 w-3.5" />
                Лаборатории
              </button>
            </nav>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setActiveCourse(null);
                setViewMode("labs");
              }}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/[0.1] px-2.5 py-1.5 text-xs font-medium text-[#D6D2C7] hover:bg-white/[0.05] sm:hidden"
            >
              <FlaskConical className="h-3.5 w-3.5" />
              3D
            </button>
            <button
              type="button"
              onClick={() => setWizardOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#D97736] px-3.5 py-2 text-xs font-semibold text-[#0E1014] transition hover:bg-[#E58A4A] sm:text-sm"
            >
              <Plus className="h-4 w-4" />
              <span>Создать курс</span>
            </button>
          </div>
        </div>
      </header>

      <main id="main-content" className="mx-auto max-w-6xl px-4 pb-16 pt-6 sm:px-6 sm:pt-10">
        {openError && (
          <div className="mb-6 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
            {openError}
          </div>
        )}

        {/* Экран открытого курса */}
        {activeCourse ? (
          <CourseWorkspace key={activeCourse.course_id} pkg={activeCourse} onBack={handleCloseCourse} />
        ) : viewMode === "labs" ? (
          /* Экран 3D-лабораторий */
          <section className="space-y-6">
            <div className="flex flex-wrap items-end justify-between gap-4 border-b border-white/[0.08] pb-5">
              <div>
                <p className="text-xs font-medium text-[#D97736]">Интерактивные стенды</p>
                <h1 className="mt-1 font-display text-2xl font-bold text-[#F4F1EA] sm:text-3xl">
                  3D-лаборатории по главам
                </h1>
                <p className="mt-1.5 max-w-2xl text-sm text-[#A39E93]">
                  Меняйте физические параметры и сразу проверяйте гипотезы по каротажу и гидродинамике.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setViewMode("home")}
                className="rounded-lg border border-white/[0.1] px-3.5 py-2 text-sm text-[#D6D2C7] hover:bg-white/[0.05]"
              >
                К библиотеке курсов
              </button>
            </div>
            <GuidedLabWrapper initialLab={labChoice} onSelectLab={setLabChoice} />
          </section>
        ) : (
          /* Главный экран: Hero + 300 000 частиц + Библиотека курсов */
          <div className="space-y-12 sm:space-y-16">
            <section className="grid items-center gap-8 lg:grid-cols-12 lg:gap-10">
              {/* Левая колонка: главный смысл и CTA видны без прокрутки */}
              <div className="space-y-5 lg:col-span-6">
                <div className="inline-flex items-center gap-2 rounded-full border border-white/[0.1] bg-[#151922] px-3 py-1 text-xs text-[#A39E93]">
                  <Compass className="h-3.5 w-3.5 text-[#D97736]" />
                  <span>Геологический атлас · Глава → Курс</span>
                </div>

                <h1 className="font-display text-3xl font-bold leading-[1.12] tracking-tight text-[#F4F1EA] sm:text-5xl">
                  Превратите главу книги в курс
                </h1>

                <p className="max-w-xl text-base leading-relaxed text-[#A39E93] sm:text-lg">
                  Загрузите свою книгу в PDF, Markdown или тексте — либо выберите главу из библиотеки.
                  LITHOS соберёт урок по шагам, задания с проверкой и карточки повторения со ссылками на страницы.
                </p>

                <div className="flex flex-wrap items-center gap-3 pt-1">
                  <button
                    type="button"
                    data-testid="hero-create-course-btn"
                    onClick={() => setWizardOpen(true)}
                    className="inline-flex items-center gap-2 rounded-xl bg-[#D97736] px-5 py-3 text-sm font-semibold text-[#0E1014] shadow-lg shadow-[#D97736]/15 transition hover:bg-[#E58A4A] sm:text-base"
                  >
                    <Sparkles className="h-4 w-4" />
                    <span>Создать курс из главы</span>
                  </button>

                  <button
                    type="button"
                    data-testid="hero-example-btn"
                    onClick={() => openCourse("t3_train_latyshova")}
                    disabled={openingCourseId !== null}
                    className="inline-flex items-center gap-2 rounded-xl border border-white/[0.14] bg-[#151922] px-4 py-3 text-sm font-medium text-[#F4F1EA] transition hover:border-white/[0.25] hover:bg-[#1B202C] sm:text-base"
                  >
                    {openingCourseId === "t3_train_latyshova" ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4 text-[#D97736]" />
                    )}
                    <span>Посмотреть пример</span>
                  </button>
                </div>

                {/* Быстрый возврат к последнему курсу, если есть сохранённый прогресс */}
                {lastCourse && (
                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={() => openCourse(lastCourse.course_id)}
                      className="inline-flex max-w-full items-center gap-3 rounded-xl border border-[#D97736]/30 bg-[#151922]/90 px-4 py-2.5 text-left transition hover:border-[#D97736]/60"
                    >
                      <BookOpen className="h-4 w-4 shrink-0 text-[#D97736]" />
                      <div className="min-w-0">
                        <div className="text-xs text-[#A39E93]">
                          Продолжить курс · шаг {lastCourse.stepIdx + 1} из {lastCourse.totalSteps}
                        </div>
                        <div className="truncate text-sm font-medium text-[#F4F1EA]">
                          {lastCourse.title}
                        </div>
                      </div>
                      <ArrowRight className="h-4 w-4 shrink-0 text-[#D97736]" />
                    </button>
                  </div>
                )}
              </div>

              {/* Правая колонка: 300 000 GPU-частиц */}
              <div className="lg:col-span-6">
                <LithosParticles
                  mode={particleMode}
                  onModeChange={setParticleMode}
                  active={particlesActive}
                  className="h-[300px] sm:h-[380px] lg:h-[430px]"
                />
              </div>
            </section>

            {/* Библиотека готовых и пользовательских курсов */}
            <section aria-labelledby="library-heading" className="space-y-6">
              <div className="flex flex-wrap items-end justify-between gap-4 border-b border-white/[0.08] pb-4">
                <div>
                  <h2
                    id="library-heading"
                    className="font-display text-2xl font-bold text-[#F4F1EA]"
                  >
                    Библиотека курсов
                  </h2>
                  <p className="mt-1 text-sm text-[#A39E93]">
                    Готовые главы по геологии и курсы, собранные из ваших книг.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setFilter("all")}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                      filter === "all"
                        ? "bg-[#F4F1EA] text-[#0E1014]"
                        : "bg-[#151922] text-[#A39E93] hover:text-[#F4F1EA]"
                    }`}
                  >
                    Все ({courses.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setFilter("video")}
                    className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                      filter === "video"
                        ? "bg-[#F4F1EA] text-[#0E1014]"
                        : "bg-[#151922] text-[#A39E93] hover:text-[#F4F1EA]"
                    }`}
                  >
                    <Video className="h-3.5 w-3.5" />
                    С видео ({courses.filter((c) => c.media_passports_count > 0).length})
                  </button>
                  {hasCustomCourses && (
                    <button
                      type="button"
                      onClick={() => setFilter("custom")}
                      className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                        filter === "custom"
                          ? "bg-[#D97736] text-[#0E1014]"
                          : "bg-[#151922] text-[#D97736] hover:bg-[#1B202C]"
                      }`}
                    >
                      Мои книги ({courses.filter((c) => c.is_custom).length})
                    </button>
                  )}
                </div>
              </div>

              {loadingList ? (
                <div className="flex items-center gap-3 py-10 text-sm text-[#A39E93]">
                  <Loader2 className="h-4 w-4 animate-spin text-[#D97736]" />
                  <span>Загружаем библиотеку курсов…</span>
                </div>
              ) : listError ? (
                <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-200">
                  {listError}
                </div>
              ) : (
                <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
                  {filteredCourses.map((c) => {
                    const isOpening = openingCourseId === c.course_id;
                    return (
                      <article
                        key={c.course_id}
                        onMouseEnter={() => handleCardHover(c.course_id)}
                        onFocus={() => handleCardHover(c.course_id)}
                        className="group flex flex-col overflow-hidden rounded-2xl border border-white/[0.08] bg-[#151922] transition hover:border-[#D97736]/45"
                      >
                        <div className="relative aspect-[2/1] w-full overflow-hidden border-b border-white/[0.06] bg-[#11151E]">
                          <CourseCoverSvg
                            courseId={c.course_id}
                            title={c.chapter_title || c.book_title}
                            className="h-full w-full object-cover transition duration-500 group-hover:scale-[1.02]"
                          />
                          <div className="absolute left-3 top-3 flex flex-wrap gap-1.5">
                            {c.is_custom && (
                              <span className="rounded-md bg-[#D97736] px-2 py-0.5 text-[11px] font-semibold text-[#0E1014]">
                                Своя книга
                              </span>
                            )}
                            {c.media_passports_count > 0 && (
                              <span className="inline-flex items-center gap-1 rounded-md bg-[#0E1014]/80 px-2 py-0.5 text-[11px] font-medium text-[#F4F1EA] backdrop-blur-sm">
                                <Video className="h-3 w-3 text-[#D97736]" />
                                Видео
                              </span>
                            )}
                          </div>
                        </div>

                        <div className="flex flex-1 flex-col justify-between p-4 sm:p-5">
                          <div>
                            <p className="text-xs text-[#A39E93]">{c.book_title}</p>
                            <h3 className="mt-1 font-display text-base font-semibold leading-snug text-[#F4F1EA]">
                              {c.chapter_title}
                            </h3>
                          </div>

                          <div className="mt-4 flex items-center justify-between gap-2 border-t border-white/[0.06] pt-3">
                            <span className="font-mono text-xs text-[#A39E93]">
                              {c.steps_count} шаг. · {c.tasks_count} зад. · {c.flashcards_count} карт.
                            </span>
                            <button
                              type="button"
                              onClick={() => openCourse(c.course_id)}
                              disabled={openingCourseId !== null}
                              className="inline-flex items-center gap-1 rounded-lg bg-white/[0.06] px-3 py-1.5 text-xs font-medium text-[#F4F1EA] transition hover:bg-[#D97736] hover:text-[#0E1014]"
                            >
                              {isOpening ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <>
                                  <span>Открыть</span>
                                  <ArrowRight className="h-3.5 w-3.5" />
                                </>
                              )}
                            </button>
                          </div>
                        </div>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        )}
      </main>

      {/* Мастер «Своя книга → Глава → Курс» */}
      {wizardOpen && (
        <CreateCourseWizard
          libraryBooks={libraryBooks}
          onClose={() => setWizardOpen(false)}
          onCourseReady={handleWizardCourseReady}
        />
      )}
    </div>
  );
}

export default App;
