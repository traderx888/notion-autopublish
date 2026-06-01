from __future__ import annotations

import unittest

from tools import alert_router


class AlertRouterWrapperTests(unittest.TestCase):
    def test_get_active_destinations_uses_jarvis_alerting_config(self):
        class _Config:
            @staticmethod
            def load_routing_config(path=None):
                return {"alerts": {"schedule_audit": {"destinations": ["ops"]}}}

            @staticmethod
            def resolve_destinations(alert_key, config):
                self.assertEqual(alert_key, "schedule_audit")
                self.assertIn("schedule_audit", config["alerts"])
                return [{"name": "ops", "type": "telegram"}]

        class _Cli:
            @staticmethod
            def main(argv=None):
                return 0

        class _Runtime:
            config = _Config()
            cli = _Cli()

        original = getattr(alert_router, "_load_jarvis_alerting", None)
        alert_router._load_jarvis_alerting = lambda: _Runtime()
        try:
            assert alert_router.get_active_destinations("schedule_audit") == [{"name": "ops", "type": "telegram"}]
            assert alert_router.main(["list"]) == 0
        finally:
            if original is None:
                delattr(alert_router, "_load_jarvis_alerting")
            else:
                alert_router._load_jarvis_alerting = original


if __name__ == "__main__":
    unittest.main()
