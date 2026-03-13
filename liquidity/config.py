from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_path(value: str | os.PathLike[str] | None, *, base: Path) -> Path | None:
    if not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base / path).resolve()
    return path


def _as_bool(value: str | bool | None, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_liquidity_config(env: dict | None = None) -> dict:
    if env is None:
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        env = dict(os.environ)

    checker_path = _resolve_path(
        env.get("LIQUIDITY_CHECKER_CONFIG", "config/liquidity_checker.local.json"),
        base=PROJECT_ROOT,
    )
    if checker_path is None or not checker_path.exists():
        raise FileNotFoundError(f"Liquidity checker config not found: {checker_path}")

    raw_cfg = json.loads(checker_path.read_text(encoding="utf-8"))
    excel_path = _resolve_path(env.get(raw_cfg["excel"]["path_env"]), base=PROJECT_ROOT)
    screenshot_dir = _resolve_path(env.get(raw_cfg["screenshot"]["dir_env"]), base=PROJECT_ROOT)
    output_dir = _resolve_path(env.get("LIQUIDITY_OUTPUT_DIR", "outputs/liquidity"), base=PROJECT_ROOT)
    raw_dir = _resolve_path(env.get("LIQUIDITY_RAW_DIR", "scraped_data/liquidity"), base=PROJECT_ROOT)

    return {
        "h_model": {
            "author_url": env.get("H_MODEL_AUTHOR_URL", "https://substack.com/@capitalwars"),
            "headless": _as_bool(env.get("H_MODEL_HEADLESS", "1"), default=True),
            "stale_hours": int(env.get("H_MODEL_STALE_HOURS", "120")),
        },
        "checker": {
            "excel": {**raw_cfg["excel"], "path": excel_path},
            "screenshot": {**raw_cfg["screenshot"], "dir": screenshot_dir},
            "thresholds": raw_cfg["thresholds"],
        },
        "paths": {
            "output_dir": output_dir,
            "raw_dir": raw_dir,
            "checker_config_path": checker_path,
        },
    }

