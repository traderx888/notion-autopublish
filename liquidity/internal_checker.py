from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _now_iso(now_iso: str | None = None) -> str:
    return now_iso or datetime.now(timezone.utc).isoformat()


def _resolve_tesseract_cmd(default_path: str | Path | None = None) -> str | None:
    configured = os.environ.get("TESSERACT_CMD")
    if configured and Path(configured).exists():
        return configured

    resolved_default = Path(default_path) if default_path else Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if resolved_default.exists():
        return str(resolved_default)
    return None


def ocr_image_to_text(path: str | Path) -> str:
    try:
        from PIL import Image
        import pytesseract
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("OCR dependencies unavailable") from exc
    tesseract_cmd = _resolve_tesseract_cmd()
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    return pytesseract.image_to_string(Image.open(path))


def _resolve_latest_excel_path(excel_path: str | Path | None, pattern: str = "*.xlsx") -> Path | None:
    if not excel_path:
        return None
    path = Path(excel_path)
    if path.is_file():
        return path
    if not path.exists() or not path.is_dir():
        return path

    candidates = [
        item for item in path.glob(pattern)
        if item.is_file() and not item.name.startswith("~$")
    ]
    if not candidates:
        return path
    return max(candidates, key=lambda item: item.stat().st_mtime)


def _resolve_latest_screenshot_path(screenshot_dir: str | Path | None, pattern: str = "*.png", recursive: bool = False) -> Path | None:
    if not screenshot_dir:
        return None
    path = Path(screenshot_dir)
    if not path.exists():
        return None
    iterator = path.rglob(pattern) if recursive else path.glob(pattern)
    candidates = [item for item in iterator if item.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def load_internal_checker_inputs(config: dict) -> dict:
    excel_path = _resolve_latest_excel_path(
        config["excel"].get("path"),
        config["excel"].get("glob", "*.xlsx"),
    )
    latest_screenshot = _resolve_latest_screenshot_path(
        config["screenshot"].get("dir"),
        config["screenshot"].get("glob", "*.png"),
        recursive=bool(config["screenshot"].get("recursive")),
    )
    return {
        "excel_path": Path(excel_path) if excel_path else None,
        "screenshot_path": latest_screenshot,
    }


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _label_is_positive(label: str) -> bool:
    lowered = label.lower()
    return lowered.endswith("up") or "up" in lowered or "support" in lowered or "easing" in lowered


def _metric_value_from_selector(df: pd.DataFrame, selector: dict) -> float:
    match_column = selector.get("match_column")
    match_text = str(selector.get("match_text", "")).strip()
    value_column = selector.get("value_column")
    if not match_column or not value_column or match_column not in df.columns or value_column not in df.columns:
        return 0.0

    matches = df[df[match_column].astype(str).str.strip() == match_text]
    if matches.empty:
        return 0.0
    value = _safe_float(matches.iloc[-1].get(value_column))
    return value * _safe_float(selector.get("multiplier", 1.0))


def _extract_metric_value(df: pd.DataFrame, latest: pd.Series, metric_config: str | dict) -> float:
    if isinstance(metric_config, dict):
        return _metric_value_from_selector(df, metric_config)
    return _safe_float(latest.get(metric_config))


def build_internal_checker_snapshot(
    config: dict,
    now_iso: str | None = None,
) -> dict:
    snapshot_at = _now_iso(now_iso)
    inputs = load_internal_checker_inputs(config)
    excel_path = inputs["excel_path"]
    screenshot_path = inputs["screenshot_path"]
    thresholds = config["thresholds"]
    note_parts = []

    if excel_path is None or not excel_path.exists():
        return {
            "snapshot_at": snapshot_at,
            "excel_source": str(excel_path or ""),
            "screenshot_source": str(screenshot_path or ""),
            "ocr_available": False,
            "series": {"level": 0.0, "mom_5d": 0.0, "mom_20d": 0.0},
            "alert_hits": [],
            "signal_points": 0,
            "liquidity_direction": "UNKNOWN",
            "urgent_change": False,
            "available": False,
            "note": "Excel source is missing.",
        }

    df = pd.read_excel(excel_path, sheet_name=config["excel"]["sheet_name"])
    date_column = config["excel"].get("date_column")
    if date_column in df.columns:
        df = df.copy()
        df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
        df = df.sort_values(date_column)
    latest = df.iloc[-1]

    metrics = config["excel"]["metrics"]
    series = {
        "level": _extract_metric_value(df, latest, metrics["level"]),
        "mom_5d": _extract_metric_value(df, latest, metrics["mom_5d"]),
        "mom_20d": _extract_metric_value(df, latest, metrics["mom_20d"]),
    }

    signal_points = 0
    if series["mom_5d"] >= thresholds["mom_5d_positive"]:
        signal_points += 2
    elif series["mom_5d"] <= thresholds["mom_5d_negative"]:
        signal_points -= 2

    if series["mom_20d"] >= thresholds["mom_20d_positive"]:
        signal_points += 1
    elif series["mom_20d"] <= thresholds["mom_20d_negative"]:
        signal_points -= 1

    alert_hits = []
    positive_hits = 0
    negative_hits = 0
    ocr_available = False
    if screenshot_path is not None:
        try:
            ocr_text = ocr_image_to_text(screenshot_path)
            ocr_available = True
            for label, pattern in config["screenshot"]["ocr_patterns"].items():
                if re.search(pattern, ocr_text, re.IGNORECASE):
                    alert_hits.append(label)
                    if _label_is_positive(label):
                        signal_points += 1
                        positive_hits += 1
                    else:
                        signal_points -= 1
                        negative_hits += 1
        except Exception:
            note_parts.append("OCR unavailable; used Excel-only logic.")
    else:
        note_parts.append("No screenshot found; used Excel-only logic.")

    signal_points = max(-5, min(5, signal_points))
    if signal_points >= 2:
        direction = "EXPANDING"
    elif signal_points <= -2:
        direction = "CONTRACTING"
    else:
        direction = "FLAT"

    urgent_change = abs(signal_points) >= 3
    if positive_hits >= thresholds["urgent_alert_min_hits"] or negative_hits >= thresholds["urgent_alert_min_hits"]:
        urgent_change = True

    return {
        "snapshot_at": snapshot_at,
        "excel_source": str(excel_path),
        "screenshot_source": str(screenshot_path or ""),
        "ocr_available": ocr_available,
        "series": series,
        "alert_hits": alert_hits,
        "signal_points": signal_points,
        "liquidity_direction": direction,
        "urgent_change": urgent_change,
        "available": True,
        "note": " ".join(note_parts).strip() or "OK",
    }
