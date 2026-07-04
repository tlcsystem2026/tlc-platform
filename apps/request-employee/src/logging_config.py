import logging
from pathlib import Path

def configure_logging(log_file="logs/request_employee.log"):
    p=Path(log_file); p.parent.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[logging.FileHandler(p,encoding="utf-8"),logging.StreamHandler()]
    )
