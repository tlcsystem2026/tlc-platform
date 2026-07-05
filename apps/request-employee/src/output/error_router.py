from __future__ import annotations
from pathlib import Path
import shutil
import json
from datetime import datetime

def route_error_pair(pdf_path, excel_path, error_root, reason: dict) -> Path:
    pdf_path = Path(pdf_path)
    excel_path = Path(excel_path)
    error_root = Path(error_root)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    request_key = reason.get("request_no") or pdf_path.stem
    target = error_root / f"{request_key}_{stamp}"
    target.mkdir(parents=True, exist_ok=True)

    if pdf_path.exists():
        shutil.copy2(pdf_path, target / pdf_path.name)
    if excel_path.exists():
        shutil.copy2(excel_path, target / excel_path.name)

    (target / "error_reason.json").write_text(
        json.dumps(reason, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    return target
