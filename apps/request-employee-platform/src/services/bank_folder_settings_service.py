
from __future__ import annotations
import os, re, tempfile
from pathlib import Path
from typing import Any
import yaml

DEFAULTS = {
    "bank_root_path": r"Y:\TLC-BOS\Data\Bank",
    "bank_incoming_dir": "Incoming",
    "bank_processing_dir": "Processing",
    "bank_completed_dir": "Completed",
    "bank_error_dir": "Error",
    "bank_archive_dir": "Archive",
}
PARAMETER_KEYS = tuple(DEFAULTS)
CODE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

def _config_root() -> Path:
    configured = os.environ.get("TLC_CONFIG_ROOT")
    if configured:
        return Path(configured)
    app_root = Path(__file__).resolve().parents[2]
    return app_root.parents[1] / "config"

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
        "w", encoding="utf-8", dir=str(path.parent),
        prefix="paths.", suffix=".tmp", delete=False
    ) as handle:
        handle.write(content)
        temp_name = handle.name
    Path(temp_name).replace(path)

def get_bank_folder_settings() -> dict[str, str]:
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

def _dir_name(value: Any, key: str) -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"{key} is required")
    if any(part in value for part in ("/", "\\", "..")):
        raise ValueError(f"{key} must be a directory name, not a path")
    return value

def validate_settings(payload: dict[str, Any]) -> dict[str, str]:
    root = str(payload.get("bank_root_path", "")).strip()
    if not root:
        raise ValueError("bank_root_path is required")
    settings = {
        "bank_root_path": root,
        "bank_incoming_dir": _dir_name(payload.get("bank_incoming_dir"), "bank_incoming_dir"),
        "bank_processing_dir": _dir_name(payload.get("bank_processing_dir"), "bank_processing_dir"),
        "bank_completed_dir": _dir_name(payload.get("bank_completed_dir"), "bank_completed_dir"),
        "bank_error_dir": _dir_name(payload.get("bank_error_dir"), "bank_error_dir"),
        "bank_archive_dir": _dir_name(payload.get("bank_archive_dir"), "bank_archive_dir"),
    }
    names = [settings[k] for k in PARAMETER_KEYS if k != "bank_root_path"]
    if len(set(x.casefold() for x in names)) != len(names):
        raise ValueError("bank subdirectory names must be unique")
    return settings

def standard_directories(settings: dict[str, str] | None = None) -> dict[str, Path]:
    settings = settings or get_bank_folder_settings()
    root = Path(settings["bank_root_path"])
    return {
        "root": root,
        "incoming": root / settings["bank_incoming_dir"],
        "processing": root / settings["bank_processing_dir"],
        "completed": root / settings["bank_completed_dir"],
        "error": root / settings["bank_error_dir"],
        "archive": root / settings["bank_archive_dir"],
    }

def ensure_standard_directories(settings: dict[str, str] | None = None) -> dict[str, Path]:
    directories = standard_directories(settings)
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    return directories

def validate_bank_account_code(value: str) -> str:
    value = str(value or "").strip()
    if not CODE_PATTERN.fullmatch(value):
        raise ValueError("bank_account_code must use lowercase letters, numbers, '_' or '-'")
    return value

def ensure_bank_account_directories(bank_account_code: str) -> dict[str, str]:
    code = validate_bank_account_code(bank_account_code)
    directories = ensure_standard_directories()
    result = {}
    for name in ("incoming", "processing", "completed", "error", "archive"):
        path = directories[name] / code
        path.mkdir(parents=True, exist_ok=True)
        result[name] = str(path)
    return result

def save_bank_folder_settings(payload: dict[str, Any]) -> dict[str, str]:
    settings = validate_settings(payload)
    document = _read_document()
    paths = document.setdefault("paths", {})
    if not isinstance(paths, dict):
        raise RuntimeError("paths in config/paths.yaml must be a mapping")
    paths.update(settings)
    _atomic_write(document)
    ensure_standard_directories(settings)
    return settings

def check_bank_folder_settings() -> dict[str, Any]:
    settings = get_bank_folder_settings()
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
    codes, invalid = set(), []
    for name in ("incoming", "processing", "completed", "error", "archive"):
        base = directories[name]
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir(), key=lambda item: item.name):
            if not child.is_dir():
                continue
            try:
                codes.add(validate_bank_account_code(child.name))
            except ValueError:
                invalid.append(f"{name}/{child.name}")
    return {
        "settings": settings,
        "checks": checks,
        "bank_account_codes": sorted(codes),
        "invalid_bank_account_folders": sorted(invalid),
        "all_standard_directories_ready": all(
            item["exists"] and item["is_directory"] and item["readable"] and item["writable"]
            for item in checks
        ),
    }
