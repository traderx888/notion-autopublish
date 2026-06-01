from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import pandas as pd

DEFAULT_NOTION_DB_ID = "95034222f2c9447eabda963715eee382"
DEFAULT_BENCHMARK = "SPY"

NO_SHORT_REGIONS = {"A-Share", "A 股", "India", "印度", "EM", "Emerging Markets"}
COMMON_UPPERCASE_WORDS = {
    "AI",
    "API",
    "CAPEX",
    "CPU",
    "ETF",
    "EPS",
    "FCF",
    "GPU",
    "HBM",
    "IPO",
    "LLM",
    "LONG",
    "PE",
    "QOQ",
    "ROE",
    "SK",
    "TAM",
    "YOY",
}

TICKER_ALIASES = {
    "SK Hynix": "000660.KS",
    "Hynix": "000660.KS",
    "Samsung": "005930.KS",
    "Micron": "MU",
    "NVIDIA": "NVDA",
    "Nvidia": "NVDA",
    "Meta": "META",
    "TSMC": "TSM",
    "Xiaomi": "1810.HK",
    "Apple": "AAPL",
    "Wolfspeed": "WOLF",
    "Infineon": "IFX.DE",
    "Vale": "VALE",
    "Petrobras": "PBR",
    "Cargill": None,
    "CXMT": None,
    "YMTC": None,
}

PriceProvider = Callable[[str, datetime, datetime], pd.DataFrame]


def quarter_to_range(quarter: str) -> tuple[str, str]:
    match = re.fullmatch(r"(\d{4})Q([1-4])", quarter.strip().upper())
    if not match:
        raise ValueError("Quarter must use YYYYQn format, for example 2026Q1")

    year = int(match.group(1))
    quarter_num = int(match.group(2))
    start_month = (quarter_num - 1) * 3 + 1
    start = datetime(year, start_month, 1)
    if quarter_num == 4:
        next_quarter = datetime(year + 1, 1, 1)
    else:
        next_quarter = datetime(year, start_month + 3, 1)
    end = next_quarter - timedelta(days=1)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def parse_date(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.upper()
        if normalized not in seen:
            seen.add(normalized)
            result.append(value)
    return result


def _require_yfinance():
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Install yfinance before running live backtests: pip install yfinance") from exc
    return yf


def _require_notion_client():
    try:
        from notion_client import Client
    except ImportError as exc:
        raise RuntimeError("Install notion-client before using Notion integration: pip install notion-client") from exc
    return Client


@dataclass
class ThesisEntry:
    page_id: str
    title: str
    publish_date: datetime
    direction: str
    time_horizon: str
    asset_class: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    verdict: str = ""
    series: str = ""

    def is_backtestable(self) -> tuple[bool, str]:
        direction = self.direction.lower()
        tickers = self.extract_tickers()
        if "educational" in direction or "neutral" in direction:
            return False, "Educational or neutral content"
        if "multi-strategy" in direction and not tickers:
            return False, "Multi-Strategy without parseable tickers"
        if "hedge" in direction and not tickers:
            return False, "Hedge thesis without specific tickers"
        if "pair" in direction and len(tickers) < 2:
            return False, "Pair trade requires at least two tickers"
        if not tickers:
            return False, "No parseable ticker in verdict"
        return True, "OK"

    def extract_tickers(self) -> list[str]:
        candidates: list[tuple[int, str]] = []
        text = self.verdict or ""

        for alias, ticker in TICKER_ALIASES.items():
            if not ticker:
                continue
            for match in re.finditer(re.escape(alias), text, flags=re.IGNORECASE):
                candidates.append((match.start(), ticker))

        exchange_pattern = r"(?<![A-Z0-9.])(?:\d{4}\.(?:TW|HK|SS|SZ)|\d{6}\.KS|[A-Z]{1,5}\.[A-Z]{1,3})(?![A-Z0-9])"
        for match in re.finditer(exchange_pattern, text):
            candidates.append((match.start(), match.group(0)))

        for match in re.finditer(r"\$([A-Z]{1,5})(?![A-Z])", text):
            candidates.append((match.start(1), match.group(1)))
        for match in re.finditer(r"\(([A-Z]{1,5})\)", text):
            candidates.append((match.start(1), match.group(1)))
        action_pattern = r"\b(?:Long|Short|Buy|Sell|Overweight|Underweight)\s+\$?([A-Z]{1,5})\b"
        for match in re.finditer(action_pattern, text, flags=re.IGNORECASE):
            candidates.append((match.start(1), match.group(1)))

        ordered = [ticker for _, ticker in sorted(candidates, key=lambda item: item[0])]
        cleaned = [ticker.upper() for ticker in ordered if ticker.upper() not in COMMON_UPPERCASE_WORDS]
        return _dedupe(cleaned)

    def check_short_rules(self) -> tuple[bool, str]:
        if "short" not in self.direction.lower():
            return True, "OK"

        searchable = [*self.asset_class, *self.tags, self.verdict]
        for forbidden in NO_SHORT_REGIONS:
            if any(self._matches_forbidden_short(str(item), forbidden) for item in searchable):
                return False, f"Cannot short {forbidden} (operator rule)"
        return True, "OK"

    @staticmethod
    def _matches_forbidden_short(value: str, forbidden: str) -> bool:
        if forbidden == "EM":
            return re.search(r"\bEM\b", value, flags=re.IGNORECASE) is not None
        return forbidden.lower() in value.lower()


class BacktestEngine:
    def __init__(
        self,
        benchmark: str = DEFAULT_BENCHMARK,
        *,
        notion_token: str | None = None,
        notion_db_id: str | None = None,
        notion_client: Any | None = None,
        price_provider: PriceProvider | None = None,
    ) -> None:
        self.benchmark = benchmark
        self.notion_token = notion_token
        self.notion_db_id = notion_db_id or os.getenv("NOTION_BACKTEST_DB_ID") or os.getenv("NOTION_DATABASE_ID") or DEFAULT_NOTION_DB_ID
        self._notion = notion_client
        self.price_provider = price_provider

    def _get_notion(self):
        if self._notion is not None:
            return self._notion

        token = self.notion_token or os.getenv("NOTION_TOKEN")
        if not token:
            raise RuntimeError("NOTION_TOKEN is required for Notion reads or write-back")

        Client = _require_notion_client()
        self._notion = Client(auth=token)
        return self._notion

    def fetch_pending_theses(self, start: str, end: str) -> list[ThesisEntry]:
        notion = self._get_notion()
        payload: dict[str, Any] = {
            "database_id": self.notion_db_id,
            "filter": {
                "and": [
                    {"property": "Hit/Miss Status", "select": {"equals": "Pending"}},
                    {"property": "Date", "date": {"on_or_after": start}},
                    {"property": "Date", "date": {"on_or_before": end}},
                ]
            },
        }

        pages: list[dict[str, Any]] = []
        while True:
            response = notion.databases.query(**payload)
            pages.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            payload["start_cursor"] = response.get("next_cursor")
        return [self._parse_page(page) for page in pages]

    def _parse_page(self, page: dict[str, Any]) -> ThesisEntry:
        props = page.get("properties", {})
        date_value = props.get("Date", {}).get("date", {}).get("start")
        if not date_value:
            raise ValueError(f"Notion page {page.get('id')} is missing Date")

        return ThesisEntry(
            page_id=page["id"],
            title=self._title(props),
            publish_date=parse_date(date_value),
            direction=self._select(props, "Thesis Direction"),
            time_horizon=self._select(props, "Time Horizon"),
            asset_class=self._multi_select(props, "Asset Class"),
            tags=self._multi_select(props, "Tags"),
            verdict=self._rich_text(props, "Verdict"),
            series=self._select(props, "Series"),
        )

    @staticmethod
    def _title(props: dict[str, Any]) -> str:
        for key in ("Title", "Name"):
            title = props.get(key, {}).get("title", [])
            if title:
                return "".join(part.get("plain_text", "") for part in title)
        return ""

    @staticmethod
    def _select(props: dict[str, Any], key: str) -> str:
        return props.get(key, {}).get("select", {}).get("name", "") or ""

    @staticmethod
    def _multi_select(props: dict[str, Any], key: str) -> list[str]:
        return [item.get("name", "") for item in props.get(key, {}).get("multi_select", []) if item.get("name")]

    @staticmethod
    def _rich_text(props: dict[str, Any], key: str) -> str:
        parts = props.get(key, {}).get("rich_text", [])
        return "".join(part.get("plain_text", "") for part in parts)

    def _download_prices(self, ticker: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
        if self.price_provider:
            return self.price_provider(ticker, start_date, end_date)

        yf = _require_yfinance()
        inclusive_end = end_date + timedelta(days=1)
        return yf.download(
            ticker,
            start=start_date.strftime("%Y-%m-%d"),
            end=inclusive_end.strftime("%Y-%m-%d"),
            progress=False,
            auto_adjust=False,
        )

    @staticmethod
    def _close_series(data: pd.DataFrame) -> pd.Series:
        if data.empty:
            return pd.Series(dtype="float64")
        close = data["Close"] if "Close" in data.columns else data.iloc[:, 0]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close.dropna()

    def compute_return(self, ticker: str, start_date: datetime, end_date: datetime) -> float | None:
        try:
            data = self._download_prices(ticker, start_date, end_date)
            close = self._close_series(data)
            if len(close) < 2:
                return None
            return round(float((close.iloc[-1] - close.iloc[0]) / close.iloc[0] * 100), 2)
        except Exception as exc:
            print(f"  price fetch failed for {ticker}: {exc}")
            return None

    def get_benchmark_return(self, start_date: datetime, end_date: datetime) -> float | None:
        return self.compute_return(self.benchmark, start_date, end_date)

    def evaluate_thesis(self, thesis: ThesisEntry, end_date: datetime) -> dict[str, Any]:
        base = {"page_id": thesis.page_id, "title": thesis.title}
        backtest_ok, reason = thesis.is_backtestable()
        if not backtest_ok:
            return {**base, "status": "skip", "reason": reason}

        short_ok, short_reason = thesis.check_short_rules()
        if not short_ok:
            return {**base, "status": "skip", "reason": short_reason}

        returns: dict[str, float] = {}
        for ticker in thesis.extract_tickers():
            ticker_return = self.compute_return(ticker, thesis.publish_date, end_date)
            if ticker_return is not None:
                returns[ticker] = ticker_return

        if not returns:
            return {**base, "status": "skip", "reason": "All tickers failed to fetch"}

        benchmark_return = self.get_benchmark_return(thesis.publish_date, end_date) or 0.0
        direction = thesis.direction.lower()
        avg_return = round(sum(returns.values()) / len(returns), 2)

        if "pair" in direction and len(returns) >= 2:
            values = list(returns.values())
            strategy_return = round(values[0] - values[1], 2)
            alpha = strategy_return
            status = self._status_from_score(strategy_return, hit_threshold=3.0)
        elif "short" in direction:
            strategy_return = round(-avg_return, 2)
            alpha = round(strategy_return - benchmark_return, 2)
            status = self._status_from_score(strategy_return, hit_threshold=5.0)
        else:
            strategy_return = avg_return
            alpha = round(strategy_return - benchmark_return, 2)
            status = self._status_from_score(alpha, hit_threshold=5.0)

        return {
            **base,
            "publish_date": thesis.publish_date.strftime("%Y-%m-%d"),
            "direction": thesis.direction,
            "tickers": list(returns.keys()),
            "returns_pct": returns,
            "strategy_return_pct": strategy_return,
            "benchmark_return_pct": round(benchmark_return, 2),
            "alpha_pct": alpha,
            "status": status,
        }

    @staticmethod
    def _status_from_score(score: float, *, hit_threshold: float) -> str:
        if score > hit_threshold:
            return "Hit"
        if score > 0:
            return "Partial Hit"
        return "Miss"

    def write_back_to_notion(self, result: dict[str, Any], end_date: datetime) -> None:
        if result.get("status") not in {"Hit", "Partial Hit", "Miss"}:
            return

        evidence = (
            f"Backtest from {result['publish_date']} to {end_date.strftime('%Y-%m-%d')}: "
            f"Tickers={result['tickers']}, Strategy Return={result['strategy_return_pct']}%, "
            f"Benchmark({self.benchmark})={result['benchmark_return_pct']}%, "
            f"Alpha={result['alpha_pct']}%"
        )
        notes = f"Auto-backtested with yfinance. Alpha vs {self.benchmark}: {result['alpha_pct']}%."

        self._get_notion().pages.update(
            page_id=result["page_id"],
            properties={
                "Hit/Miss Status": {"select": {"name": result["status"]}},
                "Verification Date": {"date": {"start": end_date.strftime("%Y-%m-%d")}},
                "Key Trigger": {"rich_text": [{"text": {"content": evidence[:500]}}]},
                "Review Notes": {"rich_text": [{"text": {"content": notes[:1000]}}]},
            },
        )

    def run(self, start: str, end: str, *, write_back: bool = False, output: str | None = None) -> list[dict[str, Any]]:
        end_date = parse_date(end)
        theses = self.fetch_pending_theses(start, end)
        print(f"Backtest from {start} to {end}, benchmark={self.benchmark}")
        print(f"Found {len(theses)} pending theses")

        results = [self.evaluate_thesis(thesis, end_date) for thesis in theses]
        reportable = [result for result in results if result.get("status") != "skip"]

        if reportable:
            df = pd.DataFrame(reportable)
            print(df.to_string(index=False))
            if output:
                self.write_csv(reportable, output)
                print(f"Wrote CSV: {output}")
        else:
            print("No backtestable theses in this range")

        if write_back:
            for result in reportable:
                self.write_back_to_notion(result, end_date)
            print("Notion write-back complete")
        else:
            print("Dry run mode. Pass --write-back to update Notion.")

        return results

    @staticmethod
    def write_csv(results: list[dict[str, Any]], output: str) -> None:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "page_id",
            "title",
            "publish_date",
            "direction",
            "tickers",
            "strategy_return_pct",
            "benchmark_return_pct",
            "alpha_pct",
            "status",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = pd.DataFrame(results)
            writer.to_csv(handle, columns=[field for field in fieldnames if field in writer.columns], index=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backtest Notion newsletter theses with yfinance prices.")
    parser.add_argument("--quarter", help="Calendar quarter in YYYYQn format, for example 2026Q1")
    parser.add_argument("--start", help="Start date in YYYY-MM-DD format")
    parser.add_argument("--end", default=datetime.now().strftime("%Y-%m-%d"), help="End date in YYYY-MM-DD format")
    parser.add_argument("--benchmark", default=DEFAULT_BENCHMARK)
    parser.add_argument("--notion-db-id", default=None)
    parser.add_argument("--output", help="Optional CSV output path")
    parser.add_argument("--write-back", action="store_true", help="Update Notion review fields")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.quarter:
        start, end = quarter_to_range(args.quarter)
    else:
        end = args.end
        start = args.start or (parse_date(end) - timedelta(days=30)).strftime("%Y-%m-%d")

    engine = BacktestEngine(benchmark=args.benchmark, notion_db_id=args.notion_db_id)
    engine.run(start, end, write_back=args.write_back, output=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
