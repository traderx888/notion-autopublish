import importlib.util
from datetime import date
from pathlib import Path

import pytest


def _load_series_module(repo_root: Path):
    module_path = repo_root / "tools" / "action_meditation_series.py"
    spec = importlib.util.spec_from_file_location("action_meditation_series", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_action_meditation_series_artifact_is_valid():
    repo_root = Path(__file__).resolve().parents[1]
    module = _load_series_module(repo_root)

    payload = module.load_series()

    assert module.validate_series(payload) == []


def test_action_meditation_preview_matches_generated_output():
    repo_root = Path(__file__).resolve().parents[1]
    module = _load_series_module(repo_root)

    payload = module.load_series()
    preview_path = repo_root / "outputs" / "telegram" / "28_day_action_meditation_preview.md"

    assert preview_path.read_text(encoding="utf-8") == module.render_preview_markdown(payload)


def test_resolve_day_number_from_start_date():
    repo_root = Path(__file__).resolve().parents[1]
    module = _load_series_module(repo_root)

    assert module.resolve_day_number(start_date=date(2026, 4, 1), target_date=date(2026, 4, 14)) == 14


def test_resolve_day_number_rejects_date_outside_series():
    repo_root = Path(__file__).resolve().parents[1]
    module = _load_series_module(repo_root)

    with pytest.raises(ValueError, match="outside the 28-day series"):
        module.resolve_day_number(start_date=date(2026, 4, 1), target_date=date(2026, 5, 1))


def test_send_message_text_uses_existing_telegram_helpers():
    repo_root = Path(__file__).resolve().parents[1]
    module = _load_series_module(repo_root)
    sent: list[dict] = []

    def fake_credentials_loader(*, env_file=None):
        assert env_file == Path("custom.env")
        return "token-1", "chat-1"

    def fake_splitter(text: str, max_length: int):
        assert text == "<b>hello</b>"
        assert max_length == 3900
        return ["<b>hello</b>"]

    def fake_sender(*, bot_token: str, chat_id: str, text: str, parse_mode: str):
        sent.append(
            {
                "bot_token": bot_token,
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            }
        )

    module.send_message_text(
        "<b>hello</b>",
        env_file=Path("custom.env"),
        credentials_loader=fake_credentials_loader,
        split_func=fake_splitter,
        send_func=fake_sender,
    )

    assert sent == [
        {
            "bot_token": "token-1",
            "chat_id": "chat-1",
            "text": "<b>hello</b>",
            "parse_mode": "HTML",
        }
    ]
