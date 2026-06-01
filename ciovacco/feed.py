from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import requests
from yt_dlp import YoutubeDL

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANNEL_ID = "UC_ywfvIR2JrnMuZt33y7QYQ"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "scraped_data" / "ciovacco"
DEFAULT_PREVIEW_DIR = PROJECT_ROOT / "output"
FEED_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
}
KEYWORDS = (
    "AVWAP",
    "Bollinger",
    "VIX",
    "breadth",
    "rotation",
    "risk-on",
    "risk-off",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_output_dir(output_dir: str | Path | None = None) -> Path:
    if output_dir is None:
        output_dir = os.getenv("CIOVACCO_OUTPUT_DIR", str(DEFAULT_OUTPUT_DIR))
    path = Path(output_dir).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_preview_targets(resolved_output_dir: Path) -> list[Path]:
    preview_paths = [resolved_output_dir / "ciovacco_latest_preview.html"]
    repo_output_preview = DEFAULT_PREVIEW_DIR / "ciovacco_latest_preview.html"
    if repo_output_preview not in preview_paths:
        repo_output_preview.parent.mkdir(parents=True, exist_ok=True)
        preview_paths.append(repo_output_preview)
    return preview_paths


def _feed_url(channel_id: str) -> str:
    return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


def schedule_metadata() -> dict[str, str]:
    return {
        "primary_run": "Saturday 14:00 HKT",
        "recheck_run": "Sunday 14:00 HKT",
    }


def parse_latest_feed_entry(xml_text: str) -> dict[str, str]:
    root = ET.fromstring(xml_text)
    entries: list[dict[str, str]] = []
    for entry in root.findall("atom:entry", FEED_NAMESPACES):
        video_id = (entry.findtext("yt:videoId", default="", namespaces=FEED_NAMESPACES) or "").strip()
        title = (entry.findtext("atom:title", default="", namespaces=FEED_NAMESPACES) or "").strip()
        published = (entry.findtext("atom:published", default="", namespaces=FEED_NAMESPACES) or "").strip()
        updated = (entry.findtext("atom:updated", default="", namespaces=FEED_NAMESPACES) or "").strip()
        video_url = ""
        for link in entry.findall("atom:link", FEED_NAMESPACES):
            if link.get("rel") == "alternate":
                video_url = link.get("href", "").strip()
                break
        if not video_url and video_id:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
        if video_id:
            entries.append(
                {
                    "video_id": video_id,
                    "title": title,
                    "video_url": video_url,
                    "published": published,
                    "updated": updated,
                }
            )
    if not entries:
        raise ValueError("No CiovaccoCapital feed entries found")
    entries.sort(key=lambda item: item.get("published", ""), reverse=True)
    return entries[0]


def _discover_latest_video(channel_id: str, session: requests.sessions.Session | None = None) -> dict[str, str]:
    client = session or requests
    response = client.get(_feed_url(channel_id), timeout=30)
    response.raise_for_status()
    return parse_latest_feed_entry(response.text)


def _extract_video_info(video_url: str) -> dict:
    with YoutubeDL({"quiet": True, "skip_download": True, "no_warnings": True}) as ydl:
        return ydl.extract_info(video_url, download=False)


def _language_priority(captions: dict | None) -> list[str]:
    keys = list((captions or {}).keys())
    preferred = [key for key in ("en", "en-US", "en-GB") if key in keys]
    others = sorted(key for key in keys if key not in preferred and key.lower().startswith("en"))
    return preferred + others


def _choose_track(captions: dict | None, kind: str) -> dict | None:
    if not captions:
        return None
    for language in _language_priority(captions):
        tracks = captions.get(language) or []
        preferred = next((track for track in tracks if track.get("ext") == "vtt" and track.get("url")), None)
        chosen = preferred or next((track for track in tracks if track.get("url")), None)
        if chosen is not None:
            return {
                "language": language,
                "kind": kind,
                "ext": chosen.get("ext", ""),
                "url": chosen.get("url", ""),
            }
    return None


def pick_preferred_caption_track(info: dict) -> dict | None:
    return _choose_track(info.get("subtitles"), "subtitles") or _choose_track(
        info.get("automatic_captions"),
        "automatic_captions",
    )


def _download_caption_text(track_url: str, session: requests.sessions.Session | None = None) -> str:
    client = session or requests
    response = client.get(track_url, timeout=30)
    response.raise_for_status()
    return response.text


def parse_vtt_captions(vtt_text: str) -> tuple[list[dict[str, str]], str]:
    segments: list[dict[str, str]] = []
    start = ""
    end = ""
    lines: list[str] = []

    def flush() -> None:
        nonlocal start, end, lines
        if start and lines:
            text = " ".join(lines).strip()
            if text:
                segments.append({"start": start, "end": end, "text": text})
        start = ""
        end = ""
        lines = []

    for raw_line in vtt_text.splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if line == "WEBVTT" or line.startswith("NOTE"):
            continue
        if re.fullmatch(r"\d+", line):
            continue
        if "-->" in line:
            flush()
            parts = [part.strip() for part in line.split("-->", 1)]
            start = parts[0]
            end = parts[1] if len(parts) > 1 else ""
            continue
        cleaned = re.sub(r"<[^>]+>", "", line)
        if cleaned:
            lines.append(cleaned)
    flush()
    transcript = "\n".join(segment["text"] for segment in segments).strip()
    return segments, transcript


def normalize_transcript_text(text: str) -> str:
    normalized_lines: list[str] = []
    previous = ""
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        if line == previous:
            continue
        normalized_lines.append(line)
        previous = line
    return "\n".join(normalized_lines)


def extract_ratio_mentions(text: str) -> list[dict[str, int]]:
    counts: Counter[str] = Counter()
    patterns = (
        re.compile(r"\b([A-Za-z]{2,5})\s*/\s*([A-Za-z]{2,5})\b"),
        re.compile(r"\b([A-Za-z]{2,5})\s+(?:versus|vs\.?|v\.)\s+([A-Za-z]{2,5})\b", re.IGNORECASE),
        re.compile(
            r"\b([A-Z]{2,5})\b(?:\s+[A-Za-z0-9&'-]+){0,4}\s+relative to\s+\b([A-Z]{2,5})\b"
        ),
    )
    for pattern in patterns:
        for left, right in pattern.findall(text):
            counts[f"{left.upper()}/{right.upper()}"] += 1
    return [
        {"ratio": ratio, "count": count}
        for ratio, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def extract_keyword_hits(text: str, keywords: tuple[str, ...] = KEYWORDS) -> dict[str, int]:
    hits: dict[str, int] = {}
    for keyword in keywords:
        pattern = re.compile(rf"(?i)\b{re.escape(keyword)}\b")
        count = len(pattern.findall(text))
        if count:
            hits[keyword] = count
    return hits


def _find_line(lines: list[str], *phrases: str) -> str:
    needles = [phrase.lower() for phrase in phrases if phrase]
    for width in range(1, 5):
        for start in range(0, max(0, len(lines) - width + 1)):
            excerpt = " ".join(lines[start : start + width])
            lowered = excerpt.lower()
            if all(needle in lowered for needle in needles):
                return excerpt
    return ""


def _unique_nonempty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        ordered.append(cleaned)
    return ordered


def _first_line(lines: list[str], options: list[tuple[str, ...]]) -> str:
    for option in options:
        found = _find_line(lines, *option)
        if found:
            return found
    return ""


def build_ciovacco_analysis(text: str) -> dict:
    normalized_text = normalize_transcript_text(text)
    lines = normalized_text.splitlines()

    situation_line = _first_line(
        lines,
        [
            ("strait of hormuz",),
            ("market worried about",),
        ],
    )
    market_logic_line = _first_line(
        lines,
        [
            ("news becomes less bad",),
            ("materially less bad",),
            ("weak and volatile",),
        ],
    )
    base_case_line = _first_line(
        lines,
        [
            ("base case", "secular bull market"),
            ("correction within the context of a secular bull market",),
        ],
    )
    measured_line = _first_line(
        lines,
        [
            ("measured approach",),
            ("flexible", "open mind"),
        ],
    )
    better_line = _first_line(
        lines,
        [
            ("better than january of 2022",),
            ("better than early 2008",),
        ],
    )

    ratio_signals: list[dict[str, object]] = []

    xlk_signal_line = _first_line(
        lines,
        [
            ("xlk", "relative to spy", "answer is no"),
            ("uptrend in tech stocks xlk", "relative to spy", "answer is no"),
        ],
    )
    if xlk_signal_line:
        evidence = _unique_nonempty(
            [
                xlk_signal_line,
                _find_line(lines, "higher high"),
                _find_line(lines, "lower low"),
                _find_line(lines, "ongoing uptrend"),
            ]
        )
        ratio_signals.append(
            {
                "ratio": "XLK/SPY",
                "signal": "Tech leadership is not broken; the XLK/SPY uptrend is not over.",
                "reason": (
                    "He says the ratio most recently made a higher high, has not made an important lower low, "
                    "and still has multiple guideposts aligned with an ongoing uptrend."
                ),
                "action": (
                    "Do not force a dump-tech / rotate-away rotation until XLK/SPY actually loses those guideposts "
                    "and starts behaving like a real trend failure."
                ),
                "evidence": evidence,
            }
        )

    rsp_signal_line = _first_line(
        lines,
        [
            ("rsp", "relative to xlk", "monthly cloud"),
        ],
    )
    if rsp_signal_line:
        evidence = _unique_nonempty(
            [
                rsp_signal_line,
                _find_line(lines, "monthly close below the blue span"),
                _find_line(lines, "additional downside would increase"),
            ]
        )
        ratio_signals.append(
            {
                "ratio": "RSP/XLK",
                "signal": "Equal-weight leadership versus tech is still unconfirmed.",
                "reason": (
                    "He says RSP relative to XLK is still 'batting 0 for 5 monthly cloud', and a confirmed monthly "
                    "close below the blue span would raise the odds of additional downside."
                ),
                "action": (
                    "Do not assume broadening has already replaced tech leadership. Watch the monthly close before "
                    "treating this as a durable rotation into equal-weight."
                ),
                "evidence": evidence,
            }
        )

    xlf_signal_line = _first_line(
        lines,
        [
            ("xlf financials", "relative to xlk", "not yet"),
        ],
    )
    if xlf_signal_line:
        evidence = _unique_nonempty(
            [
                xlf_signal_line,
                _find_line(lines, "looks similar", "2011"),
                _find_line(lines, "could potentially be significant"),
            ]
        )
        ratio_signals.append(
            {
                "ratio": "XLF/XLK",
                "signal": "Financials have not yet reclaimed long-term leadership from tech.",
                "reason": (
                    "He explicitly says the long-term trend flip is 'not yet' in place and compares the current setup "
                    "to 2011, where a monthly cloud break became meaningful and potentially significant."
                ),
                "action": (
                    "Treat a financials-over-tech regime change as unproven until the monthly cloud gives confirmed "
                    "evidence. If that break arrives, the risk-management posture should turn more defensive."
                ),
                "evidence": evidence,
            }
        )

    ftec_signal_line = _first_line(
        lines,
        [
            ("ftec", "relative to spy", "keep an open mind"),
        ],
    )
    if ftec_signal_line:
        evidence = _unique_nonempty(
            [
                ftec_signal_line,
                _find_line(lines, "good things happen"),
            ]
        )
        ratio_signals.append(
            {
                "ratio": "FTEC/SPY",
                "signal": "Long-term tech leadership still argues for better-than-expected outcomes remaining possible.",
                "reason": (
                    "He uses the long-term FTEC/SPY relationship to say investors should keep an open mind because "
                    "similar setups were followed by good outcomes for the S&P."
                ),
                "action": (
                    "Do not lock into a permanently bearish view too early. Use this ratio as a reminder to stay "
                    "open to recovery while other risk guideposts remain intact."
                ),
                "evidence": evidence,
            }
        )

    ief_signal_line = _first_line(
        lines,
        [
            ("major inflation problem",),
            ("traditional economic recession",),
        ],
    )
    if ief_signal_line:
        evidence = _unique_nonempty(
            [
                _find_line(lines, "major inflation problem"),
                _find_line(lines, "traditional economic recession"),
            ]
        )
        ratio_signals.append(
            {
                "ratio": "IEF/SPY",
                "signal": "The bond-vs-equity signal is not yet confirming a classic recession or inflation panic.",
                "reason": (
                    "He says the chart is not screaming either a major inflation problem or a traditional recessionary "
                    "macro alarm, which keeps the current drawdown from looking like a confirmed 2008-style template."
                ),
                "action": (
                    "Avoid jumping straight to the most bearish macro conclusion while this relationship still looks "
                    "materially better than the historical danger cases."
                ),
                "evidence": evidence,
            }
        )

    watch_items = _unique_nonempty(
        [
            "Wait for monthly cloud confirmations before treating a style rotation as durable.",
            "Respect lower-low / guidepost breaks in leadership ratios before declaring trend failure.",
            "Stay incremental while war and shipping news remain the main volatility driver.",
        ]
    )

    core_conclusion = (
        "Base case: this still looks like a correction inside a secular bull market, not a confirmed structural bear "
        "regime, even though the drawdown can still deepen."
    )
    if better_line:
        core_conclusion = (
            "Base case: this still looks better than January 2022 and much better than early 2008, which keeps the "
            "working assumption in the 'correction inside a secular bull market' camp unless the guideposts fail."
        )

    situation = (
        "War and energy-shock risk around the Strait of Hormuz is the market's current problem, and Ciovacco argues "
        "conditions may stay weak until that news flow becomes materially less bad."
        if situation_line
        else "The current setup is being driven by an external shock rather than a confirmed internal market breakdown."
    )
    posture = (
        "Measured, flexible, and incremental risk management."
        if measured_line or base_case_line
        else "Flexible, evidence-driven risk management."
    )
    practical_action = (
        "Use the ratios as invalidation guideposts, not as an excuse for an all-at-once style rotation. The focus is "
        "on monthly closes, important lower lows, and whether leadership ratios stop acting like counter-trend moves."
    )

    return {
        "situation": situation,
        "market_logic": (
            "Markets tend to stay weak and volatile until the problem they fear has either been addressed or the news cycle becomes less bad."
            if market_logic_line
            else ""
        ),
        "core_conclusion": core_conclusion,
        "posture": posture,
        "practical_action": practical_action,
        "watch_items": watch_items,
        "ratio_signals": ratio_signals,
    }


def build_ciovacco_telegram_summary(artifact: dict) -> str:
    analysis = artifact.get("analysis", {})
    ratio_signals = analysis.get("ratio_signals", [])
    lead_lines = [
        f"Ciovacco weekly update: {artifact['latest_video']['title']}",
        analysis.get("core_conclusion", ""),
        analysis.get("situation", ""),
    ]
    for signal in ratio_signals[:4]:
        lead_lines.append(f"{signal['ratio']}: {signal['signal']} {signal['action']}")
    return "\n".join(line for line in lead_lines if line).strip()


def _format_upload_date(upload_date: str) -> str:
    if re.fullmatch(r"\d{8}", upload_date or ""):
        return datetime.strptime(upload_date, "%Y%m%d").strftime("%B %d, %Y")
    return upload_date


def render_ciovacco_preview(artifact: dict, preview_paths: list[Path]) -> Path:
    analysis = artifact["analysis"]
    notebooklm = artifact.get("notebooklm") or {}
    ratio_cards = []
    for signal in analysis["ratio_signals"]:
        ratio_cards.append(
            f"""
            <article class="card">
              <div class="ratio">{escape(signal['ratio'])}</div>
              <h3>{escape(signal['signal'])}</h3>
              <p><strong>Reason:</strong> {escape(signal['reason'])}</p>
              <p><strong>Action:</strong> {escape(signal['action'])}</p>
            </article>
            """
        )
    watch_items = "".join(f"<li>{escape(item)}</li>" for item in analysis.get("watch_items", []))
    notebooklm_section = ""
    if notebooklm:
        question_cards = []
        for key, item in notebooklm.get("questions", {}).items():
            label = key.replace("_", " ").title()
            question_cards.append(
                f"""
                <article class="card">
                  <div class="ratio">{escape(label)}</div>
                  <p><strong>Question:</strong> {escape(item.get('question', ''))}</p>
                  <p><strong>Answer:</strong> {escape(item.get('answer', ''))}</p>
                </article>
                """
            )
        notebooklm_section = f"""
      <h2>NotebookLM Historical Context</h2>
      <div class="summary">
        <div class="mini"><h3>Notebook</h3><p>{escape(notebooklm.get('notebook_title', notebooklm.get('notebook_id', '')))}</p></div>
        <div class="mini"><h3>Historical Summary</h3><p>{escape(notebooklm.get('summary', ''))}</p></div>
      </div>
      <div class="ratio-grid">
        {''.join(question_cards)}
      </div>
"""
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ciovacco Weekly Feed Preview</title>
  <style>
    :root {{
      --bg: #0f1317;
      --panel: #182028;
      --panel-2: #1d2933;
      --border: #2d4150;
      --text: #edf3f7;
      --muted: #9fb1bd;
      --accent: #8fd0ff;
      --warn: #ffd38c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top right, rgba(143, 208, 255, 0.14), transparent 30%),
        linear-gradient(180deg, #11161a 0%, #0f1317 100%);
      line-height: 1.6;
    }}
    .wrap {{ width: min(1180px, calc(100vw - 32px)); margin: 28px auto 44px; }}
    .panel {{
      background: rgba(24, 32, 40, 0.95);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: 0 18px 48px rgba(0, 0, 0, 0.24);
      padding: 24px;
    }}
    h1, h2, h3 {{ margin: 0 0 12px; line-height: 1.15; }}
    h1 {{ font-size: clamp(2rem, 4.7vw, 3.3rem); }}
    h2 {{ font-size: 1.15rem; color: var(--accent); margin-top: 24px; }}
    h3 {{ font-size: 1.02rem; color: var(--warn); }}
    p {{ margin: 0 0 12px; }}
    a {{ color: var(--accent); }}
    .muted {{ color: var(--muted); }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin-top: 18px;
    }}
    .mini, .card {{
      background: var(--panel-2);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px;
    }}
    .ratio-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}
    .ratio {{
      display: inline-block;
      font-size: 0.9rem;
      letter-spacing: 0.04em;
      color: var(--warn);
      border: 1px solid rgba(255, 211, 140, 0.24);
      border-radius: 999px;
      padding: 6px 11px;
      margin-bottom: 10px;
    }}
    ul {{ margin: 8px 0 0 18px; padding: 0; color: var(--muted); }}
  </style>
</head>
<body>
  <main class="wrap">
    <section class="panel">
      <p class="muted">Ciovacco Thesis Preview</p>
      <h1>{escape(artifact['latest_video']['title'])}</h1>
        <p class="muted">
          Source: <a href="{escape(artifact['latest_video']['url'])}" target="_blank" rel="noreferrer">CiovaccoCapital YouTube</a>
        | Upload date: {escape(_format_upload_date(artifact['latest_video'].get('upload_date', '')))}
        | Transcript: {escape(artifact['transcript']['kind'])}
      </p>

      <div class="summary">
        <div class="mini"><h3>Core Conclusion</h3><p>{escape(analysis['core_conclusion'])}</p></div>
        <div class="mini"><h3>Situation</h3><p>{escape(analysis['situation'])}</p></div>
        <div class="mini"><h3>Posture</h3><p>{escape(analysis['posture'])}</p></div>
        <div class="mini"><h3>Action</h3><p>{escape(analysis['practical_action'])}</p></div>
      </div>

      <h2>Ratio Thesis</h2>
      <div class="ratio-grid">
        {''.join(ratio_cards)}
      </div>

      <h2>Watch Items</h2>
      <ul>{watch_items}</ul>
{notebooklm_section}
    </section>
  </main>
</body>
</html>
"""
    for preview_path in preview_paths:
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_text(html_text, encoding="utf-8")
    return preview_paths[0]


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def persist_ciovacco_artifact(artifact: dict, *, output_dir: str | Path | None = None) -> dict:
    resolved_output_dir = _resolve_output_dir(output_dir)
    preview_paths = _resolve_preview_targets(resolved_output_dir)
    preview_path = render_ciovacco_preview(artifact, preview_paths)
    artifact["preview"] = {"html_path": str(preview_path)}

    video_id = artifact.get("latest_video", {}).get("id", "").strip()
    latest_path = resolved_output_dir / "ciovacco_latest.json"
    video_path = resolved_output_dir / f"{video_id}.json"
    _write_json(latest_path, artifact)
    _write_json(video_path, artifact)

    notebooklm_payload = artifact.get("notebooklm")
    if isinstance(notebooklm_payload, dict) and notebooklm_payload:
        _write_json(resolved_output_dir / "ciovacco_notebooklm_latest.json", notebooklm_payload)

    return artifact


def capture_ciovacco_feed(
    *,
    output_dir: str | Path | None = None,
    channel_id: str | None = None,
    video_url: str | None = None,
    session: requests.sessions.Session | None = None,
) -> dict:
    resolved_output_dir = _resolve_output_dir(output_dir)
    resolved_channel_id = channel_id or os.getenv("CIOVACCO_CHANNEL_ID", DEFAULT_CHANNEL_ID)

    latest_feed_entry = (
        _discover_latest_video(resolved_channel_id, session=session)
        if not video_url
        else {
            "video_id": "",
            "title": "",
            "video_url": video_url,
            "published": "",
            "updated": "",
        }
    )

    info = _extract_video_info(latest_feed_entry["video_url"])
    track = pick_preferred_caption_track(info)
    caption_text = _download_caption_text(track["url"], session=session) if track else ""
    segments, transcript_text = parse_vtt_captions(caption_text)
    normalized_transcript_text = normalize_transcript_text(transcript_text)

    video_id = (info.get("id") or latest_feed_entry.get("video_id") or "").strip()
    transcript_path = resolved_output_dir / f"{video_id}_transcript.txt"
    transcript_path.write_text(normalized_transcript_text, encoding="utf-8")

    analysis = build_ciovacco_analysis(normalized_transcript_text)

    artifact = {
        "captured_at": _now_iso(),
        "channel": {
            "channel_id": resolved_channel_id,
            "name": info.get("channel", "CiovaccoCapital"),
            "uploader_id": info.get("uploader_id", ""),
        },
        "latest_video": {
            "id": video_id,
            "title": info.get("title") or latest_feed_entry.get("title", ""),
            "url": info.get("webpage_url") or latest_feed_entry["video_url"],
            "published": latest_feed_entry.get("published", ""),
            "updated": latest_feed_entry.get("updated", ""),
            "upload_date": info.get("upload_date", ""),
            "duration": info.get("duration_string", ""),
        },
        "transcript": {
            "available": bool(normalized_transcript_text),
            "segment_count": len(segments),
            "text_path": str(transcript_path),
            "language": track.get("language", "") if track else "",
            "kind": track.get("kind", "") if track else "",
        },
        "observations": {
            "ratio_mentions": extract_ratio_mentions(normalized_transcript_text),
            "keyword_hits": extract_keyword_hits(normalized_transcript_text),
        },
        "analysis": analysis,
        "schedule": schedule_metadata(),
    }
    artifact["telegram_alert"] = build_ciovacco_telegram_summary(artifact)
    return persist_ciovacco_artifact(artifact, output_dir=resolved_output_dir)
