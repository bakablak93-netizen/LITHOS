"""
Загрузчик заменяемого предметного пакета Т3 (вне ядра конвейера).
Позволяет сменить глоссарий, легенду цветов, заблуждения, словарь произношений и правила маршрутизации
подстановкой другого JSON-файла в data/domain_packages/.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DOMAIN_PACKAGE_PATH = PROJECT_ROOT / "data" / "domain_packages" / "oil_gas_ru.json"

_CACHE: dict[str, dict[str, Any]] = {}


def load_domain_package(package_path: Path | str | None = None) -> dict[str, Any]:
    """Загружает и кеширует предметный пакет JSON с контрольной суммой SHA-256."""
    path = Path(package_path) if package_path else DEFAULT_DOMAIN_PACKAGE_PATH
    key = str(path.resolve())
    if key in _CACHE:
        return _CACHE[key]
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    data["_source_path"] = str(path.relative_to(PROJECT_ROOT)) if path.is_relative_to(PROJECT_ROOT) else str(path)
    data["_sha256"] = hashlib.sha256(raw).hexdigest()
    _CACHE[key] = data
    return data


def get_domain_legend(package_path: Path | str | None = None) -> list[dict[str, str]]:
    pkg = load_domain_package(package_path)
    return list(pkg.get("unified_visual_legend", []))


def get_domain_pronunciation_dict(package_path: Path | str | None = None) -> dict[str, str]:
    pkg = load_domain_package(package_path)
    return dict(pkg.get("pronunciation_dictionary", {}))


def get_domain_difficulty_codes(package_path: Path | str | None = None) -> dict[str, str]:
    pkg = load_domain_package(package_path)
    return dict(pkg.get("routing_rules", {}).get("difficulty_codes", {}))
