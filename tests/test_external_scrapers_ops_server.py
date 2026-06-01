from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


def _http_get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _http_post_json(url: str, payload: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class _BlockingProcess:
    def __init__(self, release_event: threading.Event):
        self._release_event = release_event
        self.returncode = None

    def wait(self) -> int:
        self._release_event.wait(timeout=5)
        self.returncode = 0
        return 0


@pytest.fixture
def server_module():
    import importlib

    return importlib.import_module("tools.external_scrapers_ops_server")


def test_http_api_returns_grouped_catalog_and_separates_advanced_tools(tmp_path: Path, server_module):
    repo_root = tmp_path / "notion-autopublish"
    fundman_root = tmp_path / "fundman-jarvis"
    fundman_root.mkdir(parents=True, exist_ok=True)
    (fundman_root / "external_scrapers.py").write_text("# test inventory anchor\n", encoding="utf-8")

    app = server_module.OpsServerApp(repo_root=repo_root, fundman_root=fundman_root)
    httpd = server_module.create_http_server(app, host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_port}"
        catalog = _http_get_json(f"{base}/api/catalog")
        status = _http_get_json(f"{base}/api/status")
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)

    family_ids = {item["source_id"] for item in catalog["families"]}
    advanced_ids = {item["source_id"] for item in catalog["advanced_tools"]}
    assert "deepvue" in family_ids
    assert "substack" in family_ids
    assert "twitter_search" in advanced_ids
    assert "notebooklm_research" in advanced_ids
    assert "families" in status
    assert "advanced_tools" in status


def test_start_action_rejects_duplicate_running_jobs(tmp_path: Path, server_module):
    repo_root = tmp_path / "notion-autopublish"
    fundman_root = tmp_path / "fundman-jarvis"
    fundman_root.mkdir(parents=True, exist_ok=True)
    (fundman_root / "external_scrapers.py").write_text("# test inventory anchor\n", encoding="utf-8")

    release = threading.Event()
    launched = []

    def fake_launch(command: list[str], cwd: str):
        launched.append((command, cwd))
        return _BlockingProcess(release)

    app = server_module.OpsServerApp(
        repo_root=repo_root,
        fundman_root=fundman_root,
        launch_process=fake_launch,
    )

    first = app.start_action("institutional", {})
    second = app.start_action("institutional", {})
    assert first["accepted"] is True
    assert second["accepted"] is False
    assert second["status_code"] == 409
    assert len(launched) == 1

    release.set()
    for _ in range(50):
        job = app.jobs.get("institutional")
        if not job or job.get("state") != "running":
            break
        time.sleep(0.02)


def test_http_post_action_returns_conflict_for_duplicate_job(tmp_path: Path, server_module):
    repo_root = tmp_path / "notion-autopublish"
    fundman_root = tmp_path / "fundman-jarvis"
    fundman_root.mkdir(parents=True, exist_ok=True)
    (fundman_root / "external_scrapers.py").write_text("# test inventory anchor\n", encoding="utf-8")

    release = threading.Event()

    def fake_launch(command: list[str], cwd: str):
        return _BlockingProcess(release)

    app = server_module.OpsServerApp(
        repo_root=repo_root,
        fundman_root=fundman_root,
        launch_process=fake_launch,
    )
    httpd = server_module.create_http_server(app, host="127.0.0.1", port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_port}"
        status_one, body_one = _http_post_json(f"{base}/api/action/institutional")
        status_two, body_two = _http_post_json(f"{base}/api/action/institutional")
    finally:
        release.set()
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)

    assert status_one == 202
    assert body_one["job"]["state"] == "running"
    assert status_two == 409
    assert body_two["error"] == "job_already_running"
