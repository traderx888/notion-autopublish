from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import telegram_schedule_audit as audit


class TelegramScheduleAuditTests(unittest.TestCase):
    def test_extract_daily_reminder_config_reads_tasks_and_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily_reminders.py"
            path.write_text(
                "\n".join(
                    [
                        "TASKS = {",
                        "    'morning_digest': {'time': '07:00', 'title': 'Morning'},",
                        "    'excel': {'time': '10:00', 'title': 'Excel'},",
                        "}",
                        "TASK_ALIASES = {",
                        "    'pam_check': 'p_model_check',",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            tasks, aliases = audit.extract_daily_reminder_config(path)

            self.assertIn("morning_digest", tasks)
            self.assertEqual(tasks["excel"]["time"], "10:00")
            self.assertEqual(aliases["pam_check"], "p_model_check")

    def test_extract_daily_reminder_config_supports_annotated_assignments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "daily_reminders.py"
            path.write_text(
                "\n".join(
                    [
                        "from typing import Dict",
                        "TASKS: Dict[str, Dict[str, str]] = {",
                        "    'southbound': {'time': '15:30', 'title': 'Southbound'},",
                        "}",
                        "TASK_ALIASES: Dict[str, str] = {'pam_check': 'p_model_check'}",
                    ]
                ),
                encoding="utf-8",
            )

            tasks, aliases = audit.extract_daily_reminder_config(path)

            self.assertIn("southbound", tasks)
            self.assertEqual(aliases["pam_check"], "p_model_check")

    def test_parse_scheduler_query_output_keeps_relevant_tasks_and_normalizes_keys(self):
        scheduler_text = "\n".join(
            [
                "TaskName:                             \\JARVIS-Reminder-morning_digest",
                "Status:                               Ready",
                "Task To Run:                          python daily_reminders.py --task morning_digest",
                "Start In:                             C:\\Users\\User\\Documents\\GitHub\\fundman-jarvis",
                "Schedule Type:                        Weekly",
                "Start Time:                           7:00:00",
                "Days:                                 MON, TUE, WED, THU, FRI",
                "",
                "TaskName:                             \\Fundman-Storyteller-1030",
                "Status:                               Ready",
                'Task To Run:                          cmd /c "C:\\Users\\User\\Documents\\GitHub\\fundman-jarvis\\run_daily_reminder.bat story_1030"',
                "Schedule Type:                        Daily",
                "Start Time:                           10:30:00",
                "",
                "TaskName:                             \\TelegramHubHourly",
                "Status:                               Disabled",
                "Task To Run:                          C:\\Users\\User\\Documents\\GitHub\\notion-autopublish\\tools\\run_telegram_hub.bat",
                "Schedule Type:                        One Time Only, Hourly",
                "Start Time:                           16:26:00",
                "Repeat: Every:                        1 Hour(s), 0 Minute(s)",
                "",
                "TaskName:                             \\Bloomberg Updater",
                "Status:                               Ready",
                "Task To Run:                          C:\\blp\\Wintrv\\clientratermgr.exe",
            ]
        )

        rows = audit.parse_scheduler_query_output(scheduler_text)
        by_key = {row["task_key"]: row for row in rows}

        self.assertEqual(set(by_key), {"morning_digest", "story_1030", "telegram_hub_hourly"})
        self.assertEqual(by_key["story_1030"]["scheduler_name"], "Fundman-Storyteller-1030")
        self.assertFalse(by_key["telegram_hub_hourly"]["enabled"])
        self.assertEqual(by_key["morning_digest"]["schedule_text"], "Mon-Fri 07:00 HKT")

    def test_normalize_task_key_handles_named_scheduler_wrappers(self):
        self.assertEqual(audit.normalize_task_key("Fundman-Telegram-Ops-Listener"), "fundman_telegram_ops_listener")
        self.assertEqual(audit.normalize_task_key("Jarvis Excel Sync AM"), "jarvis_excel_sync_am")
        self.assertEqual(audit.normalize_task_key("Jarvis Excel Sync PM"), "jarvis_excel_sync_pm")
        self.assertEqual(audit.normalize_task_key("Jarvis CBBC Tracker AM"), "jarvis_cbbc_tracker_am")
        self.assertEqual(
            audit.normalize_task_key(
                "JARVIS-Reminder-options-earnings-2100",
                command="C:\\Users\\User\\Documents\\GitHub\\fundman-jarvis\\run_options_expiry.bat",
            ),
            "options_earnings_2100",
        )
        self.assertEqual(
            audit.normalize_task_key(
                "JARVIS-Reminder-options-earnings-2330",
                command="C:\\Users\\User\\Documents\\GitHub\\fundman-jarvis\\run_options_expiry.bat",
            ),
            "options_earnings_2330",
        )
        self.assertEqual(
            audit.normalize_task_key("Crypto ETF Flow AM", command="run_crypto_etf_flows.bat morning"),
            "crypto_etf_flow_am",
        )
        self.assertEqual(
            audit.normalize_task_key("Crypto ETF Flow Mid", command="send_crypto_etf_flows.py --label midday"),
            "crypto_etf_flow_mid",
        )

    def test_audit_schedule_state_classifies_missing_in_control_and_enabled_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_fixture_repos(root)
            (root / "All-in-one" / "workflow").mkdir(parents=True)
            (root / "All-in-one" / "workflow" / "cross_repo_tasks.yaml").write_text(
                "\n".join(
                    [
                        "{",
                        '  "version": 1,',
                        '  "tasks": {',
                        '    "TelegramHubHourly": {',
                        '      "enabled": false,',
                        '      "owner_repo": "notion-autopublish",',
                        '      "schedule": "Hourly",',
                        '      "purpose": "Cross-repo Telegram digest"',
                        "    }",
                        "  }",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            scheduler_text = "\n".join(
                [
                    "TaskName:                             \\JARVIS-Reminder-morning_digest",
                    "Status:                               Ready",
                    "Task To Run:                          python daily_reminders.py --task morning_digest",
                    "Start In:                             C:\\Users\\User\\Documents\\GitHub\\fundman-jarvis",
                    "Schedule Type:                        Weekly",
                    "Start Time:                           7:00:00",
                    "Days:                                 MON, TUE, WED, THU, FRI",
                    "",
                    "TaskName:                             \\TelegramHubHourly",
                    "Status:                               Ready",
                    "Task To Run:                          C:\\Users\\User\\Documents\\GitHub\\notion-autopublish\\tools\\run_telegram_hub.bat",
                    "Schedule Type:                        One Time Only, Hourly",
                    "Start Time:                           16:26:00",
                    "Repeat: Every:                        1 Hour(s), 0 Minute(s)",
                ]
            )

            result = audit.audit_schedule_state(
                root=root,
                repos=["All-in-one", "fundman-jarvis", "notion-autopublish"],
                scheduler_text=scheduler_text,
            )
            by_key = {row["task_key"]: row for row in result["records"]}

            self.assertIn("missing_in_control", by_key["morning_digest"]["issues"])
            self.assertIn("enabled_mismatch", by_key["telegram_hub_hourly"]["issues"])

    def test_audit_schedule_state_marks_publish_workflow_informational(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_fixture_repos(root)
            (root / "All-in-one" / "workflow").mkdir(parents=True)
            (root / "All-in-one" / "workflow" / "cross_repo_tasks.yaml").write_text(
                '{"version": 1, "tasks": {}}',
                encoding="utf-8",
            )

            result = audit.audit_schedule_state(
                root=root,
                repos=["All-in-one", "fundman-jarvis", "notion-autopublish"],
                scheduler_text="",
            )
            by_key = {row["task_key"]: row for row in result["records"]}

            self.assertIn("notion_publish_daily", by_key)
            self.assertIn("info_only_schedule", by_key["notion_publish_daily"]["issues"])

    def test_discover_repo_sources_includes_wrapper_alert_senders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_fixture_repos(root)

            rows = audit.discover_repo_sources(
                root=root,
                repos=["All-in-one", "fundman-jarvis", "notion-autopublish"],
            )
            by_key = {row["task_key"]: row for row in rows}

            self.assertEqual(by_key["crypto_etf_flow_am"]["command"], "run_crypto_etf_flows.bat morning")
            self.assertEqual(by_key["crypto_etf_flow_am"]["schedule_text"], "Daily 09:00 HKT")
            self.assertEqual(by_key["crypto_etf_flow_mid"]["command"], "run_crypto_etf_flows.bat midday")
            self.assertEqual(by_key["crypto_etf_flow_mid"]["schedule_text"], "Daily 11:50 HKT")
            self.assertEqual(by_key["crypto_news_daily"]["command"], "run_crypto_news.bat")
            self.assertEqual(by_key["crypto_news_daily"]["schedule_text"], "Daily 11:00 HKT")
            self.assertEqual(by_key["options_earnings_2100"]["command"], "run_options_expiry.bat")
            self.assertEqual(by_key["options_earnings_2100"]["schedule_text"], "Daily 21:00 HKT")
            self.assertEqual(by_key["options_earnings_2330"]["command"], "run_options_expiry.bat")
            self.assertEqual(by_key["options_earnings_2330"]["schedule_text"], "Daily 23:30 HKT")
            self.assertEqual(by_key["portfolio_digest"]["command"], "run_portfolio_digest.bat")
            self.assertEqual(by_key["portfolio_digest"]["schedule_text"], "")

    def test_audit_schedule_state_adds_chart_metadata_and_lanes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_fixture_repos(root)
            (root / "All-in-one" / "workflow").mkdir(parents=True)
            (root / "All-in-one" / "workflow" / "cross_repo_tasks.yaml").write_text(
                "\n".join(
                    [
                        "{",
                        '  "version": 1,',
                        '  "tasks": {',
                        '    "TelegramHubHourly": {',
                        '      "enabled": false,',
                        '      "owner_repo": "notion-autopublish",',
                        '      "schedule": "Hourly"',
                        "    }",
                        "  }",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            scheduler_text = "\n".join(
                [
                    "TaskName:                             \\Jarvis CBBC Tracker AM",
                    "Status:                               Ready",
                    'Task To Run:                          "C:\\Python\\python.exe" "C:\\Users\\User\\Documents\\GitHub\\fundman-jarvis\\send_cbbc_tracker.py"',
                    "Schedule Type:                        Daily",
                    "Start Time:                           9:00:00",
                    "",
                    "TaskName:                             \\JARVIS_Portfolio_AM",
                    "Status:                               Ready",
                    "Task To Run:                          C:\\Users\\User\\Documents\\GitHub\\fundman-jarvis\\run_portfolio_commentary.bat",
                    "Schedule Type:                        Daily",
                    "Start Time:                           9:00:00",
                    "",
                    "TaskName:                             \\JARVIS_Portfolio_PM",
                    "Status:                               Ready",
                    "Task To Run:                          C:\\Users\\User\\Documents\\GitHub\\fundman-jarvis\\run_portfolio_commentary.bat",
                    "Schedule Type:                        Daily",
                    "Start Time:                           20:30:00",
                    "",
                    "TaskName:                             \\TelegramHubHourly",
                    "Status:                               Disabled",
                    "Task To Run:                          C:\\Users\\User\\Documents\\GitHub\\notion-autopublish\\tools\\run_telegram_hub.bat",
                    "Schedule Type:                        One Time Only, Hourly",
                    "Start Time:                           16:26:00",
                    "Repeat: Every:                        1 Hour(s), 0 Minute(s)",
                ]
            )

            result = audit.audit_schedule_state(
                root=root,
                repos=["All-in-one", "fundman-jarvis", "notion-autopublish"],
                scheduler_text=scheduler_text,
            )
            by_key = {row["task_key"]: row for row in result["records"]}

            self.assertEqual(by_key["jarvis_cbbc_tracker_am"]["display_name"], "HK CBBC Tracker (牛熊證)")
            self.assertEqual(by_key["jarvis_cbbc_tracker_am"]["lane"], "live_scheduler")
            self.assertEqual(by_key["jarvis_cbbc_tracker_am"]["time_slots"], ["09:00 HKT"])
            self.assertEqual(by_key["jarvis_portfolio_am"]["lane"], "live_scheduler")
            self.assertEqual(by_key["jarvis_portfolio_pm"]["time_slots"], ["20:30 HKT"])
            self.assertEqual(by_key["crypto_etf_flow_am"]["lane"], "repo_only")
            self.assertEqual(by_key["crypto_etf_flow_mid"]["time_slots"], ["11:50 HKT"])
            self.assertEqual(by_key["options_earnings_2100"]["lane"], "repo_only")
            self.assertEqual(by_key["options_earnings_2100"]["time_slots"], ["21:00 HKT"])
            self.assertIn("orphaned_wrapper", by_key["options_earnings_2100"]["issues"])
            self.assertEqual(by_key["options_earnings_2330"]["time_slots"], ["23:30 HKT"])
            self.assertIn("orphaned_wrapper", by_key["portfolio_digest"]["issues"])
            self.assertEqual(by_key["telegram_hub_hourly"]["lane"], "disabled")

    def test_build_report_contains_sections_and_checklist(self):
        records = [
            {
                "task_key": "morning_digest",
                "scheduler_name": "JARVIS-Reminder-morning_digest",
                "owner_repo": "fundman-jarvis",
                "source_type": "scheduler",
                "command": "python daily_reminders.py --task morning_digest",
                "schedule_text": "Mon-Fri 07:00 HKT",
                "enabled": True,
                "telegram_related": True,
                "observed_in": ["repo", "scheduler"],
                "issues": ["missing_in_control"],
            },
            {
                "task_key": "notion_publish_daily",
                "scheduler_name": "",
                "owner_repo": "notion-autopublish",
                "source_type": "workflow",
                "command": ".github/workflows/publish.yml",
                "schedule_text": "Daily 09:00 HKT",
                "enabled": True,
                "telegram_related": False,
                "observed_in": ["workflow"],
                "issues": ["info_only_schedule"],
            },
        ]

        report = audit.build_report(records=records)

        self.assertIn("<b>Summary</b>", report)
        self.assertIn("<b>Missing In Control</b>", report)
        self.assertIn("<b>Informational</b>", report)
        self.assertIn("<b>Checklist</b>", report)
        self.assertIn("Add or update control entry for <code>morning_digest</code>", report)

    def test_render_flow_markdown_contains_live_and_repo_only_rows(self):
        records = [
            {
                "task_key": "jarvis_cbbc_tracker_am",
                "display_name": "HK CBBC Tracker (牛熊證)",
                "lane": "live_scheduler",
                "source_group": "HK CBBC tracker",
                "source_detail": "SG Warrants bull/bear distribution",
                "time_slots": ["09:00 HKT"],
                "runtime_entry": "send_cbbc_tracker.py",
                "state_reason": "active scheduler job",
                "observed_in": ["repo", "scheduler"],
                "telegram_related": True,
            },
            {
                "task_key": "crypto_etf_flow_am",
                "display_name": "Crypto ETF Flow (AM)",
                "lane": "repo_only",
                "source_group": "Crypto ETF flow",
                "source_detail": "Pre-Market Crypto ETF cash flow summary",
                "time_slots": ["09:00 HKT"],
                "runtime_entry": "run_crypto_etf_flows.bat morning",
                "state_reason": "repo sender with no scheduler match",
                "observed_in": ["repo"],
                "telegram_related": True,
            },
            {
                "task_key": "crypto_etf_flow_mid",
                "display_name": "Crypto ETF Flow (Mid)",
                "lane": "repo_only",
                "source_group": "Crypto ETF flow",
                "source_detail": "Midday Crypto ETF cash flow update",
                "time_slots": ["11:50 HKT"],
                "runtime_entry": "run_crypto_etf_flows.bat midday",
                "state_reason": "repo sender with no scheduler match",
                "observed_in": ["repo"],
                "telegram_related": True,
            },
            {
                "task_key": "options_earnings_2100",
                "display_name": "Options & Earnings Alert (21:00)",
                "lane": "repo_only",
                "source_group": "Options + earnings reminders",
                "source_detail": "Expiring options contracts and Dash earnings reminder",
                "time_slots": ["21:00 HKT"],
                "runtime_entry": "run_options_expiry.bat",
                "state_reason": "repo sender with no scheduler match",
                "observed_in": ["repo"],
                "telegram_related": True,
            },
            {
                "task_key": "telegram_hub_hourly",
                "display_name": "Telegram Hub Hourly",
                "lane": "disabled",
                "source_group": "Cross-repo digest",
                "source_detail": "Hourly cross-repo Telegram digest",
                "time_slots": ["16:26 HKT"],
                "runtime_entry": "run_telegram_hub.bat",
                "state_reason": "disabled task",
                "observed_in": ["repo", "scheduler"],
                "telegram_related": True,
            },
        ]

        markdown = audit.render_flow_markdown(records)

        self.assertIn("# Telegram Alert Map", markdown)
        self.assertIn("## Live Scheduler Tasks", markdown)
        self.assertIn("## Repo-defined / Not Currently Scheduled", markdown)
        self.assertIn("## Disabled", markdown)
        self.assertIn("HK CBBC Tracker (牛熊證)", markdown)
        self.assertIn("Crypto ETF Flow (AM)", markdown)
        self.assertIn("Crypto ETF Flow (Mid)", markdown)
        self.assertIn("Options & Earnings Alert (21:00)", markdown)
        self.assertIn("| State | Time (HKT) | Display Name | Task Key | Source / Model | Runtime Path | Evidence |", markdown)

    def _write_fixture_repos(self, root: Path) -> None:
        fundman = root / "fundman-jarvis"
        notion = root / "notion-autopublish"
        (fundman / "tests").mkdir(parents=True)
        (notion / "tools").mkdir(parents=True)
        (notion / ".github" / "workflows").mkdir(parents=True)

        (fundman / "daily_reminders.py").write_text(
            "\n".join(
                [
                    "TASKS = {",
                    "    'morning_digest': {'time': '07:00', 'title': 'Morning'},",
                    "    'deepvue_dashboard': {'time': '15:30', 'title': 'DeepVue'},",
                    "}",
                    "TASK_ALIASES = {'pam_check': 'p_model_check'}",
                ]
            ),
            encoding="utf-8",
        )
        (fundman / "run_deepvue_dashboard.bat").write_text(
            "@echo off\npython daily_reminders.py --task deepvue_dashboard\n",
            encoding="utf-8",
        )
        (fundman / "run_sector_screenshots.bat").write_text(
            "@echo off\npython send_sector_screenshots.py\n",
            encoding="utf-8",
        )
        (fundman / "run_daily_reminder.bat").write_text(
            "@echo off\npython daily_reminders.py --task %1\n",
            encoding="utf-8",
        )
        (fundman / "run_cbbc_tracker.bat").write_text(
            "@echo off\npython send_cbbc_tracker.py\n",
            encoding="utf-8",
        )
        (fundman / "run_portfolio_commentary.bat").write_text(
            "@echo off\npython send_portfolio_commentary.py\n",
            encoding="utf-8",
        )
        (fundman / "run_crypto_etf_flows.bat").write_text(
            "@echo off\npython send_crypto_etf_flows.py --label %1\n",
            encoding="utf-8",
        )
        (fundman / "run_crypto_news.bat").write_text(
            "@echo off\npython send_crypto_news.py\n",
            encoding="utf-8",
        )
        (fundman / "run_options_expiry.bat").write_text(
            "@echo off\npython send_options_expiry.py\n",
            encoding="utf-8",
        )
        (fundman / "run_portfolio_digest.bat").write_text(
            "@echo off\npython send_portfolio_digest.py\n",
            encoding="utf-8",
        )
        (notion / "tools" / "run_telegram_hub.bat").write_text(
            "@echo off\npython \"%~dp0telegram_hub.py\" --send\n",
            encoding="utf-8",
        )
        (notion / ".github" / "workflows" / "publish.yml").write_text(
            "on:\n  schedule:\n    - cron: '0 1 * * *'\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
