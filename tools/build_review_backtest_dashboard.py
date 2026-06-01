from __future__ import annotations

import argparse
import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUTS_DIR = REPO_ROOT / "outputs"
DEFAULT_REVIEW_DIR = REPO_ROOT / "review"
DEFAULT_DASHBOARD_PATH = REPO_ROOT / "output" / "review_backtest_dashboard.html"
DEFAULT_SNAPSHOT_PATH = DEFAULT_OUTPUTS_DIR / "backtest" / "review_backtest_dashboard_latest.json"
STATUS_ORDER = ("Hit", "Partial Hit", "Miss", "Pending")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _float_or_none(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def discover_backtest_csvs(outputs_dir: Path) -> list[Path]:
    if not outputs_dir.exists():
        return []
    return sorted(
        {
            path
            for path in outputs_dir.rglob("backtest*.csv")
            if path.is_file() and "history" not in path.name.lower()
        },
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def read_backtest_rows(outputs_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for csv_path in discover_backtest_csvs(outputs_dir):
        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                row = dict(row)
                row["source_file"] = str(csv_path.relative_to(outputs_dir))
                row["alpha_pct_num"] = _float_or_none(row.get("alpha_pct"))
                row["strategy_return_pct_num"] = _float_or_none(row.get("strategy_return_pct"))
                row["benchmark_return_pct_num"] = _float_or_none(row.get("benchmark_return_pct"))
                rows.append(row)
    return rows


def discover_review_reports(review_dir: Path) -> list[dict[str, Any]]:
    if not review_dir.exists():
        return []

    reports = []
    for path in sorted(review_dir.glob("review_*.md"), key=lambda item: item.stat().st_mtime, reverse=True):
        text = path.read_text(encoding="utf-8")
        reports.append(
            {
                "file": path.name,
                "modifiedAt": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
                "lineCount": len(text.splitlines()),
                "sectionCount": text.count("## "),
                "preview": " ".join(line.strip() for line in text.splitlines() if line.strip())[:240],
            }
        )
    return reports


def summarize_backtests(rows: list[dict[str, Any]], csvs: list[Path], outputs_dir: Path) -> dict[str, Any]:
    status_counts = {status: 0 for status in STATUS_ORDER}
    for row in rows:
        status = row.get("status") or "Pending"
        status_counts[status] = status_counts.get(status, 0) + 1

    graded_total = sum(status_counts.get(status, 0) for status in ("Hit", "Partial Hit", "Miss"))
    weighted_hits = status_counts.get("Hit", 0) + 0.5 * status_counts.get("Partial Hit", 0)
    hit_rate = round(weighted_hits / graded_total * 100, 1) if graded_total else None
    alpha_values = [row["alpha_pct_num"] for row in rows if row.get("alpha_pct_num") is not None]

    latest_rows = sorted(
        rows,
        key=lambda row: (row.get("publish_date") or "", row.get("title") or ""),
        reverse=True,
    )[:12]
    return {
        "csvFiles": [str(path.relative_to(outputs_dir)) for path in csvs],
        "totalRows": len(rows),
        "statusCounts": status_counts,
        "gradedHitRatePct": hit_rate,
        "avgAlphaPct": round(mean(alpha_values), 2) if alpha_values else None,
        "latestRows": latest_rows,
    }


def build_snapshot(outputs_dir: Path = DEFAULT_OUTPUTS_DIR, review_dir: Path = DEFAULT_REVIEW_DIR) -> dict[str, Any]:
    csvs = discover_backtest_csvs(outputs_dir)
    rows = read_backtest_rows(outputs_dir)
    reports = discover_review_reports(review_dir)
    return {
        "generatedAt": _now_iso(),
        "backtests": summarize_backtests(rows, csvs, outputs_dir),
        "reviews": {
            "totalReports": len(reports),
            "latestReports": reports[:8],
        },
        "artifacts": {
            "outputsDir": str(outputs_dir),
            "reviewDir": str(review_dir),
        },
    }


def _badge_class(status: str) -> str:
    return {
        "Hit": "badge hit",
        "Partial Hit": "badge partial",
        "Miss": "badge miss",
        "Pending": "badge pending",
    }.get(status, "badge pending")


def _render_latest_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return '<div class="empty">No backtest CSVs found. Run the backtest command below to create one.</div>'

    body = []
    for row in rows:
        status = row.get("status") or "Pending"
        body.append(
            "<tr>"
            f"<td>{html.escape(row.get('publish_date') or '')}</td>"
            f"<td>{html.escape(row.get('title') or '')}</td>"
            f"<td>{html.escape(row.get('direction') or '')}</td>"
            f"<td>{html.escape(row.get('tickers') or '')}</td>"
            f"<td class=\"num\">{html.escape(str(row.get('strategy_return_pct') or ''))}</td>"
            f"<td class=\"num\">{html.escape(str(row.get('benchmark_return_pct') or ''))}</td>"
            f"<td class=\"num\">{html.escape(str(row.get('alpha_pct') or ''))}</td>"
            f"<td><span class=\"{_badge_class(status)}\">{html.escape(status)}</span></td>"
            f"<td>{html.escape(row.get('source_file') or '')}</td>"
            "</tr>"
        )
    return (
        "<table>"
        "<thead><tr><th>Date</th><th>Thesis</th><th>Direction</th><th>Tickers</th>"
        "<th>Strategy</th><th>Benchmark</th><th>Alpha</th><th>Status</th><th>File</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def _render_reports(reports: list[dict[str, Any]]) -> str:
    if not reports:
        return '<div class="empty">No review reports found. Save Codex review output as <code>review/review_YYYY-MM-DD.md</code>.</div>'

    cards = []
    for report in reports:
        cards.append(
            '<div class="report">'
            f"<div><strong>{html.escape(report['file'])}</strong><span>{html.escape(report['modifiedAt'])}</span></div>"
            f"<p>{html.escape(report['preview'])}</p>"
            f"<small>{report['lineCount']} lines · {report['sectionCount']} sections</small>"
            "</div>"
        )
    return "".join(cards)


def render_html(snapshot: dict[str, Any]) -> str:
    backtests = snapshot["backtests"]
    reviews = snapshot["reviews"]
    status_counts = backtests["statusCounts"]
    csv_files = backtests["csvFiles"]
    generated_at = html.escape(snapshot["generatedAt"])
    csv_list = "".join(f"<li>{html.escape(item)}</li>" for item in csv_files) or "<li>No local CSV files yet</li>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Review / Backtest Monitor</title>
<style>
:root {{
  --bg: #f6f8fb;
  --surface: #ffffff;
  --ink: #172033;
  --muted: #667085;
  --border: #d9e0ea;
  --blue: #2563eb;
  --green: #1f9d55;
  --amber: #b7791f;
  --red: #d92d20;
  --slate: #475467;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
  line-height: 1.45;
}}
header {{
  padding: 24px 32px 18px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}}
h1 {{ margin: 0; font-size: 26px; font-weight: 700; }}
.sub {{ margin-top: 5px; color: var(--muted); font-size: 14px; }}
main {{ padding: 24px 32px 36px; max-width: 1440px; margin: 0 auto; }}
.metrics {{ display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap: 12px; margin-bottom: 18px; }}
.metric, .panel {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
}}
.label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }}
.value {{ margin-top: 5px; font-size: 24px; font-weight: 700; }}
.grid {{ display: grid; grid-template-columns: 1.6fr .9fr; gap: 16px; }}
h2 {{ margin: 0 0 12px; font-size: 17px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ text-align: left; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; padding: 8px; border-bottom: 1px solid var(--border); }}
td {{ padding: 8px; border-bottom: 1px solid #edf1f6; vertical-align: top; }}
.num {{ font-variant-numeric: tabular-nums; }}
.badge {{ display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 12px; font-weight: 700; white-space: nowrap; }}
.hit {{ color: var(--green); background: #e7f7ed; }}
.partial {{ color: var(--amber); background: #fff5db; }}
.miss {{ color: var(--red); background: #fdeceb; }}
.pending {{ color: var(--slate); background: #eef2f6; }}
.empty {{ border: 1px dashed var(--border); border-radius: 8px; padding: 18px; color: var(--muted); background: #fbfcfe; }}
.report {{ padding: 12px 0; border-bottom: 1px solid #edf1f6; }}
.report:last-child {{ border-bottom: 0; }}
.report div {{ display: flex; gap: 8px; justify-content: space-between; align-items: baseline; }}
.report span, .report small {{ color: var(--muted); font-size: 12px; }}
.report p {{ margin: 7px 0 6px; color: var(--slate); font-size: 13px; }}
.commands {{ margin-top: 16px; }}
code, pre {{ font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; }}
pre {{ overflow-x: auto; padding: 12px; border-radius: 8px; background: #101828; color: #f8fafc; font-size: 12px; }}
ul {{ margin: 8px 0 0; padding-left: 18px; color: var(--slate); font-size: 13px; }}
@media (max-width: 980px) {{
  .metrics, .grid {{ grid-template-columns: 1fr; }}
  main, header {{ padding-left: 16px; padding-right: 16px; }}
}}
</style>
</head>
<body>
<header>
  <h1>Review / Backtest Monitor</h1>
  <div class="sub">Local thesis review and quantitative backtest status · generated {generated_at}</div>
</header>
<main>
  <section class="metrics">
    <div class="metric"><div class="label">Backtest Rows</div><div class="value">{backtests['totalRows']}</div></div>
    <div class="metric"><div class="label">Hit Rate</div><div class="value">{_pct(backtests['gradedHitRatePct'])}</div></div>
    <div class="metric"><div class="label">Avg Alpha</div><div class="value">{_pct(backtests['avgAlphaPct'])}</div></div>
    <div class="metric"><div class="label">Review Reports</div><div class="value">{reviews['totalReports']}</div></div>
  </section>
  <section class="metrics">
    <div class="metric"><div class="label">Hit</div><div class="value">{status_counts.get('Hit', 0)}</div></div>
    <div class="metric"><div class="label">Partial</div><div class="value">{status_counts.get('Partial Hit', 0)}</div></div>
    <div class="metric"><div class="label">Miss</div><div class="value">{status_counts.get('Miss', 0)}</div></div>
    <div class="metric"><div class="label">Pending</div><div class="value">{status_counts.get('Pending', 0)}</div></div>
  </section>
  <section class="grid">
    <div class="panel">
      <h2>Latest Backtest Rows</h2>
      {_render_latest_rows(backtests['latestRows'])}
    </div>
    <div class="panel">
      <h2>Review Reports</h2>
      {_render_reports(reviews['latestReports'])}
      <div class="commands">
        <h2>Tracked Backtest Files</h2>
        <ul>{csv_list}</ul>
      </div>
      <div class="commands">
        <h2>Runbook</h2>
        <pre>python backtest/run_backtest.py --quarter 2026Q1 --benchmark SPY --output outputs/backtest_2026Q1.csv
python tools/build_review_backtest_dashboard.py</pre>
      </div>
    </div>
  </section>
</main>
</body>
</html>
"""


def build_dashboard(
    *,
    outputs_dir: Path = DEFAULT_OUTPUTS_DIR,
    review_dir: Path = DEFAULT_REVIEW_DIR,
    dashboard_path: Path = DEFAULT_DASHBOARD_PATH,
    snapshot_path: Path | None = None,
) -> dict[str, Any]:
    snapshot = build_snapshot(outputs_dir=outputs_dir, review_dir=review_dir)
    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    dashboard_path.write_text(render_html(snapshot), encoding="utf-8")

    resolved_snapshot_path = snapshot_path or outputs_dir / "backtest" / "review_backtest_dashboard_latest.json"
    resolved_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the local review/backtest monitor dashboard.")
    parser.add_argument("--outputs-dir", type=Path, default=DEFAULT_OUTPUTS_DIR)
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD_PATH)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT_PATH)
    args = parser.parse_args()

    snapshot = build_dashboard(
        outputs_dir=args.outputs_dir,
        review_dir=args.review_dir,
        dashboard_path=args.dashboard,
        snapshot_path=args.snapshot,
    )
    print(f"Dashboard output: {args.dashboard}")
    print(f"Snapshot output: {args.snapshot}")
    print(f"Backtest rows: {snapshot['backtests']['totalRows']}")
    print(f"Review reports: {snapshot['reviews']['totalReports']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
