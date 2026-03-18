#!/usr/bin/env python3
"""MacroMicro browser-session scraper."""

from __future__ import annotations

import argparse
import json
import sys

from browser.scrapers.macromicro import MacroMicroScraper


def _ensure_utf8_stdout() -> None:
    stream = getattr(sys, "stdout", None)
    if stream is None:
        return
    encoding = getattr(stream, "encoding", "") or ""
    if encoding.lower() == "utf-8":
        return
    reconfigure = getattr(stream, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape configured MacroMicro targets.")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (requires an existing session for paid content).",
    )
    parser.add_argument(
        "--chrome",
        action="store_true",
        help="Use the local Chrome channel/profile path for tougher Cloudflare-protected pages.",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open MacroMicro and establish a logged-in session without scraping targets.",
    )
    parser.add_argument(
        "--target",
        action="append",
        help="Named MacroMicro target to scrape. Repeat to include multiple targets.",
    )
    parser.add_argument(
        "--url",
        action="append",
        help="Direct MacroMicro URL to scrape. Repeat to include multiple URLs.",
    )
    parser.add_argument(
        "--record-network",
        action="store_true",
        help="Run headed manual network recording for the selected targets and save endpoint artifacts.",
    )
    return parser


def _run_scrape(
    *,
    headless: bool,
    use_chrome,
    login_only: bool,
    record_network: bool = False,
    target_keys=None,
    urls=None,
    allow_manual_login: bool = True,
):
    scraper_kwargs = {
        "headless": headless,
        "use_chrome": use_chrome,
    }
    if allow_manual_login is False:
        scraper_kwargs["allow_manual_login"] = False

    with MacroMicroScraper(**scraper_kwargs) as scraper:
        if login_only:
            scraper.ensure_session()
            return {"login": "ok"}
        if record_network:
            return scraper.record_network(target_keys=target_keys, urls=urls)
        return scraper.run(target_keys=target_keys, urls=urls)


def _should_retry_headed(exc: RuntimeError) -> bool:
    message = str(exc).lower()
    return "run non-headless with --login first" in message


def main(argv=None) -> int:
    _ensure_utf8_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)

    use_chrome = True if args.chrome else None
    run_headless = bool(args.headless and not args.record_network)
    try:
        manifest = _run_scrape(
            headless=run_headless,
            use_chrome=use_chrome,
            login_only=args.login,
            record_network=args.record_network,
            target_keys=args.target,
            urls=args.url,
        )
    except RuntimeError as exc:
        if run_headless and not args.login and not args.record_network and _should_retry_headed(exc):
            try:
                manifest = _run_scrape(
                    headless=False,
                    use_chrome=use_chrome,
                    login_only=False,
                    record_network=False,
                    target_keys=args.target,
                    urls=args.url,
                    allow_manual_login=False,
                )
            except RuntimeError as fallback_exc:
                print(str(fallback_exc), file=sys.stderr)
                return 2
        else:
            print(str(exc), file=sys.stderr)
            return 2

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
