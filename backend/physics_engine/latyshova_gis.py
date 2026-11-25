"""
Детерминированный петрофизический расчёт по М.Г. Латышовой (1991):
«Практическое руководство по интерпретации диаграмм ГИС».

Реализованные уравнения:
- Eq. (2)-(3): P_п = a_m / K_п^m,  rho_вп = P_п * rho_в
- Eq. (4):     P_п.пресн = Pi * P_п,  rho_зп = Pi * P_п * rho_ф (поверхностная проводимость)
- Eq. (5)-(6): k_п_общ = k_пмз*(1 - k_пвт) + k_пвт,  P_пт = P_пбл / (P_пбл * k_пт * A + 1)
- Eq. (10):    P_н = a_n / K_в^n,  K_нг = 1 - K_в,  rho_п = P_н * P_п * rho_в
- SP (Глава II, §8): delta_E_ст = -k_СП * lg(rho_ф / rho_в), alpha_СП = delta_E / delta_E_max
"""

from __future__ import annotations

from typing import Any
import numpy as np


def _smooth_step(x: np.ndarray, edge: float, width: float = 0.8) -> np.ndarray:
    """Гладкий переход границы пласта (учёт конечной разрешающей способности зонда)."""
    t = np.clip((x - edge) / max(width, 1e-6) + 0.5, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _layer_window(z: np.ndarray, top: float, bottom: float, width: float = 0.9) -> np.ndarray:
    return _smooth_step(z, top, width) * (1.0 - _smooth_step(z, bottom, width))


def evaluate_archie_curve(
    rho_v: float = 0.05,
    a_m: float = 0.81,
    m: float = 2.0,
    a_n: float = 1.0,
    n: float = 2.0,
    k_p_min: float = 0.04,
    k_p_max: float = 0.32,
    num_points: int = 40,
) -> dict[str, Any]:
    """
    Генерирует семейство кривых пористости и насыщения (аналог рис. 4 и рис. 69 у Латышовой):
    - P_п(K_п) = a_m / K_п^m
    - rho_вп(K_п) = P_п * rho_в  (100% водоносный пласт)
    - rho_п_oil(K_п) при K_в = 0.22 (предельно нефтенасыщенный коллектор)
    - rho_п_crit(K_п) при K_в* = 0.45 (критическая граница нефть / нефть+вода)
    """
    kp = np.linspace(k_p_min, k_p_max, num_points)
    p_p = a_m / np.power(kp, m)
    rho_vp = p_p * rho_v
    rho_oil = (a_n / np.power(0.22, n)) * rho_vp
    rho_crit = (a_n / np.power(0.45, n)) * rho_vp

    return {
        "k_p_pct": np.round(kp * 100.0, 2).tolist(),
        "p_p": np.round(p_p, 2).tolist(),
        "rho_vp_ohmm": np.round(rho_vp, 3).tolist(),
        "rho_oil_ohmm": np.round(rho_oil, 3).tolist(),
        "rho_crit_ohmm": np.round(rho_crit, 3).tolist(),
        "params": {"rho_v": rho_v, "a_m": a_m, "m": m, "a_n": a_n, "n": n},
    }


def simulate_well_log(
    depth_start_m: float = 2400.0,
    depth_end_m: float = 2450.0,
    step_m: float = 0.5,
    rho_v: float = 0.05,
    rho_f: float = 1.20,
    a_m: float = 0.81,
    m: float = 1.95,
    a_n: float = 1.0,
    n: float = 2.0,
    temp_c: float = 65.0,
    reservoir_mode: str = "clastic",
    k_pt: float = 0.015,
    fracture_A: float = 2.0 / 3.0,
    vnk_depth_m: float = 2425.0,
) -> dict[str, Any]:
    """
    Рассчитывает синтетический каротаж скважины (КС, МБК, ПС, K_п, P_п, P_н, K_в, K_нг)
    на интервале глубин с четырьмя характерными пластами:
      1) 2400-2409 м: Глинистая покрышка (неколлектор, высокая глинистость)
      2) 2409-2416 м: Плотный карбонат/алевролит (низкая пористость, нет проникновения)
      3) 2416-2433 м: Проницаемый продуктивный коллектор (выше ВНК = нефть, ниже = вода)
      4) 2433-2441 м: Глинистая перемычка (неколлектор)
      5) 2441-2450 м: Водоносный песчаник (чистая вода, понижающее проникновение при rho_f > rho_v)
    """
    z = np.arange(depth_start_m, depth_end_m + 1e-6, step_m)

    # Весовые окна пластов
    w_shale_top = 1.0 - _smooth_step(z, 2409.0, 1.0)
    w_tight = _layer_window(z, 2409.0, 2416.0, 0.8)
    w_res_main = _layer_window(z, 2416.0, 2433.0, 0.9)
    w_shale_mid = _layer_window(z, 2433.0, 2441.0, 0.9)
    w_res_water = _smooth_step(z, 2441.0, 0.9)

    # Пористость K_п (в д.е.) и относительная глинистость C_гл
    k_p = (
        0.045 * w_shale_top
        + 0.055 * w_tight
        + (0.22 + 0.018 * np.sin((z - 2416.0) * 0.6)) * w_res_main
        + 0.040 * w_shale_mid
        + (0.20 + 0.015 * np.cos((z - 2441.0) * 0.5)) * w_res_water
    )
    k_p = np.clip(k_p, 0.03, 0.32)

    c_gl = np.clip(
        0.72 * w_shale_top + 0.14 * w_tight + 0.07 * w_res_main + 0.78 * w_shale_mid + 0.09 * w_res_water,
        0.02,
        0.85,
    )

    # Температурная поправка коэффициента ПС (Глава II, §8: k_СП,t = k_СП,18 * (273 + t)/291)
    k_sp_t = 69.6 * (273.0 + temp_c) / 291.0
    delta_e_max = -k_sp_t * np.log10(max(rho_f, 1e-3) / max(rho_v, 1e-3))

    # Относительная амплитуда ПС: alpha_СП ~ (1 - C_гл / C_гл_max) в коллекторе, ~0.05 в глинах
    alpha_sp = np.clip(
        0.06 * w_shale_top
        + 0.18 * w_tight
        + 0.88 * w_res_main
        + 0.05 * w_shale_mid
        + 0.84 * w_res_water,
        0.0,
        1.0,
    )
    sp_mv = alpha_sp * delta_e_max  # отрицательная аномалия против коллекторов при rho_f > rho_v

    # Параметр пористости P_п (уравнение 3, для трещинного карбоната — уравнение 6 из §1)
    p_p_matrix = a_m / np.power(k_p, m)
    if reservoir_mode == "fractured_carbonate":
        # Eq. (6): P_пт = P_пбл / (P_пбл * k_пт * A + 1) в зоне коллектора
        is_res_zone = (w_res_main + w_res_water) > 0.4
        p_p = np.where(
            is_res_zone,
            p_p_matrix / (p_p_matrix * k_pt * fracture_A + 1.0),
            p_p_matrix,
        )
    else:
        p_p = p_p_matrix

    # Водонасыщенное сопротивление пласта rho_вп = P_п * rho_в (уравнение 2)
    rho_vp = p_p * rho_v

    # Водонасыщенность K_в (переходная зона ВНК около vnk_depth_m +/- 1.8 м)
    trans_vnk = _smooth_step(z, vnk_depth_m, width=3.2)
    k_v_main = 0.22 + (0.98 - 0.22) * trans_vnk
    k_v = np.clip(
        0.98 * w_shale_top
        + 0.95 * w_tight
        + k_v_main * w_res_main
        + 0.99 * w_shale_mid
        + 0.98 * w_res_water,
        0.18,
        1.0,
    )
    k_ng = 1.0 - k_v

    # Параметр насыщения P_н = a_n / K_в^n и истинное удельное сопротивление пласта rho_п
    p_n = a_n / np.power(k_v, n)

    # В глинах учитываем низкое собственное сопротивление глинистой породы (~3.5-5 Ом·м)
    rho_shale = 4.2
    rho_clean = p_n * rho_vp
    shale_weight = np.clip(w_shale_top + w_shale_mid, 0.0, 1.0)
    rho_bk = (1.0 - shale_weight) * rho_clean + shale_weight * rho_shale

    # В зоне проникновения: коэффициент поверхностной проводимости Pi = 1 - 0.35 * C_гл (Eq. 4, пример 10)
    # При rho_f > rho_v:
    #   - в водоносном коллекторе: повышающее проникновение (rho_зп > rho_вп)
    #   - в нефтеносном коллекторе: понижающее проникновение (rho_зп < rho_п)
    pi_surf = np.clip(1.0 - 0.55 * c_gl, 0.45, 1.0)
    k_v_flushed = np.where(k_ng > 0.25, 0.75, 0.96)  # остаточная нефть k_но ~ 0.25
    rho_zp = (a_n / np.power(k_v_flushed, n)) * pi_surf * p_p * rho_f
    rho_mbk = (1.0 - shale_weight) * (0.85 * rho_zp + 0.15 * rho_bk) + shale_weight * (rho_shale * 0.9)

    # Критерии выделения коллектора (§20): alpha_СП* = 0.45, K_п* = 0.12, P_н* = 2.5
    alpha_cutoff = 0.45
    kp_cutoff = 0.12
    pn_cutoff = 2.5
    is_reservoir = (alpha_sp >= alpha_cutoff) & (k_p >= kp_cutoff)
    mudcake_cm = np.where(is_reservoir, 0.8 + 0.25 * alpha_sp, 0.0)

    saturation_class = []
    for res, pn_val, kv_val in zip(is_reservoir, p_n, k_v):
        if not res:
            saturation_class.append("non_reservoir")
        elif pn_val >= 6.0 and kv_val <= 0.40:
            saturation_class.append("oil")
        elif pn_val >= pn_cutoff:
            saturation_class.append("transition_oil_water")
        else:
            saturation_class.append("water")

    layers_summary = [
        {"name": "Глинистая покрышка", "top_m": 2400.0, "bottom_m": 2409.0, "type": "shale"},
        {"name": "Плотный карбонатный пропласток", "top_m": 2409.0, "bottom_m": 2416.0, "type": "tight"},
        {"name": "Продуктивный коллектор (нефть + ВНК)", "top_m": 2416.0, "bottom_m": 2433.0, "type": "reservoir_oil"},
        {"name": "Глинистая перемычка", "top_m": 2433.0, "bottom_m": 2441.0, "type": "shale"},
        {"name": "Водоносный песчаник", "top_m": 2441.0, "bottom_m": 2450.0, "type": "reservoir_water"},
    ]

    net_pay_m = float(np.sum((np.array(saturation_class) == "oil")) * step_m)

    return {
        "module": "latyshova_gis",
        "reservoir_mode": reservoir_mode,
        "parameters": {
            "rho_v_ohmm": rho_v,
            "rho_f_ohmm": rho_f,
            "a_m": a_m,
            "m": m,
            "a_n": a_n,
            "n": n,
            "temp_c": temp_c,
            "vnk_depth_m": vnk_depth_m,
            "alpha_sp_cutoff": alpha_cutoff,
            "k_p_cutoff": kp_cutoff,
            "p_n_cutoff": pn_cutoff,
            "delta_e_max_mv": round(float(delta_e_max), 2),
        },
        "summary": {
            "net_pay_oil_m": round(net_pay_m, 2),
            "total_reservoir_m": round(float(np.sum(is_reservoir) * step_m), 2),
            "max_rho_bk_ohmm": round(float(np.max(rho_bk)), 2),
            "max_p_n": round(float(np.max(p_n)), 2),
        },
        "layers": layers_summary,
        "logs": {
            "depth_m": np.round(z, 2).tolist(),
            "k_p_pct": np.round(k_p * 100.0, 2).tolist(),
            "c_gl_pct": np.round(c_gl * 100.0, 2).tolist(),
            "alpha_sp": np.round(alpha_sp, 3).tolist(),
            "sp_mv": np.round(sp_mv, 2).tolist(),
            "p_p": np.round(p_p, 2).tolist(),
            "rho_vp_ohmm": np.round(rho_vp, 3).tolist(),
            "rho_bk_ohmm": np.round(rho_bk, 2).tolist(),
            "rho_mbk_ohmm": np.round(rho_mbk, 2).tolist(),
            "p_n": np.round(p_n, 2).tolist(),
            "k_v": np.round(k_v, 3).tolist(),
            "k_ng": np.round(k_ng, 3).tolist(),
            "mudcake_cm": np.round(mudcake_cm, 2).tolist(),
            "is_reservoir": [bool(v) for v in is_reservoir],
            "saturation_class": saturation_class,
        },
        "archie_family": evaluate_archie_curve(rho_v=rho_v, a_m=a_m, m=m, a_n=a_n, n=n),
    }
