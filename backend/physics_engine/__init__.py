"""Physics & math simulation engines grounded in textbook equations."""

from .latyshova_gis import simulate_well_log, evaluate_archie_curve
from .basniev_hydro import simulate_dupuit_flow, simulate_psss_transient

__all__ = [
    "simulate_well_log",
    "evaluate_archie_curve",
    "simulate_dupuit_flow",
    "simulate_psss_transient",
]
