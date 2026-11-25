import React, { useEffect, useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Download,
  FlaskConical,
  HelpCircle,
  Layers,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { GuidedLabWrapper } from "./GuidedLabWrapper";

export interface T3CoursePackage {
  course_id: string;
  book_file: string;
  book_title: string;
  chapter_title: string;
  is_training: boolean;
  offline_html_url: string;
  offline_zip_url: string;
  offline_package_size_mb: number;
  steps: Array<{
    step_id: string;
    node_id: string;
    order: number;
    estimated_minutes: number;
    source_heading: string;
    step_title: string;
    summary_2_3_sentences: string;
    explanation_paragraphs: Array<{
      role: string;
      text: string;
      source_citation: string;
      pdf_page: number;
      verbatim_quote?: string;
    }>;
    epistemic_split: {
      observation: string;
      inference: string;
      assumption: string;
    };
    illustration?: {
      illustration_id: string;
      visual_class: string;
      title: string;
      source_ref: string;
      pdf_page: number;
      redraw_caption: string;
      svg_markup?: string;
      origin_label?: string;
    };
    tables?: Array<{ title: string; headers: string[]; rows: string[][] }>;
    video_url?: string | null;
    video_vtt_url?: string | null;
    video_aspect?: string | null;
    data_decision_card?: {
      title: string;
      origin_and_assumptions: string;
      observed_features: Array<{ label: string; value: string }>;
      decision_rule: string;
      rule_limits: string;
      question: string;
      options: Array<{ id: string; label: string; correct: boolean; feedback: string }>;
    } | null;
  }>;
  tasks: Array<{
    task_id: string;
    node_id: string;
    claim_id: string;
    task_type: string;
    prompt: string;
    options: string[];
    correct_answer: unknown;
    explanation: string;
    source_pdf_page: number;
  }>;
  flashcards: Array<{
    card_id: string;
    node_id: string;
    front_question: string;
    back_answer: string;
    source_pdf_page: number;
  }>;
  media_passports: Array<{
    passport_id: string;
    aspect_ratio: string;
    duration_sec: number;
    video_rel_path: string;
    srt_rel_path: string;
    vtt_rel_path?: string;
    audio_report?: {
      synthesis_mode: string;
      integrated_lufs: number;
      measured_wer_pct?: number | null;
      max_word_desync_sec?: number;
    };
  }>;
  registry_report: {
    passed: boolean;
    total_registry_units: number;
    covered_units_count: number;
    excluded_units_count: number;
    manual_verification_required_count: number;
  };
}

type CourseTab = "lesson" | "tasks" | "cards" | "lab";

interface CourseWorkspaceProps {
  pkg: T3CoursePackage;
  onBack: () => void;
}

export const CourseWorkspace: React.FC<CourseWorkspaceProps> = ({ pkg, onBack }) => {
  const storageKey = `lithos_progress_${pkg.course_id}`;
  const [tab, setTab] = useState<CourseTab>("lesson");
  const [stepIdx, setStepIdx] = useState<number>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
      return typeof saved.stepIdx === "number" ? Math.min(saved.stepIdx, Math.max(0, pkg.steps.length - 1)) : 0;
    } catch {
      return 0;
    }
  });
  const [cardMarks, setCardMarks] = useState<Record<string, "know" | "repeat">>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
      return saved.cardMarks || {};
    } catch {
      return {};
    }
  });
  const [flippedCards, setFlippedCards] = useState<Record<string, boolean>>({});
  const [taskInputs, setTaskInputs] = useState<Record<string, unknown>>({});
  const [taskFeedback, setTaskFeedback] = useState<
    Record<string, { is_correct: boolean; explanation: string; source_page?: number }>
  >({});
  const [decisionPick, setDecisionPick] = useState<Record<string, string>>({});
  const [showVerify, setShowVerify] = useState(false);

  // Сохранение прогресса курса и последнего открытого курса для кнопки «Продолжить курс»
  useEffect(() => {
    try {
      localStorage.setItem(storageKey, JSON.stringify({ stepIdx, cardMarks }));
      localStorage.setItem(
        "lithos_last_course",
        JSON.stringify({
          course_id: pkg.course_id,
          title: pkg.chapter_title || pkg.book_title,
          stepIdx,
          totalSteps: pkg.steps.length,
        })
      );
    } catch {
      // ignore
    }
  }, [pkg.course_id, pkg.chapter_title, pkg.book_title, pkg.steps.length, stepIdx, cardMarks, storageKey]);

  const currentStep = pkg.steps[stepIdx] || pkg.steps[0];
  const mp = pkg.media_passports?.[0];

  const resolveMediaUrl = (relPath?: string | null) => {
    if (!relPath) return "";
    if (relPath.startsWith("/outputs/") || relPath.startsWith("http")) return relPath;
    return `/outputs/${pkg.course_id}/${relPath.replace(/^\/+/, "")}`;
  };

  const checkTask = async (taskId: string, answer: unknown) => {
    try {
      const res = await fetch(`/api/t3/courses/${pkg.course_id}/check-task`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_id: taskId, answer }),
      });
      if (res.ok) {
        const data = await res.json();
        setTaskFeedback((prev) => ({
          ...prev,
          [taskId]: {
            is_correct: Boolean(data.is_correct),
            explanation: data.explanation || "",
            source_page: data.source_pdf_page,
          },
        }));
      }
    } catch {
      // ignore
    }
  };

  const initialLab: "latyshova" | "basniev" = pkg.course_id.includes("basniev") ? "basniev" : "latyshova";

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 pt-6 sm:px-6">
      {/* Верхняя полоса навигации курса */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-6">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-2 text-sm font-medium text-[#A39E93] hover:text-[#F4F1EA]"
        >
          <ArrowLeft className="h-4 w-4" />
          К атласу курсов
        </button>

        <div className="flex flex-wrap items-center gap-2">
          {pkg.offline_zip_url && (
            <a
              href={`/api/t3/courses/${pkg.course_id}/download`}
              className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.06] px-3 py-1.5 text-xs font-medium text-[#F4F1EA] hover:bg-white/[0.12]"
            >
              <Download className="h-3.5 w-3.5 text-[#D97736]" />
              Скачать офлайн-курс (.zip)
            </a>
          )}
          <button
            type="button"
            onClick={() => setShowVerify((v) => !v)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.04] px-3 py-1.5 text-xs text-[#A39E93] hover:text-[#F4F1EA]"
          >
            <ShieldCheck className="h-3.5 w-3.5 text-[#10B981]" />
            Верификация
            {showVerify ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Заголовок курса */}
      <header className="pb-6">
        <div className="text-sm text-[#A39E93]">{pkg.book_title}</div>
        <h1 className="mt-1 text-2xl font-bold text-[#F4F1EA] sm:text-3xl">{pkg.chapter_title}</h1>
      </header>

      {/* Скрытая по умолчанию техническая панель верификации для жюри/преподавателя */}
      {showVerify && (
        <section className="mb-6 rounded-xl bg-[#15181F] p-4 text-sm text-[#A39E93]">
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            <span>
              Реестр PDF:{" "}
              <strong className="text-[#10B981]">
                {pkg.registry_report.covered_units_count} / {pkg.registry_report.total_registry_units}
              </strong>{" "}
              (проверено: {pkg.registry_report.passed ? "да" : "нет"})
            </span>
            <span>
              Шагов: <strong className="text-[#F4F1EA]">{pkg.steps.length}</strong> · Заданий:{" "}
              <strong className="text-[#F4F1EA]">{pkg.tasks.length}</strong> · Карточек:{" "}
              <strong className="text-[#F4F1EA]">{pkg.flashcards.length}</strong>
            </span>
            {mp?.audio_report && (
              <span>
                Озвучка ({mp.audio_report.synthesis_mode}):{" "}
                <strong className="text-[#F4F1EA]">{mp.audio_report.integrated_lufs} LUFS</strong>
                {mp.audio_report.measured_wer_pct != null && (
                  <>
                    {" "}
                    · WER <strong className="text-[#10B981]">{mp.audio_report.measured_wer_pct}%</strong>
                  </>
                )}
              </span>
            )}
          </div>
        </section>
      )}

      {/* 4 чистых раздела внутри курса */}
      <nav
        aria-label="Разделы курса"
        className="mb-8 flex flex-wrap gap-2 border-b border-white/[0.08] pb-3"
      >
        {(
          [
            { id: "lesson", label: "Урок", icon: BookOpen, count: `${pkg.steps.length}` },
            { id: "tasks", label: "Задания", icon: HelpCircle, count: `${pkg.tasks.length}` },
            { id: "cards", label: "Карточки", icon: Layers, count: `${pkg.flashcards.length}` },
            { id: "lab", label: "Лаборатория", icon: FlaskConical, count: "" },
          ] as const
        ).map((item) => {
          const Icon = item.icon;
          const active = tab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setTab(item.id)}
              className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-medium transition ${
                active
                  ? "bg-[#D97736] text-[#0E1014]"
                  : "text-[#A39E93] hover:bg-white/[0.05] hover:text-[#F4F1EA]"
              }`}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
              {item.count && (
                <span className={`text-xs ${active ? "text-[#0E1014]/75" : "text-[#A39E93]"}`}>{item.count}</span>
              )}
            </button>
          );
        })}
      </nav>

      {/* ВКЛАДКА 1: УРОК */}
      {tab === "lesson" && currentStep && (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
          {/* Содержание шагов */}
          <aside className="lg:col-span-3">
            <div className="space-y-1.5">
              {pkg.steps.map((st, idx) => (
                <button
                  key={st.step_id}
                  type="button"
                  onClick={() => setStepIdx(idx)}
                  className={`flex w-full items-start gap-3 rounded-xl px-3.5 py-3 text-left transition ${
                    idx === stepIdx
                      ? "bg-[#1B1F28] text-[#F4F1EA] ring-1 ring-[#D97736]/60"
                      : "text-[#A39E93] hover:bg-white/[0.04] hover:text-[#F4F1EA]"
                  }`}
                >
                  <span className="mt-0.5 font-mono text-xs text-[#D97736]">{st.order}</span>
                  <div>
                    <div className="text-sm font-medium leading-snug">{st.step_title}</div>
                    <div className="mt-0.5 text-xs text-[#A39E93]">~{st.estimated_minutes} мин</div>
                  </div>
                </button>
              ))}
            </div>
          </aside>

          {/* Контент шага */}
          <article className="max-w-[70ch] space-y-6 lg:col-span-9">
            <div>
              <div className="text-xs text-[#A39E93]">{currentStep.source_heading}</div>
              <h2 className="mt-1 text-2xl font-bold text-[#F4F1EA]">
                Шаг {currentStep.order}. {currentStep.step_title}
              </h2>
              <p className="mt-3 text-base text-[#F4F1EA]/90">{currentStep.summary_2_3_sentences}</p>
            </div>

            {/* Видеоплеер (если к шагу или курсу привязан MP4) */}
            {(currentStep.video_url || (stepIdx === 0 && mp?.video_rel_path)) && (
              <div className="space-y-2.5 rounded-2xl bg-[#15181F] p-4">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[#A39E93]">
                  <span>
                    Учебный ролик ({currentStep.video_aspect || mp?.aspect_ratio || "16:9"}) · Симуляция по модели курса
                  </span>
                  {mp?.srt_rel_path && (
                    <a
                      href={resolveMediaUrl(mp.srt_rel_path)}
                      download
                      className="text-[#D97736] hover:underline"
                    >
                      Скачать субтитры (.srt)
                    </a>
                  )}
                </div>
                <video
                  key={resolveMediaUrl(currentStep.video_url || mp?.video_rel_path)}
                  controls
                  playsInline
                  preload="metadata"
                  className="max-h-[480px] w-full rounded-xl bg-black"
                >
                  <source src={resolveMediaUrl(currentStep.video_url || mp?.video_rel_path)} type="video/mp4" />
                  {(currentStep.video_vtt_url || mp?.vtt_rel_path) && (
                    <track
                      kind="subtitles"
                      srcLang="ru"
                      label="Русские субтитры"
                      src={resolveMediaUrl(currentStep.video_vtt_url || mp?.vtt_rel_path)}
                      default
                    />
                  )}
                </video>
              </div>
            )}

            {/* Векторная иллюстрация шага с честной маркировкой происхождения */}
            {currentStep.illustration?.svg_markup && (
              <figure className="rounded-2xl bg-[#15181F] p-4">
                <div
                  className="overflow-x-auto [&_svg]:mx-auto [&_svg]:max-h-[340px] [&_svg]:w-full"
                  dangerouslySetInnerHTML={{ __html: currentStep.illustration.svg_markup }}
                />
                <figcaption className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-[#A39E93]">
                  <span>
                    <strong className="text-[#F4F1EA]">
                      {currentStep.illustration.origin_label || `Класс ${currentStep.illustration.visual_class}`}
                    </strong>{" "}
                    · {currentStep.illustration.redraw_caption}
                  </span>
                  <span>
                    {currentStep.illustration.source_ref}, стр. {currentStep.illustration.pdf_page}
                  </span>
                </figcaption>
              </figure>
            )}

            {/* Интерактивный блок «Решение на данных» (Басниев / Кузнецов) */}
            {currentStep.data_decision_card && (
              <section className="space-y-3 rounded-2xl bg-[#15181F] p-5 ring-1 ring-[#10B981]/30">
                <div className="text-xs font-medium text-[#10B981]">Решение на данных</div>
                <h3 className="text-lg font-bold text-[#F4F1EA]">{currentStep.data_decision_card.title}</h3>
                <p className="text-xs text-[#A39E93]">{currentStep.data_decision_card.origin_and_assumptions}</p>
                <ul className="space-y-1.5 text-sm">
                  {currentStep.data_decision_card.observed_features.map((f, i) => (
                    <li key={i}>
                      <span className="text-[#A39E93]">{f.label}: </span>
                      <strong className="text-[#F4F1EA]">{f.value}</strong>
                    </li>
                  ))}
                </ul>
                <p className="text-sm text-[#F4F1EA]/90">{currentStep.data_decision_card.decision_rule}</p>
                <p className="text-xs text-[#F59E0B]">
                  Границы правила: {currentStep.data_decision_card.rule_limits}
                </p>
                <div className="pt-1 text-sm font-medium">{currentStep.data_decision_card.question}</div>
                <div className="space-y-2">
                  {currentStep.data_decision_card.options.map((opt) => {
                    const picked = decisionPick[currentStep.step_id] === opt.id;
                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => setDecisionPick((prev) => ({ ...prev, [currentStep.step_id]: opt.id }))}
                        className={`w-full rounded-xl px-4 py-2.5 text-left text-sm transition ${
                          picked ? "bg-[#D97736] text-[#0E1014] font-medium" : "bg-[#1B1F28] hover:bg-[#232836]"
                        }`}
                      >
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
                {decisionPick[currentStep.step_id] && (() => {
                  const hit = currentStep.data_decision_card.options.find(
                    (o) => o.id === decisionPick[currentStep.step_id]
                  );
                  return hit ? (
                    <div
                      className={`rounded-xl px-4 py-3 text-sm ${
                        hit.correct ? "bg-[#10B981]/15 text-[#6EE7B7]" : "bg-[#F43F5E]/15 text-[#FDA4AF]"
                      }`}
                    >
                      {hit.feedback}
                    </div>
                  ) : null;
                })()}
              </section>
            )}

            {/* Объяснение со ссылками на страницы оригинала */}
            <section className="space-y-4">
              {currentStep.explanation_paragraphs.map((p, i) => (
                <div key={i} className="space-y-1.5 border-l-2 border-[#D97736]/60 pl-4">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-[#A39E93]">
                    <span className="font-semibold text-[#F4F1EA]">{p.role}</span>
                    <span>· {p.source_citation}</span>
                  </div>
                  <p className="text-base text-[#F4F1EA]/90">{p.text}</p>
                  {p.verbatim_quote && (
                    <blockquote className="text-sm text-[#A39E93]">
                      Цитата (стр. {p.pdf_page}): «{p.verbatim_quote.slice(0, 260)}»
                    </blockquote>
                  )}
                </div>
              ))}
            </section>

            {/* Наблюдение / Вывод / Допущение */}
            <section className="grid grid-cols-1 gap-4 rounded-2xl bg-[#15181F] p-5 sm:grid-cols-3">
              <div>
                <div className="text-xs font-medium text-[#38BDF8]">Наблюдение</div>
                <p className="mt-1 text-sm text-[#F4F1EA]/90">{currentStep.epistemic_split.observation}</p>
              </div>
              <div>
                <div className="text-xs font-medium text-[#10B981]">Вывод</div>
                <p className="mt-1 text-sm text-[#F4F1EA]/90">{currentStep.epistemic_split.inference}</p>
              </div>
              <div>
                <div className="text-xs font-medium text-[#F59E0B]">Допущение</div>
                <p className="mt-1 text-sm text-[#F4F1EA]/90">{currentStep.epistemic_split.assumption}</p>
              </div>
            </section>

            {/* Таблицы шага с горизонтальной прокруткой внутри блока */}
            {currentStep.tables && currentStep.tables.length > 0 && (
              <div className="space-y-3">
                {currentStep.tables.map((tb, ti) => (
                  <div key={ti} className="rounded-2xl bg-[#15181F] p-4">
                    <div className="mb-3 text-sm font-semibold">{tb.title}</div>
                    <div className="atlas-table-wrap">
                      <table className="w-full min-w-[540px] border-collapse text-left text-sm">
                        <thead>
                          <tr className="border-b border-white/10 text-xs text-[#A39E93]">
                            {tb.headers.map((h, hi) => (
                              <th key={hi} className="px-3 py-2 font-medium">
                                {h}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {tb.rows.map((r, ri) => (
                            <tr key={ri} className="border-b border-white/[0.05]">
                              {r.map((cell, ci) => (
                                <td key={ci} className="px-3 py-2 align-top text-[#F4F1EA]/90">
                                  {cell}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Навигация между шагами */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-4">
              <button
                type="button"
                disabled={stepIdx === 0}
                onClick={() => setStepIdx((s) => Math.max(0, s - 1))}
                className="inline-flex items-center gap-2 rounded-xl bg-[#1B1F28] px-4 py-2.5 text-sm font-medium text-[#F4F1EA] disabled:opacity-40"
              >
                <ArrowLeft className="h-4 w-4" />
                Предыдущий шаг
              </button>
              {stepIdx < pkg.steps.length - 1 ? (
                <button
                  type="button"
                  onClick={() => setStepIdx((s) => Math.min(pkg.steps.length - 1, s + 1))}
                  className="inline-flex items-center gap-2 rounded-xl bg-[#D97736] px-5 py-2.5 text-sm font-semibold text-[#0E1014] hover:bg-[#E58A4C]"
                >
                  Следующий шаг
                  <ArrowRight className="h-4 w-4" />
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => setTab("tasks")}
                  className="inline-flex items-center gap-2 rounded-xl bg-[#D97736] px-5 py-2.5 text-sm font-semibold text-[#0E1014] hover:bg-[#E58A4C]"
                >
                  Перейти к заданиям
                  <ArrowRight className="h-4 w-4" />
                </button>
              )}
            </div>
          </article>
        </div>
      )}

      {/* ВКЛАДКА 2: ЗАДАНИЯ */}
      {tab === "tasks" && (
        <div className="max-w-3xl space-y-5">
          {pkg.tasks.map((t, idx) => {
            const fb = taskFeedback[t.task_id];
            const val = taskInputs[t.task_id];

            return (
              <section key={t.task_id} className="space-y-3 rounded-2xl bg-[#15181F] p-5">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-[#A39E93]">
                  <span>
                    Задание {idx + 1} из {pkg.tasks.length} · {t.task_type}
                  </span>
                  <span>Источник: стр. {t.source_pdf_page}</span>
                </div>
                <div className="text-base font-semibold text-[#F4F1EA]">{t.prompt}</div>

                {/* single_choice / case_decision */}
                {(t.task_type === "single_choice" || t.task_type === "case_decision") && (
                  <div className="space-y-2">
                    {t.options.map((opt, oi) => (
                      <button
                        key={oi}
                        type="button"
                        onClick={() => {
                          setTaskInputs((p) => ({ ...p, [t.task_id]: oi }));
                          checkTask(t.task_id, oi);
                        }}
                        className={`w-full rounded-xl px-4 py-2.5 text-left text-sm transition ${
                          val === oi ? "bg-[#D97736] text-[#0E1014] font-medium" : "bg-[#1B1F28] hover:bg-[#232836]"
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                )}

                {/* multi_select */}
                {t.task_type === "multi_select" && (
                  <div className="space-y-2">
                    {t.options.map((opt, oi) => {
                      const arr = Array.isArray(val) ? (val as number[]) : [];
                      const checked = arr.includes(oi);
                      return (
                        <label
                          key={oi}
                          className="flex cursor-pointer items-center gap-3 rounded-xl bg-[#1B1F28] px-4 py-2.5 text-sm"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => {
                              const next = checked ? arr.filter((x) => x !== oi) : [...arr, oi];
                              setTaskInputs((p) => ({ ...p, [t.task_id]: next }));
                            }}
                            className="h-4 w-4 accent-[#D97736]"
                          />
                          <span>{opt}</span>
                        </label>
                      );
                    })}
                    <button
                      type="button"
                      onClick={() => checkTask(t.task_id, Array.isArray(val) ? val : [])}
                      className="rounded-xl bg-[#D97736] px-4 py-2 text-sm font-semibold text-[#0E1014]"
                    >
                      Проверить выбор
                    </button>
                  </div>
                )}

                {/* fill_in_blank / calculation / matching */}
                {(t.task_type === "fill_in_blank" || t.task_type === "calculation" || t.task_type === "matching") && (
                  <div className="flex flex-wrap gap-2">
                    <input
                      type="text"
                      value={typeof val === "string" ? val : ""}
                      onChange={(e) => setTaskInputs((p) => ({ ...p, [t.task_id]: e.target.value }))}
                      placeholder={t.task_type === "calculation" ? "Введите число…" : "Введите ответ…"}
                      className="flex-1 rounded-xl border border-white/15 bg-[#0E1014] px-3.5 py-2 text-sm text-[#F4F1EA]"
                    />
                    <button
                      type="button"
                      onClick={() =>
                        checkTask(
                          t.task_id,
                          t.task_type === "fill_in_blank" ? [String(val || "")] : String(val || "")
                        )
                      }
                      className="rounded-xl bg-[#D97736] px-4 py-2 text-sm font-semibold text-[#0E1014]"
                    >
                      Проверить
                    </button>
                  </div>
                )}

                {/* ordering */}
                {t.task_type === "ordering" && (() => {
                  const seq = Array.isArray(val) ? (val as string[]) : [...t.options];
                  const move = (from: number, to: number) => {
                    if (to < 0 || to >= seq.length) return;
                    const copy = [...seq];
                    const [item] = copy.splice(from, 1);
                    copy.splice(to, 0, item);
                    setTaskInputs((p) => ({ ...p, [t.task_id]: copy }));
                  };
                  return (
                    <div className="space-y-2">
                      {seq.map((item, si) => (
                        <div
                          key={si}
                          className="flex items-center justify-between gap-2 rounded-xl bg-[#1B1F28] px-3.5 py-2 text-sm"
                        >
                          <span>
                            {si + 1}. {item}
                          </span>
                          <div className="flex gap-1">
                            <button
                              type="button"
                              onClick={() => move(si, si - 1)}
                              aria-label="Переместить выше"
                              className="rounded bg-white/[0.08] px-2 py-1 text-xs"
                            >
                              ↑
                            </button>
                            <button
                              type="button"
                              onClick={() => move(si, si + 1)}
                              aria-label="Переместить ниже"
                              className="rounded bg-white/[0.08] px-2 py-1 text-xs"
                            >
                              ↓
                            </button>
                          </div>
                        </div>
                      ))}
                      <button
                        type="button"
                        onClick={() => checkTask(t.task_id, seq)}
                        className="rounded-xl bg-[#D97736] px-4 py-2 text-sm font-semibold text-[#0E1014]"
                      >
                        Проверить порядок
                      </button>
                    </div>
                  );
                })()}

                {/* Мгновенная обратная связь */}
                {fb && (
                  <div
                    className={`flex items-start gap-2.5 rounded-xl px-4 py-3 text-sm ${
                      fb.is_correct ? "bg-[#10B981]/15 text-[#6EE7B7]" : "bg-[#F43F5E]/15 text-[#FDA4AF]"
                    }`}
                  >
                    {fb.is_correct ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                    ) : (
                      <XCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    )}
                    <div>
                      <strong>{fb.is_correct ? "Верно." : "Есть ошибка."}</strong> {fb.explanation || t.explanation}
                    </div>
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      {/* ВКЛАДКА 3: КАРТОЧКИ */}
      {tab === "cards" && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {pkg.flashcards.map((fc) => {
            const flipped = Boolean(flippedCards[fc.card_id]);
            const mark = cardMarks[fc.card_id];
            return (
              <div key={fc.card_id} className="flex flex-col justify-between rounded-2xl bg-[#15181F] p-5">
                <div>
                  <div className="text-xs text-[#A39E93]">Источник · стр. {fc.source_pdf_page}</div>
                  <div className="mt-2 text-base font-semibold text-[#F4F1EA]">{fc.front_question}</div>
                  {flipped && (
                    <div className="mt-3 rounded-xl bg-[#1B1F28] p-3.5 text-sm text-[#F4F1EA]/90">
                      {fc.back_answer}
                    </div>
                  )}
                </div>
                <div className="mt-4 flex flex-wrap items-center justify-between gap-2 pt-3">
                  <button
                    type="button"
                    onClick={() => setFlippedCards((p) => ({ ...p, [fc.card_id]: !flipped }))}
                    className="text-sm font-medium text-[#D97736] hover:underline"
                  >
                    {flipped ? "Скрыть ответ" : "Показать ответ"}
                  </button>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setCardMarks((p) => ({ ...p, [fc.card_id]: "know" }))}
                      className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                        mark === "know" ? "bg-[#10B981] text-[#0E1014]" : "bg-white/[0.06] text-[#A39E93]"
                      }`}
                    >
                      Знаю
                    </button>
                    <button
                      type="button"
                      onClick={() => setCardMarks((p) => ({ ...p, [fc.card_id]: "repeat" }))}
                      className={`rounded-lg px-3 py-1.5 text-xs font-medium ${
                        mark === "repeat" ? "bg-[#F59E0B] text-[#0E1014]" : "bg-white/[0.06] text-[#A39E93]"
                      }`}
                    >
                      Повторить
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ВКЛАДКА 4: ЛАБОРАТОРИЯ */}
      {tab === "lab" && <GuidedLabWrapper initialLab={initialLab} />}
    </div>
  );
};
