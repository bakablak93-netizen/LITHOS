import React, { useMemo, useState } from "react";
import { ChevronDown, ChevronUp, RotateCcw } from "lucide-react";
import { BasnievHydroLab } from "../labs/BasnievHydroLab";
import { LatyshovaProbeLab } from "../labs/LatyshovaProbeLab";

interface GuidedLabWrapperProps {
  initialLab: "latyshova" | "basniev";
  onSelectLab?: (lab: "latyshova" | "basniev") => void;
}

/**
 * Лаборатория, перестроенная вокруг понятного учебного действия:
 * сначала короткая задача, 1–2 ключевых элемента управления, синхронный результат и вывод с границами применимости;
 * полный 3D-стенд со всеми ползунками и формулами раскрывается по запросу или виден прямо ниже без визуального шума.
 */
export const GuidedLabWrapper: React.FC<GuidedLabWrapperProps> = ({ initialLab, onSelectLab }) => {
  const [lab, setLab] = useState<"latyshova" | "basniev">(initialLab);

  // Басниев: «Удвойте проницаемость. Что произойдёт с дебитом?»
  const [kMd, setKMd] = useState<number>(120);
  const [deltaP, setDeltaP] = useState<number>(7.5);

  // Латышова: «Переместите зонд через ВНК (2425 м) и сравните два зонда»
  const [probeDepth, setProbeDepth] = useState<number>(2420);
  const [rhoF, setRhoF] = useState<number>(1.2);

  const [showFullControls, setShowFullControls] = useState<boolean>(false);

  const switchLab = (next: "latyshova" | "basniev") => {
    setLab(next);
    onSelectLab?.(next);
  };

  // Точный расчёт Дюпюи (согласован с backend/physics_engine/basniev_hydro.py)
  const basnievCalc = useMemo(() => {
    const h = 14.0;
    const mu = 1.8;
    const lnRatio = Math.log(250.0 / 0.1);
    const qBase = (2 * Math.PI * 120 * 1e-15 * h * 7.5e6 * 86400) / (mu * 1e-3 * lnRatio);
    const qNow = (2 * Math.PI * kMd * 1e-15 * h * (deltaP * 1e6) * 86400) / (mu * 1e-3 * lnRatio);
    return {
      qBase: Number(qBase.toFixed(1)),
      qNow: Number(qNow.toFixed(1)),
      ratio: Number((qNow / Math.max(0.1, qBase)).toFixed(2)),
      doubled: kMd >= 230,
    };
  }, [kMd, deltaP]);

  // Точный расчёт показаний двух зондов по глубине (согласован с latyshova_gis.py)
  const latyshovaCalc = useMemo(() => {
    const isTight = probeDepth >= 2409 && probeDepth < 2416;
    const isOil = probeDepth >= 2416 && probeDepth < 2425;
    const isWater = probeDepth >= 2425 && probeDepth <= 2433;
    const alphaSp = isOil || isWater ? 0.82 : isTight ? 0.18 : 0.08;
    const rhoBk = isOil ? 18.5 : isTight ? 24.0 : isWater ? 1.1 : 4.2;
    const rhoMbk = isOil ? Number((5.2 * (rhoF / 1.2)).toFixed(1)) : isTight ? 22.8 : isWater ? Number((6.4 * (rhoF / 1.2)).toFixed(1)) : 3.9;
    const interpretation = isOil
      ? "Коллектор (α_СП ≥ 0,45), нефть: выше ВНК 2425 м, при пресном растворе ρ_МБК < ρ_БК"
      : isWater
      ? "Коллектор (α_СП ≥ 0,45), вода: ниже ВНК 2425 м, сопротивление БК падает до ~1,1 Ом·м"
      : isTight
      ? "Плотный неколлектор: высокое сопротивление, но α_СП = 0,18 < 0,45 и нет корки"
      : "Глинистая покрышка: низкое сопротивление и минимальная аномалия СП";
    return { alphaSp, rhoBk, rhoMbk, interpretation, crossedVnk: probeDepth >= 2425 };
  }, [probeDepth, rhoF]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Выбор 3D-лаборатории">
          <button
            type="button"
            role="tab"
            aria-selected={lab === "basniev"}
            onClick={() => switchLab("basniev")}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
              lab === "basniev" ? "bg-[#D97736] text-[#0E1014]" : "bg-[#1B1F28] text-[#A39E93] hover:text-[#F4F1EA]"
            }`}
          >
            Гидромеханика пласта (Басниев)
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={lab === "latyshova"}
            onClick={() => switchLab("latyshova")}
            className={`rounded-xl px-4 py-2 text-sm font-medium transition ${
              lab === "latyshova" ? "bg-[#D97736] text-[#0E1014]" : "bg-[#1B1F28] text-[#A39E93] hover:text-[#F4F1EA]"
            }`}
          >
            Каротаж и два зонда (Латышова)
          </button>
        </div>
        <span className="rounded-lg bg-white/[0.06] px-2.5 py-1 text-xs text-[#A39E93]">
          Симуляция по уравнениям учебника
        </span>
      </div>

      {/* Сфокусированная задача ученика (1 задача + 1–2 главных контрола + мгновенный вывод) */}
      {lab === "basniev" ? (
        <section className="rounded-2xl bg-[#15181F] p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl">
              <div className="text-xs font-medium text-[#D97736]">Задача на данных</div>
              <h3 className="mt-1 text-xl font-bold text-[#F4F1EA]">
                Удвойте проницаемость. Что произойдёт с дебитом?
              </h3>
              <p className="mt-1.5 text-sm text-[#A39E93]">
                Исходно: проницаемость 120 мД, депрессия 7,5 МПа, дебит {basnievCalc.qBase} м³/сут. Сдвиньте ползунок
                и посмотрите, как меняется приток.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setKMd(120);
                setDeltaP(7.5);
              }}
              className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.06] px-3 py-2 text-xs font-medium text-[#F4F1EA] hover:bg-white/[0.12]"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Сбросить
            </button>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-3">
            <div className="space-y-4 md:col-span-2">
              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <label htmlFor="guided-k">Проницаемость пласта, мД</label>
                  <span className="font-mono font-semibold text-[#10B981]">{kMd} мД</span>
                </div>
                <input
                  id="guided-k"
                  type="range"
                  min={40}
                  max={300}
                  step={10}
                  value={kMd}
                  onChange={(e) => setKMd(Number(e.target.value))}
                  className="w-full accent-[#D97736]"
                />
              </div>

              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <label htmlFor="guided-dp">Перепад давления (депрессия), МПа</label>
                  <span className="font-mono font-semibold text-[#F59E0B]">{deltaP.toFixed(1)} МПа</span>
                </div>
                <input
                  id="guided-dp"
                  type="range"
                  min={2}
                  max={14}
                  step={0.5}
                  value={deltaP}
                  onChange={(e) => setDeltaP(Number(e.target.value))}
                  className="w-full accent-[#D97736]"
                />
              </div>
            </div>

            <div className="flex flex-col justify-between rounded-xl bg-[#1B1F28] p-4">
              <div>
                <div className="text-xs text-[#A39E93]">Расчётный дебит Q</div>
                <div className="mt-1 font-mono text-3xl font-bold text-[#F4F1EA]">
                  {basnievCalc.qNow} <span className="text-sm font-normal text-[#A39E93]">м³/сут</span>
                </div>
                <div className="mt-1 text-xs text-[#10B981]">
                  ×{basnievCalc.ratio} к исходному ({basnievCalc.qBase} м³/сут)
                </div>
              </div>
              {basnievCalc.doubled && (
                <div className="mt-3 rounded-lg bg-[#10B981]/15 px-3 py-2 text-xs text-[#6EE7B7]">
                  Верно: дебит вырос пропорционально проницаемости (линейный закон Дарси–Дюпюи). Граница: правило
                  работает при ламинарном однофазном притоке без падения давления ниже давления насыщения.
                </div>
              )}
            </div>
          </div>

          <div className="mt-5">
            <BasnievHydroLab preset={{ k_md: kMd, delta_p_mpa: deltaP, p_c_mpa: 24.0 - deltaP }} />
          </div>
        </section>
      ) : (
        <section className="rounded-2xl bg-[#15181F] p-5 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl">
              <div className="text-xs font-medium text-[#D97736]">Задача на данных</div>
              <h3 className="mt-1 text-xl font-bold text-[#F4F1EA]">
                Проведите зонд через отметку ВНК (2425 м) и сравните показания
              </h3>
              <p className="mt-1.5 text-sm text-[#A39E93]">
                Отделяйте показание прибора (сопротивление БК, МБК и кривую СП) от геологической интерпретации.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setProbeDepth(2420);
                setRhoF(1.2);
              }}
              className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.06] px-3 py-2 text-xs font-medium text-[#F4F1EA] hover:bg-white/[0.12]"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Сбросить
            </button>
          </div>

          <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-3">
            <div className="space-y-4 md:col-span-2">
              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <label htmlFor="guided-depth">Глубина зонда в скважине, м</label>
                  <span className="font-mono font-semibold text-[#38BDF8]">{probeDepth} м</span>
                </div>
                <input
                  id="guided-depth"
                  type="range"
                  min={2405}
                  max={2442}
                  step={1}
                  value={probeDepth}
                  onChange={(e) => setProbeDepth(Number(e.target.value))}
                  className="w-full accent-[#D97736]"
                />
              </div>

              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <label htmlFor="guided-rhof">Сопротивление фильтрата раствора, Ом·м</label>
                  <span className="font-mono font-semibold text-[#F59E0B]">{rhoF.toFixed(2)} Ом·м</span>
                </div>
                <input
                  id="guided-rhof"
                  type="range"
                  min={0.05}
                  max={1.5}
                  step={0.05}
                  value={rhoF}
                  onChange={(e) => setRhoF(Number(e.target.value))}
                  className="w-full accent-[#D97736]"
                />
              </div>
            </div>

            <div className="space-y-2 rounded-xl bg-[#1B1F28] p-4 text-sm">
              <div className="text-xs text-[#A39E93]">Показания приборов (симуляция)</div>
              <div className="flex justify-between font-mono">
                <span>Глубокий зонд БК:</span>
                <span className="text-[#10B981]">{latyshovaCalc.rhoBk} Ом·м</span>
              </div>
              <div className="flex justify-between font-mono">
                <span>Мелкий зонд МБК:</span>
                <span className="text-[#F59E0B]">{latyshovaCalc.rhoMbk} Ом·м</span>
              </div>
              <div className="flex justify-between font-mono">
                <span>Относительная СП:</span>
                <span className="text-[#38BDF8]">{latyshovaCalc.alphaSp}</span>
              </div>
              <div className="mt-2 border-t border-white/[0.08] pt-2 text-xs text-[#F4F1EA]">
                <strong className="text-[#D97736]">Интерпретация: </strong>
                {latyshovaCalc.interpretation}
              </div>
            </div>
          </div>

          <div className="mt-5">
            <LatyshovaProbeLab preset={{ rho_f: rhoF }} />
          </div>
        </section>
      )}

      {/* Раскрываемый справочник формул и границ применимости */}
      <div>
        <button
          type="button"
          onClick={() => setShowFullControls((v) => !v)}
          className="inline-flex items-center gap-2 text-sm font-medium text-[#A39E93] hover:text-[#F4F1EA]"
        >
          {showFullControls ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          Формулы, обозначения СНГ ↔ SPE и границы применимости
        </button>
        {showFullControls && (
          <div className="mt-3 rounded-xl bg-[#15181F] p-4 text-sm text-[#A39E93]">
            {lab === "basniev" ? (
              <p>
                Формула Дюпюи: <code className="text-[#F4F1EA]">Q = 2πkh(p_к − p_с) / [μ ln(R_к / r_с)]</code> ·
                Фронт ПССС Чарного: <code className="text-[#F4F1EA]">R(t) = √(r_с² + 4κt)</code>. Обозначения:{" "}
                <code className="text-[#F4F1EA]">R_к ↔ r_e</code>, <code className="text-[#F4F1EA]">p_к ↔ p_e</code>,{" "}
                <code className="text-[#F4F1EA]">κ ↔ η</code>. Ограничения: однородный пласт, линейный закон Дарси.
              </p>
            ) : (
              <p>
                Закон Арчи–Дахнова: <code className="text-[#F4F1EA]">P_п = a_m / K_п^m</code>,{" "}
                <code className="text-[#F4F1EA]">P_н = ρ_п / ρ_вп = 1 / K_в^n</code>. Критерии коллектора:
                <code className="text-[#F4F1EA]"> α_СП ≥ 0,45</code>, <code className="text-[#F4F1EA]">K_п ≥ 0,12</code>.
                Обозначения: <code className="text-[#F4F1EA]">K_п ↔ φ</code>, <code className="text-[#F4F1EA]">ρ_п ↔ R_t</code>.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
