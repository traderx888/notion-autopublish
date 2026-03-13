from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tools.telegram_hub import (
    build_digest_messages,
    collect_repo_updates,
    load_telegram_credentials,
    resolve_task_runtime_settings,
    split_message,
)


class TelegramHubTests(unittest.TestCase):
    def test_load_telegram_credentials_from_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "TELEGRAM_BOT_TOKEN=test-token\nTELEGRAM_CHAT_ID=test-chat\n",
                encoding="utf-8",
            )
            token, chat_id = load_telegram_credentials(
                env={},
                env_file=env_path,
                fallback_files=[],
            )
            self.assertEqual(token, "test-token")
            self.assertEqual(chat_id, "test-chat")

    def test_collect_repo_updates_picks_recent_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo-a"
            (repo / "data").mkdir(parents=True)
            recent = repo / "data" / "headlines.json"
            recent.write_text(json.dumps({"summary": "market up"}), encoding="utf-8")
            old = repo / "data" / "old.txt"
            old.write_text("old", encoding="utf-8")

            old_ts = (datetime.now(timezone.utc) - timedelta(hours=30)).timestamp()
            recent_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).timestamp()
            old.touch()
            recent.touch()
            old_ch = (old_ts, old_ts)
            recent_ch = (recent_ts, recent_ts)
            import os

            os.utime(old, old_ch)
            os.utime(recent, recent_ch)

            snapshots = collect_repo_updates(root=root, hours=24, max_files_per_repo=3)
            target = next(s for s in snapshots if s["repo"] == "repo-a")
            files = [item["file"] for item in target["files"]]
            self.assertIn("data/headlines.json", files)
            self.assertNotIn("data/old.txt", files)

    def test_build_digest_messages_includes_multiple_repos(self):
        snapshots = [
            {
                "repo": "repo-a",
                "files": [
                    {
                        "file": "data/a.json",
                        "updated_at": "2026-03-05T14:00:00+00:00",
                        "snippet": "alpha",
                    }
                ],
            },
            {
                "repo": "repo-b",
                "files": [
                    {
                        "file": "data/b.txt",
                        "updated_at": "2026-03-05T13:30:00+00:00",
                        "snippet": "beta",
                    }
                ],
            },
        ]
        messages = build_digest_messages(
            snapshots=snapshots,
            hours=6,
            generated_at=datetime(2026, 3, 5, 14, 0, tzinfo=timezone.utc),
            max_length=3900,
        )
        text = "\n".join(messages)
        self.assertIn("repo-a", text)
        self.assertIn("repo-b", text)
        self.assertIn("alpha", text)
        self.assertIn("beta", text)
        self.assertNotIn("data/a.json", text)
        self.assertNotIn("data/b.txt", text)

    def test_build_digest_messages_skips_technical_noise(self):
        snapshots = [
            {
                "repo": "fundman-jarvis",
                "files": [
                    {
                        "file": "data/hybrid_memory.json",
                        "updated_at": "2026-03-05T14:00:00+00:00",
                        "snippet": "list items: 15",
                    },
                    {
                        "file": "data/jarvis_runs.json",
                        "updated_at": "2026-03-05T14:00:00+00:00",
                        "snippet": "list items: 42",
                    },
                ],
            }
        ]
        messages = build_digest_messages(
            snapshots=snapshots,
            hours=8,
            generated_at=datetime(2026, 3, 5, 14, 0, tzinfo=timezone.utc),
            max_length=3900,
        )
        text = "\n".join(messages)
        self.assertIn("本時段沒有可發送的跨倉庫內容", text)
        self.assertNotIn("list items:", text)

    def test_split_message_respects_limit(self):
        text = "\n".join([f"line {i}" for i in range(200)])
        chunks = split_message(text, max_length=180)
        self.assertTrue(len(chunks) > 1)
        self.assertTrue(all(len(c) <= 180 for c in chunks))

    def test_resolve_task_runtime_settings_from_control_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "All-in-one" / "workflow"
            config_dir.mkdir(parents=True)
            (config_dir / "cross_repo_tasks.yaml").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "tasks": {
                            "TelegramHubHourly": {
                                "enabled": False,
                                "lookback_hours": 3,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            enabled, hours = resolve_task_runtime_settings(
                root=root,
                task_name="TelegramHubHourly",
                default_hours=8,
            )
            self.assertFalse(enabled)
            self.assertEqual(hours, 3)

    def test_resolve_task_runtime_settings_defaults_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            enabled, hours = resolve_task_runtime_settings(
                root=root,
                task_name="TelegramHubHourly",
                default_hours=8,
            )
            self.assertTrue(enabled)
            self.assertEqual(hours, 8)


if __name__ == "__main__":
    unittest.main()
