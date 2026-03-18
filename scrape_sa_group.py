"""
Seeking Alpha group scraper for the P-model/PAM bundle.

Default behavior scrapes the full multi-page P-model bundle:
trade summaries, analytics trading, gamma-charm surface, and monthly OPEX.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

from browser.base import BrowserAutomation

PROJECT_ROOT = Path(__file__).resolve().parent
SCRAPED_DATA_DIR = PROJECT_ROOT / "scraped_data"
P_MODEL_MANIFEST = SCRAPED_DATA_DIR / "sa_group_p_model_manifest.json"
POSITIONING_OUTPUT = SCRAPED_DATA_DIR / "sa_group_predictive_models.txt"
POSITIONING_GROUPS = ("trade-summaries", "analytics-trading")
DEFAULT_BUNDLE = "p-model-core"

SA_GROUPS = {
    "gamma-charm-surface": {
        "url": "https://rc.seekingalpha.com/group/PAM_SPX-GAMMA-CHARM-SURFACE",
        "output": "scraped_data/sa_group_gamma_charm.txt",
        "horizon": "intraday",
        "required": True,
    },
    "monthly-opex": {
        "url": "https://rc.seekingalpha.com/group/PAM_SPX-MONTHLY-OPEX",
        "output": "scraped_data/sa_group_monthly_opex.txt",
        "horizon": "1-4W",
        "required": True,
    },
    "trade-summaries": {
        "url": "https://rc.seekingalpha.com/group/pam-trade-summaries-read-only",
        "output": "scraped_data/sa_group_trade_summaries.txt",
        "horizon": "1-5D",
        "required": True,
    },
    "analytics-trading": {
        "url": "https://rc.seekingalpha.com/group/PAM-ANALYTICS-TRADING",
        "output": "scraped_data/sa_group_analytics_trading.txt",
        "horizon": "1-5D",
        "required": True,
    },
}

GROUP_BUNDLES = {
    DEFAULT_BUNDLE: [
        "trade-summaries",
        "analytics-trading",
        "gamma-charm-surface",
        "monthly-opex",
    ],
}

GROUP_ALIASES = {
    "pam": DEFAULT_BUNDLE,
    "gamma-charm": "gamma-charm-surface",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def _normalize_text(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", str(text or "")).strip()
    return collapsed


def dedupe_content_blocks(blocks: Iterable[str]) -> List[str]:
    deduped: List[str] = []
    seen_hashes = set()
    for block in blocks:
        normalized = _normalize_text(block)
        if not normalized:
            continue
        digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
        if digest in seen_hashes:
            continue
        seen_hashes.add(digest)
        deduped.append(normalized)
    return deduped


def canonical_group_key(group: str) -> str:
    if not group:
        raise KeyError("Missing group key")
    if group in GROUP_ALIASES:
        alias_target = GROUP_ALIASES[group]
        if alias_target in GROUP_BUNDLES:
            return alias_target
        return alias_target
    if group in SA_GROUPS:
        return group
    raise KeyError(f"Unknown group key: {group}")


def resolve_group_keys(group: str | None = None, bundle: str | None = None) -> List[str]:
    if bundle:
        if bundle not in GROUP_BUNDLES:
            raise KeyError(f"Unknown bundle: {bundle}")
        return list(GROUP_BUNDLES[bundle])

    if not group:
        return list(GROUP_BUNDLES[DEFAULT_BUNDLE])

    canonical = canonical_group_key(group)
    if canonical in GROUP_BUNDLES:
        return list(GROUP_BUNDLES[canonical])
    return [canonical]


def _screenshot_path(name: str) -> Path:
    return PROJECT_ROOT / f"debug_seekingalpha_{name}.png"


def _build_section_header(group_key: str) -> str:
    url = SA_GROUPS[group_key]["url"]
    return f"=== SOURCE: {group_key} | URL: {url} ==="


def _build_positioning_corpus(group_results: Dict[str, Dict[str, object]]) -> str:
    parts: List[str] = []
    for group_key in POSITIONING_GROUPS:
        result = group_results.get(group_key, {})
        content = str(result.get("content", "") or "").strip()
        if not content:
            continue
        parts.append(_build_section_header(group_key))
        parts.append(content)
    return "\n\n".join(parts).strip()


def refresh_merged_positioning_output(output_root: Path = PROJECT_ROOT) -> Path:
    parts: List[str] = []
    for group_key in POSITIONING_GROUPS:
        path = Path(output_root) / SA_GROUPS[group_key]["output"]
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8").strip()
        if not content:
            continue
        parts.append(_build_section_header(group_key))
        parts.append(content)
    merged_path = Path(output_root) / POSITIONING_OUTPUT.relative_to(PROJECT_ROOT)
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    merged_path.write_text("\n\n".join(parts).strip(), encoding="utf-8")
    return merged_path


def write_bundle_outputs(group_results: Dict[str, Dict[str, object]], output_root: Path = PROJECT_ROOT) -> Dict[str, object]:
    scraped_dir = Path(output_root) / "scraped_data"
    scraped_dir.mkdir(parents=True, exist_ok=True)

    manifest_groups: Dict[str, Dict[str, object]] = {}
    for group_key, spec in SA_GROUPS.items():
        result = dict(group_results.get(group_key, {}))
        out_path = Path(output_root) / spec["output"]
        content = str(result.get("content", "") or "")
        if content:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(content, encoding="utf-8")

        manifest_groups[group_key] = {
            "url": spec["url"],
            "output_path": str(out_path),
            "screenshot_path": str(result.get("screenshot_path", "") or ""),
            "scraped_at": result.get("scraped_at", ""),
            "block_count": int(result.get("block_count", 0) or 0),
            "char_count": int(result.get("char_count", len(content)) or len(content)),
            "required": bool(spec.get("required", False)),
            "success": bool(result.get("success", False)),
            "error": str(result.get("error", "") or ""),
        }

    positioning_text = _build_positioning_corpus(group_results)
    merged_path = Path(output_root) / POSITIONING_OUTPUT.relative_to(PROJECT_ROOT)
    merged_path.write_text(positioning_text, encoding="utf-8")

    manifest = {
        "generated_at": _now_iso(),
        "bundle": DEFAULT_BUNDLE,
        "groups": manifest_groups,
    }
    manifest_path = Path(output_root) / P_MODEL_MANIFEST.relative_to(PROJECT_ROOT)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


class SAGroupReader(BrowserAutomation):
    SERVICE_NAME = "seekingalpha"
    USE_CHROME_PROFILE = False

    def is_logged_in(self) -> bool:
        return True

    def login(self):
        pass

    def _click_load_more_buttons(self) -> None:
        selectors = [
            'button:has-text("Load more")',
            'button:has-text("Show more")',
            'a:has-text("Load more")',
            'a:has-text("Show more")',
            '[role="button"]:has-text("Load more")',
            '[role="button"]:has-text("Show more")',
        ]
        for selector in selectors:
            try:
                locator = self.page.locator(selector)
                count = min(locator.count(), 3)
                for index in range(count):
                    button = locator.nth(index)
                    if button.is_visible():
                        button.click(timeout=1000)
                        self.page.wait_for_timeout(750)
            except Exception:
                continue

    def _extract_blocks(self) -> List[str]:
        selectors = [
            "article",
            '[data-test-id="post"]',
            '[class*="post"]',
            '[class*="message"]',
            '[class*="comment"]',
            '[class*="card"]',
            ".feed-item",
            '[class*="feed"]',
            '[class*="content-block"]',
        ]
        posts: List[str] = []
        for selector in selectors:
            try:
                elements = self.page.locator(selector)
                count = min(elements.count(), 40)
            except Exception:
                continue
            for index in range(count):
                try:
                    text = elements.nth(index).inner_text(timeout=1000)
                except Exception:
                    continue
                posts.append(text)
        return dedupe_content_blocks(posts)

    def _extract_main_content(self) -> List[str]:
        try:
            body = self.page.locator("main, #content, [role='main'], body").first
            text = body.inner_text(timeout=2000)
        except Exception:
            text = ""
        return dedupe_content_blocks([text])

    def read_group_page(self, url: str, screenshot_name: str) -> Dict[str, object]:
        print(f"  Navigating to: {url}")
        self.page.goto(url, wait_until="networkidle")
        self.page.wait_for_timeout(5000)

        best_blocks: List[str] = []
        stagnant_rounds = 0
        last_block_count = -1
        for _ in range(12):
            self._click_load_more_buttons()
            blocks = self._extract_blocks()
            block_count = len(blocks)
            if block_count > last_block_count:
                best_blocks = blocks
                last_block_count = block_count
                stagnant_rounds = 0
            else:
                stagnant_rounds += 1
            if stagnant_rounds >= 2:
                break
            self.page.evaluate("window.scrollBy(0, Math.max(window.innerHeight, 900))")
            self.page.wait_for_timeout(1500)

        if not best_blocks:
            print("  No posts found via selectors, grabbing full page text...")
            best_blocks = self._extract_main_content()

        content = "\n\n---\n\n".join(best_blocks)
        self.screenshot(screenshot_name)
        screenshot_path = _screenshot_path(screenshot_name)
        print(f"\n  Extracted {len(best_blocks)} content blocks ({len(content)} chars)")
        return {
            "content": content,
            "block_count": len(best_blocks),
            "char_count": len(content),
            "screenshot_path": str(screenshot_path),
            "scraped_at": _now_iso(),
            "success": bool(content),
            "error": "" if content else "No content extracted",
        }


def _scrape_group(reader: SAGroupReader, group_key: str) -> Dict[str, object]:
    spec = SA_GROUPS[group_key]
    screenshot_name = group_key.replace("-", "_")
    try:
        result = reader.read_group_page(spec["url"], screenshot_name=screenshot_name)
    except Exception as exc:
        result = {
            "content": "",
            "block_count": 0,
            "char_count": 0,
            "screenshot_path": str(_screenshot_path(screenshot_name)),
            "scraped_at": _now_iso(),
            "success": False,
            "error": str(exc),
        }
    return result


def _write_single_output(group_key: str, content: str, output_root: Path = PROJECT_ROOT, output_override: str | None = None) -> Path:
    spec = SA_GROUPS[group_key]
    out_path = Path(output_override) if output_override else Path(output_root) / spec["output"]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument(
        "--group",
        default=None,
        choices=sorted(set(SA_GROUPS) | set(GROUP_ALIASES)),
        help="Scrape a single SA group or compatibility alias",
    )
    parser.add_argument(
        "--bundle",
        default=None,
        choices=sorted(GROUP_BUNDLES.keys()),
        help="Scrape a named bundle of SA groups",
    )
    parser.add_argument("--url", default=None, help="Custom group URL (single-group override)")
    parser.add_argument("--output", default=None, help="Custom output path (single-group override)")
    args = parser.parse_args()

    if args.url:
        group_key = resolve_group_keys(group=args.group or "gamma-charm-surface")[0]
        with SAGroupReader(headless=args.headless) as reader:
            result = reader.read_group_page(args.url, screenshot_name=group_key.replace("-", "_"))
        out_path = _write_single_output(group_key, str(result.get("content", "") or ""), output_override=args.output)
        print(f"\n  Saved to: {out_path}")
        print(f"\n{'=' * 60}")
        print("  PREVIEW (first 2000 chars):")
        print(f"{'=' * 60}")
        print(str(result.get("content", "") or "")[:2000])
        return 0

    group_keys = resolve_group_keys(group=args.group, bundle=args.bundle)
    results: Dict[str, Dict[str, object]] = {}
    with SAGroupReader(headless=args.headless) as reader:
        for group_key in group_keys:
            print(f"\n{'=' * 60}")
            print(f"  SCRAPING {group_key}")
            print(f"{'=' * 60}")
            result = _scrape_group(reader, group_key)
            results[group_key] = result
            _write_single_output(group_key, str(result.get("content", "") or ""))

    is_bundle_run = bool(args.bundle) or (args.group in {None, "pam"})
    if is_bundle_run:
        manifest = write_bundle_outputs(results)
        print(f"\n  Manifest saved to: {P_MODEL_MANIFEST}")
        print(f"  Positioning corpus saved to: {POSITIONING_OUTPUT}")
        print(f"  Groups captured: {', '.join(group_keys)}")
        print(f"  Manifest timestamp: {manifest['generated_at']}")
    elif any(group_key in POSITIONING_GROUPS for group_key in group_keys):
        merged_path = refresh_merged_positioning_output()
        print(f"\n  Positioning corpus refreshed: {merged_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
