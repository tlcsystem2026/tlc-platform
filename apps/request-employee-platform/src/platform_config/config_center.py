from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


@dataclass(frozen=True)
class PlatformConfig:
    root: Path
    data: dict[str, Any]

    def get(self, path: str, default: Any = None) -> Any:
        current: Any = self.data
        for part in path.split("."):
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    @property
    def environment(self) -> str:
        return str(self.get("environment.current", self.get("app.environment", "test")))

    @property
    def repository_root(self) -> str:
        return str(self.get("paths.repository_root", ""))

    @property
    def export_root(self) -> str:
        return str(self.get("paths.export_root", ""))

    @property
    def temp_root(self) -> str:
        return str(self.get("paths.temp_root", ""))


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if yaml is None:
        raise RuntimeError("PyYAML is required for Platform Configuration Center")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Config file must contain a YAML mapping: {path}")
    return data


def load_platform_config(config_root: str | Path | None = None) -> PlatformConfig:
    root = Path(config_root or os.environ.get("TLC_CONFIG_ROOT") or Path.cwd().parents[1] / "config")
    files = [
        "app.yaml",
        "environment.yaml",
        "paths.yaml",
        "database.yaml",
        "export.yaml",
        "logging.yaml",
    ]
    merged: dict[str, Any] = {}
    for name in files:
        merged = _merge(merged, _read_yaml(root / name))
    return PlatformConfig(root=root, data=merged)


_cached: PlatformConfig | None = None


def get_config(config_root: str | Path | None = None, reload: bool = False) -> PlatformConfig:
    global _cached
    if reload or _cached is None:
        _cached = load_platform_config(config_root)
    return _cached
