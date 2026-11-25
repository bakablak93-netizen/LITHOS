import React, { useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { RotateCcw } from "lucide-react";
import * as THREE from "three";
import { MathText } from "../components/MathText";

interface BasnievData {
  dupuit: {
    metrics: {
      q_m3_day: number;
      productivity_index_m3_day_mpa: number;
      w_wellbore_mm_s: number;
    };
    radial_profile: {
      r_m: number[];
      p_mpa: number[];
      w_mm_s: number[];
    };
    indicator_line: {
      delta_p_mpa: number[];
      q_m3_day: number[];
    };
  };
  transient_psss: {
    parameters: {
      kappa_m2_s: number;
    };
    r_m: number[];
    snapshots: Array<{
      time_hours: number;
      r_front_m: number;
      p_psss_mpa: number[];
      p_exact_mpa: number[];
    }>;
  };
}

const BASNIEV_PRESETS = [
  {
    id: "high_perm",
    label: "Высокопроницаемый коллектор",
    k: 280,
    mu: 1.2,
    h: 24,
    dp: 7.0,
    t: 3.5,
  },
  {
    id: "low_perm",
    label: "Низкопроницаемый пласт (узкий фронт ПССС)",
    k: 25,
    mu: 2.4,
    h: 10,
    dp: 9.5,
    t: 2.0,
  },
  {
    id: "viscous_oil",
    label: "Вязкая нефть (замедленная фильтрация)",
    k: 130,
    mu: 8.5,
    h: 16,
    dp: 8.5,
    t: 4.0,
  },
];

function computeLocalBasniev(params: {
  k_md: number;
  mu_cp: number;
  h_m: number;
  delta_p_mpa: number;
  t_hours: number;
}): BasnievData {
  const p_k = 24.0;
  const p_c = Math.max(2.0, p_k - params.delta_p_mpa);
  const r_c = 0.1;
  const r_k = 250.0;
  const k_si = params.k_md * 1e-15;
  const mu_si = params.mu_cp * 1e-3;
  const lnRatio = Math.log(r_k / r_c);

  const q_m3_s = (2 * Math.PI * k_si * params.h_m * params.delta_p_mpa * 1e6) / (mu_si * lnRatio);
  const q_m3_day = q_m3_s * 86400;
  const prod = q_m3_day / Math.max(params.delta_p_mpa, 0.1);

  const r_m: number[] = [];
  const p_mpa: number[] = [];
  const w_mm_s: number[] = [];
  for (let i = 0; i < 60; i++) {
    const r = r_c * Math.pow(r_k / r_c, i / 59);
    r_m.push(Number(r.toFixed(3)));
    p_mpa.push(Number((p_c + params.delta_p_mpa * (Math.log(r / r_c) / lnRatio)).toFixed(3)));
    w_mm_s.push(Number(((q_m3_s / (2 * Math.PI * params.h_m * r)) * 1000).toFixed(4)));
  }

  const dpSweep = [0, 2, 4, 6, 8, 10, 12];
  const qSweep = dpSweep.map((dp) => Number((prod * dp).toFixed(1)));

  const betaStar = 0.18 * 1.2e-9 + 1.0e-10;
  const kappa = k_si / (mu_si * betaStar);
  const t_s = Math.max(0.05, params.t_hours) * 3600;
  const r_front = Math.sqrt(r_c * r_c + 4 * kappa * t_s);
  const coef = ((q_m3_s * mu_si) / (2 * Math.PI * k_si * params.h_m)) * 1e-6;

  const p_psss = r_m.map((r) =>
    r <= r_front ? Number((p_k - coef * Math.log(Math.max(r_front, 0.2) / r)).toFixed(3)) : p_k
  );
  const p_exact = r_m.map((r) => {
    const u = (r * r) / (4 * kappa * t_s);
    const wApprox = u < 2.5 ? Math.max(0, -0.5772 - Math.log(Math.max(u, 1e-7)) + u - (u * u) / 4) : 0;
    return Number((p_k - 0.5 * coef * wApprox).toFixed(3));
  });

  return {
    dupuit: {
      metrics: {
        q_m3_day: Number(q_m3_day.toFixed(1)),
        productivity_index_m3_day_mpa: Number(prod.toFixed(2)),
        w_wellbore_mm_s: w_mm_s[0],
      },
      radial_profile: { r_m, p_mpa, w_mm_s },
      indicator_line: { delta_p_mpa: dpSweep, q_m3_day: qSweep },
    },
    transient_psss: {
      parameters: { kappa_m2_s: Number(kappa.toFixed(3)) },
      r_m,
      snapshots: [
        {
          time_hours: params.t_hours,
          r_front_m: Number(r_front.toFixed(1)),
          p_psss_mpa: p_psss,
          p_exact_mpa: p_exact,
        },
      ],
    },
  };
}

const RADIAL_SEGS = 42;
const ANGULAR_SEGS = 54;
const R_MIN_SCENE = 0.2;
const R_MAX_SCENE = 4.0;

const DepressionConeMesh: React.FC<{
  kMd: number;
  muCp: number;
  hM: number;
  deltaP: number;
  rFrontM: number;
  onHoverInfo: (info: string | null) => void;
  controlsRef: React.RefObject<any>;
}> = ({ kMd, muCp, hM, deltaP, rFrontM, onHoverInfo, controlsRef }) => {
  const particlesRef = useRef<THREE.Points>(null);

  // Физический масштаб мощности пласта h в 3D-сцене (от 2 до 40 м)
  const hScene = 0.5 + (hM / 40) * 2.1; // 0.60 .. 2.60
  const reservoirCenterY = -0.35 - hScene * 0.5;
  // Радиус фронта возмущения ПССС R(t) в координатах сцены
  const frontSceneR = Math.min(R_MAX_SCENE, Math.max(0.35, (rFrontM / 250) * R_MAX_SCENE));

  // Создаём геометрию воронки депрессии один раз и обновляем буферы на месте (без утечек WebGL)
  const coneGeo = useMemo(() => {
    const vertexCount = (RADIAL_SEGS + 1) * (ANGULAR_SEGS + 1);
    const positions = new Float32Array(vertexCount * 3);
    const colors = new Float32Array(vertexCount * 3);
    const indices: number[] = [];

    const row = ANGULAR_SEGS + 1;
    for (let ir = 0; ir < RADIAL_SEGS; ir++) {
      for (let ia = 0; ia < ANGULAR_SEGS; ia++) {
        const a = ir * row + ia;
        const b = a + 1;
        const c = (ir + 1) * row + ia;
        const d = c + 1;
        indices.push(a, c, b, b, c, d);
      }
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    geo.setIndex(indices);
    return geo;
  }, []);

  // Мгновенное обновление 3D-поверхности воронки депрессии p(r) при движении ползунков Δp и R(t)
  useEffect(() => {
    const posAttr = coneGeo.getAttribute("position") as THREE.BufferAttribute;
    const colAttr = coneGeo.getAttribute("color") as THREE.BufferAttribute;

    const depthScale = Math.min(2.45, deltaP * 0.205);
    const colLow = new THREE.Color("#ef4444");
    const colMid = new THREE.Color("#f59e0b");
    const colHigh = new THREE.Color("#38bdf8");
    const tmpColor = new THREE.Color();

    const effFront = Math.max(R_MIN_SCENE * 1.4, frontSceneR);
    const lnDenom = Math.log(effFront / R_MIN_SCENE);

    let vIdx = 0;
    for (let ir = 0; ir <= RADIAL_SEGS; ir++) {
      const t = ir / RADIAL_SEGS;
      const rScene = R_MIN_SCENE * Math.pow(R_MAX_SCENE / R_MIN_SCENE, t);
      const normP = rScene >= effFront ? 1.0 : Math.min(1.0, Math.max(0.0, Math.log(rScene / R_MIN_SCENE) / lnDenom));
      const y = -depthScale * (1 - normP) + 0.65;

      // Градиент цветовой карты зависит от абсолютного падения давления Δp·(1 - normP)
      const pressureDropFrac = ((1 - normP) * deltaP) / 12.0;
      const colorT = Math.max(0, Math.min(1, 1 - pressureDropFrac * 1.15));
      if (colorT < 0.5) {
        tmpColor.copy(colLow).lerp(colMid, colorT * 2);
      } else {
        tmpColor.copy(colMid).lerp(colHigh, (colorT - 0.5) * 2);
      }

      for (let ia = 0; ia <= ANGULAR_SEGS; ia++) {
        const ang = (ia / ANGULAR_SEGS) * Math.PI * 2;
        posAttr.setXYZ(vIdx, rScene * Math.cos(ang), y, rScene * Math.sin(ang));
        colAttr.setXYZ(vIdx, tmpColor.r, tmpColor.g, tmpColor.b);
        vIdx++;
      }
    }

    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    coneGeo.computeVertexNormals();
  }, [coneGeo, deltaP, frontSceneR]);

  // Буфер 3D-частиц флюида (нефти): ускоряются ~ 1/r внутри R(t), неподвижны за пределами R(t)
  const particleState = useMemo(() => {
    const count = 280;
    const radii = new Float32Array(count);
    const angles = new Float32Array(count);
    const relHeights = new Float32Array(count);
    const pos = new Float32Array(count * 3);
    const col = new Float32Array(count * 3);

    for (let i = 0; i < count; i++) {
      radii[i] = 0.26 + Math.random() * (R_MAX_SCENE - 0.3);
      angles[i] = Math.random() * Math.PI * 2;
      relHeights[i] = 0.08 + Math.random() * 0.84;
    }

    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setAttribute("color", new THREE.BufferAttribute(col, 3));
    return { count, radii, angles, relHeights, geo };
  }, []);

  const physRef = useRef({ kMd, muCp, hScene, deltaP, frontSceneR });
  physRef.current = { kMd, muCp, hScene, deltaP, frontSceneR };

  useFrame((_, dt) => {
    const { kMd: k, muCp: mu, hScene: hSc, deltaP: dp, frontSceneR: rFrontSc } = physRef.current;
    const posAttr = particleState.geo.getAttribute("position") as THREE.BufferAttribute;
    const colAttr = particleState.geo.getAttribute("color") as THREE.BufferAttribute;

    // Скорость фильтрации по Дарси w(r) ~ (k * Δp) / (μ * r)
    const darcyMobility = ((k / 120) * (dp / 7.5)) / Math.max(mu / 1.8, 0.12);
    const baseSpeed = Math.min(4.0, Math.max(0.05, darcyMobility * 0.78));
    const clampedDt = Math.min(dt, 0.05);

    for (let i = 0; i < particleState.count; i++) {
      let r = particleState.radii[i];

      // Причинная физика упругого режима (ПССС): движение только внутри фронта возмущения r <= R(t)
      if (r <= rFrontSc) {
        const radialVel = baseSpeed / Math.max(r, 0.22);
        r -= radialVel * clampedDt;
        if (r < 0.22) {
          r = Math.max(0.32, rFrontSc * (0.86 + Math.random() * 0.14));
          particleState.angles[i] = Math.random() * Math.PI * 2;
        }
        particleState.radii[i] = r;

        const nearWellBoost = Math.max(0, 1 - r / Math.max(rFrontSc, 0.4));
        colAttr.setXYZ(i, 0.99, 0.65 + nearWellBoost * 0.28, 0.1 + nearWellBoost * 0.25);
      } else {
        // Невозмущённая область пласта r > R(t) — частицы неподвижны (v = 0)
        colAttr.setXYZ(i, 0.28, 0.48, 0.68);
      }

      const a = particleState.angles[i];
      const y = -0.35 - particleState.relHeights[i] * hSc;
      posAttr.setXYZ(i, r * Math.cos(a), y, r * Math.sin(a));
    }

    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
  });

  return (
    <>
      <ambientLight intensity={0.72} />
      <directionalLight position={[6, 8, 5]} intensity={1.15} />

      {/* 3D-ЦИЛИНДР ПРОДУКТИВНОГО ПЛАСТА (масштабируется по вертикали от ползунка мощности h) */}
      <group position={[0, reservoirCenterY, 0]}>
        <mesh
          scale={[1, hScene, 1]}
          onPointerOver={(e) => {
            e.stopPropagation();
            onHoverInfo(
              `Продуктивный пласт-коллектор: мощность h = ${hM} м, проницаемость k = ${kMd} мД, вязкость флюида μ = ${muCp.toFixed(1)} мПа·с`
            );
          }}
          onPointerOut={() => onHoverInfo(null)}
        >
          <cylinderGeometry args={[R_MAX_SCENE, R_MAX_SCENE, 1.0, 48, 1, true]} />
          <meshStandardMaterial color="#1e293b" transparent opacity={0.52} side={THREE.DoubleSide} />
        </mesh>

        {/* Кровля и подошва пласта */}
        <mesh position={[0, hScene * 0.5, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.2, R_MAX_SCENE, 48]} />
          <meshBasicMaterial color="#334155" transparent opacity={0.3} side={THREE.DoubleSide} />
        </mesh>
        <mesh position={[0, -hScene * 0.5, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <ringGeometry args={[0.2, R_MAX_SCENE, 48]} />
          <meshBasicMaterial color="#1e293b" transparent opacity={0.48} side={THREE.DoubleSide} />
        </mesh>
      </group>

      {/* СТВОЛ СКВАЖИНЫ И ВСКРЫТЫЙ ИНТЕРВАЛ (удлиняется при увеличении мощности пласта h) */}
      <mesh
        position={[0, 0.35 - hScene * 0.5, 0]}
        scale={[1, 1.6 + hScene, 1]}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHoverInfo(
            `Добывающая скважина: r_с = 0.1 м, вскрытая мощность h = ${hM} м, забойное давление p_с = ${(24 - deltaP).toFixed(1)} МПа`
          );
        }}
        onPointerOut={() => onHoverInfo(null)}
      >
        <cylinderGeometry args={[0.16, 0.16, 1.0, 24]} />
        <meshStandardMaterial color="#e2e8f0" metalness={0.55} roughness={0.3} />
      </mesh>

      {/* 3D-ПОВЕРХНОСТЬ ВОРОНКИ ДЕПРЕССИИ p(r) */}
      <mesh
        geometry={coneGeo}
        onPointerOver={(e) => {
          e.stopPropagation();
          onHoverInfo(
            `Воронка депрессии p(r): депрессия Δp = ${deltaP.toFixed(1)} МПа (от p_к = 24.0 МПа до p_с = ${(24 - deltaP).toFixed(1)} МПа)`
          );
        }}
        onPointerOut={() => onHoverInfo(null)}
      >
        <meshStandardMaterial vertexColors transparent opacity={0.85} side={THREE.DoubleSide} />
      </mesh>

      {/* ОБЪЁМНЫЙ 3D-ЦИЛИНДР И КОЛЬЦА ФРОНТА ВОЗМУЩЕНИЯ ПССС R(t) = √(r_с² + 4κt) */}
      <group
        onPointerOver={(e) => {
          e.stopPropagation();
          onHoverInfo(
            `Фронт возмущения ПССС R(t) = ${rFrontM.toFixed(1)} м: внутри фронта флюид ускоряется к забою по закону w(r) ~ 1/r, снаружи пласт не возмущён`
          );
        }}
        onPointerOut={() => onHoverInfo(null)}
      >
        <mesh position={[0, reservoirCenterY, 0]} scale={[frontSceneR, hScene, frontSceneR]}>
          <cylinderGeometry args={[1.0, 1.0, 1.0, 56, 1, true]} />
          <meshStandardMaterial
            color="#10b981"
            emissive="#059669"
            emissiveIntensity={0.38}
            transparent
            opacity={0.24}
            side={THREE.DoubleSide}
            depthWrite={false}
          />
        </mesh>

        <mesh position={[0, 0.65, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[frontSceneR, frontSceneR, 1]}>
          <ringGeometry args={[0.96, 1.02, 64]} />
          <meshBasicMaterial color="#10b981" side={THREE.DoubleSide} />
        </mesh>

        <mesh
          position={[0, -0.35 - hScene, 0]}
          rotation={[Math.PI / 2, 0, 0]}
          scale={[frontSceneR, frontSceneR, 1]}
        >
          <ringGeometry args={[0.97, 1.01, 64]} />
          <meshBasicMaterial color="#10b981" transparent opacity={0.65} side={THREE.DoubleSide} />
        </mesh>
      </group>

      <Html position={[frontSceneR, 0.82, 0]} center>
        <div className="rounded border border-emerald-400/50 bg-emerald-600/90 px-2 py-0.5 text-[10px] font-mono font-bold text-white whitespace-nowrap shadow">
          Фронт R(t) = {rFrontM.toFixed(0)} м
        </div>
      </Html>

      {/* ЧАСТИЦЫ ФЛЮИДА С УСКОРЕНИЕМ 1/r ВНУТРИ R(t) */}
      <points ref={particlesRef} geometry={particleState.geo}>
        <pointsMaterial vertexColors size={0.1} sizeAttenuation />
      </points>

      <OrbitControls ref={controlsRef} enableDamping dampingFactor={0.08} />
    </>
  );
};

export const BasnievHydroLab: React.FC<{ preset?: Record<string, any> }> = ({ preset }) => {
  const [kMd, setKMd] = useState<number>(Number(preset?.k_md ?? 120));
  const [muCp, setMuCp] = useState<number>(Number(preset?.mu_cp ?? 1.8));
  const [hM, setHM] = useState<number>(Number(preset?.h_m ?? 14));
  const [deltaP, setDeltaP] = useState<number>(Number(preset?.delta_p_mpa ?? 7.5));
  const [tHours, setTHours] = useState<number>(3.0);
  const [activePresetId, setActivePresetId] = useState<string>("");
  const [hoverInfo, setHoverInfo] = useState<string | null>(null);
  const controlsRef = useRef<any>(null);

  const [data, setData] = useState<BasnievData>(() =>
    computeLocalBasniev({ k_md: 120, mu_cp: 1.8, h_m: 14, delta_p_mpa: 7.5, t_hours: 3.0 })
  );

  // Единый источник параметров для 3D-сцены и графиков Дюпюи / ПССС
  useEffect(() => {
    setData(computeLocalBasniev({ k_md: kMd, mu_cp: muCp, h_m: hM, delta_p_mpa: deltaP, t_hours: tHours }));
  }, [kMd, muCp, hM, deltaP, tHours]);

  const applyPreset = (p: (typeof BASNIEV_PRESETS)[number]) => {
    setActivePresetId(p.id);
    setKMd(p.k);
    setMuCp(p.mu);
    setHM(p.h);
    setDeltaP(p.dp);
    setTHours(p.t);
  };

  const resetAll = () => {
    setActivePresetId("");
    setKMd(120);
    setMuCp(1.8);
    setHM(14);
    setDeltaP(7.5);
    setTHours(3.0);
    controlsRef.current?.reset();
  };

  const snap =
    data.transient_psss.snapshots.find((s) => Math.abs(s.time_hours - tHours) < 0.05) ||
    data.transient_psss.snapshots[0];
  const rArr = data.dupuit.radial_profile.r_m;
  const pArr = data.dupuit.radial_profile.p_mpa;
  const minP = Math.min(...pArr, 10);
  const maxP = 25;

  const dupuitPts = rArr
    .map((r, i) => {
      const x = 35 + (r / 250) * 305;
      const y = 175 - ((pArr[i] - minP) / Math.max(maxP - minP, 1)) * 145;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const psssPts = (snap?.p_psss_mpa || [])
    .map((p, i) => {
      const r = data.transient_psss.r_m[i] || rArr[i] || 1;
      const x = 35 + (r / 250) * 305;
      const y = 175 - ((Math.max(minP - 2, p) - minP) / Math.max(maxP - minP, 1)) * 145;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const maxQInd = Math.max(...data.dupuit.indicator_line.q_m3_day, 100);
  const indPts = data.dupuit.indicator_line.delta_p_mpa
    .map((dp, i) => {
      const x = 35 + (dp / 12) * 305;
      const y = 145 - (data.dupuit.indicator_line.q_m3_day[i] / maxQInd) * 120;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <div className="flex flex-col gap-3">
      {/* Пресеты и сброс */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-800 bg-slate-900 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Пресеты пластов:</span>
          {BASNIEV_PRESETS.map((p) => (
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
        {/* 3D пласт + воронка депрессии + фронт ПССС + HUD */}
        <div className="relative h-[550px] overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 lg:col-span-5">
          <div className="pointer-events-none absolute left-3 top-3 z-10 rounded-xl border border-blue-500/30 bg-[#090D16]/90 px-3 py-2 text-xs backdrop-blur">
            <div className="font-semibold text-blue-400">3D-стенд гидромеханики · Басниев и др. (2005)</div>
            <div className="mt-1 font-mono text-[11px] text-slate-200">
              <MathText text="Q = 2πkh·Δp / [μ ln(R_к/r_с)]  |  R(t) = √(r_с^2 + 4κt)" />
            </div>
            <div className="mt-1.5 flex flex-wrap gap-2 font-mono text-[11px]">
              <span className="rounded bg-slate-800/90 px-1.5 py-0.5 text-amber-300">
                Q={data.dupuit.metrics.q_m3_day} м³/сут
              </span>
              <span className="rounded bg-slate-800/90 px-1.5 py-0.5 text-sky-300">
                κ={data.transient_psss.parameters.kappa_m2_s} м²/с
              </span>
              <span className="rounded bg-slate-800/90 px-1.5 py-0.5 text-emerald-300">
                R(t)={snap?.r_front_m || 0} м
              </span>
            </div>
          </div>

          {hoverInfo && (
            <div className="pointer-events-none absolute bottom-3 left-3 right-3 z-10 rounded-xl border border-blue-400/40 bg-[#090D16]/95 px-3 py-2 text-xs text-slate-200 shadow-lg">
              <MathText text={hoverInfo} />
            </div>
          )}

          <Canvas camera={{ position: [5.4, 3.6, 5.4], fov: 45 }}>
            <DepressionConeMesh
              kMd={kMd}
              muCp={muCp}
              hM={hM}
              deltaP={deltaP}
              rFrontM={snap?.r_front_m || 95}
              onHoverInfo={setHoverInfo}
              controlsRef={controlsRef}
            />
          </Canvas>
        </div>

        {/* Графики p(r), ПССС и индикаторная линия */}
        <div className="flex flex-col gap-3 lg:col-span-4">
          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
            <div className="mb-1 text-xs font-bold uppercase tracking-wider text-sky-400">
              Воронка депрессии Дюпюи (оранж.) vs ПССС R(t) (зелён.)
            </div>
            <svg viewBox="0 0 360 195" className="h-[180px] w-full rounded-xl bg-slate-950">
              <line x1="35" y1="175" x2="342" y2="175" stroke="#334155" />
              <line x1="35" y1="20" x2="35" y2="175" stroke="#334155" />
              <polyline fill="none" stroke="#f59e0b" strokeWidth="2.6" points={dupuitPts} />
              <polyline fill="none" stroke="#10b981" strokeWidth="2.2" strokeDasharray="5 3" points={psssPts} />
              <text x="275" y="190" fill="#94a3b8" fontSize="10">
                r, м (0..250)
              </text>
              <text x="6" y="30" fill="#94a3b8" fontSize="10">
                p,МПа
              </text>
            </svg>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
            <div className="mb-1 text-xs font-bold uppercase tracking-wider text-emerald-400">
              Индикаторная линия Q(Δp) — формула (20.22)
            </div>
            <svg viewBox="0 0 360 160" className="h-[145px] w-full rounded-xl bg-slate-950">
              <line x1="35" y1="145" x2="342" y2="145" stroke="#334155" />
              <line x1="35" y1="18" x2="35" y2="145" stroke="#334155" />
              <polyline fill="none" stroke="#38bdf8" strokeWidth="2.6" points={indPts} />
              <circle
                cx={35 + (deltaP / 12) * 305}
                cy={145 - (data.dupuit.metrics.q_m3_day / maxQInd) * 120}
                r="5"
                fill="#facc15"
              />
              <text x="265" y="157" fill="#94a3b8" fontSize="10">
                Δp, МПа
              </text>
            </svg>
          </div>

          <div className="grid grid-cols-3 gap-2 rounded-2xl border border-slate-800 bg-slate-900 p-3 text-center">
            <div className="rounded-xl bg-slate-950 p-2">
              <div className="text-[11px] text-slate-400">Дебит Q</div>
              <div className="font-mono text-base font-bold text-amber-400">{data.dupuit.metrics.q_m3_day} м³/сут</div>
            </div>
            <div className="rounded-xl bg-slate-950 p-2">
              <div className="text-[11px] text-slate-400">Пьезопр. κ</div>
              <div className="font-mono text-base font-bold text-sky-300">
                {data.transient_psss.parameters.kappa_m2_s} м²/с
              </div>
            </div>
            <div className="rounded-xl bg-slate-950 p-2">
              <div className="text-[11px] text-slate-400">Фронт R(t)</div>
              <div className="font-mono text-base font-bold text-emerald-400">{snap?.r_front_m || 0} м</div>
            </div>
          </div>
        </div>

        {/* Ползунки параметров */}
        <div className="flex flex-col gap-4 rounded-2xl border border-slate-800 bg-slate-900 p-4 lg:col-span-3">
          <div className="text-xs font-bold uppercase tracking-wider text-blue-400">
            Управление пластом (Дюпюи + ПССС)
          </div>

          <div>
            <div className="flex justify-between text-xs">
              <span>Проницаемость k</span>
              <span className="font-mono text-sky-300">{kMd} мД</span>
            </div>
            <input
              type="range"
              min={10}
              max={400}
              step={5}
              value={kMd}
              onChange={(e) => setKMd(Number(e.target.value))}
              className="w-full accent-sky-400"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs">
              <span>Вязкость флюида μ</span>
              <span className="font-mono text-sky-300">{muCp.toFixed(1)} мПа·с</span>
            </div>
            <input
              type="range"
              min={0.5}
              max={10.0}
              step={0.1}
              value={muCp}
              onChange={(e) => setMuCp(Number(e.target.value))}
              className="w-full accent-amber-400"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs">
              <span>
                Депрессия <MathText text="Δp = p_к − p_с" />
              </span>
              <span className="font-mono text-amber-300">{deltaP.toFixed(1)} МПа</span>
            </div>
            <input
              type="range"
              min={1.0}
              max={12.0}
              step={0.5}
              value={deltaP}
              onChange={(e) => setDeltaP(Number(e.target.value))}
              className="w-full accent-red-400"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs">
              <span>Мощность пласта h</span>
              <span className="font-mono text-emerald-300">{hM} м</span>
            </div>
            <input
              type="range"
              min={2}
              max={40}
              step={1}
              value={hM}
              onChange={(e) => setHM(Number(e.target.value))}
              className="w-full accent-emerald-400"
            />
          </div>

          <div>
            <div className="flex justify-between text-xs">
              <span>Время работы t (фронт ПССС)</span>
              <span className="font-mono text-emerald-300">{tHours.toFixed(1)} ч</span>
            </div>
            <input
              type="range"
              min={0.2}
              max={24.0}
              step={0.2}
              value={tHours}
              onChange={(e) => setTHours(Number(e.target.value))}
              className="w-full accent-emerald-400"
            />
          </div>

          <div className="mt-auto rounded-xl border border-slate-800 bg-slate-950 p-3 text-xs text-slate-300">
            <div className="font-semibold text-blue-400">Терминологический мост:</div>
            <div className="mt-1">κ (пьезопроводность) ↔ η (hydraulic diffusivity)</div>
            <div className="mt-0.5">
              <MathText text="R_к, p_к ↔ r_e, p_e · r_с, p_с ↔ r_w, p_wf" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
