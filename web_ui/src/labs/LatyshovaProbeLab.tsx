import React, { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { RotateCcw } from "lucide-react";
import * as THREE from "three";
import { MathText } from "../components/MathText";

interface WellLogData {
  parameters: {
    rho_v_ohmm: number;
    rho_f_ohmm: number;
    m: number;
    n: number;
    vnk_depth_m: number;
    alpha_sp_cutoff: number;
    delta_e_max_mv: number;
  };
  summary: {
    net_pay_oil_m: number;
    total_reservoir_m: number;
    max_rho_bk_ohmm: number;
    max_p_n: number;
  };
  logs: {
    depth_m: number[];
    k_p_pct: number[];
    alpha_sp: number[];
    sp_mv: number[];
    p_p: number[];
    rho_vp_ohmm: number[];
    rho_bk_ohmm: number[];
    rho_mbk_ohmm: number[];
    p_n: number[];
    k_v: number[];
    k_ng: number[];
    is_reservoir: boolean[];
    saturation_class: string[];
  };
}

const LATYSHOVA_PRESETS = [
  {
    id: "clean_oil_sand",
    label: "Чистый нефтеносный песчаник",
    kpPct: 24,
    kngPct: 80,
    rhoV: 0.05,
    rhoF: 1.2,
    m: 1.95,
    n: 2.0,
    vnk: 2425.5,
    mode: "clastic" as const,
    probe: 2420.5,
  },
  {
    id: "shaly_reservoir",
    label: "Глинистый коллектор",
    kpPct: 15,
    kngPct: 58,
    rhoV: 0.08,
    rhoF: 0.9,
    m: 1.75,
    n: 1.6,
    vnk: 2423.0,
    mode: "clastic" as const,
    probe: 2421.0,
  },
  {
    id: "water_sand",
    label: "Водоносный пласт",
    kpPct: 22,
    kngPct: 12,
    rhoV: 0.04,
    rhoF: 1.4,
    m: 1.95,
    n: 2.0,
    vnk: 2417.5,
    mode: "clastic" as const,
    probe: 2428.0,
  },
  {
    id: "fractured_carb",
    label: "Трещинный карбонат (§21)",
    kpPct: 14,
    kngPct: 76,
    rhoV: 0.035,
    rhoF: 1.5,
    m: 2.15,
    n: 2.1,
    vnk: 2426.0,
    mode: "fractured_carbonate" as const,
    probe: 2421.0,
  },
];

function computeLocalLatyshova(params: {
  kp_pct: number;
  kng_pct: number;
  rho_v: number;
  rho_f: number;
  m: number;
  n: number;
  vnk_depth_m: number;
  reservoir_mode: string;
}): WellLogData {
  const depth_m: number[] = [];
  const k_p_pct: number[] = [];
  const alpha_sp: number[] = [];
  const sp_mv: number[] = [];
  const p_p: number[] = [];
  const rho_vp_ohmm: number[] = [];
  const rho_bk_ohmm: number[] = [];
  const rho_mbk_ohmm: number[] = [];
  const p_n: number[] = [];
  const k_v: number[] = [];
  const k_ng: number[] = [];
  const is_reservoir: boolean[] = [];
  const saturation_class: string[] = [];

  const smoothStep = (x: number, edge: number, w = 0.85) => {
    const t = Math.max(0, Math.min(1, (x - edge) / w + 0.5));
    return t * t * (3 - 2 * t);
  };
  const win = (z: number, a: number, b: number) => smoothStep(z, a) * (1 - smoothStep(z, b));

  const deltaEMax = -75.0 * Math.log10(Math.max(params.rho_f, 0.01) / Math.max(params.rho_v, 0.005));
  const kpRes = Math.min(0.34, Math.max(0.06, params.kp_pct / 100));
  const kpWat = Math.min(0.32, Math.max(0.06, kpRes * 0.92));
  const kvOilMin = Math.min(0.92, Math.max(0.1, 1 - params.kng_pct / 100));

  for (let z = 2400; z <= 2450.001; z += 0.5) {
    const wSh1 = 1 - smoothStep(z, 2409);
    const wTight = win(z, 2409, 2416);
    const wRes = win(z, 2416, 2433);
    const wSh2 = win(z, 2433, 2441);
    const wWat = smoothStep(z, 2441);

    const kp = Math.min(
      0.34,
      Math.max(0.03, 0.045 * wSh1 + 0.055 * wTight + kpRes * wRes + 0.04 * wSh2 + kpWat * wWat)
    );
    const aspBase = Math.min(0.98, Math.max(0.35, 0.45 + (kpRes - 0.1) * 2.2));
    const asp = Math.min(1, Math.max(0, 0.06 * wSh1 + 0.18 * wTight + aspBase * wRes + 0.05 * wSh2 + 0.84 * wWat));
    const cgl = 0.72 * wSh1 + 0.14 * wTight + 0.07 * wRes + 0.78 * wSh2 + 0.09 * wWat;

    let pp = 0.81 / Math.pow(kp, params.m);
    if (params.reservoir_mode === "fractured_carbonate" && wRes + wWat > 0.4) {
      pp = pp / (pp * 0.015 * (2 / 3) + 1);
    }
    const rvp = pp * params.rho_v;

    const tvnk = smoothStep(z, params.vnk_depth_m, 2.4);
    const kvRes = kvOilMin + (0.98 - kvOilMin) * tvnk;
    const kv = Math.min(
      1,
      Math.max(0.1, 0.98 * wSh1 + 0.95 * wTight + kvRes * wRes + 0.99 * wSh2 + 0.98 * wWat)
    );
    const kng = 1 - kv;
    const pn = 1.0 / Math.pow(kv, params.n);
    const shaleW = Math.min(1, wSh1 + wSh2);
    const rbk = (1 - shaleW) * (pn * rvp) + shaleW * 4.2;

    const pi = Math.max(0.45, 1 - 0.55 * cgl);
    const kvFlush = kng > 0.25 ? Math.min(0.92, kv + 0.45 * kng) : 0.96;
    const rzp = (1 / Math.pow(kvFlush, params.n)) * pi * pp * params.rho_f;
    const rmbk = (1 - shaleW) * (0.85 * rzp + 0.15 * rbk) + shaleW * 3.8;

    const res = asp >= 0.45 && kp >= 0.11;
    let sat = "non_reservoir";
    if (res) {
      sat = pn >= 4.5 && kv <= 0.48 ? "oil" : pn >= 2.2 ? "transition_oil_water" : "water";
    }

    depth_m.push(Number(z.toFixed(1)));
    k_p_pct.push(Number((kp * 100).toFixed(2)));
    alpha_sp.push(Number(asp.toFixed(3)));
    sp_mv.push(Number((asp * deltaEMax).toFixed(1)));
    p_p.push(Number(pp.toFixed(2)));
    rho_vp_ohmm.push(Number(rvp.toFixed(3)));
    rho_bk_ohmm.push(Number(rbk.toFixed(2)));
    rho_mbk_ohmm.push(Number(rmbk.toFixed(2)));
    p_n.push(Number(pn.toFixed(2)));
    k_v.push(Number(kv.toFixed(3)));
    k_ng.push(Number(kng.toFixed(3)));
    is_reservoir.push(res);
    saturation_class.push(sat);
  }

  return {
    parameters: {
      rho_v_ohmm: params.rho_v,
      rho_f_ohmm: params.rho_f,
      m: params.m,
      n: params.n,
      vnk_depth_m: params.vnk_depth_m,
      alpha_sp_cutoff: 0.45,
      delta_e_max_mv: Number(deltaEMax.toFixed(1)),
    },
    summary: {
      net_pay_oil_m: Number((saturation_class.filter((s) => s === "oil").length * 0.5).toFixed(1)),
      total_reservoir_m: Number((is_reservoir.filter(Boolean).length * 0.5).toFixed(1)),
      max_rho_bk_ohmm: Number(Math.max(...rho_bk_ohmm).toFixed(1)),
      max_p_n: Number(Math.max(...p_n).toFixed(1)),
    },
    logs: {
      depth_m,
      k_p_pct,
      alpha_sp,
      sp_mv,
      p_p,
      rho_vp_ohmm,
      rho_bk_ohmm,
      rho_mbk_ohmm,
      p_n,
      k_v,
      k_ng,
      is_reservoir,
      saturation_class,
    },
  };
}

// Индексы узлов 3x3x3 для зёрен и 2x2x2 для межзерновых пор (масштабируются динамически от K_п)
const GRAIN_INDICES: [number, number, number][] = [];
for (let ix = -1; ix <= 1; ix++) {
  for (let iy = -1; iy <= 1; iy++) {
    for (let iz = -1; iz <= 1; iz++) {
      GRAIN_INDICES.push([ix, iy, iz]);
    }
  }
}

const PORE_POCKET_SIGNS: [number, number, number][] = [];
for (const ix of [-0.5, 0.5]) {
  for (const iy of [-0.5, 0.5]) {
    for (const iz of [-0.5, 0.5]) {
      PORE_POCKET_SIGNS.push([ix, iy, iz]);
    }
  }
}

const PORE_THROAT_SPECS: { signs: [number, number, number]; rot: [number, number, number] }[] = [
  { signs: [0, -0.5, -0.5], rot: [0, 0, Math.PI / 2] },
  { signs: [0, 0.5, -0.5], rot: [0, 0, Math.PI / 2] },
  { signs: [0, -0.5, 0.5], rot: [0, 0, Math.PI / 2] },
  { signs: [0, 0.5, 0.5], rot: [0, 0, Math.PI / 2] },
  { signs: [-0.5, 0, -0.5], rot: [0, 0, 0] },
  { signs: [0.5, 0, -0.5], rot: [0, 0, 0] },
  { signs: [-0.5, 0, 0.5], rot: [0, 0, 0] },
  { signs: [0.5, 0, 0.5], rot: [0, 0, 0] },
  { signs: [-0.5, -0.5, 0], rot: [Math.PI / 2, 0, 0] },
  { signs: [0.5, -0.5, 0], rot: [Math.PI / 2, 0, 0] },
  { signs: [-0.5, 0.5, 0], rot: [Math.PI / 2, 0, 0] },
  { signs: [0.5, 0.5, 0], rot: [Math.PI / 2, 0, 0] },
];

const Wellbore3DScene: React.FC<{
  probeDepth: number;
  vnkDepth: number;
  kpPct: number;
  kngPct: number;
  rhoV: number;
  rhoF: number;
  currentRhoBk: number;
  currentKngAtProbe: number;
  reservoirMode: "clastic" | "fractured_carbonate";
  autoScan: boolean;
  onDepthTick: (d: number) => void;
  onHoverInfo: (info: string | null) => void;
  controlsRef: React.RefObject<any>;
}> = ({
  probeDepth,
  vnkDepth,
  kpPct,
  kngPct,
  rhoV,
  rhoF,
  currentRhoBk,
  currentKngAtProbe,
  reservoirMode,
  autoScan,
  onDepthTick,
  onHoverInfo,
  controlsRef,
}) => {
  const probeRef = useRef<THREE.Group>(null);
  const microLensRef = useRef<THREE.Group>(null);
  const pulseRef = useRef<THREE.Mesh>(null);
  const depthRef = useRef(probeDepth);
  depthRef.current = probeDepth;

  const depthToY = (d: number) => ((2425 - d) / 50) * 10;

  useFrame((state, delta) => {
    if (autoScan) {
      let next = depthRef.current + delta * 4.5;
      if (next > 2450) next = 2400;
      onDepthTick(Number(next.toFixed(1)));
    }
    if (probeRef.current) {
      probeRef.current.position.y = depthToY(depthRef.current);
    }
    if (microLensRef.current) {
      microLensRef.current.rotation.y = state.clock.elapsedTime * 0.25;
    }
    if (pulseRef.current) {
      const s = 1 + 0.08 * Math.sin(state.clock.elapsedTime * 3.8);
      pulseRef.current.scale.set(s, 1, s);
    }
  });

  // Физические параметры из единого источника
  const kpNorm = Math.max(0, Math.min(1, (kpPct - 8) / 24)); // 8%..32% -> 0..1
  const kngNorm = Math.max(0, Math.min(1, kngPct / 100)); // 0..1

  // Шаг упаковки и радиус зёрен меняются от K_п: чем выше пористость, тем шире поровые каналы между зёрнами
  const latticeStep = 0.39 + kpNorm * 0.11; // 0.39 .. 0.50
  const grainRadius = 0.235 - kpNorm * 0.068; // 0.235 .. 0.167
  // Смачивающая плёночная/остаточная вода вдоль поверхности каждого зерна (растёт с K_в = 1 - K_нг)
  const waterFilmRadius = grainRadius + 0.012 + (1 - kngNorm) * 0.028;
  // Размер межзерновой поры (растёт с K_п)
  const poreVoidRadius = 0.115 + kpNorm * 0.095;
  // Янтарная нефть строго в центре пор (масштабируется от K_нг)
  const oilDropletRadius = poreVoidRadius * Math.max(0.1, Math.pow(kngNorm, 0.42));
  const throatRadius = (0.038 + kpNorm * 0.062) * Math.max(0.22, kngNorm);

  // Радиус зоны проникновения фильтрата D вокруг ствола (зависит от K_п и отношения ρ_ф / ρ_в)
  const invasionContrast = Math.min(2.4, Math.max(0.3, Math.log10(Math.max(1.05, rhoF / Math.max(rhoV, 0.008)))));
  const invasionRadius = 0.56 + kpNorm * 0.52 + invasionContrast * 0.26; // 0.56 .. 1.65
  const mudcakeRadius = 0.335 + kpNorm * 0.055;

  // Радиус зоны чувствительности зонда БК (расширяется/сужается от удельного сопротивления пласта ρ_п)
  const senseRadius = 0.42 + Math.min(1.38, Math.log10(Math.max(1.0, currentRhoBk)) * 0.66);
  const senseColor = currentKngAtProbe > 0.45 ? "#f59e0b" : currentRhoBk > 8 ? "#10b981" : "#38bdf8";

  // Плавная смена цвета нефтенасыщенного пласта от K_нг
  const oilLayerColor = useMemo(() => {
    const cWater = new THREE.Color("#0284c7");
    const cOil = new THREE.Color("#d97706");
    return "#" + cWater.lerp(cOil, Math.min(1, Math.max(0.12, kngNorm * 1.15))).getHexString();
  }, [kngNorm]);

  const strata = [
    {
      name: "Глинистая покрышка (неколлектор)",
      detail: "2400–2409 м · α_СП ≈ 0.06 · ρ_п ≈ 4.2 Ом·м",
      top: 2400,
      bot: 2409,
      color: "#334155",
      permeable: false,
      isOilZone: false,
    },
    {
      name: "Плотный карбонатный пропласток",
      detail: "2409–2416 м · K_п ≈ 5.5% · нет зоны проникновения",
      top: 2409,
      bot: 2416,
      color: "#475569",
      permeable: false,
      isOilZone: false,
    },
    {
      name: "Продуктивный коллектор (выше ВНК)",
      detail: `2416–${vnkDepth.toFixed(1)} м · K_п = ${kpPct}% · K_нг = ${kngPct}% · зона проникновения D = ${(invasionRadius * 0.85).toFixed(2)} м`,
      top: 2416,
      bot: vnkDepth,
      color: oilLayerColor,
      permeable: true,
      isOilZone: true,
    },
    {
      name: "Коллектор ниже ВНК (водонасыщенная зона)",
      detail: `${vnkDepth.toFixed(1)}–2433 м · K_п = ${kpPct}% · K_в → 98% · повышающее проникновение`,
      top: vnkDepth,
      bot: 2433,
      color: "#0284c7",
      permeable: true,
      isOilZone: false,
    },
    {
      name: "Глинистая перемычка (экран)",
      detail: "2433–2441 м · непроницаемый глинистый раздел",
      top: 2433,
      bot: 2441,
      color: "#1e293b",
      permeable: false,
      isOilZone: false,
    },
    {
      name: "Нижний водоносный песчаник",
      detail: `2441–2450 м · K_п = ${(kpPct * 0.92).toFixed(0)}% · ρ_вп = P_п·ρ_в`,
      top: 2441,
      bot: 2450,
      color: "#0369a1",
      permeable: true,
      isOilZone: false,
    },
  ];

  const vnkY = depthToY(vnkDepth);
  const probeY = depthToY(probeDepth);

  return (
    <>
      <ambientLight intensity={0.72} />
      <directionalLight position={[6, 8, 6]} intensity={1.15} />
      <pointLight position={[-4, 2, 4]} intensity={0.65} color="#38bdf8" />

      {/* СТВОЛ СКВАЖИНЫ, ПЛАСТЫ, ДИНАМИЧЕСКИЙ ВНК И ЗОНА ПРОНИКНОВЕНИЯ D */}
      <group position={[-1.2, 0, 0]}>
        {strata.map((st, idx) => {
          const h = ((st.bot - st.top) / 50) * 10;
          if (h <= 0.02) return null;
          const yCenter = depthToY((st.top + st.bot) / 2);
          return (
            <group key={idx} position={[0, yCenter, 0]}>
              {/* Основной цилиндр пласта (unit height = 1.0 + scale.y = h без пересоздания геометрии!) */}
              <mesh
                position={[0, 0, -0.25]}
                scale={[1, h, 1]}
                onPointerOver={(e) => {
                  e.stopPropagation();
                  onHoverInfo(`${st.name} — ${st.detail}`);
                }}
                onPointerOut={() => onHoverInfo(null)}
              >
                <cylinderGeometry args={[2.22, 2.22, 1.0, 32, 1, false, Math.PI * 0.22, Math.PI * 1.56]} />
                <meshStandardMaterial
                  color={reservoirMode === "fractured_carbonate" && st.permeable ? "#475569" : st.color}
                  transparent
                  opacity={0.74}
                  roughness={reservoirMode === "fractured_carbonate" ? 0.35 : 0.65}
                  side={THREE.DoubleSide}
                />
              </mesh>

              {/* Сеть трещин на пласте в режиме трещинного карбоната (§21) */}
              {reservoirMode === "fractured_carbonate" && st.permeable && (
                <group position={[0, 0, -0.25]}>
                  {[-0.28, 0, 0.28].map((fy, fi) => (
                    <mesh
                      key={fi}
                      position={[0, fy * h, 0]}
                      rotation={[0.35 * (fi - 1), 0.5 * fi, 0.25]}
                      scale={[1, 1, 1 + kpNorm * 0.2]}
                    >
                      <torusGeometry args={[1.55, 0.032, 10, 32, Math.PI * 1.45]} />
                      <meshBasicMaterial color={st.isOilZone ? "#f59e0b" : "#38bdf8"} />
                    </mesh>
                  ))}
                </group>
              )}

              {/* Полупрозрачный 3D-цилиндр зоны проникновения фильтрата D и глинистая корка */}
              {st.permeable && (
                <>
                  <mesh
                    position={[0, 0, -0.25]}
                    scale={[invasionRadius, h, invasionRadius]}
                    onPointerOver={(e) => {
                      e.stopPropagation();
                      onHoverInfo(
                        `Зона проникновения фильтрата D (${st.isOilZone ? "понижающее проникновение ρ_МБК < ρ_БК" : "повышающее проникновение ρ_МБК > ρ_БК"}) · радиус D = ${(invasionRadius * 0.85).toFixed(2)} м`
                      );
                    }}
                    onPointerOut={() => onHoverInfo(null)}
                  >
                    <cylinderGeometry args={[1.0, 1.0, 1.0, 28, 1, false, Math.PI * 0.22, Math.PI * 1.56]} />
                    <meshStandardMaterial
                      color={st.isOilZone ? "#38bdf8" : "#7dd3fc"}
                      transparent
                      opacity={0.24 + Math.min(0.28, (rhoF / 3.5) * 0.2)}
                      side={THREE.DoubleSide}
                      depthWrite={false}
                    />
                  </mesh>

                  {/* Глинистая корка на стенке скважины */}
                  <mesh position={[0, 0, -0.25]} scale={[mudcakeRadius, h, mudcakeRadius]}>
                    <cylinderGeometry args={[1.0, 1.0, 1.0, 24, 1, true, Math.PI * 0.2, Math.PI * 1.6]} />
                    <meshStandardMaterial color="#a16207" transparent opacity={0.88} side={THREE.DoubleSide} />
                  </mesh>
                </>
              )}
            </group>
          );
        })}

        {/* 3D-ПЛОСКОСТЬ ВНК (динамически смещается от K_нг и уровня ВНК) */}
        <mesh position={[0, vnkY, -0.25]} rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.34, 2.36, 48]} />
          <meshBasicMaterial color="#ef4444" side={THREE.DoubleSide} transparent opacity={0.9} />
        </mesh>
        <Html position={[-2.35, vnkY, 0]} center>
          <div className="rounded border border-red-400/50 bg-red-600/90 px-2 py-0.5 text-[10px] font-bold text-white whitespace-nowrap shadow">
            ВНК / OWC {vnkDepth.toFixed(1)} м
          </div>
        </Html>

        {/* Ствол скважины и каротажный кабель */}
        <mesh position={[0, 0, -0.25]}>
          <cylinderGeometry args={[0.32, 0.32, 10.2, 24, 1, true]} />
          <meshStandardMaterial color="#cbd5e1" transparent opacity={0.22} side={THREE.DoubleSide} />
        </mesh>
        <mesh position={[0, 2.6, -0.25]}>
          <cylinderGeometry args={[0.02, 0.02, 5.2, 8]} />
          <meshStandardMaterial color="#94a3b8" />
        </mesh>

        {/* КАРОТАЖНЫЙ ЗОНД + ДИНАМИЧЕСКОЕ ПОЛЕ ЧУВСТВИТЕЛЬНОСТИ (ТОКОВЫЕ ЛИНИИ БК) */}
        <group
          ref={probeRef}
          position={[0, probeY, -0.25]}
          onPointerOver={(e) => {
            e.stopPropagation();
            onHoverInfo(
              `Зонд БК/МБК/СП (${probeDepth.toFixed(1)} м) · ρ_п ≈ ${currentRhoBk.toFixed(1)} Ом·м · радиус поля чувствительности ${(senseRadius * 1.1).toFixed(2)} м`
            );
          }}
          onPointerOut={() => onHoverInfo(null)}
        >
          <mesh>
            <cylinderGeometry args={[0.12, 0.12, 0.85, 20]} />
            <meshStandardMaterial color="#f59e0b" metalness={0.6} roughness={0.25} />
          </mesh>
          {[-0.26, 0, 0.26].map((ey, i) => (
            <mesh key={i} position={[0, ey, 0]}>
              <torusGeometry args={[0.138, 0.02, 12, 24]} />
              <meshStandardMaterial color="#38bdf8" emissive="#0284c7" emissiveIntensity={0.9} />
            </mesh>
          ))}

          {/* Светящееся поле чувствительности зонда (расширяется/сужается от ρ_п) */}
          <mesh ref={pulseRef} scale={[senseRadius, 0.55 + senseRadius * 0.35, senseRadius]}>
            <sphereGeometry args={[1.0, 24, 20]} />
            <meshBasicMaterial color={senseColor} transparent opacity={0.18} depthWrite={false} />
          </mesh>

          {/* Токовые линии / кольца фокусировки БК */}
          {[0.65, 1.0].map((ringScale, ri) => (
            <mesh key={ri} rotation={[Math.PI / 2, 0, 0]} scale={[senseRadius * ringScale, senseRadius * ringScale, 1]}>
              <ringGeometry args={[0.92, 1.0, 36]} />
              <meshBasicMaterial color={senseColor} transparent opacity={0.48 - ri * 0.15} side={THREE.DoubleSide} />
            </mesh>
          ))}

          <Html position={[0, 0.65, 0]} center>
            <div className="rounded border border-amber-400/60 bg-[#090D16]/90 px-2 py-0.5 text-[10px] font-mono text-amber-300 whitespace-nowrap">
              {probeDepth.toFixed(1)} м · {currentRhoBk.toFixed(1)} Ом·м
            </div>
          </Html>
        </group>
      </group>

      {/* ИНТЕРАКТИВНАЯ 3D-ЛИНЗА / МИКРОВСТАВКА ПОРОВОГО ПРОСТРАНСТВА (НЕФТЬ И ВОДА СТРОГО В ПОРАХ) */}
      <group
        position={[2.15, 0.35, 0.15]}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHoverInfo(
            reservoirMode === "fractured_carbonate"
              ? `3D-линза трещинного карбоната (§21): плотная матрица + 3D-сеть трещин (K_п = ${kpPct}%, K_нг = ${kngPct}%)`
              : `3D-линза порового пространства: K_п = ${kpPct}% определяет ширину поровых каналов, K_нг = ${kngPct}% — янтарную нефть в центре пор и голубую плёночную воду вдоль зёрен`
          );
        }}
        onPointerOut={() => onHoverInfo(null)}
      >
        {/* Оптическое кольцо 3D-линзы и тёмная подложка */}
        <mesh>
          <torusGeometry args={[1.34, 0.038, 16, 48]} />
          <meshStandardMaterial color="#38bdf8" metalness={0.5} roughness={0.2} />
        </mesh>
        <mesh>
          <sphereGeometry args={[1.3, 24, 24]} />
          <meshBasicMaterial color="#0b1120" transparent opacity={0.52} depthWrite={false} />
        </mesh>

        {/* Вращающийся 3D-фрагмент порового пространства */}
        <group ref={microLensRef}>
          {reservoirMode === "clastic" ? (
            <>
              {/* Сферические зёрна песчаника (раздвигаются и меняют радиус от K_п) + плёночная вода вдоль зёрен */}
              {GRAIN_INDICES.map(([ix, iy, iz], gi) => (
                <group key={`g_${gi}`} position={[ix * latticeStep, iy * latticeStep, iz * latticeStep]}>
                  <mesh scale={[grainRadius, grainRadius, grainRadius]}>
                    <sphereGeometry args={[1, 14, 14]} />
                    <meshStandardMaterial color="#cbb99e" roughness={0.75} metalness={0.05} />
                  </mesh>
                  {/* Голубая плёночная/остаточная вода вдоль стенок зёрен */}
                  <mesh scale={[waterFilmRadius, waterFilmRadius, waterFilmRadius]}>
                    <sphereGeometry args={[1, 12, 12]} />
                    <meshStandardMaterial
                      color="#0ea5e9"
                      transparent
                      opacity={0.2 + (1 - kngNorm) * 0.42}
                      depthWrite={false}
                    />
                  </mesh>
                </group>
              ))}

              {/* Межзерновые поры: водяная оболочка + янтарная нефть строго в центре пор */}
              {PORE_POCKET_SIGNS.map(([sx, sy, sz], pi) => (
                <group key={`p_${pi}`} position={[sx * latticeStep, sy * latticeStep, sz * latticeStep]}>
                  <mesh scale={[poreVoidRadius, poreVoidRadius, poreVoidRadius]}>
                    <sphereGeometry args={[1, 14, 14]} />
                    <meshStandardMaterial
                      color="#0284c7"
                      transparent
                      opacity={0.22 + (1 - kngNorm) * 0.55}
                      depthWrite={false}
                    />
                  </mesh>
                  <mesh scale={[oilDropletRadius, oilDropletRadius, oilDropletRadius]}>
                    <sphereGeometry args={[1, 14, 14]} />
                    <meshStandardMaterial
                      color="#f59e0b"
                      emissive="#d97706"
                      emissiveIntensity={0.5 * kngNorm}
                      roughness={0.2}
                    />
                  </mesh>
                </group>
              ))}

              {/* Поровые каналы (горловины) между зёрнами */}
              {PORE_THROAT_SPECS.map((th, ti) => (
                <mesh
                  key={`t_${ti}`}
                  position={[
                    th.signs[0] * latticeStep,
                    th.signs[1] * latticeStep,
                    th.signs[2] * latticeStep,
                  ]}
                  rotation={th.rot}
                  scale={[throatRadius, latticeStep, throatRadius]}
                >
                  <cylinderGeometry args={[1, 1, 1, 10]} />
                  <meshStandardMaterial
                    color={kngNorm > 0.35 ? "#f59e0b" : "#0284c7"}
                    emissive={kngNorm > 0.35 ? "#b45309" : "#0369a1"}
                    emissiveIntensity={0.4}
                  />
                </mesh>
              ))}
            </>
          ) : (
            /* РЕЖИМ ТРЕЩИННОГО КАРБОНАТА (§21): плотная матрица + светящаяся 3D-сеть трещин */
            <group>
              <mesh>
                <boxGeometry args={[1.36, 1.36, 1.36]} />
                <meshStandardMaterial color="#475569" transparent opacity={0.8} roughness={0.4} />
              </mesh>
              {[
                { rot: [0.35, 0.2, 0.4] as [number, number, number], pos: [0, 0, 0] as [number, number, number] },
                { rot: [-0.5, 0.4, -0.3] as [number, number, number], pos: [0.08, -0.05, 0.04] as [number, number, number] },
                { rot: [0.15, -0.6, 1.1] as [number, number, number], pos: [-0.06, 0.08, -0.05] as [number, number, number] },
              ].map((fr, fi) => (
                <mesh
                  key={fi}
                  position={fr.pos}
                  rotation={fr.rot}
                  scale={[1.42, 0.025 + kpNorm * 0.06, 1.42]}
                >
                  <boxGeometry args={[1, 1, 1]} />
                  <meshStandardMaterial
                    color={kngNorm > 0.35 ? "#f59e0b" : "#38bdf8"}
                    emissive={kngNorm > 0.35 ? "#d97706" : "#0284c7"}
                    emissiveIntensity={0.7}
                    transparent
                    opacity={0.92}
                  />
                </mesh>
              ))}
            </group>
          )}
        </group>

        <Html position={[0, -1.62, 0]} center>
          <div className="rounded-lg border border-blue-500/35 bg-[#090D16]/92 px-2.5 py-1 text-center text-[10px] text-slate-200 whitespace-nowrap shadow-lg">
            <div className="font-semibold text-blue-300">
              {reservoirMode === "fractured_carbonate" ? "3D-линза: Трещины §21" : "3D-линза пор (зёрна + флюид в порах)"}
            </div>
            <div className="font-mono text-[10px] text-slate-300">
              Kп={kpPct}% · Нефть Kнг={kngPct}% · Вода Kв={100 - kngPct}%
            </div>
          </div>
        </Html>
      </group>

      <OrbitControls ref={controlsRef} enableDamping dampingFactor={0.08} />
    </>
  );
};

export const LatyshovaProbeLab: React.FC<{ preset?: Record<string, any> }> = ({ preset }) => {
  const [kpPct, setKpPct] = useState<number>(24);
  const [kngPct, setKngPct] = useState<number>(80);
  const [rhoV, setRhoV] = useState<number>(Number(preset?.rho_v ?? 0.05));
  const [rhoF, setRhoF] = useState<number>(Number(preset?.rho_f ?? 1.2));
  const [mExp, setMExp] = useState<number>(Number(preset?.m ?? 1.95));
  const [nExp, setNExp] = useState<number>(Number(preset?.n ?? 2.0));
  const [vnkDepth, setVnkDepth] = useState<number>(Number(preset?.vnk_depth_m ?? 2425.5));
  const [reservoirMode, setReservoirMode] = useState<"clastic" | "fractured_carbonate">("clastic");
  const [probeDepth, setProbeDepth] = useState<number>(2420.5);
  const [autoScan, setAutoScan] = useState<boolean>(false);
  const [activePresetId, setActivePresetId] = useState<string>("clean_oil_sand");
  const [hoverInfo, setHoverInfo] = useState<string | null>(null);
  const controlsRef = useRef<any>(null);

  const [data, setData] = useState<WellLogData>(() =>
    computeLocalLatyshova({
      kp_pct: 24,
      kng_pct: 80,
      rho_v: 0.05,
      rho_f: 1.2,
      m: 1.95,
      n: 2.0,
      vnk_depth_m: 2425.5,
      reservoir_mode: "clastic",
    })
  );

  // Единый источник параметров для 3D-сцены и кривых ГИС
  useEffect(() => {
    setData(
      computeLocalLatyshova({
        kp_pct: kpPct,
        kng_pct: kngPct,
        rho_v: rhoV,
        rho_f: rhoF,
        m: mExp,
        n: nExp,
        vnk_depth_m: vnkDepth,
        reservoir_mode: reservoirMode,
      })
    );
  }, [kpPct, kngPct, rhoV, rhoF, mExp, nExp, vnkDepth, reservoirMode]);

  const applyPreset = (p: (typeof LATYSHOVA_PRESETS)[number]) => {
    setActivePresetId(p.id);
    setAutoScan(false);
    setKpPct(p.kpPct);
    setKngPct(p.kngPct);
    setRhoV(p.rhoV);
    setRhoF(p.rhoF);
    setMExp(p.m);
    setNExp(p.n);
    setVnkDepth(p.vnk);
    setReservoirMode(p.mode);
    setProbeDepth(p.probe);
  };

  const resetAll = () => {
    applyPreset(LATYSHOVA_PRESETS[0]);
    controlsRef.current?.reset();
  };

  const handleKngChange = (val: number) => {
    setKngPct(val);
    const coupledVnk = Number((2417.5 + ((val - 10) / 80) * 12.5).toFixed(1));
    setVnkDepth(Math.min(2431, Math.max(2417.5, coupledVnk)));
  };

  const idx = useMemo(() => {
    const arr = data.logs.depth_m;
    let best = 0;
    let bestDiff = Infinity;
    for (let i = 0; i < arr.length; i++) {
      const diff = Math.abs(arr[i] - probeDepth);
      if (diff < bestDiff) {
        bestDiff = diff;
        best = i;
      }
    }
    return best;
  }, [data, probeDepth]);

  const satClass = data.logs.saturation_class[idx] || "non_reservoir";
  const satBadge =
    satClass === "oil"
      ? { text: "КОЛЛЕКТОР · НЕФТЬ", cls: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40" }
      : satClass === "transition_oil_water"
      ? { text: "ПЕРЕХОДНАЯ ЗОНА (НЕФТЬ+ВОДА)", cls: "bg-amber-500/20 text-amber-300 border-amber-500/40" }
      : satClass === "water"
      ? { text: "КОЛЛЕКТОР · ВОДА", cls: "bg-sky-500/20 text-sky-300 border-sky-500/40" }
      : { text: "НЕКОЛЛЕКТОР (ГЛИНА/ПЛОТНЫЙ)", cls: "bg-slate-700/60 text-slate-300 border-slate-600" };

  const spPoints = data.logs.depth_m
    .map((d, i) => {
      const x = 14 + (data.logs.alpha_sp[i] || 0) * 112;
      const y = 18 + ((d - 2400) / 50) * 340;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const bkPoints = data.logs.depth_m
    .map((d, i) => {
      const val = Math.max(0.5, Math.min(200, data.logs.rho_bk_ohmm[i] || 1));
      const x = 165 + (Math.log10(val) / 2.3) * 175;
      const y = 18 + ((d - 2400) / 50) * 340;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const mbkPoints = data.logs.depth_m
    .map((d, i) => {
      const val = Math.max(0.5, Math.min(200, data.logs.rho_mbk_ohmm[i] || 1));
      const x = 165 + (Math.log10(val) / 2.3) * 175;
      const y = 18 + ((d - 2400) / 50) * 340;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const cursorY = 18 + ((probeDepth - 2400) / 50) * 340;
  const vnkY = 18 + ((vnkDepth - 2400) / 50) * 340;

  return (
    <div className="flex flex-col gap-3">
      {/* Панель пресетов пластов + кнопка сброса */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-800 bg-slate-900 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Пресеты пластов:</span>
          {LATYSHOVA_PRESETS.map((p) => (
            <button
              key={p.id}
              onClick={() => applyPreset(p)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                activePresetId === p.id
                  ? "bg-[#2563EB] text-white"
                  : "bg-slate-800 text-slate-200 hover:bg-slate-700"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>
        <button
          onClick={resetAll}
          className="flex items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-800"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          Сброс камеры и параметров
        </button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
        {/* 3D Окно скважины + 3D-линза пор + HUD */}
        <div className="relative h-[560px] overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 lg:col-span-5">
          <div className="pointer-events-none absolute left-3 top-3 z-10 rounded-xl border border-blue-500/30 bg-[#090D16]/90 px-3 py-2 text-xs backdrop-blur">
            <div className="font-semibold text-blue-400">3D-стенд ГИС + 3D-линза пор · Латышова (1991)</div>
            <div className="mt-1 font-mono text-[11px] text-slate-200">
              <MathText
                text={
                  reservoirMode === "fractured_carbonate"
                    ? "P_пт = P_пбл / (P_пбл·k_пт·A + 1)"
                    : "P_п = a_m / K_п^m  |  P_н = ρ_п / ρ_вп = a_n / K_в^n"
                }
              />
            </div>
            <div className="mt-1.5 flex flex-wrap gap-2 font-mono text-[11px]">
              <span className="rounded bg-slate-800/90 px-1.5 py-0.5 text-sky-300">
                <MathText text={`P_п=${data.logs.p_p[idx]}`} />
              </span>
              <span className="rounded bg-slate-800/90 px-1.5 py-0.5 text-emerald-300">
                <MathText text={`P_н=${data.logs.p_n[idx]}`} />
              </span>
              <span className="rounded bg-slate-800/90 px-1.5 py-0.5 text-amber-300">
                <MathText text={`K_нг=${(data.logs.k_ng[idx] * 100).toFixed(0)}%`} />
              </span>
              <span className="rounded bg-slate-800/90 px-1.5 py-0.5 text-rose-300">
                <MathText text={`h_эф=${data.summary.net_pay_oil_m}м`} />
              </span>
            </div>
          </div>

          {hoverInfo && (
            <div className="pointer-events-none absolute bottom-3 left-3 right-3 z-10 rounded-xl border border-blue-400/40 bg-[#090D16]/95 px-3 py-2 text-xs text-slate-200 shadow-lg">
              <MathText text={hoverInfo} />
            </div>
          )}

          <Canvas camera={{ position: [0.55, 0.85, 7.1], fov: 44 }}>
            <Wellbore3DScene
              probeDepth={probeDepth}
              vnkDepth={vnkDepth}
              kpPct={kpPct}
              kngPct={kngPct}
              rhoV={rhoV}
              rhoF={rhoF}
              currentRhoBk={data.logs.rho_bk_ohmm[idx] || 4.2}
              currentKngAtProbe={data.logs.k_ng[idx] || 0}
              reservoirMode={reservoirMode}
              autoScan={autoScan}
              onDepthTick={setProbeDepth}
              onHoverInfo={setHoverInfo}
              controlsRef={controlsRef}
            />
          </Canvas>
        </div>

        {/* Живые кривые ГИС + телеметрия Арчи */}
        <div className="flex flex-col gap-4 lg:col-span-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-sky-400">
                Синхронизированный планшет ГИС
              </span>
              <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-bold ${satBadge.cls}`}>
                {satBadge.text}
              </span>
            </div>
            <svg viewBox="0 0 365 375" className="h-[340px] w-full rounded-xl bg-slate-950">
              {[2400, 2410, 2420, 2430, 2440, 2450].map((d) => {
                const y = 18 + ((d - 2400) / 50) * 340;
                return (
                  <g key={d}>
                    <line x1="12" y1={y} x2="352" y2={y} stroke="#1e293b" strokeWidth="1" />
                    <text x="134" y={y + 3} fill="#64748b" fontSize="9" fontFamily="monospace">
                      {d}м
                    </text>
                  </g>
                );
              })}
              <line x1={14 + 0.45 * 112} y1="18" x2={14 + 0.45 * 112} y2="358" stroke="#f43f5e" strokeDasharray="4 3" />
              <line x1="12" y1={vnkY} x2="352" y2={vnkY} stroke="#ef4444" strokeWidth="1.5" strokeDasharray="5 3" />
              <polyline fill="none" stroke="#38bdf8" strokeWidth="2.4" points={spPoints} />
              <polyline fill="none" stroke="#10b981" strokeWidth="2.6" points={bkPoints} />
              <polyline fill="none" stroke="#f59e0b" strokeWidth="1.8" strokeDasharray="4 2" points={mbkPoints} />
              <line x1="10" y1={cursorY} x2="355" y2={cursorY} stroke="#facc15" strokeWidth="1.8" />
              <text x="14" y="12" fill="#38bdf8" fontSize="10" fontWeight="bold">
                α_СП (SP/SSP)
              </text>
              <text x="170" y="12" fill="#10b981" fontSize="10" fontWeight="bold">
                ρ_БК (зелён.) vs ρ_МБК (янт.)
              </text>
            </svg>
          </div>

          <div className="grid grid-cols-3 gap-2 rounded-2xl border border-slate-800 bg-slate-900 p-3 text-center">
            <div className="rounded-xl bg-slate-950 p-2">
              <div className="text-[11px] text-slate-400">
                <MathText text="K_п (φ)" />
              </div>
              <div className="font-mono text-base font-bold text-white">{data.logs.k_p_pct[idx]}%</div>
            </div>
            <div className="rounded-xl bg-slate-950 p-2">
              <div className="text-[11px] text-slate-400">
                <MathText text="ρ_БК (R_t)" />
              </div>
              <div className="font-mono text-base font-bold text-emerald-400">{data.logs.rho_bk_ohmm[idx]} Ом·м</div>
            </div>
            <div className="rounded-xl bg-slate-950 p-2">
              <div className="text-[11px] text-slate-400">
                <MathText text="K_нг (S_hc)" />
              </div>
              <div className="font-mono text-base font-bold text-amber-400">
                {(data.logs.k_ng[idx] * 100).toFixed(0)}%
              </div>
            </div>
            <div className="rounded-xl bg-slate-950 p-2">
              <div className="text-[11px] text-slate-400">
                <MathText text="P_п (F)" />
              </div>
              <div className="font-mono text-sm font-semibold text-sky-300">{data.logs.p_p[idx]}</div>
            </div>
            <div className="rounded-xl bg-slate-950 p-2">
              <div className="text-[11px] text-slate-400">
                <MathText text="P_н (I)" />
              </div>
              <div className="font-mono text-sm font-semibold text-sky-300">{data.logs.p_n[idx]}</div>
            </div>
            <div className="rounded-xl bg-slate-950 p-2">
              <div className="text-[11px] text-slate-400">
                <MathText text="h_эф (нефть)" />
              </div>
              <div className="font-mono text-sm font-semibold text-emerald-300">{data.summary.net_pay_oil_m} м</div>
            </div>
          </div>
        </div>

        {/* Ползунки параметров (единый источник для 3D-сцены и планшета ГИС) */}
        <div className="flex flex-col gap-2.5 rounded-2xl border border-slate-800 bg-slate-900 p-4 lg:col-span-3">
          <div className="text-xs font-bold uppercase tracking-wider text-blue-400">Управление пластом и порами</div>

          <div>
            <div className="flex justify-between text-xs">
              <span>
                Пористость коллектора <MathText text="K_п (φ)" />
              </span>
              <span className="font-mono text-emerald-300">{kpPct}%</span>
            </div>
            <input
              type="range"
              min={8}
              max={32}
              step={1}
              value={kpPct}
              onChange={(e) => setKpPct(Number(e.target.value))}
              className="w-full accent-emerald-400"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs">
              <span>
                Нефтенасыщенность пор <MathText text="K_нг" />
              </span>
              <span className="font-mono text-amber-300">{kngPct}%</span>
            </div>
            <input
              type="range"
              min={10}
              max={88}
              step={2}
              value={kngPct}
              onChange={(e) => handleKngChange(Number(e.target.value))}
              className="w-full accent-amber-400"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs">
              <span>Глубина зонда z</span>
              <span className="font-mono text-amber-300">{probeDepth.toFixed(1)} м</span>
            </div>
            <input
              type="range"
              min={2400}
              max={2450}
              step={0.5}
              value={probeDepth}
              onChange={(e) => {
                setAutoScan(false);
                setProbeDepth(Number(e.target.value));
              }}
              className="w-full accent-amber-400"
            />
            <button
              onClick={() => setAutoScan((v) => !v)}
              className={`mt-1 w-full rounded-lg px-3 py-1.5 text-xs font-semibold ${
                autoScan ? "bg-amber-500 text-slate-950" : "bg-slate-800 text-slate-200 hover:bg-slate-700"
              }`}
            >
              {autoScan ? "Остановить каротаж" : "Авто-протяжка зонда"}
            </button>
          </div>

          <div>
            <div className="flex justify-between text-xs">
              <span>
                УЭС пластовой воды <MathText text="ρ_в (R_w)" />
              </span>
              <span className="font-mono text-sky-300">{rhoV.toFixed(3)} Ом·м</span>
            </div>
            <input
              type="range"
              min={0.02}
              max={0.2}
              step={0.005}
              value={rhoV}
              onChange={(e) => setRhoV(Number(e.target.value))}
              className="w-full accent-sky-400"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs">
              <span>
                УЭС фильтрата <MathText text="ρ_ф (зона D)" />
              </span>
              <span className="font-mono text-sky-300">{rhoF.toFixed(2)} Ом·м</span>
            </div>
            <input
              type="range"
              min={0.1}
              max={3.5}
              step={0.1}
              value={rhoF}
              onChange={(e) => setRhoF(Number(e.target.value))}
              className="w-full accent-sky-400"
            />
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div>
              <div className="flex justify-between text-xs">
                <span>Цементация m</span>
                <span className="font-mono text-sky-300">{mExp.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={1.3}
                max={2.3}
                step={0.05}
                value={mExp}
                onChange={(e) => setMExp(Number(e.target.value))}
                className="w-full accent-emerald-400"
              />
            </div>

            <div>
              <div className="flex justify-between text-xs">
                <span>Насыщение n</span>
                <span className="font-mono text-sky-300">{nExp.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min={1.4}
                max={2.8}
                step={0.05}
                value={nExp}
                onChange={(e) => setNExp(Number(e.target.value))}
                className="w-full accent-emerald-400"
              />
            </div>
          </div>

          <div>
            <div className="flex justify-between text-xs">
              <span>Уровень ВНК (OWC)</span>
              <span className="font-mono text-red-400">{vnkDepth.toFixed(1)} м</span>
            </div>
            <input
              type="range"
              min={2417.5}
              max={2431}
              step={0.5}
              value={vnkDepth}
              onChange={(e) => setVnkDepth(Number(e.target.value))}
              className="w-full accent-red-500"
            />
          </div>

          <div className="pt-1">
            <div className="mb-1 text-xs text-slate-400">Структура пустотного пространства:</div>
            <div className="grid grid-cols-2 gap-1.5">
              <button
                onClick={() => setReservoirMode("clastic")}
                className={`rounded-lg px-2 py-1.5 text-xs font-semibold ${
                  reservoirMode === "clastic" ? "bg-[#2563EB] text-white" : "bg-slate-800 text-slate-300"
                }`}
              >
                Межзерновой (песчаник)
              </button>
              <button
                onClick={() => setReservoirMode("fractured_carbonate")}
                className={`rounded-lg px-2 py-1.5 text-xs font-semibold ${
                  reservoirMode === "fractured_carbonate" ? "bg-amber-500 text-slate-950" : "bg-slate-800 text-slate-300"
                }`}
              >
                Трещинный карбонат §21
              </button>
            </div>
            {reservoirMode === "fractured_carbonate" && (
              <div className="mt-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2 text-[11px] text-amber-200">
                <MathText text="Активна формула (6) §1: P_пт = P_пбл / (P_пбл·k_пт·A + 1). В 3D-линзе показана матрица с сетью трещин." />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
