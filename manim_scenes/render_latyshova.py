"""
Детерминированные Manim-сцены для Модуля 1: М.Г. Латышова (1991) — ГИС.
Все кривые строятся по массивам из backend.physics_engine.latyshova_gis.
"""

from __future__ import annotations

import numpy as np
from manim import (
    Axes,
    Create,
    DashedLine,
    DOWN,
    Dot,
    FadeIn,
    FadeOut,
    GREEN_C,
    LEFT,
    Line,
    ORANGE,
    RED_C,
    RIGHT,
    Rectangle,
    Scene,
    Text,
    UP,
    VGroup,
    WHITE,
    Write,
)

from backend.physics_engine.latyshova_gis import evaluate_archie_curve, simulate_well_log
from manim_scenes.common import (
    ACCENT_AMBER,
    ACCENT_CORAL,
    ACCENT_CYAN,
    ACCENT_EMERALD,
    PANEL_BG,
    load_manim_context,
    make_header,
    make_term_bridge_badge,
    safe_mathtex,
)


class LatyshovaIntroScene(Scene):
    """Сцена 1: Электропроводность горных пород и формула ρ_вп = P_п · ρ_в."""

    def construct(self) -> None:
        header = make_header(
            "Электропроводность пород-коллекторов",
            "Латышова М.Г. (1991), Глава I, §1 — формула (2)",
        )
        self.play(FadeIn(header))

        # Схема элемента породы: непроводящий скелет + проводящая поровая вода
        rock_box = Rectangle(width=4.6, height=3.2, color=ACCENT_AMBER, fill_color=PANEL_BG, fill_opacity=0.85)
        rock_box.shift(LEFT * 3.1 + DOWN * 0.2)
        grains = VGroup(
            *[
                Dot(
                    point=rock_box.get_center() + np.array([dx, dy, 0.0]),
                    radius=0.32,
                    color="#94A3B8",
                )
                for dx in (-1.4, -0.45, 0.5, 1.4)
                for dy in (-0.85, 0.05, 0.9)
            ]
        )
        pore_label = Text("Поровая вода ρ_в — проводник тока", font_size=18, color=ACCENT_CYAN)
        pore_label.next_to(rock_box, DOWN, buff=0.22)

        formula = safe_mathtex(r"\rho_{\text{вп}} = P_{\text{п}} \cdot \rho_{\text{в}}", font_size=46, color=WHITE)
        formula.shift(RIGHT * 2.8 + UP * 0.5)

        badge = make_term_bridge_badge("P_п", "Параметр пористости", "F", "Formation factor")
        badge.next_to(formula, DOWN, buff=0.55)

        self.play(FadeIn(rock_box), FadeIn(grains), Write(pore_label))
        self.play(Write(formula))
        self.play(FadeIn(badge))
        self.wait(4.0)


class LatyshovaArchieScene(Scene):
    """Сцена 2: Семейство кривых Арчи ρ_п(K_п) для воды и нефти."""

    def construct(self) -> None:
        ctx = load_manim_context()
        pdata = ctx.get("physics_data", {})
        archie = pdata.get("archie_family") or evaluate_archie_curve()

        header = make_header(
            "Уравнение Арчи–Дахнова: P_п и параметр насыщения P_н",
            "Зависимость удельного сопротивления от пористости K_п",
        )
        self.play(FadeIn(header))

        eq = safe_mathtex(
            r"P_{\text{п}} = \frac{a_m}{K_{\text{п}}^{m}}, \quad P_{\text{н}} = \frac{\rho_{\text{п}}}{\rho_{\text{вп}}} = \frac{a_n}{K_{\text{в}}^{n}}",
            font_size=34,
            color=WHITE,
        )
        eq.next_to(header, DOWN, buff=0.25)
        self.play(Write(eq))

        axes = Axes(
            x_range=[4, 34, 5],
            y_range=[0, 120, 20],
            x_length=6.8,
            y_length=3.9,
            axis_config={"color": "#64748B", "include_numbers": True, "font_size": 18},
        ).shift(LEFT * 2.0 + DOWN * 0.85)
        x_lbl = Text("Пористость K_п, %", font_size=18, color="#CBD5E1").next_to(axes.x_axis, DOWN, buff=0.2)
        y_lbl = Text("ρ_п, Ом·м", font_size=18, color="#CBD5E1").next_to(axes.y_axis, UP, buff=0.15)

        kp = archie["k_p_pct"]
        rho_vp = np.clip(archie["rho_vp_ohmm"], 0, 120)
        rho_oil = np.clip(archie["rho_oil_ohmm"], 0, 120)
        rho_crit = np.clip(archie["rho_crit_ohmm"], 0, 120)

        pts_vp = [axes.coords_to_point(x, y) for x, y in zip(kp, rho_vp)]
        pts_oil = [axes.coords_to_point(x, y) for x, y in zip(kp, rho_oil)]
        pts_crit = [axes.coords_to_point(x, y) for x, y in zip(kp, rho_crit)]

        line_vp = VGroup(*[Line(pts_vp[i], pts_vp[i + 1], color=ACCENT_CYAN, stroke_width=3.5) for i in range(len(pts_vp) - 1)])
        line_crit = VGroup(*[Line(pts_crit[i], pts_crit[i + 1], color=ACCENT_AMBER, stroke_width=3.0) for i in range(len(pts_crit) - 1)])
        line_oil = VGroup(*[Line(pts_oil[i], pts_oil[i + 1], color=ACCENT_EMERALD, stroke_width=3.8) for i in range(len(pts_oil) - 1)])

        legend = VGroup(
            Text("— Нефть (K_в = 0.22)", font_size=18, color=ACCENT_EMERALD),
            Text("— Граница нефть/вода (K_в* = 0.45)", font_size=18, color=ACCENT_AMBER),
            Text("— Вода 100% (ρ_вп)", font_size=18, color=ACCENT_CYAN),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.18).to_edge(RIGHT, buff=0.45).shift(DOWN * 0.2)

        badge = make_term_bridge_badge("K_п, P_н", "Пористость и насыщение", "φ, I = Rt/R0", "Porosity & Resistivity Index")
        badge.scale(0.85).next_to(legend, DOWN, buff=0.35)

        self.play(Create(axes), Write(x_lbl), Write(y_lbl))
        self.play(Create(line_vp), Create(line_crit), Create(line_oil), run_time=3.0)
        self.play(FadeIn(legend), FadeIn(badge))
        self.wait(3.0)


class LatyshovaWellLogScene(Scene):
    """Сцена 3: Каротажная диаграмма КС (ρ_БК, ρ_МБК) + СП (α_СП) и отбивка ВНК."""

    def construct(self) -> None:
        ctx = load_manim_context()
        pdata = ctx.get("physics_data")
        if not pdata or "logs" not in pdata:
            pdata = simulate_well_log()

        logs = pdata["logs"]
        params = pdata["parameters"]
        z = logs["depth_m"]
        alpha_sp = logs["alpha_sp"]
        rho_bk = np.log10(np.clip(logs["rho_bk_ohmm"], 0.5, 200.0))
        rho_mbk = np.log10(np.clip(logs["rho_mbk_ohmm"], 0.5, 200.0))
        vnk = params["vnk_depth_m"]

        header = make_header(
            "Выделение коллекторов и отбивка ВНК по комплексу ГИС",
            f"Кривые α_СП и ρ_БК / ρ_МБК (ВНК = {vnk:.1f} м)",
        )
        self.play(FadeIn(header))

        # Трек 1: ПС (alpha_sp)
        ax_sp = Axes(
            x_range=[0, 1.05, 0.5],
            y_range=[2450, 2400, -10],
            x_length=3.6,
            y_length=4.7,
            axis_config={"color": "#64748B", "include_numbers": True, "font_size": 16},
        ).shift(LEFT * 3.2 + DOWN * 0.5)
        sp_title = Text("α_СП (отсечка 0.45)", font_size=18, color=ACCENT_CYAN).next_to(ax_sp, UP, buff=0.15)

        # Трек 2: КС log10(rho)
        ax_ks = Axes(
            x_range=[0, 2.2, 1.0],
            y_range=[2450, 2400, -10],
            x_length=4.2,
            y_length=4.7,
            axis_config={"color": "#64748B", "include_numbers": True, "font_size": 16},
        ).shift(RIGHT * 1.8 + DOWN * 0.5)
        ks_title = Text("lg(ρ_БК) vs lg(ρ_МБК)", font_size=18, color=ACCENT_EMERALD).next_to(ax_ks, UP, buff=0.15)

        sp_pts = [ax_sp.coords_to_point(x, y) for x, y in zip(alpha_sp, z)]
        bk_pts = [ax_ks.coords_to_point(x, y) for x, y in zip(rho_bk, z)]
        mbk_pts = [ax_ks.coords_to_point(x, y) for x, y in zip(rho_mbk, z)]

        curve_sp = VGroup(*[Line(sp_pts[i], sp_pts[i + 1], color=ACCENT_CYAN, stroke_width=3.0) for i in range(len(sp_pts) - 1)])
        curve_bk = VGroup(*[Line(bk_pts[i], bk_pts[i + 1], color=ACCENT_EMERALD, stroke_width=3.2) for i in range(len(bk_pts) - 1)])
        curve_mbk = VGroup(*[Line(mbk_pts[i], mbk_pts[i + 1], color=ACCENT_AMBER, stroke_width=2.5) for i in range(len(mbk_pts) - 1)])

        cutoff_line = DashedLine(
            ax_sp.coords_to_point(0.45, 2400),
            ax_sp.coords_to_point(0.45, 2450),
            color=ACCENT_CORAL,
        )
        vnk_line = DashedLine(
            ax_ks.coords_to_point(0.0, vnk),
            ax_ks.coords_to_point(2.2, vnk),
            color=RED_C,
        )
        vnk_label = Text(f"ВНК (OWC) {vnk:.0f} м", font_size=18, color=RED_C).next_to(vnk_line, RIGHT, buff=0.15)

        self.play(Create(ax_sp), Create(ax_ks), Write(sp_title), Write(ks_title))
        self.play(Create(cutoff_line), Create(curve_sp), Create(curve_bk), Create(curve_mbk), run_time=3.5)
        self.play(Create(vnk_line), Write(vnk_label))
        self.wait(3.5)
