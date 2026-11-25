"""
Универсальная детерминированная Manim-сцена для любой контрольной книги (ctrl_*)
или загруженного пользователем учебника: читает scene_id из LITHOS_MANIFEST_PATH.
"""

from __future__ import annotations

import os
from manim import DOWN, FadeIn, LEFT, Scene, Text, UP, VGroup, WHITE, Write

from manim_scenes.common import (
    ACCENT_AMBER,
    ACCENT_CYAN,
    load_manim_context,
    make_header,
    make_term_bridge_badge,
    safe_mathtex,
)


class GenericChapterScene(Scene):
    """Рендерит заголовок, формулы LaTeX (с fallback), терминологический мост и выводы сцены."""

    def construct(self) -> None:
        ctx = load_manim_context()
        scene_id = os.getenv("LITHOS_SCENE_ID", "")
        scenes = ctx.get("scenes", [])
        scene = next((s for s in scenes if s.get("scene_id") == scene_id), scenes[0] if scenes else {})

        title = scene.get("title", ctx.get("chapter_title", "Учебный модуль"))
        subtitle = ctx.get("book_title", "LITHOS Course Engine")
        header = make_header(title, subtitle)
        self.play(FadeIn(header))

        center_items = []
        formulas = scene.get("formulas", [])
        if formulas:
            f0 = formulas[0]
            tex = f0.get("latex", "")
            if tex:
                mobj = safe_mathtex(tex, font_size=36, color=WHITE)
                center_items.append(mobj)
            f_title = f0.get("title", "")
            if f_title:
                center_items.append(Text(f_title[:70], font_size=20, color=ACCENT_AMBER))

        for tk in scene.get("key_takeaways", [])[:3]:
            center_items.append(Text(f"• {tk[:76]}", font_size=20, color="#E2E8F0"))

        if not center_items:
            center_items.append(Text(scene.get("narration", "")[:90], font_size=22, color="#E2E8F0"))

        body = VGroup(*center_items).arrange(DOWN, buff=0.35).shift(DOWN * 0.2)
        self.play(FadeIn(body), run_time=2.0)

        bridges = scene.get("term_bridges", [])
        if bridges:
            b0 = bridges[0]
            badge = make_term_bridge_badge(
                b0.get("ru_symbol", "—"),
                b0.get("ru_term", ""),
                b0.get("en_symbol", "—"),
                b0.get("en_term", ""),
            )
            badge.to_edge(DOWN, buff=0.45)
            self.play(FadeIn(badge))

        self.wait(4.0)
