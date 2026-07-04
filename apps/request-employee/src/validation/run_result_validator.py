from pathlib import Path
import json

def validate_output(output_dir: str | Path) -> dict:
    output_dir = Path(output_dir)
    summary_file = output_dir / "batch_summary.json"
    result = {
        "output_dir": str(output_dir),
        "summary_exists": summary_file.exists(),
        "jobs": 0,
        "reports": 0,
        "json_outputs": 0,
        "errors": [],
    }

    if not output_dir.exists():
        result["errors"].append("Output directory does not exist.")
        return result

    for job in output_dir.iterdir():
        if not job.is_dir():
            continue
        result["jobs"] += 1
        if (job / "differences.xlsx").exists():
            result["reports"] += 1
        if (job / "differences.json").exists():
            result["json_outputs"] += 1

    if summary_file.exists():
        try:
            summary = json.loads(summary_file.read_text(encoding="utf-8"))
            result["summary_count"] = len(summary) if isinstance(summary, list) else None
            result["summary_statuses"] = {}
            if isinstance(summary, list):
                for row in summary:
                    status = row.get("status", "UNKNOWN")
                    result["summary_statuses"][status] = result["summary_statuses"].get(status, 0) + 1
        except Exception as exc:
            result["errors"].append(f"Failed to read batch_summary.json: {exc}")

    return result
