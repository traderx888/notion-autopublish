"""Dailychartbook local packet parser and artifact writer."""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from browser.base import SCRAPED_DIR

TAXONOMY_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "dailychartbook_taxonomy.json"
DEFAULT_OUTPUT_DIR = SCRAPED_DIR / "dailychartbook"
DEFAULT_LOOKBACK_DAYS = 30
FOLDER_DATE_PATTERN = re.compile(r"(20\d{2}-\d{2}-\d{2})")
SECTION_HEADER_PATTERN = re.compile(r"^---\s*(.+?)\s*---\s*$")


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_keyword_list(values: Iterable[Any]) -> List[str]:
    return [str(value).strip().lower() for value in values or [] if str(value).strip()]


def _split_csv(value: str) -> List[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "packet"


def _resolve_importance_weight(raw_importance: Any, weights: Dict[str, Any]) -> int:
    importance_text = _normalize_text(raw_importance).lower()
    if importance_text in weights:
        return int(weights[importance_text])

    numeric_match = re.search(r"(\d+)\s*/\s*5", importance_text)
    if numeric_match:
        score = int(numeric_match.group(1))
        if score >= 5:
            return 4
        if score == 4:
            return 3
        if score == 3:
            return 2
        return 1

    bare_number = re.search(r"\d+", importance_text)
    if bare_number:
        score = int(bare_number.group(0))
        if score >= 5:
            return 4
        if score == 4:
            return 3
        if score == 3:
            return 2
        return 1

    return 2


def _extract_folder_date(path: Path) -> Optional[str]:
    match = FOLDER_DATE_PATTERN.search(path.name)
    return match.group(1) if match else None


def resolve_chartbook_root(root_dir: Optional[Path | str] = None) -> Path:
    candidate = root_dir or os.environ.get("DAILYCHARTBOOK_DIR")
    if not candidate:
        raise RuntimeError("Dailychartbook root path is required via --root or DAILYCHARTBOOK_DIR.")
    path = Path(candidate)
    if not path.exists():
        raise RuntimeError(f"Dailychartbook root does not exist: {path}")
    return path


def load_taxonomy(config_path: Path = TAXONOMY_CONFIG_PATH) -> Dict[str, Any]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    families = payload.get("families") or {}
    for spec in families.values():
        spec["match_keywords"] = _normalize_keyword_list(spec.get("match_keywords") or [])
        spec["bull_keywords"] = _normalize_keyword_list(spec.get("bull_keywords") or [])
        spec["bear_keywords"] = _normalize_keyword_list(spec.get("bear_keywords") or [])
    weights = payload.get("importance_weights") or {}
    payload["importance_weights"] = {str(key).lower(): int(value) for key, value in weights.items()}
    return payload


def select_chartbook_folders(
    root_dir: Path,
    *,
    days: int = DEFAULT_LOOKBACK_DAYS,
    date_value: Optional[str] = None,
) -> List[Path]:
    folders_by_date: Dict[str, Path] = {}
    for child in root_dir.iterdir():
        if not child.is_dir():
            continue
        folder_date = _extract_folder_date(child)
        if not folder_date:
            continue
        if date_value and folder_date != date_value:
            continue
        folders_by_date[folder_date] = child

    ordered_dates = sorted(folders_by_date)
    if date_value:
        return [folders_by_date[item] for item in ordered_dates]

    if days > 0 and ordered_dates:
        latest_date = date.fromisoformat(ordered_dates[-1])
        cutoff = latest_date.toordinal() - max(days - 1, 0)
        ordered_dates = [
            item
            for item in ordered_dates
            if date.fromisoformat(item).toordinal() >= cutoff
        ]
    return [folders_by_date[item] for item in ordered_dates]


def parse_packet_file(txt_path: Path) -> Dict[str, Any]:
    text = txt_path.read_text(encoding="utf-8")
    header_lines: List[str] = []
    sections: Dict[str, List[str]] = {}
    section_name: Optional[str] = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        header_match = SECTION_HEADER_PATTERN.match(line.strip())
        if header_match:
            section_name = header_match.group(1).strip().lower()
            sections.setdefault(section_name, [])
            continue
        if section_name is None:
            header_lines.append(line)
        else:
            sections[section_name].append(line)

    header_map: Dict[str, str] = {}
    for line in header_lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        header_map[key.strip().lower()] = value.strip()

    title = _normalize_text(header_map.get("title"))
    packet_date = _normalize_text(header_map.get("date")) or _extract_folder_date(txt_path.parent)
    sequence_raw = _normalize_text(header_map.get("sequence"))
    if not title or not packet_date or not sequence_raw:
        raise ValueError(f"Packet file missing required fields: {txt_path}")

    classification_map: Dict[str, str] = {}
    for line in sections.get("classification", []):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        classification_map[key.strip().lower()] = value.strip()

    source_map: Dict[str, str] = {}
    for line in sections.get("source", []):
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        source_map[key.strip().lower()] = value.strip()

    original_text = "\n".join(item for item in sections.get("original text", [])).strip()
    ai_interpretation = "\n".join(item for item in sections.get("ai interpretation", [])).strip()
    if not original_text or not ai_interpretation:
        raise ValueError(f"Packet file missing text sections: {txt_path}")

    sequence = int(sequence_raw)
    image_path = txt_path.with_suffix(".png")

    return {
        "packet_id": f"{packet_date}-{sequence:02d}-{_slugify(title)}",
        "title": title,
        "date": packet_date,
        "sequence": sequence,
        "folder_name": txt_path.parent.name,
        "txt_path": str(txt_path),
        "image_path": str(image_path),
        "image_exists": image_path.exists(),
        "original_text": original_text,
        "ai_interpretation": ai_interpretation,
        "category": _split_csv(classification_map.get("category", "")),
        "regime_signals": _split_csv(classification_map.get("regime signals", "")),
        "affected_assets": _split_csv(classification_map.get("affected assets", "")),
        "time_horizon": _normalize_text(classification_map.get("time horizon")) or None,
        "use_case": _split_csv(classification_map.get("use case", "")),
        "importance": _normalize_text(classification_map.get("importance")) or "Medium",
        "raw_classification": classification_map,
        "source": _normalize_text(source_map.get("source")) or None,
        "url": _normalize_text(source_map.get("url")) or None,
        "image_url": _normalize_text(source_map.get("image url")) or None,
    }


def _collect_search_text(packet: Dict[str, Any]) -> str:
    parts: List[str] = [
        _normalize_text(packet.get("title")),
        _normalize_text(packet.get("original_text")),
        _normalize_text(packet.get("ai_interpretation")),
        _normalize_text(packet.get("time_horizon")),
    ]
    for key in ["category", "regime_signals", "affected_assets", "use_case"]:
        parts.extend(_normalize_text(item) for item in packet.get(key) or [])
    return " ".join(part for part in parts if part).lower()


def _find_matches(search_text: str, keywords: Iterable[str]) -> List[str]:
    matches: List[str] = []
    for keyword in keywords:
        if keyword and keyword in search_text and keyword not in matches:
            matches.append(keyword)
    return matches


def classify_packet(packet: Dict[str, Any], taxonomy: Dict[str, Any]) -> Dict[str, Any]:
    classified = dict(packet)
    search_text = _collect_search_text(packet)
    weights = taxonomy.get("importance_weights") or {}
    weight = _resolve_importance_weight(packet.get("importance"), weights)

    mapped_families: List[str] = []
    family_contributions: Dict[str, Dict[str, Any]] = {}
    for family_name, spec in (taxonomy.get("families") or {}).items():
        matched_keywords = _find_matches(search_text, spec.get("match_keywords") or [])
        bull_matches = _find_matches(search_text, spec.get("bull_keywords") or [])
        bear_matches = _find_matches(search_text, spec.get("bear_keywords") or [])
        if not matched_keywords and not bull_matches and not bear_matches:
            continue
        mapped_families.append(family_name)
        family_contributions[family_name] = {
            "ticker": spec.get("ticker"),
            "weight": weight,
            "bull": weight if bull_matches else 0,
            "bear": weight if bear_matches else 0,
            "matched_keywords": matched_keywords,
            "bull_matches": bull_matches,
            "bear_matches": bear_matches,
        }

    classified["mapped_families"] = mapped_families
    classified["family_contributions"] = family_contributions
    return classified


def _base_family_summary(family_name: str, spec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "family": family_name,
        "ticker": spec.get("ticker"),
        "packet_count": 0,
        "bull_score": 0,
        "bear_score": 0,
        "value": 0,
        "signal": "MIXED",
        "promoted": False,
        "top_bull_packets": [],
        "top_bear_packets": [],
    }


def _packet_summary(packet: Dict[str, Any], contribution: Dict[str, Any], score_key: str) -> Dict[str, Any]:
    match_key = "bull_matches" if score_key == "bull" else "bear_matches"
    return {
        "packet_id": packet.get("packet_id"),
        "title": packet.get("title"),
        "score": contribution.get(score_key, 0),
        "importance": packet.get("importance"),
        "matched_keywords": contribution.get(match_key) or contribution.get("matched_keywords") or [],
    }


def _resolve_signal(bull_score: int, bear_score: int) -> tuple[int, str, bool]:
    dominant_score = max(bull_score, bear_score)
    score_gap = abs(bull_score - bear_score)
    if dominant_score >= 6 and score_gap >= 3:
        if bull_score > bear_score:
            return (2, "STRONG_BULL", True) if dominant_score >= 9 and score_gap >= 6 else (1, "BULL", True)
        return (-2, "STRONG_BEAR", True) if dominant_score >= 9 and score_gap >= 6 else (-1, "BEAR", True)
    return 0, "MIXED", False


def build_family_scorecard(
    packets: List[Dict[str, Any]],
    taxonomy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    taxonomy_payload = taxonomy or load_taxonomy()
    families: Dict[str, Dict[str, Any]] = {
        family_name: _base_family_summary(family_name, spec)
        for family_name, spec in (taxonomy_payload.get("families") or {}).items()
    }

    for packet in packets:
        contributions = packet.get("family_contributions") or {}
        for family_name, contribution in contributions.items():
            summary = families[family_name]
            summary["packet_count"] += 1
            summary["bull_score"] += int(contribution.get("bull", 0))
            summary["bear_score"] += int(contribution.get("bear", 0))
            if contribution.get("bull", 0):
                summary["top_bull_packets"].append(_packet_summary(packet, contribution, "bull"))
            if contribution.get("bear", 0):
                summary["top_bear_packets"].append(_packet_summary(packet, contribution, "bear"))

    conflict_count = 0
    promoted_count = 0
    for summary in families.values():
        summary["top_bull_packets"] = sorted(
            summary["top_bull_packets"],
            key=lambda item: (-int(item.get("score", 0)), str(item.get("packet_id") or "")),
        )[:3]
        summary["top_bear_packets"] = sorted(
            summary["top_bear_packets"],
            key=lambda item: (-int(item.get("score", 0)), str(item.get("packet_id") or "")),
        )[:3]
        if summary["bull_score"] > 0 and summary["bear_score"] > 0:
            conflict_count += 1
        value, signal, promoted = _resolve_signal(summary["bull_score"], summary["bear_score"])
        summary["value"] = value
        summary["signal"] = signal
        summary["promoted"] = promoted
        if promoted:
            promoted_count += 1

    return {
        "packet_count": len(packets),
        "family_count": len(families),
        "conflict_count": conflict_count,
        "promoted_count": promoted_count,
        "families": families,
    }


def build_readings_payload(scorecard: Dict[str, Any], *, as_of_date: str, generated_at: Optional[str] = None) -> Dict[str, Any]:
    readings: List[Dict[str, Any]] = []
    for summary in (scorecard.get("families") or {}).values():
        if not summary.get("promoted"):
            continue
        readings.append(
            {
                "ticker": summary.get("ticker"),
                "date": as_of_date,
                "value": summary.get("value"),
                "signal": summary.get("signal"),
                "source": "dailychartbook",
                "category": "chartbook",
                "bull_score": summary.get("bull_score"),
                "bear_score": summary.get("bear_score"),
                "packet_count": summary.get("packet_count"),
            }
        )

    readings.extend(
        [
            {
                "ticker": "DCB_CONFLICT_COUNT",
                "date": as_of_date,
                "value": scorecard.get("conflict_count", 0),
                "signal": None,
                "source": "dailychartbook",
                "category": "chartbook",
            },
            {
                "ticker": "DCB_PACKET_COUNT",
                "date": as_of_date,
                "value": scorecard.get("packet_count", 0),
                "signal": None,
                "source": "dailychartbook",
                "category": "chartbook",
            },
        ]
    )

    return {
        "generated_at": generated_at or _now_iso(),
        "as_of_date": as_of_date,
        "packet_count": scorecard.get("packet_count", 0),
        "conflict_count": scorecard.get("conflict_count", 0),
        "readings": readings,
    }


def build_daily_payload(
    folder: Path,
    *,
    taxonomy: Dict[str, Any],
    source_root: Optional[Path] = None,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    folder_date = _extract_folder_date(folder)
    if not folder_date:
        raise ValueError(f"Unable to determine chartbook date from folder: {folder}")

    packets = [parse_packet_file(path) for path in sorted(folder.glob("*.txt"))]
    packets = sorted(packets, key=lambda item: (int(item.get("sequence", 0)), str(item.get("title") or "")))
    classified_packets = [classify_packet(packet, taxonomy) for packet in packets]
    scorecard = build_family_scorecard(classified_packets, taxonomy=taxonomy)
    readings_payload = build_readings_payload(scorecard, as_of_date=folder_date, generated_at=generated_at)

    return {
        "generated_at": generated_at or _now_iso(),
        "date": folder_date,
        "folder_name": folder.name,
        "source_root": str(source_root or folder.parent),
        "packet_count": len(classified_packets),
        "packets": classified_packets,
        "family_scorecard": scorecard,
        "promoted_readings": readings_payload["readings"],
    }


def write_run_artifacts(
    daily_payloads: List[Dict[str, Any]],
    *,
    output_dir: Path,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    if not daily_payloads:
        raise RuntimeError("No Dailychartbook payloads were generated.")

    output_dir.mkdir(parents=True, exist_ok=True)
    by_date_dir = output_dir / "by_date"
    by_date_dir.mkdir(parents=True, exist_ok=True)

    for payload in daily_payloads:
        date_key = payload["date"]
        (by_date_dir / f"{date_key}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    latest_payload = daily_payloads[-1]
    latest_generated_at = generated_at or latest_payload.get("generated_at") or _now_iso()
    latest_scorecard_payload = {
        "generated_at": latest_generated_at,
        "as_of_date": latest_payload["date"],
        **latest_payload["family_scorecard"],
    }
    latest_readings_payload = {
        "generated_at": latest_generated_at,
        "as_of_date": latest_payload["date"],
        "packet_count": latest_payload["packet_count"],
        "conflict_count": latest_payload["family_scorecard"]["conflict_count"],
        "readings": latest_payload["promoted_readings"],
    }

    latest_scorecard_path = output_dir / "dailychartbook_family_scorecard_latest.json"
    latest_readings_path = output_dir / "dailychartbook_readings_latest.json"
    latest_manifest_path = output_dir / "dailychartbook_latest.json"

    latest_scorecard_path.write_text(json.dumps(latest_scorecard_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    latest_readings_path.write_text(json.dumps(latest_readings_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = {
        "generated_at": latest_generated_at,
        "as_of_date": latest_payload["date"],
        "source_root": latest_payload.get("source_root"),
        "folder_count": len(daily_payloads),
        "processed_dates": [payload["date"] for payload in daily_payloads],
        "by_date_dir": str(by_date_dir),
        "latest_scorecard_path": str(latest_scorecard_path),
        "latest_readings_path": str(latest_readings_path),
    }
    latest_manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def run(
    *,
    root_dir: Optional[Path | str],
    output_dir: Optional[Path | str] = None,
    days: int = DEFAULT_LOOKBACK_DAYS,
    date_value: Optional[str] = None,
    taxonomy: Optional[Dict[str, Any]] = None,
    taxonomy_path: Optional[Path | str] = None,
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    resolved_root = resolve_chartbook_root(root_dir)
    resolved_output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    taxonomy_payload = taxonomy or load_taxonomy(Path(taxonomy_path) if taxonomy_path else TAXONOMY_CONFIG_PATH)
    folders = select_chartbook_folders(resolved_root, days=days, date_value=date_value)
    daily_payloads = [
        build_daily_payload(
            folder,
            taxonomy=taxonomy_payload,
            source_root=resolved_root,
            generated_at=generated_at,
        )
        for folder in folders
    ]
    return write_run_artifacts(daily_payloads, output_dir=resolved_output_dir, generated_at=generated_at)
