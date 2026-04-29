from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from utils.text_utils import slugify


def ensure_dir(path: Path) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def create_run_dir(base_dir: str, keyword: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    slug = slugify(keyword, fallback="manual")
    run_dir = Path(base_dir) / f"{timestamp}_{slug}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_text(path: Path, content: str) -> None:
    Path(path).write_text(content, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
