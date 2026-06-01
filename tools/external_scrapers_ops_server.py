from __future__ import annotations

import argparse
import json
import subprocess
import threading
import uuid
import webbrowser
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from tools.external_scrapers_ops import (
    build_action_request,
    build_catalog_payload,
    build_status_payload,
    load_ops_state,
    save_ops_state,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FUNDMAN_ROOT = REPO_ROOT.parent / "fundman-jarvis"
HKT = timezone(timedelta(hours=8))


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>External Scrapers Ops</title>
<style>
  :root {
    --bg: #0a1220;
    --panel: #111c2d;
    --panel-2: #16243a;
    --border: #2e425f;
    --text: #e8eef7;
    --muted: #93a5bf;
    --accent: #58b7ff;
    --ok: #49c174;
    --warn: #e0b44c;
    --bad: #f26b6b;
    --run: #7eb6ff;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
    background: radial-gradient(circle at top, #17304d, var(--bg) 45%);
    color: var(--text);
    min-height: 100vh;
  }
  main { max-width: 1320px; margin: 0 auto; padding: 24px; }
  .hero {
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 20px;
  }
  .hero h1 { margin: 0; font-size: 30px; }
  .hero p { margin: 6px 0 0; color: var(--muted); max-width: 760px; }
  .meta { font-size: 13px; color: var(--muted); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
  .card {
    background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0)), var(--panel);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 18px;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.22);
  }
  .card-header {
    display: flex;
    gap: 10px;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 14px;
  }
  .card-title { font-size: 18px; font-weight: 700; }
  .chip {
    display: inline-flex;
    align-items: center;
    border-radius: 999px;
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border: 1px solid transparent;
  }
  .chip.ok { background: rgba(73,193,116,0.14); color: var(--ok); border-color: rgba(73,193,116,0.3); }
  .chip.stale, .chip.check_only { background: rgba(224,180,76,0.14); color: var(--warn); border-color: rgba(224,180,76,0.3); }
  .chip.missing, .chip.failed { background: rgba(242,107,107,0.14); color: var(--bad); border-color: rgba(242,107,107,0.3); }
  .chip.running { background: rgba(126,182,255,0.14); color: var(--run); border-color: rgba(126,182,255,0.3); }
  .meta-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 14px;
    margin-bottom: 14px;
  }
  .meta-item span { display: block; }
  .meta-item .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }
  .meta-item .value { font-size: 13px; margin-top: 2px; }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 14px; }
  button {
    border: 0;
    border-radius: 10px;
    padding: 10px 14px;
    cursor: pointer;
    font-weight: 700;
    background: var(--accent);
    color: #07111f;
  }
  button.secondary {
    background: transparent;
    color: var(--text);
    border: 1px solid var(--border);
  }
  button:disabled { opacity: 0.55; cursor: not-allowed; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.06); font-size: 13px; }
  th { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
  .artifact-list {
    margin: 0;
    padding-left: 18px;
    color: var(--muted);
    font-size: 12px;
  }
  .artifact-list li { margin: 4px 0; word-break: break-all; }
  .panel-title { margin: 28px 0 14px; font-size: 20px; }
  .tool-form {
    margin-top: 12px;
    display: grid;
    gap: 8px;
  }
  .tool-form label {
    display: grid;
    gap: 4px;
    font-size: 12px;
    color: var(--muted);
  }
  input, textarea {
    width: 100%;
    border-radius: 10px;
    border: 1px solid var(--border);
    background: var(--panel-2);
    color: var(--text);
    padding: 10px 12px;
    font: inherit;
  }
  textarea { min-height: 100px; resize: vertical; }
  .footer-note { margin-top: 20px; color: var(--muted); font-size: 12px; }
</style>
</head>
<body>
<main>
  <section class="hero">
    <div>
      <h1>External Scrapers Ops</h1>
      <p>Local-only operator dashboard for login state, artifact freshness, and one-click relogin or run actions across the full external scraper inventory.</p>
    </div>
    <div class="meta" id="metaLine">Loading...</div>
  </section>

  <section>
    <h2 class="panel-title">Fixed Sources</h2>
    <div class="grid" id="families"></div>
  </section>

  <section>
    <h2 class="panel-title">Advanced Tools</h2>
    <div class="grid" id="advancedTools"></div>
  </section>

  <div class="footer-note">This UI binds to <code>127.0.0.1</code> only and does not publish live scraper state to the public dashboard.</div>
</main>
<script>
const state = { status: null };

function prettyStatus(status) {
  return String(status || "missing").replaceAll("_", " ");
}

function isRunning(item) {
  return item && item.job && item.job.state === "running";
}

function safeText(value) {
  return value == null || value === "" ? "n/a" : String(value);
}

function buildFormValue(field, sourceId) {
  const raw = document.querySelector(`[data-source="${sourceId}"][name="${field.name}"]`);
  if (!raw) return undefined;
  if (field.type === "checkbox") return raw.checked;
  return raw.value;
}

function collectParams(item) {
  const params = {};
  for (const field of item.input_schema || []) {
    const value = buildFormValue(field, item.source_id);
    if (field.type === "checkbox") {
      if (value) params[field.name] = true;
      continue;
    }
    if (value != null && String(value).trim() !== "") {
      params[field.name] = value;
    }
  }
  return params;
}

async function runAction(sourceId, params) {
  const response = await fetch(`/api/action/${encodeURIComponent(sourceId)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params || {}),
  });
  const payload = await response.json();
  if (!response.ok && response.status !== 202) {
    alert(payload.error || `Action failed (${response.status})`);
  }
  await refreshStatus();
}

function renderFamilies() {
  const root = document.getElementById("families");
  root.innerHTML = "";
  for (const item of state.status.families) {
    const card = document.createElement("article");
    card.className = "card";
    const auth = item.auth || {};
    const latest = item.freshness && item.freshness.latest_at ? item.freshness.latest_at : auth.login_at;
    const running = isRunning(item);
    const actionLabel = item.action_kind === "relogin" ? "Re-login" : "Run now";
    const artifacts = (auth.outputs && auth.outputs.length ? auth.outputs : item.artifacts || []).map((value) => `<li>${value}</li>`).join("");
    const extraActions = (item.extra_actions || []).map((extra) => {
      const disabled = running ? "disabled" : "";
      return `<button class="secondary" ${disabled} data-extra-action="${extra.action_name}" data-source-id="${item.source_id}">${extra.label}</button>`;
    }).join("");
    const rows = (item.children || []).map((child) => `
      <tr>
        <td>${child.display_name}</td>
        <td><span class="chip ${child.status}">${prettyStatus(child.status)}</span></td>
      </tr>
    `).join("");
    card.innerHTML = `
      <div class="card-header">
        <div class="card-title">${item.display_name}</div>
        <span class="chip ${item.status}">${prettyStatus(item.status)}</span>
      </div>
      <div class="meta-grid">
        <div class="meta-item">
          <span class="label">Login status</span>
          <span class="value">${safeText(auth.status)}</span>
        </div>
        <div class="meta-item">
          <span class="label">Latest</span>
          <span class="value">${safeText(latest)}</span>
        </div>
        <div class="meta-item">
          <span class="label">Mode</span>
          <span class="value">${auth.check_only ? "check-only" : item.kind}</span>
        </div>
        <div class="meta-item">
          <span class="label">Last rc</span>
          <span class="value">${safeText(item.job && item.job.return_code)}</span>
        </div>
      </div>
      <div class="actions">
        ${item.action_kind ? `<button ${running ? "disabled" : ""} data-source-id="${item.source_id}">${actionLabel}</button>` : ""}
        ${extraActions}
      </div>
      ${rows ? `<table><thead><tr><th>Child</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table>` : ""}
      ${artifacts ? `<ul class="artifact-list">${artifacts}</ul>` : ""}
    `;
    root.appendChild(card);
  }
}

function renderAdvancedTools() {
  const root = document.getElementById("advancedTools");
  root.innerHTML = "";
  for (const item of state.status.advanced_tools) {
    const card = document.createElement("article");
    card.className = "card";
    const running = isRunning(item);
    const fields = (item.input_schema || []).map((field) => {
      if (field.type === "textarea") {
        return `<label>${field.label}<textarea data-source="${item.source_id}" name="${field.name}" placeholder="${field.placeholder || ""}">${field.default || ""}</textarea></label>`;
      }
      if (field.type === "checkbox") {
        const checked = field.default ? "checked" : "";
        return `<label><span>${field.label}</span><input data-source="${item.source_id}" name="${field.name}" type="checkbox" ${checked}></label>`;
      }
      return `<label>${field.label}<input data-source="${item.source_id}" name="${field.name}" type="${field.type || "text"}" value="${field.default || ""}" placeholder="${field.placeholder || ""}"></label>`;
    }).join("");
    card.innerHTML = `
      <div class="card-header">
        <div class="card-title">${item.display_name}</div>
        <span class="chip ${item.status}">${prettyStatus(item.status)}</span>
      </div>
      <div class="meta-grid">
        <div class="meta-item">
          <span class="label">Last started</span>
          <span class="value">${safeText(item.job && item.job.started_at)}</span>
        </div>
        <div class="meta-item">
          <span class="label">Last finished</span>
          <span class="value">${safeText(item.job && item.job.finished_at)}</span>
        </div>
      </div>
      <div class="tool-form">${fields}</div>
      <div class="actions" style="margin-top:12px;">
        <button ${running ? "disabled" : ""} data-source-id="${item.source_id}" data-tool-action="run">Run</button>
      </div>
    `;
    root.appendChild(card);
  }
}

function wireButtons() {
  document.querySelectorAll("button[data-source-id]").forEach((button) => {
    button.onclick = async () => {
      const sourceId = button.getAttribute("data-source-id");
      const item = state.status.families.find((entry) => entry.source_id === sourceId)
        || state.status.advanced_tools.find((entry) => entry.source_id === sourceId);
      const params = item && item.kind === "parameterized_tool" ? collectParams(item) : {};
      const extraAction = button.getAttribute("data-extra-action");
      if (extraAction) {
        params.action_name = extraAction;
      }
      await runAction(sourceId, params);
    };
  });
}

async function refreshStatus() {
  const response = await fetch("/api/status");
  state.status = await response.json();
  document.getElementById("metaLine").textContent = `Updated ${state.status.generated_at}`;
  renderFamilies();
  renderAdvancedTools();
  wireButtons();
}

refreshStatus().then(() => {
  window.setInterval(refreshStatus, 5000);
}).catch((error) => {
  document.getElementById("metaLine").textContent = `Load failed: ${error}`;
});
</script>
</body>
</html>
"""


class OpsServerApp:
    def __init__(
        self,
        *,
        repo_root: Path,
        fundman_root: Path,
        launch_process: Any | None = None,
    ) -> None:
        self.repo_root = Path(repo_root)
        self.fundman_root = Path(fundman_root)
        self.launch_process = launch_process or self._launch_process
        self._lock = threading.Lock()
        self.jobs: dict[str, dict[str, Any]] = load_ops_state(self.repo_root).get("jobs", {})

    def _launch_process(self, command: list[str], cwd: str):
        return subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def render_index(self) -> str:
        return INDEX_HTML

    def get_catalog(self) -> dict[str, Any]:
        return build_catalog_payload(repo_root=self.repo_root, fundman_root=self.fundman_root)

    def get_status(self) -> dict[str, Any]:
        return build_status_payload(
            repo_root=self.repo_root,
            fundman_root=self.fundman_root,
            jobs=self.jobs,
        )

    def _save_jobs(self) -> None:
        save_ops_state(self.repo_root, self.jobs)

    def _monitor_process(self, source_id: str, process: Any) -> None:
        stdout = ""
        stderr = ""
        try:
            if hasattr(process, "communicate"):
                stdout, stderr = process.communicate()
                return_code = process.returncode
            else:
                return_code = process.wait()
        except Exception as exc:
            return_code = 1
            stderr = str(exc)

        finished_at = datetime.now(HKT).isoformat(timespec="seconds")
        output_tail = (stdout or "") + ("\n" + stderr if stderr else "")
        output_tail = output_tail[-4000:] if output_tail else ""

        with self._lock:
            job = dict(self.jobs.get(source_id) or {})
            job["state"] = "succeeded" if return_code == 0 else "failed"
            job["finished_at"] = finished_at
            job["return_code"] = return_code
            job["output_tail"] = output_tail
            self.jobs[source_id] = job
            self._save_jobs()

    def start_action(self, source_id: str, params: dict[str, Any] | None) -> dict[str, Any]:
        params = dict(params or {})
        with self._lock:
            current_job = self.jobs.get(source_id)
            if current_job and current_job.get("state") == "running":
                return {
                    "accepted": False,
                    "status_code": HTTPStatus.CONFLICT,
                    "error": "job_already_running",
                    "job": current_job,
                }

            try:
                request = build_action_request(
                    source_id,
                    params,
                    repo_root=self.repo_root,
                    fundman_root=self.fundman_root,
                )
            except KeyError:
                return {
                    "accepted": False,
                    "status_code": HTTPStatus.NOT_FOUND,
                    "error": "unknown_source_id",
                }
            except Exception as exc:
                return {
                    "accepted": False,
                    "status_code": HTTPStatus.INTERNAL_SERVER_ERROR,
                    "error": str(exc),
                }

            try:
                process = self.launch_process(request["command"], request["cwd"])
            except Exception as exc:
                return {
                    "accepted": False,
                    "status_code": HTTPStatus.INTERNAL_SERVER_ERROR,
                    "error": str(exc),
                }

            job = {
                "job_id": uuid.uuid4().hex,
                "source_id": source_id,
                "state": "running",
                "command": request["command"],
                "cwd": request["cwd"],
                "started_at": datetime.now(HKT).isoformat(timespec="seconds"),
                "finished_at": None,
                "return_code": None,
                "output_tail": "",
                "params": params,
            }
            self.jobs[source_id] = job
            self._save_jobs()

        thread = threading.Thread(
            target=self._monitor_process,
            args=(source_id, process),
            daemon=True,
        )
        thread.start()
        return {
            "accepted": True,
            "status_code": HTTPStatus.ACCEPTED,
            "job": job,
        }


def create_http_server(app: OpsServerApp, *, host: str = "127.0.0.1", port: int = 8765):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/":
                body = app.render_index().encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path == "/api/catalog":
                self._write_json(HTTPStatus.OK, app.get_catalog())
                return
            if self.path == "/api/status":
                self._write_json(HTTPStatus.OK, app.get_status())
                return
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

        def do_POST(self) -> None:
            if not self.path.startswith("/api/action/"):
                self._write_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                return

            source_id = unquote(self.path.removeprefix("/api/action/"))
            length = int(self.headers.get("Content-Length", "0") or "0")
            raw_body = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw_body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                payload = {}

            result = app.start_action(source_id, payload)
            status_code = int(result.pop("status_code"))
            self._write_json(status_code, result)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, port), Handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local-only external scrapers ops dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--fundman-root", type=Path, default=DEFAULT_FUNDMAN_ROOT)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()

    app = OpsServerApp(repo_root=REPO_ROOT, fundman_root=args.fundman_root)
    server = create_http_server(app, host=args.host, port=args.port)
    address = f"http://{args.host}:{server.server_port}/"
    print(f"External Scrapers Ops listening on {address}")
    if args.open_browser:
        webbrowser.open(address)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
