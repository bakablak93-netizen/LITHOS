"""
Детерминированная модель подземной гидромеханики по К.С. Басниеву, Н.М. Дмитриеву, Г.Д. Розенбергу (2005):
«Нефтегазовая гидромеханика».

Реализованные уравнения:
- Глава XVIII: Закон Дарси w = -(k/mu) dp/dr, число Рейнольдса в пористой среде, параметр Дарси
- Глава XX, §3: Формула Дюпюи (20.19): Q = (2*pi*k*h*(p_к - p_с)) / (mu * ln(R_к / r_с))
  Логарифмическая воронка депрессии (20.20): p(r) = p_с + ((p_к - p_с)/ln(R_к/r_с)) * ln(r/r_с)
  Скорость фильтрации (20.21): w(r) = Q / (2*pi*h*r)
  Коэффициент продуктивности (20.22): C = 2*pi*k*h / (mu * ln(R_к/r_с))
- Глава XXIII: Коэффициент пьезопроводности kappa = k / (mu * beta*), beta* = m*beta_ж + beta_с
  Точное решение уравнения пьезопроводности (Тейса): p(r,t) = p_к + (Q*mu/(4*pi*k*h))*Ei(-r^2/(4*kappa*t))
- Глава XXIV, §1: Метод последовательной смены стационарных состояний (ПССС — метод И.А. Чарного):
  Для плоскорадиального потока: R(t) = sqrt(r_c^2 + 4*kappa*t), p(r,t) = p_к - (Q*mu/(2*pi*k*h))*ln(R(t)/r)
  Для прямолинейно-параллельной галереи (Q=const): l(t) = sqrt(2*kappa*t)
"""

from __future__ import annotations

from typing import Any
import numpy as np
from scipy.special import expi


def simulate_dupuit_flow(
    k_md: float = 120.0,
    mu_cp: float = 1.8,
    h_m: float = 14.0,
    p_k_mpa: float = 24.0,
    p_c_mpa: float = 16.5,
    r_c_m: float = 0.1,
    r_k_m: float = 250.0,
    porosity_m: float = 0.18,
    num_r: int = 80,
) -> dict[str, Any]:
    """
    Рассчитывает установившийся плоскорадиальный приток к скважине по формуле Дюпюи (Глава XX, §3).
    Перевод единиц:
      1 мД = 1e-15 м², 1 мПа·с (сП) = 1e-3 Па·с, 1 МПа = 1e6 Па, 1 сут = 86400 с.
    """
    k_si = k_md * 1e-15
    mu_si = mu_cp * 1e-3
    dp_mpa = max(p_k_mpa - p_c_mpa, 0.05)
    dp_pa = dp_mpa * 1e6

    ln_ratio = float(np.log(r_k_m / max(r_c_m, 1e-3)))
    q_m3_s = (2.0 * np.pi * k_si * h_m * dp_pa) / (mu_si * ln_ratio)
    q_m3_day = q_m3_s * 86400.0
    productivity_c_m3_day_mpa = q_m3_day / dp_mpa

    # Логарифмическая радиальная сетка для точного разрешения призабойной зоны
    r_grid = np.geomspace(r_c_m, r_k_m, num_r)
    p_profile_mpa = p_c_mpa + dp_mpa * (np.log(r_grid / r_c_m) / ln_ratio)

    # Скорость фильтрации w(r) (в м/сут и мм/с) и истинная средняя скорость v = w / m
    w_m_s = q_m3_s / (2.0 * np.pi * h_m * r_grid)
    w_mm_s = w_m_s * 1000.0
    v_mm_s = w_mm_s / max(porosity_m, 0.01)

    # Индикаторная линия Q(dp) при нескольких депрессиях
    dp_sweep = np.linspace(0.0, 12.0, 13)
    q_sweep = productivity_c_m3_day_mpa * dp_sweep

    return {
        "formula_ref": "Басниев и др. (2005), Глава XX, §3, формулы (20.19)-(20.22)",
        "inputs": {
            "k_md": k_md,
            "mu_cp": mu_cp,
            "h_m": h_m,
            "p_k_mpa": p_k_mpa,
            "p_c_mpa": p_c_mpa,
            "delta_p_mpa": round(dp_mpa, 3),
            "r_c_m": r_c_m,
            "r_k_m": r_k_m,
            "porosity_m": porosity_m,
        },
        "metrics": {
            "q_m3_s": round(float(q_m3_s), 6),
            "q_m3_day": round(float(q_m3_day), 2),
            "productivity_index_m3_day_mpa": round(float(productivity_c_m3_day_mpa), 2),
            "w_wellbore_mm_s": round(float(w_mm_s[0]), 4),
            "w_contour_mm_s": round(float(w_mm_s[-1]), 6),
        },
        "radial_profile": {
            "r_m": np.round(r_grid, 4).tolist(),
            "p_mpa": np.round(p_profile_mpa, 4).tolist(),
            "w_mm_s": np.round(w_mm_s, 5).tolist(),
            "v_mm_s": np.round(v_mm_s, 5).tolist(),
        },
        "indicator_line": {
            "delta_p_mpa": np.round(dp_sweep, 2).tolist(),
            "q_m3_day": np.round(q_sweep, 2).tolist(),
        },
    }


def simulate_psss_transient(
    k_md: float = 120.0,
    mu_cp: float = 1.8,
    h_m: float = 14.0,
    porosity_m: float = 0.18,
    beta_liq_pa: float = 1.2e-9,
    beta_rock_pa: float = 1.0e-10,
    p_k_mpa: float = 24.0,
    q_m3_day: float = 180.0,
    r_c_m: float = 0.1,
    r_max_m: float = 300.0,
    times_hours: list[float] | None = None,
    num_r: int = 80,
) -> dict[str, Any]:
    """
    Неустановившаяся фильтрация упругой жидкости в упругом пласте (Главы XXIII-XXIV):
    Сравнение метода последовательной смены стационарных состояний (ПССС)
    и точного решения уравнения пьезопроводности через Ei(-r^2 / (4*kappa*t)).
    """
    if times_hours is None:
        times_hours = [0.25, 1.5, 6.0, 24.0]

    k_si = k_md * 1e-15
    mu_si = mu_cp * 1e-3
    q_m3_s = q_m3_day / 86400.0

    # Коэффициент упругоемкости пласта beta* = m*beta_ж + beta_с и пьезопроводность kappa = k/(mu*beta*)
    beta_star = porosity_m * beta_liq_pa + beta_rock_pa
    kappa = k_si / (mu_si * beta_star)  # м²/с

    r_grid = np.geomspace(r_c_m, r_max_m, num_r)
    coef_mpa = (q_m3_s * mu_si) / (2.0 * np.pi * k_si * h_m) * 1e-6  # в МПа

    snapshots = []
    for t_hr in times_hours:
        t_s = max(t_hr * 3600.0, 1.0)

        # ПССС: радиус возмущённой области R(t) = sqrt(r_c^2 + 4*kappa*t) (Глава XXIV, §1)
        r_front = float(np.sqrt(r_c_m**2 + 4.0 * kappa * t_s))
        r_front_eff = max(r_front, r_c_m * 1.05)

        p_psss = np.where(
            r_grid <= r_front_eff,
            p_k_mpa - coef_mpa * np.log(r_front_eff / r_grid),
            p_k_mpa,
        )

        # Точное решение (Глава XXIII, §5): p(r,t) = p_к + (Q*mu/(4*pi*k*h)) * Ei(-r^2/(4*kappa*t))
        arg = -(r_grid**2) / (4.0 * kappa * t_s)
        p_theis = p_k_mpa + 0.5 * coef_mpa * expi(arg)

        # Прямолинейно-параллельная галерея (Q=const): l(t) = sqrt(2*kappa*t)
        l_gallery = float(np.sqrt(2.0 * kappa * t_s))

        snapshots.append(
            {
                "time_hours": t_hr,
                "r_front_m": round(r_front, 2),
                "l_gallery_m": round(l_gallery, 2),
                "p_wellbore_psss_mpa": round(float(p_psss[0]), 3),
                "p_wellbore_exact_mpa": round(float(p_theis[0]), 3),
                "p_psss_mpa": np.round(p_psss, 4).tolist(),
                "p_exact_mpa": np.round(p_theis, 4).tolist(),
            }
        )

    # Траектория фронта R(t)
    t_hist_hr = np.linspace(0.0, max(times_hours), 40)
    r_hist_m = np.sqrt(r_c_m**2 + 4.0 * kappa * (t_hist_hr * 3600.0))

    return {
        "formula_ref": "Басниев и др. (2005), Главы XXIII-XXIV, метод ПССС и решение через Ei",
        "parameters": {
            "k_md": k_md,
            "mu_cp": mu_cp,
            "h_m": h_m,
            "porosity_m": porosity_m,
            "beta_star_pa_inv": beta_star,
            "kappa_m2_s": round(float(kappa), 4),
            "p_k_mpa": p_k_mpa,
            "q_m3_day": q_m3_day,
        },
        "r_m": np.round(r_grid, 4).tolist(),
        "snapshots": snapshots,
        "front_trajectory": {
            "time_hours": np.round(t_hist_hr, 2).tolist(),
            "r_front_m": np.round(r_hist_m, 2).tolist(),
        },
    }
