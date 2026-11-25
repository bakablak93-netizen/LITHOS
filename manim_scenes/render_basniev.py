"""
Детерминированные Manim-сцены для Модуля 2: Басниев, Дмитриев, Розенберг (2005) —
«Нефтегазовая гидромеханика» (Дарси, Дюпюи, воронка депрессии, пьезопроводность и ПССС).
"""

from __future__ import annotations

import numpy as np
from manim import (
    Arrow,
    Axes,
    Circle,
    Create,
    DashedLine,
    DOWN,
    FadeIn,
    LEFT,
    Line,
    RIGHT,
    Scene,
    Text,
    UP,
    VGroup,
    WHITE,
    Write,
)

from backend.physics_engine.basniev_hydro import simulate_dupuit_flow, simulate_psss_transient
from manim_scenes.common import (
    ACCENT_AMBER,
    ACCENT_CORAL,
    ACCENT_CYAN,
    ACCENT_EMERALD,
    load_manim_context,
    make_header,
    make_term_bridge_badge,
    safe_mathtex,
)


class BasnievDarcyScene(Scene):
    """Сцена 1: Закон Дарси и соотношение скорости фильтрации w и истинной скорости v."""

    def construct(self) -> None:
        header = make_header(
            "Закон Дарси в пористой среде",
            "Басниев и др. (2005), Глава XVIII, §4",
        )
        self.play(FadeIn(header))

        eq = safe_mathtex(r"\vec{w} = -\frac{k}{\mu} \operatorname{grad} p, \quad v = \frac{w}{m}", font_size=44)
        eq.shift(UP * 0.8)

        arrows = VGroup(
            *[
                Arrow(start=LEFT * 3.5 + UP * dy, end=RIGHT * 3.5 + UP * dy, color=ACCENT_CYAN, buff=0)
                for dy in (-0.9, -0.45, 0.0)
            ]
        ).shift(DOWN * 0.5)
        lbl = Text("Поток от высокого p к низкому (знак минус)", font_size=20, color=ACCENT_AMBER)
        lbl.next_to(arrows, DOWN, buff=0.25)

        badge = make_term_bridge_badge("w", "Скорость фильтрации", "u / v_D", "Darcy superficial velocity")
        badge.to_edge(DOWN, buff=0.45)

        self.play(Write(eq))
        self.play(Create(arrows), Write(lbl))
        self.play(FadeIn(badge))
        self.wait(4.0)


class BasnievDupuitScene(Scene):
    """Сцена 2: Плоскорадиальный приток к скважине и вывод формулы Дюпюи."""

    def construct(self) -> None:
        ctx = load_manim_context()
        pdata = ctx.get("physics_data", {})
        dup = pdata.get("dupuit") or simulate_dupuit_flow()
        metrics = dup["metrics"]
        inputs = dup["inputs"]

        header = make_header(
            "Плоскорадиальный поток и формула Дюпюи",
            "Глава XX, §3 — формула (20.19)",
        )
        self.play(FadeIn(header))

        # Схематичный круговой контур питания R_к и скважина r_с
        outer = Circle(radius=1.7, color=ACCENT_CYAN, stroke_width=2.5).shift(LEFT * 3.6 + DOWN * 0.2)
        well = Circle(radius=0.14, color=ACCENT_CORAL, fill_color=ACCENT_CORAL, fill_opacity=1.0).move_to(outer.get_center())
        rk_lbl = Text(f"R_к = {inputs['r_k_m']} м, p_к = {inputs['p_k_mpa']} МПа", font_size=16, color=ACCENT_CYAN).next_to(outer, DOWN, buff=0.2)

        inflow_arrows = VGroup()
        for ang in np.linspace(0, 2 * np.pi, 8, endpoint=False):
            p_out = outer.get_center() + 1.45 * np.array([np.cos(ang), np.sin(ang), 0.0])
            p_in = outer.get_center() + 0.35 * np.array([np.cos(ang), np.sin(ang), 0.0])
            inflow_arrows.add(Arrow(p_out, p_in, color=ACCENT_EMERALD, buff=0, stroke_width=2.5))

        eq = safe_mathtex(
            r"Q = \frac{2\pi k h (p_{\text{к}} - p_{\text{с}})}{\mu \ln(R_{\text{к}} / r_{\text{с}})}",
            font_size=40,
        ).shift(RIGHT * 2.5 + UP * 0.6)

        res_txt = Text(
            f"Q = {metrics['q_m3_day']} м³/сут  |  C = {metrics['productivity_index_m3_day_mpa']} м³/(сут·МПа)",
            font_size=20,
            color=ACCENT_AMBER,
        ).next_to(eq, DOWN, buff=0.45)

        badge = make_term_bridge_badge("R_к, r_с", "Контур и скважина", "r_e, r_w", "Drainage & Wellbore radius")
        badge.scale(0.88).next_to(res_txt, DOWN, buff=0.45)

        self.play(Create(outer), FadeIn(well), Write(rk_lbl))
        self.play(Create(inflow_arrows))
        self.play(Write(eq), Write(res_txt))
        self.play(FadeIn(badge))
        self.wait(3.5)


class BasnievConeScene(Scene):
    """Сцена 3: Логарифмическая воронка депрессии p(r) и скачок скорости w(r) ~ 1/r."""

    def construct(self) -> None:
        ctx = load_manim_context()
        pdata = ctx.get("physics_data", {})
        dup = pdata.get("dupuit") or simulate_dupuit_flow()
        prof = dup["radial_profile"]
        inputs = dup["inputs"]

        header = make_header(
            "Воронка депрессии p(r) и закон скорости w(r) ~ 1/r",
            "Глава XX, §3 — формулы (20.20)–(20.21)",
        )
        self.play(FadeIn(header))

        axes = Axes(
            x_range=[0, inputs["r_k_m"], 50],
            y_range=[max(0, inputs["p_c_mpa"] - 2), inputs["p_k_mpa"] + 2, 2],
            x_length=8.2,
            y_length=4.1,
            axis_config={"color": "#64748B", "include_numbers": True, "font_size": 18},
        ).shift(DOWN * 0.55)
        x_lbl = Text("Радиус r, м", font_size=18, color="#CBD5E1").next_to(axes.x_axis, DOWN, buff=0.2)
        y_lbl = Text("Давление p(r), МПа", font_size=18, color="#CBD5E1").next_to(axes.y_axis, UP, buff=0.15)

        pts = [axes.coords_to_point(r, p) for r, p in zip(prof["r_m"], prof["p_mpa"])]
        curve = VGroup(*[Line(pts[i], pts[i + 1], color=ACCENT_CYAN, stroke_width=4.0) for i in range(len(pts) - 1)])

        pk_line = DashedLine(
            axes.coords_to_point(0, inputs["p_k_mpa"]),
            axes.coords_to_point(inputs["r_k_m"], inputs["p_k_mpa"]),
            color=ACCENT_AMBER,
        )
        pk_txt = Text(f"p_к = {inputs['p_k_mpa']} МПа", font_size=18, color=ACCENT_AMBER).next_to(pk_line, UP, buff=0.1)

        self.play(Create(axes), Write(x_lbl), Write(y_lbl))
        self.play(Create(pk_line), Write(pk_txt))
        self.play(Create(curve), run_time=3.0)
        self.wait(3.0)


class BasnievPSSSScene(Scene):
    """Сцена 4: Неустановившийся упругий режим — ПССС R(t) = sqrt(r_c^2 + 4*kappa*t) vs Ei."""

    def construct(self) -> None:
        ctx = load_manim_context()
        pdata = ctx.get("physics_data", {})
        tr = pdata.get("transient_psss") or simulate_psss_transient()
        snaps = tr["snapshots"]
        r_m = tr["r_m"]
        p_k = tr["parameters"]["p_k_mpa"]

        header = make_header(
            "Метод ПССС (И.А. Чарный) vs точное решение пьезопроводности",
            f"κ = {tr['parameters']['kappa_m2_s']} м²/с  |  R(t) = √(r_c² + 4κt)",
        )
        self.play(FadeIn(header))

        min_p = min(min(s["p_psss_mpa"]) for s in snaps)
        axes = Axes(
            x_range=[0, max(r_m), 50],
            y_range=[max(0, min_p - 1.5), p_k + 1.5, 2],
            x_length=8.2,
            y_length=4.1,
            axis_config={"color": "#64748B", "include_numbers": True, "font_size": 18},
        ).shift(DOWN * 0.55)
        x_lbl = Text("Радиус r, м", font_size=18, color="#CBD5E1").next_to(axes.x_axis, DOWN, buff=0.2)
        y_lbl = Text("p(r, t), МПа", font_size=18, color="#CBD5E1").next_to(axes.y_axis, UP, buff=0.15)
        self.play(Create(axes), Write(x_lbl), Write(y_lbl))

        colors = [ACCENT_CYAN, ACCENT_EMERALD, ACCENT_AMBER, ACCENT_CORAL]
        legend_items = []
        for idx, snap in enumerate(snaps[:4]):
            col = colors[idx % len(colors)]
            pts_psss = [axes.coords_to_point(r, p) for r, p in zip(r_m, snap["p_psss_mpa"])]
            curve = VGroup(*[Line(pts_psss[i], pts_psss[i + 1], color=col, stroke_width=3.2) for i in range(len(pts_psss) - 1)])
            self.play(Create(curve), run_time=1.1)
            legend_items.append(Text(f"t={snap['time_hours']} ч: R={snap['r_front_m']} м", font_size=16, color=col))

        legend = VGroup(*legend_items).arrange(DOWN, aligned_edge=LEFT, buff=0.12).to_edge(RIGHT, buff=0.35).shift(UP * 0.4)
        self.play(FadeIn(legend))
        self.wait(3.0)
