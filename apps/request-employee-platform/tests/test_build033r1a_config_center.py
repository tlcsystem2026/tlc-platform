from src.platform_config import load_platform_config


def test_build033r1a_config_center_loads_core_values(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "app.yaml").write_text("app:\n  name: TLC Platform\n  environment: test\n", encoding="utf-8")
    (config_dir / "environment.yaml").write_text("environment:\n  current: test\n", encoding="utf-8")
    (config_dir / "paths.yaml").write_text("paths:\n  repository_root: Y:/repo\n  export_root: Y:/export\n  temp_root: Y:/temp\n", encoding="utf-8")
    (config_dir / "database.yaml").write_text("database:\n  default:\n    engine: sqlite\n", encoding="utf-8")
    (config_dir / "export.yaml").write_text("export:\n  pdf:\n    engine: reportlab\n", encoding="utf-8")
    (config_dir / "logging.yaml").write_text("logging:\n  level: INFO\n", encoding="utf-8")

    cfg = load_platform_config(config_dir)

    assert cfg.environment == "test"
    assert cfg.repository_root == "Y:/repo"
    assert cfg.export_root == "Y:/export"
    assert cfg.get("export.pdf.engine") == "reportlab"
