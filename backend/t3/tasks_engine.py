"""
Этап 2 Т3: Генератор и валидатор учебных заданий (≥15 заданий на главу, 5 типов Т3),
содержательных карточек («Знаю» / «Повторить»), конспекта и локальных/онлайн подсказок
со строгим соблюдением границы приватности OpenAI (передача только разрешённых метаданных).
"""

from __future__ import annotations

import os
from typing import Any, Callable

from backend.t3.models import (
    FlashcardItem,
    KnowledgeClaim,
    KnowledgeNode,
    StudyLayer,
    StudyStepScreen,
    StudyTask,
)

ALLOWED_HINT_METADATA_KEYS = {
    "task_type",
    "difficulty_level",
    "primary_difficulty",
    "secondary_difficulty",
    "attempt_number",
    "hint_level",
    "has_formula",
}

FORBIDDEN_EXTERNAL_KEYS = {
    "chapter_text",
    "verbatim_quote",
    "quote",
    "options",
    "student_answer",
    "user_answer",
    "correct_answer",
    "narration",
}

PEDAGOGICAL_STRATEGIES = {
    "socratic_mechanism_cue": "Сократический наводящий вопрос по физическому механизму",
    "condition_and_boundary_check": "Проверка граничного условия применимости методики",
    "dimensional_and_formula_audit": "Сверка размерностей и структуры расчётной формулы",
    "signs_rule_conclusion_chain": "Декомпозиция по цепочке «признаки → правило → вывод»",
}


def build_allowed_hint_metadata(
    task: StudyTask,
    node: KnowledgeNode,
    attempt_number: int = 1,
    hint_level: int = 1,
) -> dict[str, Any]:
    """
    Формирует строго ограниченный пакет метаданных для выбора педагогического приёма подсказки.
    Никакие главы, цитаты, варианты ответов или ответы учащихся в этот пакет НЕ входят.
    """
    payload = {
        "task_type": task.task_type,
        "difficulty_level": task.difficulty_level,
        "primary_difficulty": node.primary_difficulty,
        "secondary_difficulty": node.secondary_difficulty,
        "attempt_number": max(1, int(attempt_number)),
        "hint_level": min(max(1, int(hint_level)), 3),
        "has_formula": task.task_type == "calculation",
    }
    assert set(payload.keys()).issubset(ALLOWED_HINT_METADATA_KEYS)
    assert not (set(payload.keys()) & FORBIDDEN_EXTERNAL_KEYS)
    return payload


def select_hint_strategy_and_render_locally(
    task: StudyTask,
    node: KnowledgeNode,
    attempt_number: int = 1,
    hint_level: int = 1,
    mock_api_callable: Callable[[dict[str, Any]], str] | None = None,
    allow_online_openai: bool = False,
) -> dict[str, Any]:
    """
    Реализует разграничение Т3:
    1) Внешний/имитируемый вызов получает ТОЛЬКО разрешённые метаданные и выбирает ID педагогического приёма.
    2) Текст подсказки всегда формируется ЛОКАЛЬНО по проверенному учебному слою.
    """
    metadata = build_allowed_hint_metadata(task, node, attempt_number=attempt_number, hint_level=hint_level)

    strategy_id = "socratic_mechanism_cue"
    selector_source = "local_deterministic"

    if mock_api_callable is not None:
        candidate = mock_api_callable(metadata)
        if candidate in PEDAGOGICAL_STRATEGIES:
            strategy_id = candidate
        selector_source = "mock_openai_api"
    elif allow_online_openai:
        api_key = (os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "").strip()
        if api_key and api_key != "PASTE_YOUR_KEY_HERE":
            try:
                from openai import OpenAI

                client = OpenAI(
                    api_key=api_key,
                    base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1").strip(),
                )
                resp = client.chat.completions.create(
                    model=os.getenv("LLM_MODEL", "gpt-4o-mini").strip(),
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Выбери один код педагогического приёма из списка: "
                                "socratic_mechanism_cue, condition_and_boundary_check, "
                                "dimensional_and_formula_audit, signs_rule_conclusion_chain."
                            ),
                        },
                        {"role": "user", "content": str(metadata)},
                    ],
                    temperature=0.0,
                    max_tokens=16,
                )
                raw_choice = (resp.choices[0].message.content or "").strip()
                for key in PEDAGOGICAL_STRATEGIES:
                    if key in raw_choice:
                        strategy_id = key
                        selector_source = "openai_metadata_only"
                        break
            except Exception:
                selector_source = "local_fallback_after_api_error"
    else:
        if task.task_type == "calculation":
            strategy_id = "dimensional_and_formula_audit"
        elif task.task_type == "case_decision":
            strategy_id = "signs_rule_conclusion_chain"
        elif hint_level >= 2:
            strategy_id = "condition_and_boundary_check"

    idx = min(max(0, hint_level - 1), len(task.hint_steps) - 1) if task.hint_steps else 0
    base_hint = task.hint_steps[idx] if task.hint_steps else node.threshold_concept
    strategy_title = PEDAGOGICAL_STRATEGIES[strategy_id]

    local_text = f"[{strategy_title}] {base_hint} (Источник: {task.source_ref})."
    return {
        "strategy_id": strategy_id,
        "strategy_title": strategy_title,
        "selector_source": selector_source,
        "metadata_sent": metadata,
        "hint_level": hint_level,
        "hint_text": local_text,
        "source_ref": task.source_ref,
    }


def _book_calculation_specs(book_file: str) -> list[dict[str, Any]]:
    """Предметные расчётные задания (5-й тип Т3) для каждой из 6 книг."""
    if "latyshova" in book_file:
        return [
            {
                "prompt": "Рассчитайте опорное удельное сопротивление полностью водоносного песчаника ρ_вп (Ом·м), если параметр пористости P_п = 15,5, а удельное сопротивление пластовой воды при пластовой температуре ρ_в = 0,05 Ом·м (формула 2, §1).",
                "unit": "Ом·м",
                "answer": 0.775,
                "tolerance": 0.03,
                "explanation": "По формуле (2) §1 М.Г. Латышовой: ρ_вп = P_п · ρ_в = 15,5 · 0,05 = 0,775 Ом·м.",
                "hints": [
                    "Вспомните прямую пропорциональность между сопротивлением водоносной породы ρ_вп и сопротивлением пластовой воды ρ_в.",
                    "Примените формулу (2) §1: ρ_вп = P_п · ρ_в.",
                    "Умножьте 15,5 на 0,05 Ом·м.",
                ],
            },
            {
                "prompt": "Вычислите коэффициент нефтегазонасыщения K_нг (в долях единицы), если истинное сопротивление пласта ρ_п = 16,0 Ом·м, водоносное сопротивление ρ_вп = 0,80 Ом·м, а в формуле Арчи–Дахнова P_н = 1 / K_в² (a_n = 1, n = 2).",
                "unit": "д.е.",
                "answer": 0.776,
                "tolerance": 0.03,
                "explanation": "Находим параметр насыщения P_н = ρ_п / ρ_вп = 16,0 / 0,80 = 20,0. Тогда K_в = 1 / √20,0 ≈ 0,224 и K_нг = 1 − K_в ≈ 0,776 (77,6 %).",
                "hints": [
                    "Сначала найдите параметр насыщения P_н = ρ_п / ρ_вп.",
                    "Из соотношения P_н = 1 / K_в² выразите коэффициент водонасыщения K_в = 1 / √P_н.",
                    "Перейдите к нефтегазонасыщению: K_нг = 1 − K_в.",
                ],
            },
        ]
    if "basniev" in book_file:
        return [
            {
                "prompt": "По данным опыта Дарси скорость фильтрации жидкости в пласте равна w = 0,36 мм/с, а динамическая пористость (просветность) породы составляет m = 0,18. Вычислите истинную среднюю скорость движения флюида в поровых каналах v (в мм/с).",
                "unit": "мм/с",
                "answer": 2.0,
                "tolerance": 0.05,
                "explanation": "Поскольку флюид течёт только через открытые поры (доля сечения m), истинная средняя скорость v = w / m = 0,36 / 0,18 = 2,0 мм/с.",
                "hints": [
                    "Истинная скорость движения флюида в поровых каналах всегда выше скорости фильтрации w.",
                    "Используйте соотношение §4 главы XVIII: v = w / m.",
                    "Разделите 0,36 мм/с на 0,18.",
                ],
            },
            {
                "prompt": "По формуле Дюпюи установившийся дебит скважины равен Q = 247,5 м³/сут при депрессии на пласт Δp = p_к − p_с = 7,5 МПа. Вычислите коэффициент продуктивности скважины C (в м³/(сут·МПа)).",
                "unit": "м³/(сут·МПа)",
                "answer": 33.0,
                "tolerance": 0.5,
                "explanation": "По формуле (20.22) §3 главы XX коэффициент продуктивности C = Q / (p_к − p_с) = 247,5 / 7,5 = 33,0 м³/(сут·МПа).",
                "hints": [
                    "Коэффициент продуктивности C показывает дебит скважины на 1 МПа депрессии.",
                    "Примените определение C = Q / Δp.",
                    "Разделите 247,5 м³/сут на 7,5 МПа.",
                ],
            },
        ]
    if "kuznetsov" in book_file:
        return [
            {
                "prompt": "По данным §10.3 (стр. 205, рис. 10.2) в одиночном куполовидном рифе Рейнбоу «А» (Канада) нефтенасыщенная мощность составляет 90 м, а газонасыщенная шапка — 60 м при общей высоте рифа 250 м. Вычислите суммарную продуктивную (нефтегазонасыщенную) высоту залежи в этом рифе (в метрах).",
                "unit": "м",
                "answer": 150.0,
                "tolerance": 1.0,
                "explanation": "Согласно §10.3 (стр. 205), из общей высоты пиннакла 200–250 м 90 м нефтенасыщены и 60 м газонасыщены; суммарный продуктивный этаж составляет 90 + 60 = 150 м.",
                "hints": [
                    "Проверьте параметры эталонного рифа Рейнбоу «А» в §10.3 (стр. 205).",
                    "Сложите толщину нефтенасыщенной зоны (90 м) и газовой шапки (60 м).",
                    "90 м + 60 м = 150 м.",
                ],
            },
            {
                "prompt": "В крупном рифовом комплексе (§10.2, стр. 202) доля прижизненных биогермных каркасных известняков составляет 20 %, а остальной объём массива сложен обломочными и детритовыми известняками разрушения. Какова доля обломочных/детритовых разностей в таком рифе (в %)?",
                "unit": "%",
                "answer": 80.0,
                "tolerance": 1.0,
                "explanation": "По данным §10.2 (стр. 202), содержание биогермных известняков в сложных рифовых комплексах не превышает 10–20 %, а ведущее значение по распространённости имеют обломочные разности (до 60–80 %).",
                "hints": [
                    "Вспомните баланс пород рифового комплекса из §10.2 (стр. 202).",
                    "Вычтите долю каркасных биогермных пород (20 %) из 100 %.",
                    "100 % − 20 % = 80 %.",
                ],
            },
        ]
    if "vendelshtein" in book_file:
        return [
            {
                "prompt": "Согласно §I.1.2 (стр. 19–20), для выделения проницаемых зон методом ИНМ с раствором бора требуется концентрация бора 4 г/л при K_п = 2 %, а соответствующая концентрация кадмия должна быть в 3 раза выше. Рассчитайте требуемую концентрацию кадмия (в г/л).",
                "unit": "г/л",
                "answer": 12.0,
                "tolerance": 0.2,
                "explanation": "По тексту Вендельштейна и Резванова (стр. 19–20): при концентрации бора 4 г/л соответствующая концентрация кадмия в 3 раза выше: 4 · 3 = 12 г/л.",
                "hints": [
                    "Найдите правило пересчёта концентрации бора в концентрацию кадмия на границе страниц 19–20.",
                    "Концентрация кадмия в 3 раза выше концентрации бора (4 г/л).",
                    "Умножьте 4 г/л на 3.",
                ],
            },
            {
                "prompt": "По правилу 2 временных исследований ИНМ (стр. 23) время каждого последующего замера после крепления скважины должно быть минимум в 2 раза больше времени предыдущего. Если второй замер выполнен через 3 суток после крепления, через сколько минимум суток от момента крепления следует проводить третий замер?",
                "unit": "сут",
                "answer": 6.0,
                "tolerance": 0.2,
                "explanation": "Согласно п. 2 на стр. 23, время каждого последующего замера (отсчитываемое от момента крепления скважины) должно быть в 2–3 раза больше времени предыдущего: 3 сут · 2 = 6 сут.",
                "hints": [
                    "Откройте условие №2 проведения временных замеров на стр. 23.",
                    "Умножьте время предыдущего замера (3 сут) на минимальный коэффициент 2.",
                    "3 · 2 = 6 суток.",
                ],
            },
        ]
    if "barenblatt" in book_file:
        return [
            {
                "prompt": "Рассчитайте безразмерное число Рейнольдса фильтрационного потока Re = (u · √k) / ν (§3 гл. 1, стр. 10), если скорость фильтрации u = 0,002 м/с, проницаемость k = 10⁻¹² м² (√k = 10⁻⁶ м), а кинематическая вязкость жидкости ν = 10⁻⁶ м²/с.",
                "unit": "б/р",
                "answer": 0.002,
                "tolerance": 0.0005,
                "explanation": "По формуле §3 главы 1 Г.И. Баренблатта и др.: Re = (u · √k) / ν = (0,002 · 10⁻⁶) / 10⁻⁶ = 0,002 (что много меньше критического порога 0,1–1).",
                "hints": [
                    "Характерный линейный размер пор в определении Баренблатта равен l = √k = 10⁻⁶ м.",
                    "Подставьте значения в формулу Re = (u · √k) / ν.",
                    "Сократите 10⁻⁶ в числителе и знаменателе.",
                ],
            },
            {
                "prompt": "В упругом пласте пористость m = 0,20, сжимаемость жидкости β_ж = 1,0·10⁻⁹ Па⁻¹, а сжимаемость скелета β_с = 1,0·10⁻¹⁰ Па⁻¹ (§4 гл. 1). Вычислите коэффициент упругоёмкости пласта β* = m·β_ж + β_с в единицах 10⁻¹⁰ Па⁻¹.",
                "unit": "10⁻¹⁰ Па⁻¹",
                "answer": 3.0,
                "tolerance": 0.1,
                "explanation": "β* = m·β_ж + β_с = 0,20 · 10·10⁻¹⁰ + 1,0·10⁻¹⁰ = 2,0·10⁻¹⁰ + 1,0·10⁻¹⁰ = 3,0·10⁻¹⁰ Па⁻¹.",
                "hints": [
                    "Запишите формулу суммарной упругоёмкости пласта β* = m·β_ж + β_с.",
                    "Выразите оба слагаемых в единицах 10⁻¹⁰ Па⁻¹: m·β_ж = 0,20 · 10 = 2,0.",
                    "Прибавьте сжимаемость скелета β_с = 1,0.",
                ],
            },
        ]
    return [
        {
            "prompt": "В разрезе меандрирующей реки (§1.1, стр. 24) вскрыто песчаное тело прирусловой отмели (пойнт-бара) мощностью 12 м, перекрытое пойменными глинами мощностью 4 м. Какова доля эффективной песчаной мощности в этом 16-метровом русловом циклите (в %)?",
            "unit": "%",
            "answer": 75.0,
            "tolerance": 1.0,
            "explanation": "Отношение песчаной части пойнт-бара (12 м) к полной мощности циклита (12 + 4 = 16 м) составляет (12 / 16) · 100 % = 75 %.",
            "hints": [
                "Полная мощность циклита равна сумме песчаного пойнт-бара (12 м) и пойменных глин (4 м).",
                "Разделите мощность коллектора 12 м на полную мощность 16 м.",
                "Умножьте 0,75 на 100 %.",
            ],
        },
        {
            "prompt": "В проградационном разрезе фронта дельты (§1.2, стр. 32) выделены три последовательных песчаных устьевых бара мощностями 6,5 м, 8,0 м и 9,5 м, разделённых глинами продельты. Вычислите суммарную песчаную мощность комплекса устьевых баров (в метрах).",
            "unit": "м",
            "answer": 24.0,
            "tolerance": 0.2,
            "explanation": "Суммарная мощность песчаников устьевых баров фронта дельты равна 6,5 + 8,0 + 9,5 = 24,0 м.",
            "hints": [
                "Просуммируйте мощности трёх песчаных тел устьевых баров.",
                "6,5 + 8,0 = 14,5 м.",
                "14,5 + 9,5 = 24,0 м.",
            ],
        },
    ]


def generate_chapter_tasks(layer: StudyLayer, course_id: str) -> list[StudyTask]:
    """
    Генерирует 16 проверяемых заданий для главы (минимум 15 заданий по Т3)
    пяти типов: single_choice (5), ordering (3), matching (3), case_decision (3), calculation (2).
    Каждое задание жёстко связано с узлом и утверждением (claim_id) учебного слоя.
    """
    tasks: list[StudyTask] = []
    nodes = layer.nodes
    claims_by_id: dict[str, KnowledgeClaim] = {c.claim_id: c for c in layer.claims}

    def _pick_node_and_claim(idx: int) -> tuple[KnowledgeNode, KnowledgeClaim]:
        node = nodes[idx % len(nodes)]
        cid = node.claim_ids[0] if node.claim_ids else layer.claims[0].claim_id
        return node, claims_by_id[cid]

    # ТИП 1: 5 заданий single_choice (с диагностикой заблуждений по каждому варианту)
    for i in range(5):
        node, cl = _pick_node_and_claim(i)
        step_id = node.node_id.replace("_node_", "_step_")
        task_id = f"{course_id}_task_sc_{i + 1:02d}"
        src_ref = f"{layer.book_title}, {node.source_heading}, PDF стр. {cl.pdf_page} (печ. стр. {cl.printed_page})"

        if i == 0 and "vendelshtein" in layer.book_file:
            # Специальный контрольный вопрос по стр. 20 Вендельштейна («однозначно нельзя»)
            p20_node = next((n for n in nodes if any(q.pdf_page == 20 for q in n.quotes_and_pages)), node)
            p20_cl = next((c for c in layer.claims if c.pdf_page == 20), cl)
            step_id = p20_node.node_id.replace("_node_", "_step_")
            src_ref = f"{layer.book_title}, §I.2, PDF стр. 20 (печ. стр. {p20_cl.printed_page})"
            tasks.append(
                StudyTask(
                    task_id=task_id,
                    course_id=course_id,
                    node_id=p20_node.node_id,
                    step_id=step_id,
                    claim_id=p20_cl.claim_id,
                    pdf_page=20,
                    printed_page=p20_cl.printed_page,
                    task_type="single_choice",
                    difficulty_level="инженерный",
                    prompt="Какой вывод делают Б.Ю. Вендельштейн и Р.А. Резванов (стр. 20), если глубина зоны проникновения фильтрата ПРЕВЫШАЕТ глубину исследования используемого комплекта зондов электрометрии?",
                    options=[
                        "Разделить коллекторы на продуктивные и водоносные по данным электрометрии без дополнительных сведений (испытаний и др.) однозначно нельзя",
                        "Разделить коллекторы на продуктивные и водоносные по данным одной электрометрии однозначно можно",
                        "Достаточно умножить показания малого градиент-зонда на коэффициент пористости",
                        "Глубина зоны проникновения не влияет на определение удельного сопротивления неизменённой части пласта ρ_п",
                    ],
                    correct_answer=0,
                    answer_key_display="Вариант 1: без дополнительных сведений (данные испытаний и др.) разделить коллекторы по электрометрии однозначно нельзя.",
                    explanation="На стр. 20 прямо указано: если глубина зоны проникновения превышает глубину исследования зондов, все зонды регистрируют промытую зону, и без данных испытаний разделить пласты на продуктивные и водоносные однозначно нельзя.",
                    error_analysis={
                        "1": "Грубая ошибка (переворот модальности «нельзя» → «можно»): при глубоком проникновении зонды не достают до неизменённой части пласта.",
                        "2": "Малый зонд измеряет только промытую зону вблизи стенки скважины.",
                        "3": "Именно глубина зоны проникновения является главным условием достоверного определения ρ_п.",
                    },
                    hint_steps=[
                        "Проверьте условие сопоставления глубины зоны проникновения и радиуса исследования зондов на стр. 20.",
                        "Что измеряет зонд, если фильтрат проник глубже его радиуса исследования?",
                        "В этом случае по одной электрометрии без данных испытаний разделить коллекторы однозначно нельзя.",
                    ],
                    source_ref=src_ref,
                    verbatim_quote=p20_cl.verbatim_quote,
                )
            )
            continue

        options = [
            f"Верно по источнику: {node.threshold_concept}",
            f"Типичное заблуждение: {node.misconception_to_fix}",
            "Параметры методики применяются без учёта граничных условий и литологии пласта",
            "Физический механизм не зависит от структуры порового пространства и свойств флюида",
        ]
        tasks.append(
            StudyTask(
                task_id=task_id,
                course_id=course_id,
                node_id=node.node_id,
                step_id=step_id,
                claim_id=cl.claim_id,
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                task_type="single_choice",
                difficulty_level="базовый" if i < 2 else "инженерный",
                prompt=f"Какое утверждение точно отражает ключевой физико-геологический принцип шага «{node.step_title}» ({node.source_heading})?",
                options=options,
                correct_answer=0,
                answer_key_display=f"Вариант 1: {options[0]}",
                explanation=f"{node.summary_2_3_sentences} ({src_ref}).",
                error_analysis={
                    "1": f"Это известная ошибка интерпретации: {node.misconception_to_fix}",
                    "2": f"Игнорирование граничных условий ({node.nuances}) приводит к неверному решению.",
                    "3": f"В действительности механизм основан на том, что {node.mechanism}",
                },
                hint_steps=[
                    f"Обратите внимание на наблюдение: {node.epistemic_split.observation}",
                    f"Учтите физический механизм: {node.mechanism}",
                    f"Пороговая идея шага: {node.threshold_concept}",
                ],
                source_ref=src_ref,
                verbatim_quote=cl.verbatim_quote,
            )
        )

    # ТИП 2: 3 задания ordering (упорядочивание ручных шагов специалиста — для drag-and-drop и клавиатуры)
    for i in range(3):
        node, cl = _pick_node_and_claim(i)
        step_id = node.node_id.replace("_node_", "_step_")
        task_id = f"{course_id}_task_ord_{i + 1:02d}"
        src_ref = f"{layer.book_title}, {node.source_heading}, PDF стр. {cl.pdf_page}"
        ordered_steps = list(node.specialist_manual_steps[:3])
        if len(ordered_steps) < 3:
            ordered_steps = [
                f"Зафиксировать входные наблюдения: {node.epistemic_split.observation}",
                f"Проверить допущения модели: {node.epistemic_split.assumption}",
                f"Выполнить вывод и расчёт: {node.epistemic_split.inference}",
            ]

        tasks.append(
            StudyTask(
                task_id=task_id,
                course_id=course_id,
                node_id=node.node_id,
                step_id=step_id,
                claim_id=cl.claim_id,
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                task_type="ordering",
                difficulty_level="инженерный",
                prompt=f"Расположите ручные действия специалиста на шаге «{node.step_title}» в методически правильном порядке (поддерживается перетаскивание и кнопки Вверх/Вниз с клавиатуры):",
                ordering_items=ordered_steps,
                correct_answer=ordered_steps,
                answer_key_display=" → ".join(f"{idx + 1}) {s}" for idx, s in enumerate(ordered_steps)),
                explanation=f"Методический порядок диктуется цепочкой «проверка условий и первичных данных → расчёт/построение → контроль результата» ({src_ref}).",
                error_analysis={
                    "order_mismatch": "Нарушена последовательность подготовки данных: нельзя снимать итоговый параметр до проверки граничных условий и приведения единиц."
                },
                hint_steps=[
                    "Первый шаг всегда связан с проверкой первичных данных, масштабов или условий применимости.",
                    "Второй шаг выполняет основное преобразование, расчёт или построение по палетке/формуле.",
                    "Заключительный шаг — снятие целевого параметра и проверка критерия принятия решения.",
                ],
                source_ref=src_ref,
                verbatim_quote=cl.verbatim_quote,
            )
        )

    # ТИП 3: 3 задания matching (сопоставление терминов СНГ ↔ Запад, параметров и смысловых ролей)
    all_terms = [ct for n in nodes for ct in n.core_terms]
    for i in range(3):
        node, cl = _pick_node_and_claim(i + 1)
        step_id = node.node_id.replace("_node_", "_step_")
        task_id = f"{course_id}_task_match_{i + 1:02d}"
        src_ref = f"{layer.book_title}, {node.source_heading}, PDF стр. {cl.pdf_page}"

        pairs: list[dict[str, str]] = []
        if i == 0 and len(all_terms) >= 3:
            for ct in all_terms[:3]:
                pairs.append(
                    {
                        "left": f"{ct.term} ({ct.cis_symbol})",
                        "right": f"{ct.west_symbol} — {ct.west_term or ct.definition[:60]}",
                    }
                )
        elif i == 1:
            pairs = [
                {"left": "Наблюдение (Измерение)", "right": node.epistemic_split.observation},
                {"left": "Вывод (Вычисление)", "right": node.epistemic_split.inference},
                {"left": "Допущение модели", "right": node.epistemic_split.assumption},
            ]
        else:
            mod = node.modern_equivalents[0]
            pairs = [
                {"left": f"Исторический прибор/метод: {mod.historical_item}", "right": f"Современный аналог: {mod.modern_analog}"},
                {"left": "Физический механизм шага", "right": node.mechanism[:110]},
                {"left": "Практический перенос в данные", "right": node.data_transfer[:110]},
            ]

        correct_map = {p["left"]: p["right"] for p in pairs}
        tasks.append(
            StudyTask(
                task_id=task_id,
                course_id=course_id,
                node_id=node.node_id,
                step_id=step_id,
                claim_id=cl.claim_id,
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                task_type="matching",
                difficulty_level="инженерный",
                prompt=f"Сопоставьте элементы и понятия шага «{node.step_title}» с их точными эквивалентами по источнику:",
                matching_pairs=pairs,
                correct_answer=correct_map,
                answer_key_display="; ".join(f"{k} ↔ {v}" for k, v in correct_map.items()),
                explanation=f"Точное разграничение обозначений СНГ/Запад и эпистемических ролей предотвращает ошибки интерпретации ({src_ref}).",
                error_analysis={
                    "mismatch": "Перепутаны роли наблюдения и допущения либо обозначения отечественной и международной школ."
                },
                hint_steps=[
                    "Сверьте обозначения СНГ и международные символы SPE/API в словаре шага.",
                    "Отделите прямое измерение прибора от расчётной формулы и допущения модели.",
                    f"Проверьте определения на стр. {cl.pdf_page}.",
                ],
                source_ref=src_ref,
                verbatim_quote=cl.verbatim_quote,
            )
        )

    # ТИП 4: 3 задания case_decision (задачи на решение по данным с явным ходом «признаки → правило → вывод»)
    for i in range(3):
        node, cl = _pick_node_and_claim(i)
        step_id = node.node_id.replace("_node_", "_step_")
        task_id = f"{course_id}_task_case_{i + 1:02d}"
        src_ref = f"{layer.book_title}, {node.source_heading}, PDF стр. {cl.pdf_page}"

        obs_text = f"Признаки (данные): {node.epistemic_split.observation} Кроме того, зафиксировано: {node.data_transfer}"
        rule_text = f"Правило (критерий по учебнику, стр. {cl.pdf_page}): {node.threshold_concept} (с учётом ограничения: {node.nuances})"
        concl_text = f"Вывод и решение специалиста: {node.decision_points[0] if node.decision_points else node.practice}"

        case_options = [
            f"Признаки подтверждают критерий применимости → {concl_text}",
            f"Игнорировать граничное условие ({node.nuances[:70]}) и применить формулу вслепую",
            f"Принять ошибочную трактовку: {node.misconception_to_fix[:80]}",
            "Отказаться от количественной интерпретации при выполнении всех условий применимости",
        ]

        tasks.append(
            StudyTask(
                task_id=task_id,
                course_id=course_id,
                node_id=node.node_id,
                step_id=step_id,
                claim_id=cl.claim_id,
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                task_type="case_decision",
                difficulty_level="продвинутый",
                prompt=(
                    f"Кейс принятия решения по данным («признаки → правило → вывод») по шагу «{node.step_title}».\n"
                    f"1) {obs_text}\n"
                    f"2) {rule_text}\n"
                    "Какой инженерный вывод следует сделать специалисту?"
                ),
                case_observation=obs_text,
                case_rule=rule_text,
                case_conclusion=concl_text,
                options=case_options,
                correct_answer=0,
                answer_key_display=f"Ход решения: Признаки → Правило → Вывод: {case_options[0]}",
                explanation=f"По цепочке «признаки → правило → вывод»: {obs_text} → {rule_text} → {concl_text} ({src_ref}).",
                error_analysis={
                    "1": "Применение методики без проверки граничного условия приводит к грубой ошибке в подсчётных параметрах.",
                    "2": f"Сработала типичная ловушка: {node.misconception_to_fix}",
                    "3": "Все условия применимости выполнены, поэтому отказ от интерпретации необоснован.",
                },
                hint_steps=[
                    f"Шаг 1 (Признаки): выделите ключевой диагностический сигнал в данных — {node.data_transfer}",
                    f"Шаг 2 (Правило): сопоставьте сигнал с пороговым критерием — {node.threshold_concept}",
                    f"Шаг 3 (Вывод): сформулируйте решение с учётом точки контроля — {concl_text}",
                ],
                source_ref=src_ref,
                verbatim_quote=cl.verbatim_quote,
            )
        )

    # ТИП 5: 2 расчётных задания calculation (пятый тип Т3 с проверкой числа и единицы измерения)
    calc_specs = _book_calculation_specs(layer.book_file)
    for i, cspec in enumerate(calc_specs[:2]):
        node, cl = _pick_node_and_claim(i + 1)
        step_id = node.node_id.replace("_node_", "_step_")
        task_id = f"{course_id}_task_calc_{i + 1:02d}"
        src_ref = f"{layer.book_title}, {node.source_heading}, PDF стр. {cl.pdf_page}"

        tasks.append(
            StudyTask(
                task_id=task_id,
                course_id=course_id,
                node_id=node.node_id,
                step_id=step_id,
                claim_id=cl.claim_id,
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                task_type="calculation",
                difficulty_level="продвинутый",
                prompt=cspec["prompt"],
                calculation_unit=cspec["unit"],
                calculation_tolerance=float(cspec["tolerance"]),
                correct_answer=float(cspec["answer"]),
                answer_key_display=f"{cspec['answer']} {cspec['unit']}",
                explanation=f"{cspec['explanation']} ({src_ref}).",
                error_analysis={
                    "wrong_value": f"Проверьте перевод единиц измерения в систему расчёта ({cspec['unit']}) и порядок действий в формуле."
                },
                hint_steps=list(cspec["hints"]),
                source_ref=src_ref,
                verbatim_quote=cl.verbatim_quote,
            )
        )

    # ТИП 6 (официальный тип Т3): 2 задания multi_select (выбор нескольких верных утверждений)
    for i in range(2):
        node, cl = _pick_node_and_claim(i)
        step_id = node.node_id.replace("_node_", "_step_")
        task_id = f"{course_id}_task_multi_{i + 1:02d}"
        src_ref = f"{layer.book_title}, {node.source_heading}, PDF стр. {cl.pdf_page}"
        ms_options = [
            f"Наблюдение/входные данные: {node.epistemic_split.observation[:110]}",
            f"Допущение/ограничение модели: {node.epistemic_split.assumption[:110]}",
            f"Ошибочное суждение: {node.misconception_to_fix[:110]}",
            "Граничные условия и единицы измерения учебника можно игнорировать при переносе на другие скважины.",
        ]
        tasks.append(
            StudyTask(
                task_id=task_id,
                course_id=course_id,
                node_id=node.node_id,
                step_id=step_id,
                claim_id=cl.claim_id,
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                task_type="multi_select",
                difficulty_level="инженерный",
                prompt=f"Выберите ВСЕ верные утверждения по шагу «{node.step_title}» (стр. {cl.pdf_page}):",
                options=ms_options,
                correct_answer=[0, 1],
                answer_key_display="Верны пункты 1 и 2 (наблюдение и допущение модели из источника).",
                explanation=f"Пункты 1 и 2 соответствуют эпистемическому разложению узла ({src_ref}); пункт 3 воспроизводит типичное заблуждение.",
                error_analysis={
                    "2": f"Типичное заблуждение: {node.misconception_to_fix}",
                    "3": "Нарушение границ применимости делает расчёт недостоверным.",
                },
                hint_steps=[
                    f"Сверьте наблюдения и допущения шага «{node.step_title}».",
                    f"Отбросьте типичное заблуждение: {node.misconception_to_fix[:90]}",
                    "В данном задании верны два утверждения.",
                ],
                source_ref=src_ref,
                verbatim_quote=cl.verbatim_quote,
            )
        )

    # ТИП 7 (официальный тип Т3): 2 задания fill_in_blank (заполнение пропуска по опорному термину/обозначению)
    for i in range(2):
        node, cl = _pick_node_and_claim(i + 1)
        step_id = node.node_id.replace("_node_", "_step_")
        task_id = f"{course_id}_task_blank_{i + 1:02d}"
        src_ref = f"{layer.book_title}, {node.source_heading}, PDF стр. {cl.pdf_page}"
        term_obj = node.core_terms[0] if node.core_terms else None
        target_term = term_obj.term if term_obj else node.step_title.split()[0]
        acceptable = [target_term.lower()]
        if term_obj and term_obj.cis_symbol and term_obj.cis_symbol != "—":
            acceptable.append(term_obj.cis_symbol.lower())
        if term_obj and term_obj.west_symbol and term_obj.west_symbol != "—":
            acceptable.append(term_obj.west_symbol.lower())
        short_key = target_term.split("(")[0].strip()
        if short_key.lower() not in acceptable:
            acceptable.append(short_key.lower())

        prompt_txt = (
            f"Заполните пропуск (термин или обозначение из шага «{node.step_title}», стр. {cl.pdf_page}): "
            f"«_______ — это {term_obj.definition.lower() if term_obj else node.threshold_concept.lower()}»."
        )
        tasks.append(
            StudyTask(
                task_id=task_id,
                course_id=course_id,
                node_id=node.node_id,
                step_id=step_id,
                claim_id=cl.claim_id,
                pdf_page=cl.pdf_page,
                printed_page=cl.printed_page,
                task_type="fill_in_blank",
                difficulty_level="базовый",
                prompt=prompt_txt,
                blank_acceptable_answers=acceptable,
                correct_answer=short_key,
                answer_key_display=f"{short_key} (допускаются также: {', '.join(acceptable[:3])})",
                explanation=f"По определению при первом употреблении на стр. {cl.pdf_page}: {short_key} — {term_obj.definition if term_obj else node.threshold_concept} ({src_ref}).",
                error_analysis={"wrong_text": "Проверьте орфографию опорного термина или его каноническое обозначение (СНГ/Запад) в глоссарии шага."},
                hint_steps=[
                    f"Откройте блок опорных терминов шага «{node.step_title}».",
                    f"СНГ-обозначение: {term_obj.cis_symbol if term_obj else '—'}, западное: {term_obj.west_symbol if term_obj else '—'}.",
                    f"Первое слово ответа: «{short_key.split()[0]}».",
                ],
                source_ref=src_ref,
                verbatim_quote=cl.verbatim_quote,
            )
        )

    return tasks


def validate_tasks_against_layer(tasks: list[StudyTask], layer: StudyLayer) -> dict[str, Any]:
    """
    Валидирует набор заданий главы по утверждениям учебного слоя:
    - минимум 15 заданий на главу
    - минимум 4 (фактически 5) типов заданий Т3
    - наличие задачи на решение по данным «признаки → правило → вывод»
    - привязка каждого задания к реальному node_id, claim_id и pdf_page слоя.
    """
    node_ids = {n.node_id for n in layer.nodes}
    claim_map = {c.claim_id: c for c in layer.claims}

    errors: list[str] = []
    if len(tasks) < 15:
        errors.append(f"Недостаточно заданий на главу: {len(tasks)} < 15")

    types_present = {t.task_type for t in tasks}
    if len(types_present) < 4:
        errors.append(f"Представлено менее 4 типов заданий Т3: {sorted(types_present)}")

    case_tasks = [
        t
        for t in tasks
        if t.task_type == "case_decision" and t.case_observation and t.case_rule and t.case_conclusion
    ]
    if not case_tasks:
        errors.append("Отсутствует задача на решение по данным с явным ходом «признаки → правило → вывод».")

    for t in tasks:
        if t.node_id not in node_ids:
            errors.append(f"Задание {t.task_id} ссылается на несуществующий узел {t.node_id}")
        if t.claim_id not in claim_map:
            errors.append(f"Задание {t.task_id} ссылается на несуществующее утверждение {t.claim_id}")
        else:
            cl = claim_map[t.claim_id]
            if t.pdf_page != cl.pdf_page:
                errors.append(f"Несовпадение страницы в задании {t.task_id}: {t.pdf_page} != {cl.pdf_page}")
        if not t.explanation or not t.source_ref or not t.answer_key_display:
            errors.append(f"В задании {t.task_id} отсутствует ключ, объяснение или ссылка на источник.")

    counts_by_type: dict[str, int] = {}
    for t in tasks:
        counts_by_type[t.task_type] = counts_by_type.get(t.task_type, 0) + 1

    return {
        "passed": len(errors) == 0,
        "total_tasks": len(tasks),
        "distinct_types_count": len(types_present),
        "counts_by_type": counts_by_type,
        "has_case_decision_chain": len(case_tasks) > 0,
        "has_calculation_type": "calculation" in types_present,
        "errors": errors,
    }


def check_task_submission(task: StudyTask, user_answer: Any) -> dict[str, Any]:
    """Проверяет ответ учащегося по утверждению слоя и возвращает ключ, объяснение, разбор ошибки и ссылку на источник."""
    is_correct = False
    error_detail = ""

    if task.task_type in ("single_choice", "case_decision"):
        try:
            ans_idx = int(user_answer)
            is_correct = ans_idx == int(task.correct_answer)
            if not is_correct:
                error_detail = task.error_analysis.get(
                    str(ans_idx),
                    "Выбранный вариант противоречит условиям применимости или физическому механизму из источника.",
                )
        except Exception:
            is_correct = False
            error_detail = "Некорректный формат индекса ответа."

    elif task.task_type == "ordering":
        if isinstance(user_answer, list):
            is_correct = [str(x).strip() for x in user_answer] == [str(x).strip() for x in task.correct_answer]
        if not is_correct:
            error_detail = task.error_analysis.get(
                "order_mismatch",
                "Порядок шагов нарушает последовательность «проверка условий → расчёт → верификация».",
            )

    elif task.task_type == "matching":
        if isinstance(user_answer, dict) and isinstance(task.correct_answer, dict):
            is_correct = all(str(user_answer.get(k, "")).strip() == str(v).strip() for k, v in task.correct_answer.items())
        if not is_correct:
            error_detail = task.error_analysis.get("mismatch", "Одно или несколько сопоставлений неверны.")

    elif task.task_type == "multi_select":
        if isinstance(user_answer, list) and isinstance(task.correct_answer, list):
            try:
                is_correct = sorted(int(x) for x in user_answer) == sorted(int(x) for x in task.correct_answer)
            except Exception:
                is_correct = False
        if not is_correct:
            error_detail = "Необходимо выбрать все верные утверждения без ошибочных вариантов."

    elif task.task_type == "fill_in_blank":
        norm = str(user_answer or "").strip().lower()
        acceptable = [a.lower() for a in (task.blank_acceptable_answers or [str(task.correct_answer or "")])]
        is_correct = bool(norm) and any(norm == a or a in norm for a in acceptable if a)
        if not is_correct:
            error_detail = task.error_analysis.get(
                "wrong_text",
                "Проверьте точность термина или канонического обозначения по глоссарию шага.",
            )

    elif task.task_type == "calculation":
        try:
            if isinstance(user_answer, dict):
                val = float(str(user_answer.get("value", "")).replace(",", "."))
                unit = str(user_answer.get("unit", task.calculation_unit)).strip()
            else:
                val = float(str(user_answer).replace(",", "."))
                unit = task.calculation_unit
            target = float(task.correct_answer)
            unit_ok = (not task.calculation_unit) or (unit == task.calculation_unit)
            is_correct = abs(val - target) <= task.calculation_tolerance and unit_ok
            if not is_correct:
                if not unit_ok:
                    error_detail = f"Неверная единица измерения '{unit}': ожидается '{task.calculation_unit}'."
                else:
                    error_detail = task.error_analysis.get("wrong_value", "Численное значение выходит за пределы допуска.")
        except Exception:
            is_correct = False
            error_detail = "Введите корректное числовое значение."

    result = {
        "task_id": task.task_id,
        "task_type": task.task_type,
        "is_correct": is_correct,
        "answer_key_display": task.answer_key_display,
        "explanation": task.explanation,
        "error_analysis": "" if is_correct else error_detail,
        "source_ref": task.source_ref,
        "pdf_page": task.pdf_page,
        "printed_page": task.printed_page,
        "claim_id": task.claim_id,
    }
    if task.task_type == "case_decision":
        result["case_walkthrough"] = f"{task.case_observation} → {task.case_rule} → {task.case_conclusion}"
    return result


def generate_flashcards_and_summary(
    layer: StudyLayer,
    steps: list[StudyStepScreen],
) -> tuple[list[FlashcardItem], str]:
    """
    Формирует содержательные карточки с режимами «Знаю» / «Повторить»
    и структурированный конспект главы для чтения и печати.
    """
    cards: list[FlashcardItem] = []
    summary_lines: list[str] = [
        f"# Конспект главы: {layer.chapter_title}",
        f"**Книга:** {layer.book_title} ({', '.join(layer.authors)})  ",
        f"**Файл источника:** `{layer.pdf_file}` (SHA-256: `{layer.source_sha256[:16]}...`)  ",
        "",
    ]

    for node, step in zip(layer.nodes, steps):
        p_num = node.quotes_and_pages[0].pdf_page if node.quotes_and_pages else 1
        pr_num = node.quotes_and_pages[0].printed_page if node.quotes_and_pages else str(p_num)
        src_ref = f"PDF стр. {p_num} (печ. стр. {pr_num})"

        summary_lines.append(f"## Шаг {node.order}. {node.step_title}")
        summary_lines.append(f"*Раздел источника:* {node.source_heading} ({src_ref})  ")
        summary_lines.append(f"**Суть:** {node.summary_2_3_sentences}")
        summary_lines.append(f"- **Механизм:** {node.mechanism}")
        summary_lines.append(f"- **Пороговая идея:** {node.threshold_concept}")
        summary_lines.append(f"- **Типичная ошибка:** {node.misconception_to_fix}")
        summary_lines.append(f"- **Иллюстрация:** {step.illustration.title} ({step.illustration.redraw_caption})")
        summary_lines.append("")

        for ct in node.core_terms:
            cards.append(
                FlashcardItem(
                    card_id=f"{step.step_id}_card_{len(cards) + 1:02d}",
                    node_id=node.node_id,
                    step_id=step.step_id,
                    front_question=f"Что означает термин «{ct.term}» ({ct.cis_symbol}) и каков его международный эквивалент?",
                    back_answer=f"{ct.definition}. Международный эквивалент (SPE): {ct.west_symbol} ({ct.west_term}). Единица: {ct.unit or 'б/р'}.",
                    term_or_formula=f"{ct.cis_symbol} ↔ {ct.west_symbol}",
                    pdf_page=ct.first_introduced_pdf_page,
                    printed_page=ct.first_introduced_printed_page,
                    source_ref=f"{layer.book_title}, стр. {ct.first_introduced_pdf_page}",
                )
            )

        cards.append(
            FlashcardItem(
                card_id=f"{step.step_id}_card_{len(cards) + 1:02d}",
                node_id=node.node_id,
                step_id=step.step_id,
                front_question=f"Пороговая идея и типичная ошибка шага «{node.step_title}»",
                back_answer=f"Идея: {node.threshold_concept}\nОшибка, которую нужно избегать: {node.misconception_to_fix}",
                term_or_formula=node.step_title,
                pdf_page=p_num,
                printed_page=pr_num,
                source_ref=f"{layer.book_title}, {src_ref}",
            )
        )

    return cards, "\n".join(summary_lines)
