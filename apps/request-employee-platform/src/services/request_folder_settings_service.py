from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

DEFAULTS = {
    "request_root_path": r"Y:\TLC-BOS\Data\Request",
    "request_incoming_dir": "Incoming",
    "request_processing_dir": "Processing",
    "request_completed_dir": "Completed",
    "request_error_dir": "Error",
    "request_archive_dir": "Archive",
    "request_month_folder_format": "YYYYMM",
}
PARAMETER_KEYS = tuple(DEFAULTS)
MONTH_PATTERN = re.compile(r"^\d{6}$")


def _config_root() -> Path:
    configured = os.environ.get("TLC_CONFIG_ROOT")
    if configured:
        return Path(configured)
    app_root = Path(__file__).resolve().parents[2]
    repository_root = app_root.parents[1]
    return repository_root / "config"


def _paths_file() -> Path:
    return _config_root() / "paths.yaml"


def _read_document() -> dict[str, Any]:
    path = _paths_file()
    if not path.exists():
        return {}
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(document, dict):
        raise RuntimeError("config/paths.yaml must contain a YAML mapping")
    return document


def _atomic_write(document: dict[str, Any]) -> None:
    path = _paths_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), prefix="paths.", suffix=".tmp", delete=False
    ) as handle:
        handle.write(content)
        temp_name = handle.name
    Path(temp_name).replace(path)


def get_request_folder_settings() -> dict[str, str]:
    document = _read_document()
    paths = document.get("paths")
    if not isinstance(paths, dict):
        paths = {}
    settings = dict(DEFAULTS)
    for key in PARAMETER_KEYS:
        value = paths.get(key)
        if value is not None and str(value).strip():
            settings[key] = str(value).strip()
    return settings


def _validate_dir_name(value: str, key: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    if any(part in value for part in ("/", "\\", "..")):
        raise ValueError(f"{key} must be a directory name, not a path")
    return value


def validate_settings(payload: dict[str, Any]) -> dict[str, str]:
    root = str(payload.get("request_root_path", "")).strip()
    if not root:
        raise ValueError("request_root_path is required")
    settings = {
        "request_root_path": root,
        "request_incoming_dir": _validate_dir_name(payload.get("request_incoming_dir", ""), "request_incoming_dir"),
        "request_processing_dir": _validate_dir_name(payload.get("request_processing_dir", ""), "request_processing_dir"),
        "request_completed_dir": _validate_dir_name(payload.get("request_completed_dir", ""), "request_completed_dir"),
        "request_error_dir": _validate_dir_name(payload.get("request_error_dir", ""), "request_error_dir"),
        "request_archive_dir": _validate_dir_name(payload.get("request_archive_dir", ""), "request_archive_dir"),
        "request_month_folder_format": str(payload.get("request_month_folder_format", "")).strip().upper(),
    }
    if settings["request_month_folder_format"] != "YYYYMM":
        raise ValueError("request_month_folder_format must be YYYYMM")
    names = [
        settings["request_incoming_dir"], settings["request_processing_dir"],
        settings["request_completed_dir"], settings["request_error_dir"],
        settings["request_archive_dir"],
    ]
    if len(set(name.casefold() for name in names)) != len(names):
        raise ValueError("request subdirectory names must be unique")
    return settings


def save_request_folder_settings(payload: dict[str, Any]) -> dict[str, str]:
    settings = validate_settings(payload)
    document = _read_document()
    paths = document.setdefault("paths", {})
    if not isinstance(paths, dict):
        raise RuntimeError("paths in config/paths.yaml must be a mapping")
    paths.update(settings)
    _atomic_write(document)
    ensure_standard_directories(settings)
    return settings


def standard_directories(settings: dict[str, str] | None = None) -> dict[str, Path]:
    settings = settings or get_request_folder_settings()
    root = Path(settings["request_root_path"])
    return {
        "root": root,
        "incoming": root / settings["request_incoming_dir"],
        "processing": root / settings["request_processing_dir"],
        "completed": root / settings["request_completed_dir"],
        "error": root / settings["request_error_dir"],
        "archive": root / settings["request_archive_dir"],
    }


def ensure_standard_directories(settings: dict[str, str] | None = None) -> dict[str, Path]:
    directories = standard_directories(settings)
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    return directories


def validate_business_month(business_month: str) -> str:
    value = str(business_month or "").strip()
    if not MONTH_PATTERN.fullmatch(value):
        raise ValueError("business_month must use YYYYMM")
    month = int(value[4:6])
    if month < 1 or month > 12:
        raise ValueError("business_month month must be between 01 and 12")
    return value


def ensure_month_directories(business_month: str) -> dict[str, str]:
    month = validate_business_month(business_month)
    directories = ensure_standard_directories()
    result: dict[str, str] = {}
    for name in ("incoming", "processing", "completed", "error", "archive"):
        path = directories[name] / month
        path.mkdir(parents=True, exist_ok=True)
        result[name] = str(path)
    return result


def check_request_folder_settings() -> dict[str, Any]:
    settings = get_request_folder_settings()
    directories = standard_directories(settings)
    checks = []
    for name, path in directories.items():
        exists = path.exists()
        checks.append({
            "name": name,
            "path": str(path),
            "exists": exists,
            "is_directory": path.is_dir() if exists else False,
            "readable": os.access(path, os.R_OK) if exists else False,
            "writable": os.access(path, os.W_OK) if exists else False,
        })
    incoming = directories["incoming"]
    valid_months, invalid_months = [], []
    if incoming.is_dir():
        for child in sorted(incoming.iterdir(), key=lambda item: item.name):
            if not child.is_dir():
                continue
            try:
                valid_months.append(validate_business_month(child.name))
            except ValueError:
                invalid_months.append(child.name)
    return {
        "settings": settings,
        "checks": checks,
        "valid_month_folders": valid_months,
        "invalid_month_folders": invalid_months,
        "all_standard_directories_ready": all(
            item["exists"] and item["is_directory"] and item["readable"] and item["writable"]
            for item in checks
        ),
    }
