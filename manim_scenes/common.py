"""Общие настройки темы, кириллического LaTeX и загрузки данных physics_engine для Manim."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from manim import (
    BLUE_C,
    DOWN,
    GOLD_C,
    GRAY_A,
    GRAY_C,
    GREEN_C,
    LEFT,
    MathTex,
    ORANGE,
    RED_C,
    RIGHT,
    RoundedRectangle,
    Scene,
    TEAL_C,
    TexTemplate,
    Text,
    UP,
    VGroup,
    WHITE,
    config,
)

BG_DARK = "#0B101B"
PANEL_BG = "#111827"
ACCENT_CYAN = "#38BDF8"
ACCENT_AMBER = "#F59E0B"
ACCENT_EMERALD = "#10B981"
ACCENT_CORAL = "#F43F5E"

config.background_color = BG_DARK


def get_cyrillic_tex_template() -> TexTemplate:
    tpl = TexTemplate()
    tpl.add_to_preamble(r"\usepackage[utf8]{inputenc}")
    tpl.add_to_preamble(r"\usepackage[T2A]{fontenc}")
    tpl.add_to_preamble(r"\usepackage[russian]{babel}")
    tpl.add_to_preamble(r"\usepackage{amsmath}")
    tpl.add_to_preamble(r"\usepackage{amssymb}")
    return tpl


CYRILLIC_TEX = get_cyrillic_tex_template()


def safe_mathtex(tex: str, font_size: int = 38, color: str = WHITE) -> MathTex | Text:
    """Рендерит LaTeX с кириллицей, с безопасным fallback на Text при битом OCR LaTeX."""
    try:
        return MathTex(tex, tex_template=CYRILLIC_TEX, font_size=font_size, color=color)
    except Exception:
        return Text(tex, font_size=max(20, font_size // 2), color=color)


def load_manim_context() -> dict[str, Any]:
    """Читает course_manifest / manim_context.json, переданный из backend."""
    path_str = os.getenv("LITHOS_MANIFEST_PATH", "").strip()
    if path_str and Path(path_str).exists():
        return json.loads(Path(path_str).read_text(encoding="utf-8"))
    return {}


def make_header(title: str, subtitle: str = "") -> VGroup:
    t = Text(title[:62], font_size=30, weight="BOLD", color=WHITE)
    items = [t]
    if subtitle:
        sub = Text(subtitle[:84], font_size=18, color=ACCENT_CYAN)
        sub.next_to(t, DOWN, buff=0.12)
        items.append(sub)
    grp = VGroup(*items).to_edge(UP, buff=0.35)
    return grp


def make_term_bridge_badge(ru_sym: str, ru_name: str, en_sym: str, en_name: str) -> VGroup:
    """Плашка терминологического моста СНГ ↔ Запад."""
    box = RoundedRectangle(corner_radius=0.12, width=5.6, height=0.82, color=ACCENT_CYAN, fill_color=PANEL_BG, fill_opacity=0.92, stroke_width=1.5)
    ru_txt = Text(f"СНГ: {ru_sym} ({ru_name[:26]})", font_size=16, color=ACCENT_AMBER)
    en_txt = Text(f"West: {en_sym} ({en_name[:26]})", font_size=15, color=ACCENT_CYAN)
    ru_txt.move_to(box.get_center() + UP * 0.16)
    en_txt.move_to(box.get_center() + DOWN * 0.16)
    return VGroup(box, ru_txt, en_txt)
