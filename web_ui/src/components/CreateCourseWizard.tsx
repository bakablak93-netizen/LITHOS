import React, { useEffect, useRef, useState } from "react";
import { AlertCircle, ArrowLeft, BookOpen, CheckCircle2, FileText, Loader2, Upload, X } from "lucide-react";

interface LibraryBookItem {
  book_file: string;
  title: string;
}

interface DetectedChapter {
  index: number;
  title: string;
  start_page: number;
  end_page: number;
  preview: string;
  is_t3_default?: boolean;
}

interface InspectedBook {
  book_id: string;
  library_book?: string;
  file_name: string;
  format: string;
  total_pages: number;
  chapters: DetectedChapter[];
  warnings: string[];
  is_library: boolean;
}

interface BuildJob {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  progress_pct: number;
  stage: string;
  chapter_title: string;
  start_page: number;
  end_page: number;
  course_id: string | null;
  error: string | null;
  pipeline_used: string;
}

interface CreateCourseWizardProps {
  libraryBooks: LibraryBookItem[];
  onClose: () => void;
  onCourseReady: (courseId: string) => void;
}

const ACTIVE_JOB_KEY = "lithos_active_build_job_id";

export const CreateCourseWizard: React.FC<CreateCourseWizardProps> = ({
  libraryBooks,
  onClose,
  onCourseReady,
}) => {
  const [sourceTab, setSourceTab] = useState<"upload" | "library">("upload");
  const [dragging, setDragging] = useState(false);
  const [inspecting, setInspecting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [book, setBook] = useState<InspectedBook | null>(null);

  const [selectedChapterIdx, setSelectedChapterIdx] = useState<number>(0);
  const [chapterTitle, setChapterTitle] = useState<string>("");
  const [startPage, setStartPage] = useState<number>(1);
  const [endPage, setEndPage] = useState<number>(5);

  const [job, setJob] = useState<BuildJob | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Восстановление активной или завершённой сборки после обновления страницы
  useEffect(() => {
    const savedJobId = localStorage.getItem(ACTIVE_JOB_KEY);
    if (!savedJobId) return;
    fetch(`/api/t3/jobs/${savedJobId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data: BuildJob | null) => {
        if (data) setJob(data);
      })
      .catch(() => {});
  }, []);

  // Опрос статуса реальной сборки
  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const timer = window.setInterval(async () => {
      try {
        const res = await fetch(`/api/t3/jobs/${job.job_id}`);
        if (!res.ok) return;
        const next: BuildJob = await res.json();
        setJob(next);
        if (next.status === "completed" || next.status === "failed") {
          window.clearInterval(timer);
        }
      } catch {
        // сохраняем попытку
      }
    }, 650);
    return () => window.clearInterval(timer);
  }, [job?.job_id, job?.status]);

  const applyChapter = (ch: DetectedChapter) => {
    setSelectedChapterIdx(ch.index);
    setChapterTitle(ch.title);
    setStartPage(ch.start_page);
    setEndPage(ch.end_page);
  };

  const inspectFile = async (file: File) => {
    setErrorMsg(null);
    setInspecting(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await fetch("/api/t3/books/inspect", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.detail || "Не удалось разобрать файл. Проверьте формат и попробуйте ещё раз.");
        return;
      }
      setBook(data);
      if (data.chapters?.length) applyChapter(data.chapters[0]);
    } catch {
      setErrorMsg("Сервер временно недоступен. Проверьте, что backend запущен на порту 8000.");
    } finally {
      setInspecting(false);
    }
  };

  const inspectLibraryBook = async (bookFile: string) => {
    setErrorMsg(null);
    setInspecting(true);
    try {
      const fd = new FormData();
      fd.append("library_book", bookFile);
      const res = await fetch("/api/t3/books/inspect", { method: "POST", body: fd });
      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.detail || "Не удалось открыть книгу из библиотеки.");
        return;
      }
      setBook(data);
      if (data.chapters?.length) applyChapter(data.chapters[0]);
    } catch {
      setErrorMsg("Не удалось связаться с сервером.");
    } finally {
      setInspecting(false);
    }
  };

  const startBuild = async () => {
    if (!book) return;
    if (startPage < 1 || endPage < startPage) {
      setErrorMsg("Проверьте диапазон страниц: конечная страница не может быть меньше начальной.");
      return;
    }
    setErrorMsg(null);
    try {
      const res = await fetch("/api/t3/books/build-custom", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          book_id: book.book_id,
          library_book: book.library_book || "",
          chapter_title: chapterTitle.trim() || book.file_name,
          start_page: startPage,
          end_page: endPage,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setErrorMsg(data.detail || "Не удалось запустить сборку курса.");
        return;
      }
      localStorage.setItem(ACTIVE_JOB_KEY, data.job_id);
      setJob(data);
    } catch {
      setErrorMsg("Ошибка соединения при запуске сборки.");
    }
  };

  const resetJob = () => {
    localStorage.removeItem(ACTIVE_JOB_KEY);
    setJob(null);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="wizard-title"
    >
      <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-2xl bg-[#15181F] p-6 text-[#F4F1EA] shadow-2xl">
        <div className="flex items-start justify-between gap-4 pb-5">
          <div>
            <h2 id="wizard-title" className="text-2xl font-bold text-[#F4F1EA]">
              Создать курс из главы
            </h2>
            <p className="mt-1 text-sm text-[#A39E93]">
              Выберите свою книгу или готовую главу — конвейер соберёт урок, задания с проверкой и карточки.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть окно создания курса"
            className="rounded-lg p-2 text-[#A39E93] hover:bg-white/[0.06] hover:text-[#F4F1EA]"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Ошибка с сохранением выбора */}
        {errorMsg && (
          <div
            role="alert"
            className="mb-5 flex items-start gap-3 rounded-xl bg-[#F43F5E]/10 px-4 py-3 text-sm text-[#FDA4AF]"
          >
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-[#F43F5E]" />
            <div>{errorMsg}</div>
          </div>
        )}

        {/* Шаг 3: Статус текущей или завершённой сборки */}
        {job ? (
          <div className="space-y-5 rounded-xl bg-[#1B1F28] p-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-xs text-[#A39E93]">{job.pipeline_used}</div>
                <div className="mt-1 text-lg font-semibold text-[#F4F1EA]">{job.chapter_title}</div>
                <div className="text-sm text-[#A39E93]">
                  Выбранный диапазон: стр. {job.start_page}–{job.end_page}
                </div>
              </div>
              {job.status === "completed" ? (
                <CheckCircle2 className="h-7 w-7 shrink-0 text-[#10B981]" />
              ) : job.status === "failed" ? (
                <AlertCircle className="h-7 w-7 shrink-0 text-[#F43F5E]" />
              ) : (
                <Loader2 className="h-7 w-7 shrink-0 animate-spin text-[#D97736]" />
              )}
            </div>

            <div>
              <div className="mb-1.5 flex items-center justify-between text-sm">
                <span>{job.stage}</span>
                <span className="font-mono text-[#A39E93]">{job.progress_pct}%</span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-white/[0.08]">
                <div
                  className={`h-full transition-all duration-300 ${
                    job.status === "failed"
                      ? "bg-[#F43F5E]"
                      : job.status === "completed"
                      ? "bg-[#10B981]"
                      : "bg-[#D97736]"
                  }`}
                  style={{ width: `${job.progress_pct}%` }}
                />
              </div>
            </div>

            {job.error && (
              <div className="rounded-lg bg-[#F43F5E]/10 p-3 text-sm text-[#FDA4AF]">{job.error}</div>
            )}

            <div className="flex flex-wrap items-center gap-3 pt-2">
              {job.status === "completed" && job.course_id && (
                <button
                  type="button"
                  onClick={() => {
                    localStorage.removeItem(ACTIVE_JOB_KEY);
                    onCourseReady(job.course_id!);
                  }}
                  className="rounded-xl bg-[#D97736] px-5 py-2.5 text-sm font-semibold text-[#0E1014] hover:bg-[#E58A4C]"
                >
                  Открыть готовый курс
                </button>
              )}
              <button
                type="button"
                onClick={resetJob}
                className="rounded-xl bg-white/[0.06] px-4 py-2.5 text-sm font-medium text-[#F4F1EA] hover:bg-white/[0.12]"
              >
                {job.status === "failed" ? "Повторить сборку" : "Собрать другую главу"}
              </button>
            </div>
          </div>
        ) : !book ? (
          /* Шаг 1: Выбор источника (Загрузить свою книгу | Выбрать из библиотеки) */
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-2 rounded-xl bg-[#0E1014] p-1">
              <button
                type="button"
                onClick={() => {
                  setSourceTab("upload");
                  setErrorMsg(null);
                }}
                className={`flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition ${
                  sourceTab === "upload" ? "bg-[#D97736] text-[#0E1014]" : "text-[#A39E93] hover:text-[#F4F1EA]"
                }`}
              >
                <Upload className="h-4 w-4" />
                Загрузить свою книгу
              </button>
              <button
                type="button"
                onClick={() => {
                  setSourceTab("library");
                  setErrorMsg(null);
                }}
                className={`flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition ${
                  sourceTab === "library" ? "bg-[#D97736] text-[#0E1014]" : "text-[#A39E93] hover:text-[#F4F1EA]"
                }`}
              >
                <BookOpen className="h-4 w-4" />
                Выбрать из библиотеки
              </button>
            </div>

            {sourceTab === "upload" ? (
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragging(true);
                }}
                onDragLeave={() => setDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragging(false);
                  const f = e.dataTransfer.files?.[0];
                  if (f) inspectFile(f);
                }}
                className={`flex flex-col items-center justify-center rounded-xl border border-dashed px-6 py-10 text-center transition ${
                  dragging ? "border-[#D97736] bg-[#D97736]/10" : "border-white/20 bg-[#1B1F28]/60"
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.md,.txt"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) inspectFile(f);
                  }}
                />
                {inspecting ? (
                  <div className="flex items-center gap-3 text-sm text-[#F4F1EA]">
                    <Loader2 className="h-5 w-5 animate-spin text-[#D97736]" />
                    Читаю страницы и определяю границы глав…
                  </div>
                ) : (
                  <>
                    <FileText className="h-9 w-9 text-[#D97736]" />
                    <div className="mt-3 text-base font-semibold">Перетащите файл сюда или выберите на диске</div>
                    <p className="mt-1 max-w-md text-sm text-[#A39E93]">
                      Поддерживаются <strong>текстовый PDF (.pdf)</strong>, <strong>Markdown (.md)</strong> и{" "}
                      <strong>текст (.txt)</strong>. Для PDF-сканов без текстового слоя локальный OCR не установлен.
                    </p>
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      className="mt-5 rounded-xl bg-[#D97736] px-5 py-2.5 text-sm font-semibold text-[#0E1014] hover:bg-[#E58A4C]"
                    >
                      Выбрать файл
                    </button>
                  </>
                )}
              </div>
            ) : (
              <div className="space-y-2">
                {libraryBooks.map((lb) => (
                  <button
                    key={lb.book_file}
                    type="button"
                    disabled={inspecting}
                    onClick={() => inspectLibraryBook(lb.book_file)}
                    className="flex w-full items-center justify-between gap-3 rounded-xl bg-[#1B1F28] px-4 py-3.5 text-left transition hover:bg-[#232836]"
                  >
                    <div>
                      <div className="text-sm font-semibold text-[#F4F1EA]">{lb.title}</div>
                      <div className="text-xs text-[#A39E93]">{lb.book_file}</div>
                    </div>
                    <span className="text-xs font-medium text-[#D97736]">Выбрать →</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Шаг 2: Выбор главы / ручной диапазон страниц + предпросмотр */
          <div className="space-y-5">
            <div className="flex items-center justify-between gap-3 rounded-xl bg-[#1B1F28] px-4 py-3">
              <div>
                <div className="text-sm font-semibold">{book.file_name}</div>
                <div className="text-xs text-[#A39E93]">
                  Формат: {book.format.toUpperCase()} · Всего страниц: {book.total_pages}
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setBook(null);
                  setErrorMsg(null);
                }}
                className="inline-flex items-center gap-1 text-xs font-medium text-[#A39E93] hover:text-[#F4F1EA]"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                Другой файл
              </button>
            </div>

            {book.warnings.length > 0 && (
              <div className="rounded-xl bg-[#F59E0B]/10 px-4 py-2.5 text-xs text-[#FCD34D]">
                {book.warnings.join(" ")}
              </div>
            )}

            <div>
              <label className="mb-2 block text-sm font-medium text-[#F4F1EA]">
                Выберите главу (или уточните страницы ниже)
              </label>
              <div className="max-h-52 space-y-2 overflow-y-auto pr-1">
                {book.chapters.map((ch) => {
                  const active = selectedChapterIdx === ch.index;
                  return (
                    <button
                      key={ch.index}
                      type="button"
                      onClick={() => applyChapter(ch)}
                      className={`w-full rounded-xl px-4 py-3 text-left transition ${
                        active ? "bg-[#D97736]/15 ring-1 ring-[#D97736]" : "bg-[#1B1F28] hover:bg-[#232836]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-semibold text-[#F4F1EA]">{ch.title}</span>
                        <span className="shrink-0 font-mono text-xs text-[#A39E93]">
                          стр. {ch.start_page}–{ch.end_page}
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-[#A39E93]">{ch.preview}</p>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Ручное уточнение диапазона страниц */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="sm:col-span-1">
                <label htmlFor="wiz-start-page" className="mb-1 block text-xs text-[#A39E93]">
                  Стартовая страница
                </label>
                <input
                  id="wiz-start-page"
                  type="number"
                  min={1}
                  max={book.total_pages}
                  value={startPage}
                  onChange={(e) => setStartPage(Number(e.target.value))}
                  className="w-full rounded-lg border border-white/15 bg-[#0E1014] px-3 py-2 text-sm text-[#F4F1EA]"
                />
              </div>
              <div className="sm:col-span-1">
                <label htmlFor="wiz-end-page" className="mb-1 block text-xs text-[#A39E93]">
                  Конечная страница
                </label>
                <input
                  id="wiz-end-page"
                  type="number"
                  min={1}
                  max={book.total_pages}
                  value={endPage}
                  onChange={(e) => setEndPage(Number(e.target.value))}
                  className="w-full rounded-lg border border-white/15 bg-[#0E1014] px-3 py-2 text-sm text-[#F4F1EA]"
                />
              </div>
              <div className="sm:col-span-1">
                <label htmlFor="wiz-ch-title" className="mb-1 block text-xs text-[#A39E93]">
                  Название курса
                </label>
                <input
                  id="wiz-ch-title"
                  type="text"
                  value={chapterTitle}
                  onChange={(e) => setChapterTitle(e.target.value)}
                  className="w-full rounded-lg border border-white/15 bg-[#0E1014] px-3 py-2 text-sm text-[#F4F1EA]"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <span className="text-xs text-[#A39E93]">
                Будет собрано: стр. {startPage}–{endPage} · урок, задания и карточки
              </span>
              <button
                type="button"
                onClick={startBuild}
                className="rounded-xl bg-[#D97736] px-6 py-3 text-sm font-semibold text-[#0E1014] hover:bg-[#E58A4C]"
              >
                Собрать курс
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
