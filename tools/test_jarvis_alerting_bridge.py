from __future__ import annotations

import unittest
from types import SimpleNamespace

from tools import telegram_hub


class JarvisAlertingBridgeTests(unittest.TestCase):
    def test_send_to_destinations_prefers_jarvis_alerting_emit(self):
        calls = []

        class _Runtime:
            class AlertEvent:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            @staticmethod
            def emit(event, dry_run=False, **kwargs):
                calls.append({"event": event, "dry_run": dry_run, "kwargs": kwargs})
                return SimpleNamespace(
                    suppressed=False,
                    dry_run=dry_run,
                    attempts=[
                        SimpleNamespace(destination_name="ops", status="sent"),
                    ],
                )

        original = getattr(telegram_hub, "_load_jarvis_alerting", None)
        telegram_hub._load_jarvis_alerting = lambda: _Runtime()
        try:
            result = telegram_hub.send_to_destinations(
                alert_key="schedule_audit",
                messages=["Bridge report"],
                parse_mode="HTML",
            )
        finally:
            if original is None:
                delattr(telegram_hub, "_load_jarvis_alerting")
            else:
                telegram_hub._load_jarvis_alerting = original

        self.assertEqual(result, {"ops": "ok"})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["event"].alert_key, "schedule_audit")


if __name__ == "__main__":
    unittest.main()
