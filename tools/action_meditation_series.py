from __future__ import annotations

import argparse
import html
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = REPO_ROOT / "outputs" / "telegram"
SERIES_PATH = OUTPUT_DIR / "28_day_action_meditation_series.json"
PREVIEW_PATH = OUTPUT_DIR / "28_day_action_meditation_preview.md"
HKT = ZoneInfo("Asia/Hong_Kong")
REQUIRED_TOP_LEVEL_FIELDS = ("series_key", "source_title", "language", "format", "days")
REQUIRED_DAY_FIELDS = (
    "day",
    "week",
    "week_theme",
    "title",
    "core_message",
    "practice_steps",
    "reflection_prompt",
    "telegram_html",
)


def load_series(path: Path = SERIES_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_series(payload: dict[str, Any], path: Path = SERIES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _as_non_empty_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items = [str(item).strip() for item in value if str(item).strip()]
    return items


def build_telegram_html(day_payload: dict[str, Any]) -> str:
    day = int(day_payload["day"])
    week = int(day_payload["week"])
    title = html.escape(str(day_payload["title"]).strip())
    week_theme = html.escape(str(day_payload["week_theme"]).strip())
    paragraphs = [html.escape(text) for text in _as_non_empty_text_list(day_payload["core_message"])]
    steps = [html.escape(text) for text in _as_non_empty_text_list(day_payload["practice_steps"])]
    reflection_prompt = html.escape(str(day_payload["reflection_prompt"]).strip())

    parts = [
        f"<b>第 {day} 天｜{title}</b>",
        f"<i>第 {week} 周：{week_theme}</i>",
        "",
        *paragraphs[:2],
        "",
        "<b>今日練習</b>",
    ]
    parts.extend(f"{idx}. {step}" for idx, step in enumerate(steps, start=1))
    parts.extend(
        [
            "",
            f"<i>收尾提問：{reflection_prompt}</i>",
        ]
    )
    return "\n".join(parts).strip()


def normalize_series(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized_days: list[dict[str, Any]] = []
    for day in payload.get("days", []):
        normalized_day = dict(day)
        normalized_day["telegram_html"] = build_telegram_html(normalized_day)
        normalized_days.append(normalized_day)
    normalized["days"] = normalized_days
    return normalized


def validate_series(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in payload:
            errors.append(f"missing top-level field: {field}")

    if payload.get("series_key") != "28_day_action_meditation":
        errors.append("series_key must be 28_day_action_meditation")
    if payload.get("language") != "zh-Hant":
        errors.append("language must be zh-Hant")
    if payload.get("format") != "telegram_html":
        errors.append("format must be telegram_html")

    days = payload.get("days")
    if not isinstance(days, list):
        return errors + ["days must be a list"]

    if len(days) != 28:
        errors.append(f"days must contain 28 entries, got {len(days)}")

    day_numbers = [day.get("day") for day in days if isinstance(day, dict)]
    if day_numbers != list(range(1, 29)):
        errors.append("day numbers must run from 1 to 28 in order")

    for index, day_payload in enumerate(days, start=1):
        if not isinstance(day_payload, dict):
            errors.append(f"day entry {index} must be an object")
            continue

        for field in REQUIRED_DAY_FIELDS:
            if field not in day_payload:
                errors.append(f"day {index} missing field: {field}")

        paragraphs = _as_non_empty_text_list(day_payload.get("core_message"))
        if len(paragraphs) != 2:
            errors.append(f"day {index} core_message must contain exactly 2 paragraphs")

        steps = _as_non_empty_text_list(day_payload.get("practice_steps"))
        if len(steps) < 2 or len(steps) > 3:
            errors.append(f"day {index} practice_steps must contain 2 or 3 items")

        expected_html = build_telegram_html(day_payload)
        actual_html = str(day_payload.get("telegram_html", "")).strip()
        if actual_html != expected_html:
            errors.append(f"day {index} telegram_html does not match rendered content")
        if len(actual_html) >= 3900:
            errors.append(f"day {index} telegram_html exceeds Telegram limit")

    return errors


def get_day_payload(payload: dict[str, Any], day_number: int) -> dict[str, Any]:
    if day_number < 1 or day_number > 28:
        raise ValueError("day must be between 1 and 28")
    for day_payload in payload["days"]:
        if int(day_payload["day"]) == day_number:
            return day_payload
    raise ValueError(f"day {day_number} not found in series")


def resolve_day_number(
    *,
    day: int | None = None,
    start_date: date | None = None,
    target_date: date | None = None,
) -> int:
    if day is not None:
        if day < 1 or day > 28:
            raise ValueError("day must be between 1 and 28")
        return day

    if start_date is None:
        raise ValueError("either day or start_date must be provided")

    current_date = target_date or datetime.now(HKT).date()
    resolved_day = (current_date - start_date).days + 1
    if resolved_day < 1 or resolved_day > 28:
        raise ValueError("target date is outside the 28-day series")
    return resolved_day


def parse_iso_date(value: str) -> date:
    return date.fromisoformat(value)


def send_message_text(
    text: str,
    *,
    env_file: Path | None = None,
    credentials_loader=None,
    split_func=None,
    send_func=None,
) -> None:
    if credentials_loader is None or split_func is None or send_func is None:
        try:
            from tools.telegram_hub import load_telegram_credentials, send_message, split_message
        except ModuleNotFoundError:
            from telegram_hub import load_telegram_credentials, send_message, split_message

        credentials_loader = credentials_loader or load_telegram_credentials
        split_func = split_func or split_message
        send_func = send_func or send_message

    bot_token, chat_id = credentials_loader(env_file=env_file)
    for chunk in split_func(text, max_length=3900):
        send_func(bot_token=bot_token, chat_id=chat_id, text=chunk, parse_mode="HTML")


def render_preview_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# 28-Day Telegram Reminder Preview",
        "",
        f"- Series Key: `{payload['series_key']}`",
        f"- Source Title: {payload['source_title']}",
        f"- Language: `{payload['language']}`",
        f"- Format: `{payload['format']}`",
        "",
        "This preview is generated from the canonical JSON artifact.",
        "",
    ]

    for day in payload["days"]:
        lines.extend(
            [
                f"## 第 {day['day']} 天｜{day['title']}",
                "",
                f"- Week: 第 {day['week']} 周",
                f"- Theme: {day['week_theme']}",
                f"- Reflection: {day['reflection_prompt']}",
                "",
                "### Core Message",
                "",
                day["core_message"][0],
                "",
                day["core_message"][1],
                "",
                "### Practice Steps",
                "",
            ]
        )
        lines.extend(f"{idx}. {step}" for idx, step in enumerate(day["practice_steps"], start=1))
        lines.extend(
            [
                "",
                "### Telegram HTML",
                "",
                "```html",
                build_telegram_html(day),
                "```",
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def write_preview(payload: dict[str, Any], path: Path = PREVIEW_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_preview_markdown(payload), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and render the action meditation Telegram series")
    parser.add_argument("--validate", action="store_true", help="Validate the JSON artifact")
    parser.add_argument("--write-preview", action="store_true", help="Write the Markdown preview from JSON")
    parser.add_argument("--write-canonical", action="store_true", help="Rewrite telegram_html in the JSON artifact")
    parser.add_argument("--day", type=int, default=None, help="Explicit day number to preview or send")
    parser.add_argument("--start-date", type=str, default=None, help="Series start date in YYYY-MM-DD")
    parser.add_argument("--target-date", type=str, default=None, help="Target date in YYYY-MM-DD when resolving from start date")
    parser.add_argument("--send", action="store_true", help="Send the resolved day message to Telegram")
    parser.add_argument("--env-file", type=Path, default=None, help="Explicit env file containing Telegram credentials")
    return parser.parse_args()


def main() -> int:
    try:
        args = parse_args()
        payload = load_series()
        if args.write_canonical:
            payload = normalize_series(payload)
            write_series(payload)
            print(f"Canonical JSON written to {SERIES_PATH}")

        errors = validate_series(payload)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1

        actions_requested = any(
            [
                args.validate,
                args.write_preview,
                args.day is not None,
                args.start_date is not None,
                args.send,
            ]
        )
        if args.validate or not actions_requested:
            print("Validation: passed")

        if args.write_preview:
            write_preview(payload)
            print(f"Preview written to {PREVIEW_PATH}")

        if args.day is not None or args.start_date is not None or args.send:
            day_number = resolve_day_number(
                day=args.day,
                start_date=parse_iso_date(args.start_date) if args.start_date else None,
                target_date=parse_iso_date(args.target_date) if args.target_date else None,
            )
            day_payload = get_day_payload(payload, day_number)
            message_text = day_payload["telegram_html"]
            if args.send:
                send_message_text(message_text, env_file=args.env_file)
                print(f"Telegram delivery: sent day {day_number}")
            else:
                print(message_text)

        return 0
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
