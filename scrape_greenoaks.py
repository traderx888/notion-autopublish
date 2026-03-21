#!/usr/bin/env python3
"""Greenoaks Capital Partners LLC — SEC EDGAR scraper.

Pulls 13F-HR (quarterly holdings), 13D/G (beneficial ownership),
and Form D (private placements) from the free SEC EDGAR API.

CIK: 0001840735

Usage:
    python scrape_greenoaks.py            # full scrape
    python scrape_greenoaks.py --holdings  # 13F holdings only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# ── constants ────────────────────────────────────────────────────────
CIK = "0001840735"
FIRM_NAME = "Greenoaks Capital Partners LLC"
BASE_URL = "https://data.sec.gov"
SUBMISSIONS_URL = f"{BASE_URL}/submissions/CIK{CIK}.json"
HEADERS = {
    "User-Agent": "notion-autopublish/1.0 fundman-jarvis@proton.me",
    "Accept": "application/json",
}
OUTPUT_DIR = Path(__file__).resolve().parent / "scraped_data" / "greenoaks"
RATE_LIMIT_DELAY = 0.12  # SEC allows max 10 req/s


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


# ── SEC API helpers ──────────────────────────────────────────────────
def _get(url: str) -> requests.Response:
    """GET with rate limiting and required User-Agent."""
    time.sleep(RATE_LIMIT_DELAY)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp


def fetch_submissions() -> dict[str, Any]:
    """Fetch full submission history from EDGAR."""
    print(f"  Fetching submissions for CIK {CIK}...")
    resp = _get(SUBMISSIONS_URL)
    return resp.json()


def extract_filings_by_type(
    submissions: dict[str, Any], form_types: list[str]
) -> list[dict[str, str]]:
    """Extract filing entries matching given form types."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    results: list[dict[str, str]] = []
    for i, ft in enumerate(forms):
        if ft in form_types:
            accession = recent["accessionNumber"][i]
            results.append(
                {
                    "form": ft,
                    "filingDate": recent["filingDate"][i],
                    "accessionNumber": accession,
                    "primaryDocument": recent["primaryDocument"][i],
                    "description": recent.get("primaryDocDescription", [""])[i]
                    if i < len(recent.get("primaryDocDescription", []))
                    else "",
                    "url": (
                        f"https://www.sec.gov/Archives/edgar/data/"
                        f"{CIK.lstrip('0')}/{accession.replace('-', '')}/"
                        f"{recent['primaryDocument'][i]}"
                    ),
                }
            )
    return results


# ── 13F holdings parser ──────────────────────────────────────────────
_NS = {
    "ns": "http://www.sec.gov/document/infotable",
    "ns13f": "http://www.sec.gov/document/infotable",
}


def _find_13f_xml_url(accession: str, primary_doc: str) -> str | None:
    """Find the information table XML URL from a 13F-HR filing index."""
    acc_nodash = accession.replace("-", "")
    cik_num = CIK.lstrip("0")
    index_url = (
        f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{acc_nodash}/"
    )
    try:
        resp = _get(index_url)
        text = resp.text
        # Look for the infotable XML file
        matches = re.findall(
            r'href="([^"]*(?:infotable|information_table|13f)[^"]*\.xml)"',
            text,
            re.IGNORECASE,
        )
        if matches:
            xml_file = matches[0]
            if xml_file.startswith("http"):
                return xml_file
            if xml_file.startswith("/"):
                return f"https://www.sec.gov{xml_file}"
            return index_url + xml_file
        # Fallback: look for any .xml that isn't the primary doc
        xml_matches = re.findall(r'href="([^"]*\.xml)"', text, re.IGNORECASE)
        for xm in xml_matches:
            if "primary_doc" not in xm.lower():
                if xm.startswith("http"):
                    return xm
                if xm.startswith("/"):
                    return f"https://www.sec.gov{xm}"
                return index_url + xm
    except Exception as e:
        print(f"    Warning: Could not fetch index page: {e}")
    return None


def parse_13f_holdings(xml_text: str) -> list[dict[str, Any]]:
    """Parse 13F information table XML into holdings list."""
    holdings: list[dict[str, Any]] = []
    root = ET.fromstring(xml_text)
    # Try multiple namespace patterns
    # Newer SEC format uses whole dollars; older uses thousands.
    value_is_dollars = False
    for ns_prefix in [
        "{http://www.sec.gov/edgar/document/thirteenf/informationtable}",
        "{http://www.sec.gov/document/infotable}",
        "{http://www.sec.gov/document/infotable/02}",
        "",
    ]:
        entries = root.findall(f".//{ns_prefix}infoTable")
        if entries:
            if "thirteenf" in ns_prefix:
                value_is_dollars = True
            break
    for entry in entries:
        def _t(tag: str) -> str:
            el = entry.find(f".//{ns_prefix}{tag}")
            if el is None:
                # try without namespace
                el = entry.find(f".//{tag}")
            return (el.text or "").strip() if el is not None else ""

        raw_val = int(_t("value") or 0)
        val_thousands = raw_val if not value_is_dollars else raw_val // 1000
        holding = {
            "name": _t("nameOfIssuer"),
            "title": _t("titleOfClass"),
            "cusip": _t("cusip"),
            "value_thousands": val_thousands,
            "shares": int(_t("sshPrnamt") or 0),
            "share_type": _t("sshPrnamtType"),
            "investment_discretion": _t("investmentDiscretion"),
            "voting_sole": int(_t("Sole") or 0),
            "voting_shared": int(_t("Shared") or 0),
            "voting_none": int(_t("None") or 0),
        }
        if holding["name"]:
            holdings.append(holding)
    return holdings


def fetch_latest_holdings(
    filings_13f: list[dict[str, str]],
) -> dict[str, Any] | None:
    """Fetch and parse the most recent 13F-HR filing's holdings."""
    if not filings_13f:
        print("  No 13F-HR filings found.")
        return None

    latest = filings_13f[0]
    print(f"  Latest 13F-HR: {latest['filingDate']} ({latest['accessionNumber']})")

    # Find the XML info table
    xml_url = _find_13f_xml_url(latest["accessionNumber"], latest["primaryDocument"])
    if not xml_url:
        print("    Warning: Could not locate 13F info table XML.")
        return {"filing": latest, "holdings": [], "total_value_millions": 0}

    print(f"    Fetching holdings XML: {xml_url}")
    resp = _get(xml_url)
    holdings = parse_13f_holdings(resp.text)

    total_value = sum(h["value_thousands"] for h in holdings) / 1000  # millions
    holdings.sort(key=lambda h: h["value_thousands"], reverse=True)

    return {
        "filing": latest,
        "holdings": holdings,
        "total_value_millions": round(total_value, 2),
        "position_count": len(holdings),
    }


# ── main ─────────────────────────────────────────────────────────────
def scrape_greenoaks(holdings_only: bool = False) -> dict[str, Any]:
    """Run the full Greenoaks scrape."""
    _ensure_utf8_stdout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  GREENOAKS CAPITAL PARTNERS — SEC EDGAR SCRAPER")
    print(f"  CIK: {CIK}")
    print(f"{'='*60}\n")

    submissions = fetch_submissions()

    # Company info
    company_info = {
        "name": submissions.get("name", FIRM_NAME),
        "cik": CIK,
        "sic": submissions.get("sic", ""),
        "sicDescription": submissions.get("sicDescription", ""),
        "stateOfIncorporation": submissions.get("stateOfIncorporation", ""),
        "addresses": submissions.get("addresses", {}),
    }
    print(f"  Company: {company_info['name']}")

    # Extract filings by type
    filings_13f = extract_filings_by_type(submissions, ["13F-HR", "13F-HR/A"])
    filings_13dg = extract_filings_by_type(
        submissions, ["SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A"]
    )
    filings_formd = extract_filings_by_type(submissions, ["D", "D/A"])

    print(f"  13F-HR filings: {len(filings_13f)}")
    print(f"  13D/G filings:  {len(filings_13dg)}")
    print(f"  Form D filings: {len(filings_formd)}")

    # Fetch latest holdings
    holdings_data = fetch_latest_holdings(filings_13f)

    # Build output
    result: dict[str, Any] = {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "firm": company_info,
        "latest_holdings": holdings_data,
        "recent_13dg": filings_13dg[:10],
        "recent_formd": filings_formd[:10],
        "all_13f_dates": [f["filingDate"] for f in filings_13f],
    }

    if not holdings_only:
        result["all_filings_13f"] = filings_13f[:20]

    # Save JSON
    out_path = OUTPUT_DIR / "greenoaks_latest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"\n  Saved to: {out_path}")

    # Save human-readable summary
    txt_path = OUTPUT_DIR / "greenoaks_latest.txt"
    _write_summary(result, txt_path)
    print(f"  Summary:  {txt_path}")

    # Print summary
    if holdings_data and holdings_data.get("holdings"):
        print(f"\n  {'='*50}")
        print(f"  LATEST HOLDINGS (as of {holdings_data['filing']['filingDate']})")
        print(f"  Total Value: ${holdings_data['total_value_millions']:.1f}M")
        print(f"  Positions:   {holdings_data['position_count']}")
        print(f"  {'='*50}")
        for h in holdings_data["holdings"][:15]:
            pct = (
                h["value_thousands"] / (holdings_data["total_value_millions"] * 10)
                if holdings_data["total_value_millions"] > 0
                else 0
            )
            print(
                f"    {h['name']:<30s} "
                f"${h['value_thousands']/1000:>8.1f}M  "
                f"{pct:>5.1f}%  "
                f"{h['shares']:>12,} {h['share_type']}"
            )

    return result


def _write_summary(data: dict[str, Any], path: Path) -> None:
    """Write a human-readable text summary."""
    lines: list[str] = []
    lines.append(f"GREENOAKS CAPITAL PARTNERS LLC — Holdings Report")
    lines.append(f"Scraped: {data['scraped_at']}")
    lines.append("")

    hd = data.get("latest_holdings")
    if hd and hd.get("holdings"):
        lines.append(f"Filing Date: {hd['filing']['filingDate']}")
        lines.append(f"Total Value: ${hd['total_value_millions']:.1f}M")
        lines.append(f"Positions:   {hd['position_count']}")
        lines.append("")
        lines.append(f"{'Company':<30s} {'Value ($M)':>10s} {'Weight':>7s} {'Shares':>14s}")
        lines.append("-" * 65)
        for h in hd["holdings"]:
            pct = (
                h["value_thousands"] / (hd["total_value_millions"] * 10)
                if hd["total_value_millions"] > 0
                else 0
            )
            lines.append(
                f"{h['name']:<30s} "
                f"{h['value_thousands']/1000:>10.1f} "
                f"{pct:>6.1f}% "
                f"{h['shares']:>14,}"
            )

    # 13D/G filings
    dg = data.get("recent_13dg", [])
    if dg:
        lines.append("")
        lines.append("RECENT 13D/G FILINGS (>5% Ownership)")
        lines.append("-" * 65)
        for f in dg[:5]:
            lines.append(f"  {f['filingDate']}  {f['form']:<12s}  {f.get('description','')}")

    # Form D filings
    fd = data.get("recent_formd", [])
    if fd:
        lines.append("")
        lines.append("RECENT FORM D (Private Placements)")
        lines.append("-" * 65)
        for f in fd[:5]:
            lines.append(f"  {f['filingDate']}  {f['form']:<6s}  {f.get('description','')}")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape Greenoaks Capital Partners from SEC EDGAR."
    )
    parser.add_argument(
        "--holdings",
        action="store_true",
        help="Only fetch latest 13F holdings (skip full filing history).",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    scrape_greenoaks(holdings_only=args.holdings)
