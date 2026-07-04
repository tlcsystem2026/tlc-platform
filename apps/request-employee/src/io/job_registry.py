from __future__ import annotations
from pathlib import Path
import json
from datetime import datetime, timezone

class JobRegistry:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def contains_success(self, fingerprint: str) -> bool:
        row = self._load().get(fingerprint, {})
        return row.get("status") == "SUCCESS"

    def record(self, fingerprint: str, status: str, **metadata):
        data = self._load()
        data[fingerprint] = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **metadata,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
