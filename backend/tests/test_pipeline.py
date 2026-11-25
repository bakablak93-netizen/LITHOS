from __future__ import annotations

from pathlib import Path

from backend.agents.parser_agent import build_course_manifest_sync, discover_books, load_passport
from backend.agents.qa_verifier import verify_course_manifest
from backend.physics_engine import simulate_dupuit_flow, simulate_psss_transient, simulate_well_log

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def test_discover_all_six_books() -> None:
    books = discover_books(DATA_DIR)
    files = {b.book_file for b in books}
    assert "train_latyshova.md" in files
    assert "train_basniev.md" in files
    assert "ctrl_vendelshtein.md" in files
    assert "ctrl_barenblatt.md" in files
    assert "ctrl_baraboshkin_b.md" in files
    assert all(b.passport_file is not None for b in books)


def test_latyshova_physics_invariants() -> None:
    res = simulate_well_log(rho_v=0.05, rho_f=1.2, m=1.95, n=2.0, vnk_depth_m=2425.0)
    assert res["summary"]["net_pay_oil_m"] > 0
    assert res["summary"]["max_rho_bk_ohmm"] > 10.0
    assert len(res["logs"]["depth_m"]) == len(res["logs"]["rho_bk_ohmm"])


def test_basniev_physics_invariants() -> None:
    dup = simulate_dupuit_flow(k_md=120.0, mu_cp=1.8, h_m=14.0, p_k_mpa=24.0, p_c_mpa=16.5)
    assert dup["metrics"]["q_m3_day"] > 0
    tr = simulate_psss_transient(k_md=120.0, mu_cp=1.8, h_m=14.0, times_hours=[1.0, 6.0])
    assert tr["snapshots"][1]["r_front_m"] > tr["snapshots"][0]["r_front_m"]


def test_qa_verifier_blocks_fabricated_nomogram_numbers() -> None:
    manifest, _, _, passport = build_course_manifest_sync(
        data_dir=DATA_DIR,
        book_file="train_latyshova.md",
        chapter_index=0,
    )
    # Имитируем галлюцинацию с неоцифрованной палетки
    manifest.scenes[3].narration = "По палетке снимаем 42.5 Ом*м."
    report = verify_course_manifest(manifest, passport)
    assert report.passed is True
    assert any(c.status == "FIXED" and c.category == "nomogram_guard" for c in report.checks)


def test_universal_control_book_build() -> None:
    manifest, _, _, _ = build_course_manifest_sync(
        data_dir=DATA_DIR,
        book_file="ctrl_vendelshtein.md",
        chapter_index=1,
    )
    assert manifest.module_type == "generic_chapter"
    assert len(manifest.scenes) >= 3
