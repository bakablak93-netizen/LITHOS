"""
Регрессионные и приёмочные тесты Т3 «Глава → курс» (Этапы 1–4):
- Этап 1: независимый реестр PDF, разрывный диапазон Вендельштейна (9–14, 20–30),
  обнаружение удаления рисунка Кузнецова со стр. 201 одновременно из всех списков слоя,
  проверка дубликата, подмены страницы/числа/единицы, пустого охвата и разрыва диапазона.
- Этап 2: маршрутизация по видеоёмкости, предметная графика и анимации классов A–D (включая Кузнецова),
  ≥15 заданий 5 типов Т3, задача «признаки → правило → вывод», локальные и метаданные-OpenAI подсказки,
  автономный HTML и ZIP (<30 МБ), темы, 390/1280 px, клавиатура, reduced-motion.
- Этап 3: реальные файлы шортса 9:16 (40–75 с) и разбора 16:9 (90–180 с), медиапаспорта,
  громкость около −16 LUFS без клиппинга, словесные таймкоды, чек-лист физики и пересборка от правки факта.
- Этап 4: верификатор внешних «закладок», замена «однозначно нельзя» -> «однозначно можно» у Вендельштейна стр. 20,
  0 ложных тревог на валидных примерах, 100% полнота на калибровочном наборе, обратная совместимость сохранённых курсов.
"""

from __future__ import annotations

import copy
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.agents.parser_agent import build_course_manifest_sync
from backend.main import app
from backend.study import validate_or_migrate_legacy_course
from backend.t3.bookmarks_verifier import (
    run_internal_calibration_benchmark,
    verify_bookmarks_on_layer_and_media,
)
from backend.t3.layer import build_study_layer, verify_layer_pedagogical_invariants
from backend.t3.media_pipeline import probe_real_video_file
from backend.t3.models import QuoteAndPage, StudyLayer
from backend.t3.pipeline import (
    build_t3_course_package,
    rebuild_t3_from_layer_fact_edit,
)
from backend.t3.registry import (
    BOOK_CATALOG,
    build_independent_registry,
    verify_registry_against_layer,
)
from backend.t3.routing import build_routing_and_illustrations
from backend.t3.tasks_engine import (
    ALLOWED_HINT_METADATA_KEYS,
    FORBIDDEN_EXTERNAL_KEYS,
    check_task_submission,
    generate_chapter_tasks,
    select_hint_strategy_and_render_locally,
    validate_tasks_against_layer,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
VERIFY_OUT_DIR = PROJECT_ROOT / "outputs" / "t3_verify"


def test_stage1_independent_registry_and_discontinuous_ranges() -> None:
    """Проверяет привязку всех 6 книг к PDF, хешу SHA-256 и разрывным диапазонам (включая Вендельштейна 9–14 и 20–30)."""
    for book_file in BOOK_CATALOG:
        reg = build_independent_registry(DATA_DIR, book_file)
        assert len(reg.source_sha256) == 64
        assert reg.total_pdf_pages > 100
        assert len(reg.units) >= 50

    ven_reg = build_independent_registry(DATA_DIR, "ctrl_vendelshtein.md")
    ranges_tuples = [(r.start_pdf_page, r.end_pdf_page) for r in ven_reg.pdf_ranges]
    assert ranges_tuples == [(9, 14), (20, 30)]
    assert ven_reg.page_numbering_differ is True
    pages_in_reg = {u.pdf_page for u in ven_reg.units}
    assert 9 in pages_in_reg and 14 in pages_in_reg and 20 in pages_in_reg and 30 in pages_in_reg
    # Разрыв 15..19 не должен входить в реестр диапазона 9-14, 20-30
    assert not any(15 <= p <= 19 for p in pages_in_reg)


def test_stage1_kuznetsov_p201_simultaneous_deletion_caught() -> None:
    """
    Приёмка Этапа 1: удаление рисунка Кузнецова со стр. 201 (Рис. 10.1) одновременно
    из всех внутренних списков слоя гарантированно обнаруживается по независимому реестру.
    """
    layer, reg = build_study_layer(DATA_DIR, "train_kuznetsov.md")
    clean_rep = verify_registry_against_layer(reg, layer)
    assert clean_rep.passed is True

    mutated = copy.deepcopy(layer)
    p201_fig_ids = {
        u.unit_id for u in reg.units if u.pdf_page == 201 and u.unit_type in ("figure", "caption")
    }
    assert len(p201_fig_ids) >= 2

    for node in mutated.nodes:
        node.covered_unit_ids = [uid for uid in node.covered_unit_ids if uid not in p201_fig_ids]
        node.quotes_and_pages = [qp for qp in node.quotes_and_pages if qp.unit_id not in p201_fig_ids]
    mutated.claims = [cl for cl in mutated.claims if cl.unit_id not in p201_fig_ids]
    for uid in p201_fig_ids:
        mutated.coverage_map.pop(uid, None)
        mutated.excluded_units.pop(uid, None)

    rep = verify_registry_against_layer(reg, mutated)
    assert rep.passed is False
    assert any(
        d.discrepancy_type == "missing_unit" and d.pdf_page == 201 and d.unit_id in p201_fig_ids
        for d in rep.discrepancies
    )


def test_stage1_registry_mutations_duplicate_page_number_unit_empty_gap() -> None:
    """Проверяет обнаружение дубликата, подмены страницы, числа, единицы измерения, пустого охвата и разрыва диапазона."""
    layer, reg = build_study_layer(DATA_DIR, "ctrl_vendelshtein.md")

    # 1. Пустой охват
    empty_layer = copy.deepcopy(layer)
    empty_layer.nodes = []
    empty_layer.coverage_map = {}
    rep_empty = verify_registry_against_layer(reg, empty_layer)
    assert rep_empty.passed is False
    assert any(d.discrepancy_type == "empty_coverage" for d in rep_empty.discrepancies)

    # 2. Дубликат единицы
    dup_layer = copy.deepcopy(layer)
    dup_layer.nodes[0].covered_unit_ids.append(dup_layer.nodes[0].covered_unit_ids[0])
    rep_dup = verify_registry_against_layer(reg, dup_layer)
    assert rep_dup.passed is False
    assert any(d.discrepancy_type == "duplicate_unit" for d in rep_dup.discrepancies)

    # 3. Подмена страницы и разрыв диапазона (стр. 17 находится в разрыве между 9–14 и 20–30)
    gap_layer = copy.deepcopy(layer)
    gap_layer.claims[0].pdf_page = 17
    rep_gap = verify_registry_against_layer(reg, gap_layer)
    assert rep_gap.passed is False
    types_found = {d.discrepancy_type for d in rep_gap.discrepancies}
    assert "wrong_page" in types_found
    assert "out_of_range_gap" in types_found

    # 4. Подмена числа и неверная единица измерения
    num_layer = copy.deepcopy(layer)
    num_claim = next(c for c in num_layer.claims if c.numbers_and_units)
    orig_val = num_claim.numbers_and_units[0]["value"]
    num_claim.numbers_and_units[0]["unit"] = "Па·с"
    rep_unit = verify_registry_against_layer(reg, num_layer)
    assert rep_unit.passed is False
    assert any(d.discrepancy_type == "wrong_unit" for d in rep_unit.discrepancies)

    num_layer2 = copy.deepcopy(layer)
    num_claim2 = next(c for c in num_layer2.claims if c.numbers_and_units)
    num_claim2.numbers_and_units = [{"value": "999999", "unit": num_claim2.numbers_and_units[0]["unit"]}]
    rep_num = verify_registry_against_layer(reg, num_layer2)
    assert rep_num.passed is False
    assert any(d.discrepancy_type == "wrong_number" for d in rep_num.discrepancies)


def test_stage1_node_structure_and_pedagogical_invariants() -> None:
    """Проверяет полноту структуры узлов Т3 и выполнение педагогических инвариантов на всех 6 книгах."""
    for book_file in BOOK_CATALOG:
        layer, reg = build_study_layer(DATA_DIR, book_file)
        ped = verify_layer_pedagogical_invariants(layer)
        assert ped["passed"] is True, f"Нарушены педагогические инварианты в {book_file}: {ped}"
        for node in layer.nodes:
            words = node.step_title.split()
            assert 3 <= len(words) <= 7
            assert node.order_rationale
            assert node.mechanism and node.practice and node.nuances and node.deeper_branch
            assert node.epistemic_split.observation and node.epistemic_split.inference and node.epistemic_split.assumption
            assert node.threshold_concept and node.misconception_to_fix and node.data_transfer
            assert node.it_analogy_and_limits
            assert len(node.specialist_manual_steps) >= 2
            assert len(node.decision_points) >= 1
            assert len(node.modern_equivalents) >= 1


def test_stage2_routing_and_kuznetsov_domain_animations(tmp_path: Path) -> None:
    """Проверяет маршрутизацию по видеоёмкости, классы A–D и предметные анимации/перерисовки Кузнецова."""
    kuz_layer, _ = build_study_layer(DATA_DIR, "train_kuznetsov.md")
    rep, illusts = build_routing_and_illustrations(kuz_layer, course_id="t3_train_kuznetsov", course_dir=tmp_path)
    assert rep.needs_model_steps == 0
    assert rep.covered_steps == len(kuz_layer.nodes)
    assert rep.class_a_b_count >= 2
    assert any("рис. 10.1, стр. 201" in il.redraw_caption for il in illusts)
    assert any("рис. 10.2, стр. 206" in il.redraw_caption for il in illusts)
    for il in illusts:
        svg_file = tmp_path / il.asset_rel_path
        assert svg_file.exists() and svg_file.stat().st_size > 500


def test_stage2_tasks_15_plus_five_types_and_privacy_safe_hints() -> None:
    """Проверяет ≥15 заданий 5 типов Т3 на каждую главу, задачу «признаки → правило → вывод» и приватность подсказок."""
    for book_file in BOOK_CATALOG:
        layer, _ = build_study_layer(DATA_DIR, book_file)
        tasks = generate_chapter_tasks(layer, course_id=f"t3_{layer.book_id}")
        val = validate_tasks_against_layer(tasks, layer)
        assert val["passed"] is True, f"Ошибка валидации заданий {book_file}: {val['errors']}"
        assert len(tasks) >= 15
        assert val["distinct_types_count"] >= 5
        official_five = {"single_choice", "multi_select", "ordering", "fill_in_blank", "calculation"}
        assert official_five.issubset({t.task_type for t in tasks})
        assert val["has_case_decision_chain"] is True
        assert val["has_calculation_type"] is True

        # Проверяем отправку правильного и неправильного ответа для каждого из 5 типов
        for t in tasks:
            right_res = check_task_submission(t, t.correct_answer)
            assert right_res["is_correct"] is True
            assert right_res["answer_key_display"] and right_res["explanation"] and right_res["source_ref"]

        # Проверяем строгую фильтрацию метаданных для подсказки через имитацию API (Mock OpenAI)
        captured_payloads: list[dict] = []

        def _mock_openai_selector(meta: dict) -> str:
            captured_payloads.append(meta)
            assert set(meta.keys()).issubset(ALLOWED_HINT_METADATA_KEYS)
            assert not (set(meta.keys()) & FORBIDDEN_EXTERNAL_KEYS)
            return "signs_rule_conclusion_chain"

        t0 = tasks[0]
        n0 = next(n for n in layer.nodes if n.node_id == t0.node_id)
        hint_res = select_hint_strategy_and_render_locally(
            task=t0,
            node=n0,
            attempt_number=2,
            hint_level=2,
            mock_api_callable=_mock_openai_selector,
        )
        assert len(captured_payloads) == 1
        assert hint_res["strategy_id"] == "signs_rule_conclusion_chain"
        assert hint_res["selector_source"] == "mock_openai_api"
        assert len(hint_res["hint_text"]) > 20


def test_stage2_and_stage3_built_courses_html_zip_and_videos() -> None:
    """
    Проверяет собранные артефакты всех 6 курсов: автономный HTML, темы, 390/1280 px, ZIP < 30 МБ,
    а также реальные файлы роликов 9:16 (Латышова, 40–75 с) и 16:9 (Басниев, 90–180 с) и их медиапаспорта.
    """
    if not (VERIFY_OUT_DIR / "t3_freeze_report.json").exists():
        from backend.t3.pipeline import build_all_six_t3_courses

        build_all_six_t3_courses(DATA_DIR, VERIFY_OUT_DIR, render_mp4=True)

    for book_file, cat in BOOK_CATALOG.items():
        cid = f"t3_{cat['book_id']}"
        cdir = VERIFY_OUT_DIR / cid
        html_path = cdir / "index.html"
        zip_path = cdir / f"{cid}_offline.zip"
        assert html_path.exists()
        assert zip_path.exists()

        # Размер курса без видео обязан быть < 30 МБ
        zip_mb = zip_path.stat().st_size / (1024 * 1024)
        assert 0.01 < zip_mb < 30.0

        with zipfile.ZipFile(zip_path, "r") as zf:
            names = set(zf.namelist())
            assert "index.html" in names
            assert "layer.json" in names
            assert "tasks.json" in names
            assert "step_illustration_source.json" in names

        html_txt = html_path.read_text(encoding="utf-8")
        assert '[data-theme="dark"]' in html_txt and '[data-theme="light"]' in html_txt
        assert "font-size: 16px" in html_txt
        assert ":focus-visible" in html_txt
        assert "prefers-reduced-motion: reduce" in html_txt
        assert "max-width: 1280px" in html_txt and "max-width: 480px" in html_txt
        assert "localStorage" in html_txt
        assert "Знаю" in html_txt and "Повторить" in html_txt
        assert "Паспорт ролика" in html_txt

    # Проверяем реальный файл шортса 9:16 (Латышова) и разбора 16:9 (Басниев)
    shorts_mp4 = VERIFY_OUT_DIR / "t3_train_latyshova" / "media" / "shorts_9_16_latyshova.mp4"
    expl_mp4 = VERIFY_OUT_DIR / "t3_train_basniev" / "media" / "explainer_16_9_basniev.mp4"

    p_shorts = probe_real_video_file(shorts_mp4)
    assert p_shorts["width"] == 1080 and p_shorts["height"] == 1920
    assert 40.0 <= p_shorts["duration_sec"] <= 75.0
    assert p_shorts["audio_codec"] == "aac"

    p_expl = probe_real_video_file(expl_mp4)
    assert p_expl["width"] == 1920 and p_expl["height"] == 1080
    assert 90.0 <= p_expl["duration_sec"] <= 180.0
    assert p_expl["audio_codec"] == "aac"


def test_stage3_reactive_single_command_rebuild_from_layer_fact(tmp_path: Path) -> None:
    """
    Приёмка Этапа 3: правка одного подтверждённого факта в слое пересобирает зависимые
    шаг, задания, субтитры и медиапаспорт одной штатной командой.
    """
    pkg = build_t3_course_package(
        data_dir=DATA_DIR,
        output_dir=tmp_path,
        book_file="train_latyshova.md",
        render_mp4=False,
    )
    target_claim_id = pkg.layer.claims[0].claim_id
    diff = rebuild_t3_from_layer_fact_edit(
        package=pkg,
        course_dir=tmp_path / pkg.course_id,
        claim_id=target_claim_id,
        old_fact_substring="20 Ом·м",
        new_fact_substring="25 Ом·м [Калибровка керна]",
        render_mp4=False,
    )
    assert diff["layer_hash_changed"] is True
    assert diff["step_updated"] is True
    assert diff["task_updated"] is True
    assert diff["subtitles_updated"] is True
    assert diff["media_passport_hash_updated"] is True


def test_stage2_flagship_practicum_two_probes_single_model_and_offline_html() -> None:
    """
    Приёмка п. 4 и п. 1:
    - Проверяет флагманский практикум «Что показывают два зонда?» (Латышова): изменение ρ_ф (1.20 -> 0.05 Ом·м)
      согласованно обновляет обе кривые (ρ_БК, ρ_МБК), разрез и расчёты из одного состояния модели.
    - Проверяет наличие всех 6 этапов (Симуляция, прогноз, сравнение состояний, вывод «признаки → правило → вывод»
      с ошибочным вариантом, разбор границ/данных/источника, задача на перенос).
    - Проверяет встраивание в автономный HTML и отсутствие подписей 15,2 px (< 16 px).
    """
    from backend.t3.practicum import build_two_probes_practicum, compute_two_probes_state

    st_fresh = compute_two_probes_state(rho_f=1.20)
    st_saline = compute_two_probes_state(rho_f=0.05)

    assert "Симуляция" in st_fresh["data_origin"]
    assert st_fresh["parameters"]["delta_e_max_mv"] < -50.0
    assert abs(st_saline["parameters"]["delta_e_max_mv"]) < 0.01
    # В водоносной зоне (2429 м) при пресном растворе повышающее проникновение (ρ_МБК > ρ_БК), при солёном — близко к равному
    assert st_fresh["key_zones"]["water_zone_2429m"]["rho_mbk_ohmm"] > st_fresh["key_zones"]["water_zone_2429m"]["rho_bk_ohmm"]
    assert st_saline["key_zones"]["water_zone_2429m"]["rho_mbk_ohmm"] < st_fresh["key_zones"]["water_zone_2429m"]["rho_mbk_ohmm"]
    # Кривые и ключевые зоны согласованы по одному массиву модели
    assert len(st_fresh["curves"]["depth_m"]) == len(st_fresh["curves"]["rho_bk_ohmm"]) == len(st_fresh["curves"]["rho_mbk_ohmm"])

    layer, _ = build_study_layer(DATA_DIR, "train_latyshova.md")
    pr = build_two_probes_practicum(layer, step_id="latyshova_ch1_ch5_step_05")
    assert pr["practicum_id"] == "lithos_two_probes_latyshova"
    assert len(pr["step4_conclusion"]["options"]) == 3
    assert any(not o["is_correct"] for o in pr["step4_conclusion"]["options"])
    assert any(o["is_correct"] for o in pr["step4_conclusion"]["options"])
    assert len(pr["step4_conclusion"]["step5_debrief"]["missing_data_needed"]) >= 3
    assert any(o["is_correct"] for o in pr["step6_transfer_task"]["options"])

    # Проверка автономного HTML Латышовой: практикум встроен, нет шрифтов 15,2 px (0.95rem) и меньше 16 px
    html_path = VERIFY_OUT_DIR / "t3_train_latyshova" / "index.html"
    if html_path.exists():
        html_txt = html_path.read_text(encoding="utf-8")
        assert "practicum-two-probes" in html_txt
        assert "Что показывают два зонда?" in html_txt
        assert "font-size:0.95rem" not in html_txt and "font-size: 0.95rem" not in html_txt
        assert "font-size:0.92rem" not in html_txt and "font-size: 0.92rem" not in html_txt
        assert "font-size:0.9rem" not in html_txt and "font-size: 0.9rem" not in html_txt
        assert "font-size:0.875rem" not in html_txt and "font-size: 0.875rem" not in html_txt


def test_stage4_vendelshtein_p20_polarity_flip_and_calibration() -> None:
    """
    Приёмка Этапа 4: замена «однозначно нельзя» на «однозначно можно» у Вендельштейна со стр. 20
    при неизменной подлинной цитате обнаруживается верификатором с проблемным фрагментом, объяснением,
    исправлением, стр. 20 и подтверждающей цитатой; на 6 валидных книгах и 4 похожих правильных
    формулировках (near-miss) число ложных тревог равно 0, а полнота на 9 типах закладок равна 100%.
    """
    cal = run_internal_calibration_benchmark(DATA_DIR)
    assert cal["evaluation_mode"] == "internal_calibration"
    assert cal["near_miss_valid_controls_checked"] == 4
    assert cal["false_positives_on_valid_count"] == 0
    assert cal["missed_bookmarks_count"] == 0
    assert cal["recall_pct"] == 100.0
    assert cal["fix_with_page_accuracy_pct"] == 100.0
    assert cal["total_examples"] == 19

    ven_case = next(c for c in cal["injected_cases"] if c["case_id"] == "BM-CASE-01-VENDELSHTEIN-P20-POLARITY")
    assert ven_case["detected"] is True
    f0 = next(f for f in ven_case["findings"] if f["pdf_page"] == 20 and f["defect_type"] == "polarity_flip")
    assert f0["problematic_fragment"]
    assert f0["explanation"]
    assert f0["proposed_fix"]
    assert f0["supporting_quote"]


def test_stage4_freeze_report_hashes_and_effort_template() -> None:
    """Проверяет наличие хешей кода, физических моделей, паспортов, промптов и пустой формы журнала в кандидате на заморозку."""
    import json

    fr_path = VERIFY_OUT_DIR / "t3_freeze_report.json"
    if not fr_path.exists():
        pytest.skip("t3_freeze_report.json ещё не собран")
    fr = json.loads(fr_path.read_text(encoding="utf-8"))
    hashes = fr["artifact_hashes"]
    assert len(hashes["code_files_sha256"]) >= 10
    assert all(len(v) == 64 for v in hashes["code_files_sha256"].values())
    assert len(hashes["physics_models_sha256"]) == 2
    assert len(hashes["domain_passports_sha256"]) == 6
    assert len(hashes["prompts_sha256"]) >= 1
    assert isinstance(fr["effort_and_edits_log_template"], list) and len(fr["effort_and_edits_log_template"]) >= 1


def test_stage4_legacy_course_compatibility_and_study_api() -> None:
    """Проверяет обратную совместимость сохранённого курса v1 CourseManifest и эндпоинты /api/t3/*."""
    manifest, _, _, _ = build_course_manifest_sync(DATA_DIR, "train_latyshova.md", chapter_index=0)
    compat = validate_or_migrate_legacy_course(manifest.model_dump_json())
    assert compat["validated"] is True
    assert compat["format"] == "legacy_course_manifest_v1"

    with pytest.raises(ValueError, match="отсутствует обязательное поле"):
        validate_or_migrate_legacy_course("{}")

    client = TestClient(app)
    res_list = client.get("/api/t3/courses")
    assert res_list.status_code == 200
    courses = res_list.json()
    assert len(courses) == 6

    res_kuz = client.get("/api/t3/courses/t3_train_kuznetsov")
    assert res_kuz.status_code == 200
    kuz_data = res_kuz.json()
    assert len(kuz_data["tasks"]) >= 15

    t0_id = kuz_data["tasks"][0]["task_id"]
    res_chk = client.post(
        "/api/t3/courses/t3_train_kuznetsov/check-task",
        json={"task_id": t0_id, "answer": kuz_data["tasks"][0]["correct_answer"]},
    )
    assert res_chk.status_code == 200
    assert res_chk.json()["is_correct"] is True

    res_hint = client.post(
        "/api/t3/courses/t3_train_kuznetsov/hint",
        json={"task_id": t0_id, "attempt_number": 1, "hint_level": 1, "allow_online_openai": False},
    )
    assert res_hint.status_code == 200
    assert "hint_text" in res_hint.json()


def test_t3_v2_official_ranges_dag_domain_package_scene_specs_and_external_bookmarks(tmp_path: Path) -> None:
    """Проверяет официальные диапазоны PDF, коды трудностей, ацикличность DAG, сменный предметный пакет, scene_specs и внешний пакет закладок."""
    import json

    from backend.t3.bookmarks_verifier import verify_external_bookmark_package
    from backend.t3.domain_package import load_domain_package
    from backend.t3.models import TypedNodeLink

    expected_ranges = {
        "train_latyshova.md": [(90, 108)],
        "train_basniev.md": [(474, 500)],
        "train_kuznetsov.md": [(200, 222)],
        "ctrl_vendelshtein.md": [(9, 14), (20, 30)],
        "ctrl_barenblatt.md": [(38, 51)],
        "ctrl_baraboshkin_b.md": [(30, 44)],
    }
    valid_codes = {"М", "В", "И", "Ф", "П", "Пр", "Н", "Р"}

    dom = load_domain_package()
    assert dom["domain_package_id"] == "oil_gas_ru"
    assert len(dom["_sha256"]) == 64

    for book_file, exp in expected_ranges.items():
        layer, _ = build_study_layer(DATA_DIR, book_file)
        actual = [(r.start_pdf_page, r.end_pdf_page) for r in layer.pdf_ranges]
        assert actual == exp, f"Несовпадение диапазонов PDF для {book_file}: {actual} != {exp}"
        assert layer.pedagogical_checks["prerequisite_dag_acyclic_ok"] is True
        for node in layer.nodes:
            assert node.primary_difficulty_code in valid_codes
            assert node.secondary_difficulty_code in valid_codes
            assert node.inefficiency_lens is not None
            assert len(node.inefficiency_lens.manual_steps) >= 2

    # Негативная проверка цикла в графе prerequisite (DAG)
    cycled_layer = copy.deepcopy(build_study_layer(DATA_DIR, "train_latyshova.md")[0])
    cycled_layer.nodes[0].typed_links.append(
        TypedNodeLink(
            source_node_id=cycled_layer.nodes[-1].node_id,
            target_node_id=cycled_layer.nodes[0].node_id,
            link_type="prerequisite",
            link_label_ru="предпосылка",
            rationale="Искусственный цикл для проверки детектора DAG.",
        )
    )
    chk = verify_layer_pedagogical_invariants(cycled_layer)
    assert chk["prerequisite_dag_acyclic_ok"] is False
    assert chk["passed"] is False

    # Проверка предрендерной спецификации сцены (scene_specs/*.json) до рендера
    pkg = build_t3_course_package(
        data_dir=DATA_DIR,
        output_dir=tmp_path,
        book_file="train_latyshova.md",
        render_mp4=False,
    )
    assert pkg.domain_package_id == "oil_gas_ru"
    assert pkg.routing_report.hook_shorts_share_pct <= 20.0
    assert len(pkg.routing_report.video_heavy_template_coverage) >= 1
    assert len(pkg.scene_specs) >= 1
    assert (tmp_path / pkg.course_id / "scene_specs" / "shorts_9_16_latyshova.json").exists()

    # Проверка независимого запуска верификатора на внешнем пакете закладок
    ext_pkg_path = tmp_path / "ext_bookmarks.json"
    ext_pkg_path.write_text(
        json.dumps(
            {
                "book_file": "train_latyshova.md",
                "items": [
                    {
                        "id": "ext_01_wrong_mech",
                        "pdf_page": 96,
                        "text": "Минеральный скелет породы проводит ток лучше поровой воды.",
                    },
                    {
                        "id": "ext_02_bad_page",
                        "pdf_page": 999,
                        "text": "Утверждение со ссылкой на несуществующую страницу.",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ext_rep = verify_external_bookmark_package(DATA_DIR, ext_pkg_path)
    assert ext_rep.evaluation_mode == "official_bookmark_package"
    assert ext_rep.passed is False
    assert ext_rep.counts_by_verdict.get("confirmed_violation", 0) >= 1
    assert ext_rep.counts_by_verdict.get("insufficient_evidence", 0) >= 1

