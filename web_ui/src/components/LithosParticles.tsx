import React, { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { Pause, Play } from "lucide-react";

export type ParticleShapeMode = "strata" | "wellbore" | "funnel";

interface LithosParticlesProps {
  mode: ParticleShapeMode;
  onModeChange: (mode: ParticleShapeMode) => void;
  active?: boolean;
  className?: string;
}

declare global {
  interface Window {
    __LITHOS_PARTICLES__?: {
      particleCount: number;
      mode: ParticleShapeMode;
      paused: boolean;
      webglAvailable: boolean;
      renderer: string;
      fps: number;
    };
  }
}

const SHAPE_META: Record<ParticleShapeMode, { label: string; caption: string; tag: string }> = {
  strata: {
    label: "Слои породы",
    caption: "Осадочные горизонты и границы пластов в разрезе — декоративная визуализация атласа",
    tag: "Схема",
  },
  wellbore: {
    label: "Скважина и ГИС",
    caption: "Ствол скважины, зона проникновения фильтрата и граница водонефтяного контакта",
    tag: "Симуляция",
  },
  funnel: {
    label: "Воронка депрессии",
    caption: "Логарифмическое падение давления p(r) при радиальном притоке к забою скважины",
    tag: "Симуляция",
  },
};

const VERTEX_SHADER = `
  attribute vec3 aPosWellbore;
  attribute vec3 aPosFunnel;
  attribute vec3 aColStrata;
  attribute vec3 aColWellbore;
  attribute vec3 aColFunnel;
  attribute float aSeed;

  uniform float uTime;
  uniform float uWStrata;
  uniform float uWWellbore;
  uniform float uWFunnel;
  uniform float uPointScale;
  uniform float uReducedMotion;

  varying vec3 vColor;
  varying float vAlpha;

  void main() {
    vec3 p = position * uWStrata + aPosWellbore * uWWellbore + aPosFunnel * uWFunnel;
    vec3 c = aColStrata * uWStrata + aColWellbore * uWWellbore + aColFunnel * uWFunnel;

    float motion = 1.0 - uReducedMotion;
    float wave = sin(p.x * 0.45 + uTime * 0.65 + aSeed * 6.2831) * 0.09 * motion;
    float drift = cos(p.z * 0.35 - uTime * 0.45 + aSeed * 3.1415) * 0.06 * motion;
    p.y += wave;
    p.x += drift * uWFunnel * 0.8;

    vec4 mvPosition = modelViewMatrix * vec4(p, 1.0);
    gl_Position = projectionMatrix * mvPosition;

    float depth = max(1.8, -mvPosition.z);
    gl_PointSize = clamp((uPointScale / depth) * (0.75 + 0.55 * aSeed), 1.0, 4.2);

    vColor = c;
    vAlpha = clamp(0.88 - (depth - 4.0) * 0.045, 0.22, 0.88);
  }
`;

const FRAGMENT_SHADER = `
  varying vec3 vColor;
  varying float vAlpha;

  void main() {
    vec2 uv = gl_PointCoord - vec2(0.5);
    float d2 = dot(uv, uv);
    if (d2 > 0.25) discard;
    float soft = smoothstep(0.25, 0.03, d2);
    gl_FragColor = vec4(vColor, vAlpha * soft);
  }
`;

export const LithosParticles: React.FC<LithosParticlesProps> = ({
  mode,
  onModeChange,
  active = true,
  className = "",
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const modeRef = useRef<ParticleShapeMode>(mode);
  const activeRef = useRef<boolean>(active);
  const pausedRef = useRef<boolean>(false);
  const [paused, setPaused] = useState(false);
  const [webglOk, setWebglOk] = useState(true);
  const [particleCount, setParticleCount] = useState(300000);

  useEffect(() => {
    modeRef.current = mode;
    if (window.__LITHOS_PARTICLES__) window.__LITHOS_PARTICLES__.mode = mode;
  }, [mode]);

  useEffect(() => {
    activeRef.current = active;
    if (window.__LITHOS_PARTICLES__) window.__LITHOS_PARTICLES__.paused = paused || !active;
  }, [active, paused]);

  useEffect(() => {
    pausedRef.current = paused;
    if (window.__LITHOS_PARTICLES__) window.__LITHOS_PARTICLES__.paused = paused || !active;
  }, [paused, active]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // 300,000 particles in full mode (single GPU BufferGeometry draw call)
    const isNarrowMobile = typeof window !== "undefined" && window.innerWidth < 480;
    const COUNT = isNarrowMobile ? 150000 : 300000;
    setParticleCount(COUNT);

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: false,
        alpha: true,
        powerPreference: "high-performance",
      });
    } catch {
      setWebglOk(false);
      window.__LITHOS_PARTICLES__ = {
        particleCount: 0,
        mode: modeRef.current,
        paused: true,
        webglAvailable: false,
        renderer: "svg-fallback",
        fps: 0,
      };
      return;
    }

    const gl = renderer.getContext();
    const debugInfo = gl.getExtension("WEBGL_debug_renderer_info");
    const gpuName = debugInfo ? String(gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL)) : "WebGL";

    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75));
    renderer.setSize(container.clientWidth || 900, container.clientHeight || 520);
    renderer.setClearColor(0x000000, 0);
    container.innerHTML = "";
    container.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      46,
      (container.clientWidth || 900) / Math.max(1, container.clientHeight || 520),
      0.1,
      100
    );
    camera.position.set(0, 1.45, 8.6);
    camera.lookAt(0, -0.1, 0);

    // Allocate compact Float32Arrays for 300,000 GPU particles
    const posStrata = new Float32Array(COUNT * 3);
    const posWell = new Float32Array(COUNT * 3);
    const posFunnel = new Float32Array(COUNT * 3);
    const colStrata = new Float32Array(COUNT * 3);
    const colWell = new Float32Array(COUNT * 3);
    const colFunnel = new Float32Array(COUNT * 3);
    const seeds = new Float32Array(COUNT);

    // Deterministic fast LCG PRNG
    let rng = 133742;
    const rand = () => {
      rng = (rng * 1664525 + 1013904223) >>> 0;
      return rng / 4294967296;
    };

    const strataPalette = [
      [0.85, 0.47, 0.21], // copper sandstone
      [0.64, 0.56, 0.46], // warm siltstone
      [0.22, 0.74, 0.97], // aquifer sky
      [0.06, 0.72, 0.50], // oil-bearing emerald
      [0.42, 0.46, 0.54], // slate shale
    ];

    for (let i = 0; i < COUNT; i++) {
      const i3 = i * 3;
      const s = rand();
      seeds[i] = s;

      // 1) STRATA: layered sedimentary beds extending horizontally toward library
      const layerIdx = Math.floor(rand() * 5);
      const sx = (rand() - 0.5) * 14.5;
      const sz = (rand() - 0.5) * 6.0;
      const fold = Math.sin(sx * 0.34 + layerIdx * 0.55) * 0.55 + Math.cos(sz * 0.5) * 0.22;
      const sy = -2.2 + layerIdx * 1.02 + fold + (rand() - 0.5) * 0.22;
      posStrata[i3] = sx;
      posStrata[i3 + 1] = sy;
      posStrata[i3 + 2] = sz;
      const sc = strataPalette[layerIdx];
      const shade = 0.75 + rand() * 0.35;
      colStrata[i3] = sc[0] * shade;
      colStrata[i3 + 1] = sc[1] * shade;
      colStrata[i3 + 2] = sc[2] * shade;

      // 2) WELLBORE: vertical borehole cylinder + radial invasion rings + VNK horizon
      const isCore = rand() < 0.28;
      const wy = (rand() - 0.5) * 5.8;
      const theta = rand() * Math.PI * 2;
      const rWell = isCore ? 0.35 + rand() * 0.22 : 0.75 + Math.pow(rand(), 0.75) * 3.8;
      posWell[i3] = Math.cos(theta) * rWell;
      posWell[i3 + 1] = wy;
      posWell[i3 + 2] = Math.sin(theta) * rWell;
      if (isCore) {
        // Borehole probe & mud column (copper)
        colWell[i3] = 0.9;
        colWell[i3 + 1] = 0.56;
        colWell[i3 + 2] = 0.28;
      } else if (wy > 0.15) {
        // Oil zone above VNK (emerald)
        colWell[i3] = 0.08;
        colWell[i3 + 1] = 0.76;
        colWell[i3 + 2] = 0.52;
      } else if (wy > -0.15) {
        // VNK contact line (rose)
        colWell[i3] = 0.95;
        colWell[i3 + 1] = 0.27;
        colWell[i3 + 2] = 0.38;
      } else {
        // Formation water below VNK (sky)
        colWell[i3] = 0.18;
        colWell[i3 + 1] = 0.68;
        colWell[i3 + 2] = 0.96;
      }

      // 3) FUNNEL: Dupuit logarithmic pressure depression cone p(r) ~ ln(r / r_c)
      const fr = 0.24 + Math.pow(rand(), 0.65) * 5.4;
      const fTheta = rand() * Math.PI * 2;
      const logDrop = Math.log(fr / 0.22) / Math.log(5.64 / 0.22); // 0 at wellbore -> 1 at boundary
      const fy = -2.15 + logDrop * 3.85 + (rand() - 0.5) * 0.16;
      posFunnel[i3] = Math.cos(fTheta) * fr;
      posFunnel[i3 + 1] = fy;
      posFunnel[i3 + 2] = Math.sin(fTheta) * fr;
      // Color gradient from amber-red high-gradient wellbore to cool blue outer boundary
      colFunnel[i3] = 0.95 * (1.0 - logDrop) + 0.18 * logDrop;
      colFunnel[i3 + 1] = 0.52 * (1.0 - logDrop) + 0.72 * logDrop;
      colFunnel[i3 + 2] = 0.18 * (1.0 - logDrop) + 0.96 * logDrop;
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(posStrata, 3));
    geometry.setAttribute("aPosWellbore", new THREE.BufferAttribute(posWell, 3));
    geometry.setAttribute("aPosFunnel", new THREE.BufferAttribute(posFunnel, 3));
    geometry.setAttribute("aColStrata", new THREE.BufferAttribute(colStrata, 3));
    geometry.setAttribute("aColWellbore", new THREE.BufferAttribute(colWell, 3));
    geometry.setAttribute("aColFunnel", new THREE.BufferAttribute(colFunnel, 3));
    geometry.setAttribute("aSeed", new THREE.BufferAttribute(seeds, 1));

    const uniforms = {
      uTime: { value: 0 },
      uWStrata: { value: modeRef.current === "strata" ? 1 : 0 },
      uWWellbore: { value: modeRef.current === "wellbore" ? 1 : 0 },
      uWFunnel: { value: modeRef.current === "funnel" ? 1 : 0 },
      uPointScale: { value: 14.5 },
      uReducedMotion: { value: prefersReduced ? 1.0 : 0.0 },
    };

    const material = new THREE.ShaderMaterial({
      vertexShader: VERTEX_SHADER,
      fragmentShader: FRAGMENT_SHADER,
      uniforms,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });

    const points = new THREE.Points(geometry, material);
    scene.add(points);

    let inViewport = true;
    let tabVisible = !document.hidden;
    let rafId = 0;
    let lastTs = performance.now();
    let fpsAccum = 0;
    let fpsFrames = 0;
    let measuredFps = 0;
    let activeDrawCount = COUNT;

    const io = new IntersectionObserver(
      (entries) => {
        inViewport = entries[0]?.isIntersecting ?? true;
      },
      { threshold: 0.05 }
    );
    io.observe(container);

    const onVis = () => {
      tabVisible = !document.hidden;
    };
    document.addEventListener("visibilitychange", onVis);

    const onResize = () => {
      if (!container) return;
      const w = container.clientWidth || 900;
      const h = Math.max(1, container.clientHeight || 520);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener("resize", onResize);

    // Render one immediate frame so reduced-motion & initial paint look crisp
    renderer.render(scene, camera);

    const updateTelemetry = () => {
      window.__LITHOS_PARTICLES__ = {
        particleCount: activeDrawCount,
        mode: modeRef.current,
        paused: pausedRef.current || !activeRef.current || !inViewport || !tabVisible,
        webglAvailable: true,
        renderer: gpuName,
        fps: measuredFps,
      };
    };
    updateTelemetry();

    const animate = (now: number) => {
      rafId = requestAnimationFrame(animate);
      const dt = Math.min(0.05, Math.max(0.001, (now - lastTs) / 1000));
      lastTs = now;

      const shouldRun = activeRef.current && inViewport && tabVisible && !pausedRef.current;
      if (!shouldRun) {
        updateTelemetry();
        return;
      }

      // Smooth morph interpolation even under rapid mode switches
      const tS = modeRef.current === "strata" ? 1 : 0;
      const tW = modeRef.current === "wellbore" ? 1 : 0;
      const tF = modeRef.current === "funnel" ? 1 : 0;
      const lerp = prefersReduced ? 0.35 : Math.min(1, dt * 3.4);
      uniforms.uWStrata.value += (tS - uniforms.uWStrata.value) * lerp;
      uniforms.uWWellbore.value += (tW - uniforms.uWWellbore.value) * lerp;
      uniforms.uWFunnel.value += (tF - uniforms.uWFunnel.value) * lerp;
      const wSum = uniforms.uWStrata.value + uniforms.uWWellbore.value + uniforms.uWFunnel.value || 1;
      uniforms.uWStrata.value /= wSum;
      uniforms.uWWellbore.value /= wSum;
      uniforms.uWFunnel.value /= wSum;

      if (!prefersReduced) {
        uniforms.uTime.value += dt;
        points.rotation.y += dt * 0.045;
      }

      renderer.render(scene, camera);

      fpsAccum += dt;
      fpsFrames += 1;
      if (fpsAccum >= 0.75) {
        measuredFps = Math.round(fpsFrames / fpsAccum);
        // Adaptive pixel ratio step-down only if extremely slow (<14 fps on software/low-end)
        if (measuredFps < 14 && renderer.getPixelRatio() > 1) {
          renderer.setPixelRatio(1);
        }
        fpsAccum = 0;
        fpsFrames = 0;
        updateTelemetry();
      }
    };

    rafId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafId);
      io.disconnect();
      document.removeEventListener("visibilitychange", onVis);
      window.removeEventListener("resize", onResize);
      geometry.dispose();
      material.dispose();
      renderer.dispose();
    };
  }, []);

  const meta = SHAPE_META[mode];

  return (
    <div className={`relative overflow-hidden ${className}`}>
      {webglOk ? (
        <div
          ref={containerRef}
          className="h-full w-full"
          aria-label={`Интерактивная 3D-сцена из ${particleCount.toLocaleString("ru-RU")} частиц: ${meta.label}`}
        />
      ) : (
        <svg viewBox="0 0 960 440" className="h-full w-full opacity-70" role="img" aria-label={meta.caption}>
          <rect width="960" height="440" fill="#0E1014" />
          <path d="M0 240 Q240 190 480 235 T960 220 L960 440 L0 440 Z" fill="#1A1F29" />
          <path d="M0 300 Q260 265 520 305 T960 285 L960 440 L0 440 Z" fill="#232936" />
          <path d="M0 355 Q240 335 480 360 T960 345 L960 440 L0 440 Z" fill="#D97736" fillOpacity="0.18" />
        </svg>
      )}

      {/* Компактная панель управления формой и паузой внизу сцены */}
      <div className="pointer-events-auto absolute bottom-4 left-4 right-4 z-20 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#0E1014]/80 px-4 py-2.5 backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Форма частиц">
          {(["strata", "wellbore", "funnel"] as ParticleShapeMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => onModeChange(m)}
              aria-pressed={mode === m}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                mode === m
                  ? "bg-[#D97736] text-[#0E1014]"
                  : "text-[#A39E93] hover:bg-white/[0.06] hover:text-[#F4F1EA]"
              }`}
            >
              {SHAPE_META[m].label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3 text-sm text-[#A39E93]">
          <span className="hidden md:inline">
            <span className="mr-2 rounded bg-white/[0.07] px-1.5 py-0.5 text-xs text-[#F4F1EA]">{meta.tag}</span>
            {meta.caption}
          </span>
          <button
            type="button"
            onClick={() => setPaused((p) => !p)}
            aria-label={paused ? "Возобновить анимацию частиц" : "Поставить анимацию частиц на паузу"}
            className="inline-flex items-center gap-1.5 rounded-lg bg-white/[0.06] px-2.5 py-1.5 text-xs font-medium text-[#F4F1EA] hover:bg-white/[0.12]"
          >
            {paused ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
            <span>{paused ? "Старт" : "Пауза"}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
