"""
Детерминированный научный рендер сцен через Matplotlib + FFmpeg (1920x1080, 30 fps)
в визуальной стилистике эталонных роликов:
- тёмный графитовый чертёжный фон (#0B101B) с тонкой технической сеткой
- выноски-указатели с точками на кривых (как в 01.mp4 / 05.mp4)
- схемы разреза пласта и порового пространства рядом с уравнениями (как в 03.mp4 / 06.mp4)
- бейджи терминологического моста СНГ ↔ Запад
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np


BG_COLOR = "#0B101B"
GRID_COLOR = "#162033"
PANEL_COLOR = "#111827"
CARD_EDGE = "#263349"
CYAN = "#38BDF8"
AMBER = "#F59E0B"
EMERALD = "#10B981"
CORAL = "#F43F5E"
TEXT_LIGHT = "#F8FAFC"
TEXT_MUTED = "#94A3B8"


def _draw_engineering_backdrop(fig: Any, module_label: str, title: str, subtitle: str) -> None:
    """Рисует фоновую техническую сетку, верхний пилл-бэдж и заголовок (стиль 04/05.mp4)."""
    bg_ax = fig.add_axes([0, 0, 1, 1], zorder=-10)
    bg_ax.set_facecolor(BG_COLOR)
    bg_ax.set_xlim(0, 16)
    bg_ax.set_ylim(0, 9)
    for x in np.linspace(0, 16, 33):
        bg_ax.axvline(x, color=GRID_COLOR, linewidth=0.6, alpha=0.7)
    for y in np.linspace(0, 9, 19):
        bg_ax.axhline(y, color=GRID_COLOR, linewidth=0.6, alpha=0.7)
    bg_ax.axis("off")

    fig.text(
        0.05,
        0.945,
        f"●  {module_label}",
        fontsize=11,
        fontweight="bold",
        color=AMBER,
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#172033", edgecolor="#334155", linewidth=0.9),
    )
    fig.text(0.05, 0.895, title[:70], fontsize=22, fontweight="bold", color=TEXT_LIGHT)
    fig.text(0.05, 0.858, subtitle[:92], fontsize=12.5, color=CYAN)


def _apply_dark_style(ax: Any) -> None:
    ax.set_facecolor(PANEL_COLOR)
    ax.tick_params(colors=TEXT_MUTED, labelsize=11)
    for spine in ax.spines.values():
        spine.set_color(CARD_EDGE)
    ax.grid(True, color="#1E293B", linestyle="--", linewidth=0.8)


def _draw_bridge_footer(fig: Any, scene: dict[str, Any]) -> None:
    bridges = scene.get("term_bridges") or []
    if not bridges:
        return
    b = bridges[0]
    ru_txt = f"СНГ: {b.get('ru_symbol', '')} ({b.get('ru_term', '')})"
    en_txt = f"West: {b.get('en_symbol', '')} ({b.get('en_term', '')})"
    fig.text(
        0.5,
        0.048,
        f"{ru_txt}   ↔   {en_txt}"[:118],
        ha="center",
        va="center",
        fontsize=13,
        fontweight="bold",
        color=CYAN,
        bbox=dict(boxstyle="round,pad=0.55", facecolor="#0F172A", edgecolor=CYAN, linewidth=1.2),
    )


def _render_frames_to_mp4(frames_dir: Path, out_mp4: Path, input_fps: int = 8, output_fps: int = 30) -> bool:
    if shutil.which("ffmpeg") is None:
        return False
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(input_fps),
        "-i",
        str(frames_dir / "frame_%04d.png"),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        str(output_fps),
        str(out_mp4),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return proc.returncode == 0 and out_mp4.exists()


def render_scene_matplotlib(
    manifest: dict[str, Any],
    scene: dict[str, Any],
    out_mp4: Path,
    work_dir: Path,
) -> bool:
    """Генерирует анимированный научный MP4-ролик 1920x1080 (8->30 fps) для одной сцены."""
    work_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = work_dir / f"frames_{scene['scene_id']}"
    if frames_dir.exists():
        shutil.rmtree(frames_dir, ignore_errors=True)
    frames_dir.mkdir(parents=True, exist_ok=True)

    input_fps = 6
    dur = float(scene.get("duration_sec", 8.0))
    n_frames = max(24, min(48, int(dur * 3.5)))
    cls_name = scene.get("manim_scene_class", "")
    pdata = manifest.get("physics_data", {})
    mod_type = manifest.get("module_type", "generic_chapter")
    mod_label = (
        "МОДУЛЬ 1 · ГИС (ЛАТЫШОВА 1991)"
        if mod_type == "latyshova_gis"
        else "МОДУЛЬ 2 · ГИДРОМЕХАНИКА (БАСНИЕВ 2005)"
        if mod_type == "basniev_hydro"
        else "МОДУЛЬ КУРСА · LITHOS ENGINE"
    )

    for fi in range(n_frames):
        progress = (fi + 1) / n_frames
        fig = plt.figure(figsize=(12.8, 7.2), dpi=150, facecolor=BG_COLOR)
        _draw_engineering_backdrop(
            fig,
            mod_label,
            scene.get("title", ""),
            manifest.get("book_title", ""),
        )

        if cls_name == "LatyshovaIntroScene":
            # Схематичное поперечное сечение поровых каналов и зёрен (как в 03.mp4 / 06.mp4)
            ax = fig.add_axes([0.06, 0.14, 0.44, 0.67])
            ax.set_facecolor("#0F172A")
            ax.set_xlim(0, 10)
            ax.set_ylim(0, 8)
            ax.set_xticks([])
            ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_color(CARD_EDGE)
            # Поровая вода (фон) + зёрна скелета (изоляторы)
            ax.add_patch(patches.Rectangle((0.3, 0.3), 9.4, 7.4, facecolor="#0C4A6E", alpha=0.45))
            grains = [(1.8, 1.8, 0.95), (4.2, 1.7, 1.05), (7.1, 1.9, 1.0),
                      (2.3, 4.2, 1.05), (5.3, 4.3, 0.95), (8.0, 4.5, 0.9),
                      (1.9, 6.4, 0.9), (4.8, 6.5, 1.0), (7.4, 6.4, 0.95)]
            for gx, gy, gr in grains:
                ax.add_patch(patches.Circle((gx, gy), gr, facecolor="#64748B", edgecolor="#CBD5E1", linewidth=1.2))
            # Линия тока через поровую воду
            xs = np.linspace(0.6, 9.4, 60)
            ys = 3.0 + 0.55 * np.sin(xs * 1.4)
            cut_t = max(2, int(len(xs) * progress))
            ax.plot(xs[:cut_t], ys[:cut_t], color=CYAN, linewidth=3.5)
            if cut_t >= 2:
                ax.scatter([xs[cut_t - 1]], [ys[cut_t - 1]], color=AMBER, s=75, zorder=5)
            ax.set_title("Поровая вода ρ_в (проводник) vs зёрна (изолятор)", color=CYAN, fontsize=12)

            fig.text(
                0.55,
                0.53,
                "Сопротивление водоносной породы:\n\n"
                "   ρ_вп = P_п · ρ_в     (формула 2)\n\n"
                "• Скелет (кварц, кальцит): 10⁷–10¹⁵ Ом·м\n"
                "• Ток течёт по электролиту в порах\n"
                "• Рост минерализации C -> снижение ρ_в",
                va="center",
                fontsize=14,
                color=TEXT_LIGHT,
                bbox=dict(boxstyle="round,pad=0.8", facecolor=PANEL_COLOR, edgecolor=AMBER, linewidth=1.6),
            )

        elif cls_name == "LatyshovaArchieScene" and "archie_family" in pdata:
            arch = pdata["archie_family"]
            kp = arch["k_p_pct"]
            cut = max(2, int(len(kp) * progress))
            ax = fig.add_axes([0.08, 0.16, 0.56, 0.64])
            _apply_dark_style(ax)
            y_oil = np.clip(arch["rho_oil_ohmm"], 0, 140)
            y_crit = np.clip(arch["rho_crit_ohmm"], 0, 140)
            y_vp = np.clip(arch["rho_vp_ohmm"], 0, 140)

            ax.plot(kp[:cut], y_oil[:cut], color=EMERALD, linewidth=3.2, label="Нефть (K_в = 0.22)")
            ax.plot(kp[:cut], y_crit[:cut], color=AMBER, linewidth=2.6, linestyle="--", label="Граница (K_в* = 0.45)")
            ax.plot(kp[:cut], y_vp[:cut], color=CYAN, linewidth=3.2, label="Вода 100% (ρ_вп)")

            # Выноска-указатель с точкой (как в 01.mp4)
            if cut > 6:
                idx_m = min(cut - 1, len(kp) // 3)
                ax.scatter([kp[idx_m]], [y_oil[idx_m]], color=EMERALD, s=65, zorder=6)
                ax.annotate(
                    f"ρ_п ≈ {y_oil[idx_m]:.1f} Ом·м",
                    xy=(kp[idx_m], y_oil[idx_m]),
                    xytext=(kp[idx_m] + 4, min(125, y_oil[idx_m] + 18)),
                    color=EMERALD,
                    fontsize=11,
                    fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=EMERALD, lw=1.4),
                    bbox=dict(boxstyle="round,pad=0.25", facecolor="#0F172A", edgecolor=EMERALD),
                )

            ax.set_xlim(min(kp), max(kp))
            ax.set_ylim(0, 140)
            ax.set_xlabel("Пористость K_п, %", color=TEXT_LIGHT, fontsize=12)
            ax.set_ylabel("Сопротивление ρ_п, Ом·м", color=TEXT_LIGHT, fontsize=12)
            ax.legend(facecolor=PANEL_COLOR, edgecolor=CARD_EDGE, labelcolor=TEXT_LIGHT, fontsize=10.5)

            fig.text(
                0.68,
                0.54,
                "Уравнения Арчи–Дахнова:\n\n"
                "  P_п = a_m / K_п^m\n\n"
                "  P_н = ρ_п / ρ_вп = a_n / K_в^n\n\n"
                "  K_нг = 1 − K_в\n\n"
                "• m = 1.3–2.2 (цементация)\n"
                "• При нефти P_н >> 1",
                va="center",
                fontsize=13.5,
                color=TEXT_LIGHT,
                bbox=dict(boxstyle="round,pad=0.75", facecolor=PANEL_COLOR, edgecolor=AMBER, linewidth=1.6),
            )

        elif cls_name == "LatyshovaWellLogScene" and "logs" in pdata:
            logs = pdata["logs"]
            z = logs["depth_m"]
            cut = max(2, int(len(z) * progress))
            vnk = pdata.get("parameters", {}).get("vnk_depth_m", 2425.0)
            ax1 = fig.add_axes([0.08, 0.16, 0.24, 0.65])
            ax2 = fig.add_axes([0.37, 0.16, 0.30, 0.65])
            _apply_dark_style(ax1)
            _apply_dark_style(ax2)

            ax1.plot(logs["alpha_sp"][:cut], z[:cut], color=CYAN, linewidth=2.8)
            ax1.axvline(0.45, color=CORAL, linestyle="--", linewidth=1.6)
            ax1.set_xlim(0, 1.05)
            ax1.set_ylim(max(z), min(z))
            ax1.set_title("α_СП (отсечка 0.45)", color=CYAN, fontsize=12)
            ax1.set_ylabel("Глубина, м", color=TEXT_LIGHT, fontsize=12)

            ax2.plot(logs["rho_bk_ohmm"][:cut], z[:cut], color=EMERALD, linewidth=2.8, label="ρ_БК")
            ax2.plot(logs["rho_mbk_ohmm"][:cut], z[:cut], color=AMBER, linewidth=2.0, linestyle="--", label="ρ_МБК")
            ax2.axhline(vnk, color="#EF4444", linestyle="--", linewidth=2.0)
            ax2.text(2.0, vnk - 1.2, f"ВНК / OWC = {vnk:.1f} м", color="#FCA5A5", fontsize=10.5, fontweight="bold")
            # Живой маркер зонда на текущей глубине
            ax1.axhline(z[cut - 1], color="#FACC15", linewidth=1.4)
            ax2.axhline(z[cut - 1], color="#FACC15", linewidth=1.4)
            ax2.set_xscale("log")
            ax2.set_xlim(0.5, 200)
            ax2.set_ylim(max(z), min(z))
            ax2.set_title("Кривые КС (Ом·м)", color=EMERALD, fontsize=12)
            ax2.legend(facecolor=PANEL_COLOR, edgecolor=CARD_EDGE, labelcolor=TEXT_LIGHT, fontsize=10)

            summary = pdata.get("summary", {})
            fig.text(
                0.71,
                0.53,
                f"Интерпретация по разрезу:\n\n"
                f"• h_эф (нефть): {summary.get('net_pay_oil_m', 0)} м\n"
                f"• max ρ_БК: {summary.get('max_rho_bk_ohmm', 0)} Ом·м\n"
                f"• max P_н: {summary.get('max_p_n', 0)}\n"
                f"• ВНК: {vnk:.1f} м\n\n"
                "Понижающее проникновение:\n"
                "ρ_МБК < ρ_БК (нефть)",
                va="center",
                fontsize=13,
                color=TEXT_LIGHT,
                bbox=dict(boxstyle="round,pad=0.7", facecolor=PANEL_COLOR, edgecolor=EMERALD, linewidth=1.6),
            )

        elif cls_name == "BasnievDarcyScene":
            # Потоковая трубка в пласте + градиент давления
            ax = fig.add_axes([0.07, 0.16, 0.50, 0.64])
            _apply_dark_style(ax)
            x = np.linspace(0, 100, 50)
            p_line = 24.0 - 0.08 * x
            ax.plot(x, p_line, color=AMBER, linewidth=3.4, label="Давление p(x)")
            ax.fill_between(x, 14, p_line, color=AMBER, alpha=0.14)
            # Движущиеся маркеры фильтрации
            shift = (progress * 90) % 90
            for yy in (15.5, 17.0, 18.5):
                ax.annotate("", xy=(shift + 12, yy), xytext=(shift + 2, yy),
                            arrowprops=dict(arrowstyle="->", color=CYAN, lw=2.5))
            ax.set_xlim(0, 100)
            ax.set_ylim(14, 26)
            ax.set_xlabel("Координата x вдоль пласта, м", color=TEXT_LIGHT, fontsize=12)
            ax.set_ylabel("Давление p, МПа", color=TEXT_LIGHT, fontsize=12)
            ax.legend(facecolor=PANEL_COLOR, edgecolor=CARD_EDGE, labelcolor=TEXT_LIGHT, fontsize=11)

            fig.text(
                0.62,
                0.54,
                "Закон Дарси (Глава XVIII, §4):\n\n"
                "   w = −(k / μ) · grad(p)\n\n"
                "   v = w / m   (истинная скорость)\n\n"
                "• 1 мД = 10⁻¹⁵ м²\n"
                "• 1 мПа·с = 10⁻³ Па·с\n"
                "• Знак «−»: поток к низкому p",
                va="center",
                fontsize=13.5,
                color=TEXT_LIGHT,
                bbox=dict(boxstyle="round,pad=0.75", facecolor=PANEL_COLOR, edgecolor=CYAN, linewidth=1.6),
            )

        elif cls_name in ("BasnievDupuitScene", "BasnievConeScene") and "dupuit" in pdata:
            prof = pdata["dupuit"]["radial_profile"]
            r = prof["r_m"]
            p = prof["p_mpa"]
            cut = max(2, int(len(r) * progress))
            ax = fig.add_axes([0.08, 0.16, 0.56, 0.64])
            _apply_dark_style(ax)
            ax.plot(r[:cut], p[:cut], color=AMBER, linewidth=3.4, label="Воронка депрессии p(r)")
            ax.fill_between(r[:cut], min(p) - 1.5, p[:cut], color=AMBER, alpha=0.12)
            ax.axhline(pdata["dupuit"]["inputs"]["p_k_mpa"], color=CYAN, linestyle="--", linewidth=1.6)
            if cut > 6:
                im = min(cut - 1, len(r) // 4)
                ax.scatter([r[im]], [p[im]], color=CYAN, s=65, zorder=6)
                ax.annotate(
                    f"r={r[im]:.1f} м, p={p[im]:.1f} МПа",
                    xy=(r[im], p[im]),
                    xytext=(r[im] + 25, p[im] - 1.4),
                    color=CYAN,
                    fontsize=10.5,
                    fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color=CYAN, lw=1.4),
                    bbox=dict(boxstyle="round,pad=0.25", facecolor="#0F172A", edgecolor=CYAN),
                )
            ax.set_xlim(0, max(r))
            ax.set_ylim(min(p) - 1.5, max(p) + 1.5)
            ax.set_xlabel("Радиус r, м", color=TEXT_LIGHT, fontsize=12)
            ax.set_ylabel("Давление p, МПа", color=TEXT_LIGHT, fontsize=12)
            ax.legend(facecolor=PANEL_COLOR, edgecolor=CARD_EDGE, labelcolor=TEXT_LIGHT, fontsize=11)

            metrics = pdata["dupuit"]["metrics"]
            fig.text(
                0.68,
                0.54,
                f"Формула Дюпюи (20.19):\n\n"
                f"  Q = 2πkh(p_к − p_с) / [μ ln(R_к/r_с)]\n\n"
                f"• Дебит Q = {metrics.get('q_m3_day', 0)} м³/сут\n"
                f"• Индекс C = {metrics.get('productivity_index_m3_day_mpa', 0)} м³/(сут·МПа)\n"
                f"• Скорость на забое: {metrics.get('w_wellbore_mm_s', 0)} мм/с",
                va="center",
                fontsize=12.5,
                color=TEXT_LIGHT,
                bbox=dict(boxstyle="round,pad=0.7", facecolor=PANEL_COLOR, edgecolor=AMBER, linewidth=1.6),
            )

        elif cls_name == "BasnievPSSSScene" and "transient_psss" in pdata:
            tr = pdata["transient_psss"]
            r = tr["r_m"]
            snaps = tr["snapshots"]
            ax = fig.add_axes([0.08, 0.16, 0.56, 0.64])
            _apply_dark_style(ax)
            colors = [CYAN, EMERALD, AMBER, CORAL]
            visible = max(1, int(np.ceil(progress * len(snaps))))
            for idx, snap in enumerate(snaps[:visible]):
                ax.plot(r, snap["p_psss_mpa"], color=colors[idx % 4], linewidth=2.8, label=f"t={snap['time_hours']} ч · R(t)={snap['r_front_m']} м")
            ax.set_xlim(0, max(r))
            ax.set_xlabel("Радиус r, м", color=TEXT_LIGHT, fontsize=12)
            ax.set_ylabel("Давление p(r, t), МПа", color=TEXT_LIGHT, fontsize=12)
            ax.legend(facecolor=PANEL_COLOR, edgecolor=CARD_EDGE, labelcolor=TEXT_LIGHT, fontsize=10)
            fig.text(
                0.68,
                0.54,
                f"Метод ПССС (И.А. Чарный):\n\n"
                f"  κ = k / (μ·β*) = {tr['parameters']['kappa_m2_s']} м²/с\n\n"
                f"  R(t) = √(r_с² + 4κt)\n\n"
                f"• Сравнение с точным\n"
                f"  решением через Ei(-r²/4κt)",
                va="center",
                fontsize=13,
                color=TEXT_LIGHT,
                bbox=dict(boxstyle="round,pad=0.7", facecolor=PANEL_COLOR, edgecolor=CYAN, linewidth=1.6),
            )

        else:
            # Карточка с формулами, выводами и Domain QA предупреждением
            formulas = scene.get("formulas") or []
            takeaways = scene.get("key_takeaways") or []
            body_lines = []
            if scene.get("methodology_only_nomogram"):
                body_lines.append("[Domain QA] Неоцифрованная палетка: только методика считывания (без выдуманных чисел)\n")
            if formulas:
                f0 = formulas[0]
                body_lines.append(f"Уравнение: {f0.get('title', '')}")
                body_lines.append(f"  {f0.get('latex', '')}\n")
                if f0.get("western_latex"):
                    body_lines.append(f"  West: {f0.get('western_latex')}\n")
            for tk in takeaways[:4]:
                body_lines.append(f"• {tk}")
            if not body_lines:
                body_lines.append(scene.get("narration", "")[:240])
            fig.text(
                0.07,
                0.52,
                "\n".join(body_lines),
                va="center",
                fontsize=14.5,
                color=TEXT_LIGHT,
                bbox=dict(boxstyle="round,pad=0.85", facecolor=PANEL_COLOR, edgecolor=AMBER, linewidth=1.6),
            )

        _draw_bridge_footer(fig, scene)
        frame_path = frames_dir / f"frame_{fi:04d}.png"
        fig.savefig(frame_path, facecolor=BG_COLOR)
        plt.close(fig)

    ok = _render_frames_to_mp4(frames_dir, out_mp4, input_fps=input_fps, output_fps=30)
    shutil.rmtree(frames_dir, ignore_errors=True)
    return ok
