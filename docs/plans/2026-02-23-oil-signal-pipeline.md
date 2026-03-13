# Oil Signal Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a daily oil signal script that ingests US10Y yield (Excel/Yahoo/FRED) and extracts crack spread + COT from the latest daily screenshot to output a scored signal and persist time series.

**Architecture:** A single Python module provides pure functions for parsing, trend detection, and scoring, plus thin I/O wrappers for data sources (Excel/Yahoo/FRED) and screenshot OCR. A small CLI orchestrates the pipeline and writes outputs to `data/` and `output/`.

**Tech Stack:** Python 3, `requests`, `pandas`, `yfinance`, `openpyxl`, `Pillow`, `pytesseract`, `pytest`.

---

### Task 1: Create failing tests for screenshot text parsing

**Files:**
- Create: `tests/test_oil_signal.py`
- Create: `oil_signal.py`

**Step 1: Write the failing test**

```python
# tests/test_oil_signal.py
from oil_signal import parse_legend_text


def test_parse_legend_text_extracts_values():
    text = (
        "CRK321M1 Index - Last Price (L2) 24.0877\n"
        "CRK321M3 Index - Last Price (R2) 23.34\n"
        "ICFUBMMN Index - Last Price (R4) -8033\n"
    )
    result = parse_legend_text(text)
    assert result["CRK321M1"] == 24.0877
    assert result["CRK321M3"] == 23.34
    assert result["ICFUBMMN"] == -8033.0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_oil_signal.py::test_parse_legend_text_extracts_values -v`  
Expected: FAIL with `ImportError` or `AttributeError` for missing `parse_legend_text`

**Step 3: Write minimal implementation**

```python
# oil_signal.py
import re


def parse_legend_text(text: str) -> dict:
    def find_value(symbol: str) -> float | None:
        pattern = rf"{symbol}.*?(-?\\d+[\\d,]*\\.?\\d*)"
        match = re.search(pattern, text)
        if not match:
            return None
        return float(match.group(1).replace(",", ""))

    return {
        "CRK321M1": find_value("CRK321M1"),
        "CRK321M3": find_value("CRK321M3"),
        "ICFUBMMN": find_value("ICFUBMMN"),
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_oil_signal.py::test_parse_legend_text_extracts_values -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_oil_signal.py oil_signal.py
git commit -m "test: add screenshot legend parser test"
```

---

### Task 2: Add 10Y trend rules (MA + breakout)

**Files:**
- Modify: `tests/test_oil_signal.py`
- Modify: `oil_signal.py`

**Step 1: Write the failing test**

```python
# tests/test_oil_signal.py
from oil_signal import compute_10y_trend


def test_compute_10y_trend_up_breakout():
    values = [4.0, 4.1, 4.2, 4.15, 4.3]  # last breaks prior 3-day high
    assert compute_10y_trend(values) == "up"


def test_compute_10y_trend_down_ma():
    values = [5.0] * 60 + [4.9, 4.85, 4.8, 4.75, 4.7]
    assert compute_10y_trend(values) == "down"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_oil_signal.py::test_compute_10y_trend_up_breakout -v`  
Expected: FAIL (missing `compute_10y_trend`)

**Step 3: Write minimal implementation**

```python
# oil_signal.py
from statistics import mean


def _ma(values: list[float], window: int) -> float:
    if len(values) < window:
        raise ValueError("not enough data for MA")
    return mean(values[-window:])


def compute_10y_trend(values: list[float]) -> str:
    if len(values) < 60:
        return "neutral"

    last = values[-1]
    prev3 = values[-4:-1]
    if last > max(prev3):
        return "up"
    if last < min(prev3):
        return "down"

    ma5 = _ma(values, 5)
    ma20 = _ma(values, 20)
    ma60 = _ma(values, 60)

    ma20_prev = mean(values[-23:-3])
    ma60_prev = mean(values[-63:-3])

    if ma5 > ma20 and ma20 > ma20_prev and ma60 > ma60_prev:
        return "up"
    if ma5 < ma20 and ma20 < ma20_prev and ma60 < ma60_prev:
        return "down"
    return "neutral"
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_oil_signal.py::test_compute_10y_trend_up_breakout -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_oil_signal.py oil_signal.py
git commit -m "feat: add 10Y trend detection"
```

---

### Task 3: Add crack spread trend + COT crowding logic

**Files:**
- Modify: `tests/test_oil_signal.py`
- Modify: `oil_signal.py`

**Step 1: Write the failing tests**

```python
# tests/test_oil_signal.py
from oil_signal import compute_ma_trend, compute_cot_state


def test_compute_ma_trend_up():
    values = [1] * 20 + [2, 2, 2, 2, 2]
    assert compute_ma_trend(values, fast=5, slow=20) == "up"


def test_compute_cot_state_crowded_long():
    values = list(range(100)) + [999]
    assert compute_cot_state(values, lookback=100, high_pct=0.8, low_pct=0.2) == "crowded_long"
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_oil_signal.py::test_compute_ma_trend_up -v`  
Expected: FAIL (missing functions)

**Step 3: Write minimal implementation**

```python
# oil_signal.py
def compute_ma_trend(values: list[float], fast: int = 5, slow: int = 20) -> str:
    if len(values) < slow:
        return "neutral"
    fast_ma = _ma(values, fast)
    slow_ma = _ma(values, slow)
    if fast_ma > slow_ma:
        return "up"
    if fast_ma < slow_ma:
        return "down"
    return "neutral"


def compute_cot_state(values: list[float], lookback: int = 260, high_pct: float = 0.8, low_pct: float = 0.2) -> str:
    if len(values) < lookback:
        return "neutral"
    window = values[-lookback:]
    last = window[-1]
    rank = sum(1 for v in window if v <= last) / len(window)
    if rank >= high_pct:
        return "crowded_long"
    if rank <= low_pct:
        return "washed"
    return "neutral"
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_oil_signal.py::test_compute_ma_trend_up -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_oil_signal.py oil_signal.py
git commit -m "feat: add crack and COT state logic"
```

---

### Task 4: Add signal scoring + output formatting

**Files:**
- Modify: `tests/test_oil_signal.py`
- Modify: `oil_signal.py`

**Step 1: Write the failing test**

```python
# tests/test_oil_signal.py
from oil_signal import compute_signal


def test_compute_signal_bullish():
    result = compute_signal("up", "up", "washed")
    assert result["score"] == 3
    assert result["label"] == "Bullish"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_oil_signal.py::test_compute_signal_bullish -v`  
Expected: FAIL (missing `compute_signal`)

**Step 3: Write minimal implementation**

```python
# oil_signal.py
def compute_signal(teny_trend: str, crack_trend: str, cot_state: str) -> dict:
    score = 0
    score += 1 if teny_trend == "up" else -1 if teny_trend == "down" else 0
    score += 1 if crack_trend == "up" else -1 if crack_trend == "down" else 0
    score += 1 if cot_state == "washed" else -1 if cot_state == "crowded_long" else 0

    if score >= 2:
        label = "Bullish"
    elif score <= -2:
        label = "Bearish"
    else:
        label = "Neutral"
    return {"score": score, "label": label}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_oil_signal.py::test_compute_signal_bullish -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_oil_signal.py oil_signal.py
git commit -m "feat: add signal scoring"
```

---

### Task 5: Add 10Y loaders (Excel/Yahoo/FRED)

**Files:**
- Modify: `tests/test_oil_signal.py`
- Modify: `oil_signal.py`
- Modify: `requirements.txt`

**Step 1: Write failing tests**

```python
# tests/test_oil_signal.py
import pandas as pd
from oil_signal import load_10y_from_excel, load_10y_from_yahoo, load_10y_from_fred


def test_load_10y_from_excel(tmp_path):
    df = pd.DataFrame({"Date": ["2026-02-20", "2026-02-21"], "Value": [4.1, 4.15]})
    path = tmp_path / "teny.xlsx"
    df.to_excel(path, index=False)
    values = load_10y_from_excel(path, date_col="Date", value_col="Value")
    assert values[-1] == 4.15


def test_load_10y_from_yahoo_uses_stub():
    df = pd.DataFrame({"Close": [4.1, 4.15]})
    values = load_10y_from_yahoo("^TNX", yf_download=lambda *_: df)
    assert values[-1] == 4.15


def test_load_10y_from_fred_parses_json():
    sample = {
        "observations": [
            {"date": "2026-02-20", "value": "4.10"},
            {"date": "2026-02-21", "value": "4.15"},
        ]
    }
    values = load_10y_from_fred("DGS10", "KEY", fetch_json=lambda *_: sample)
    assert values[-1] == 4.15
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_oil_signal.py::test_load_10y_from_excel -v`  
Expected: FAIL (missing loaders)

**Step 3: Write minimal implementation**

```python
# oil_signal.py
import pandas as pd
import requests


def load_10y_from_excel(path: str, date_col: str, value_col: str) -> list[float]:
    df = pd.read_excel(path)
    df = df[[date_col, value_col]].dropna()
    return df[value_col].astype(float).tolist()


def load_10y_from_yahoo(ticker: str, yf_download=None) -> list[float]:
    if yf_download is None:
        import yfinance as yf
        yf_download = yf.download
    df = yf_download(ticker, progress=False)
    return df["Close"].dropna().astype(float).tolist()


def load_10y_from_fred(series_id: str, api_key: str, fetch_json=None) -> list[float]:
    if fetch_json is None:
        def fetch_json(url, params):
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            return resp.json()

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id": series_id, "api_key": api_key, "file_type": "json"}
    data = fetch_json(url, params)
    values = []
    for row in data.get("observations", []):
        if row.get("value") not in {None, ".", ""}:
            values.append(float(row["value"]))
    return values
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_oil_signal.py::test_load_10y_from_excel -v`  
Expected: PASS

**Step 5: Update dependencies**

```text
# requirements.txt
pandas>=2.1.0
yfinance>=0.2.36
openpyxl>=3.1.2
pillow>=10.2.0
pytesseract>=0.3.10
pytest>=7.4.0
```

**Step 6: Commit**

```bash
git add tests/test_oil_signal.py oil_signal.py requirements.txt
git commit -m "feat: add 10Y loaders"
```

---

### Task 6: Add screenshot OCR + history storage

**Files:**
- Modify: `tests/test_oil_signal.py`
- Modify: `oil_signal.py`

**Step 1: Write failing tests**

```python
# tests/test_oil_signal.py
from pathlib import Path
from oil_signal import ocr_image_to_text, pick_latest_screenshot, append_series_value


def test_pick_latest_screenshot(tmp_path: Path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    a.write_bytes(b"1")
    b.write_bytes(b"2")
    a.touch()
    b.touch()
    assert pick_latest_screenshot(tmp_path).name in {"a.png", "b.png"}


def test_ocr_image_to_text_uses_stub(tmp_path: Path):
    path = tmp_path / "img.png"
    path.write_bytes(b"fake")
    text = ocr_image_to_text(path, ocr_engine=lambda *_: "HELLO")
    assert text == "HELLO"


def test_append_series_value(tmp_path: Path):
    csv_path = tmp_path / "series.csv"
    values = append_series_value(csv_path, "2026-02-23", 1.23)
    assert values[-1] == 1.23
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_oil_signal.py::test_ocr_image_to_text_uses_stub -v`  
Expected: FAIL (missing helpers)

**Step 3: Write minimal implementation**

```python
# oil_signal.py
from pathlib import Path
import csv


def pick_latest_screenshot(directory: str | Path) -> Path:
    directory = Path(directory)
    candidates = [p for p in directory.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg"}]
    if not candidates:
        raise FileNotFoundError(f"No screenshots found in {directory}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def ocr_image_to_text(path: str | Path, ocr_engine=None) -> str:
    if ocr_engine is not None:
        return ocr_engine(path)
    from PIL import Image
    import pytesseract
    return pytesseract.image_to_string(Image.open(path))


def append_series_value(path: str | Path, date_str: str, value: float) -> list[float]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if path.exists():
        with path.open("r", newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
    rows.append([date_str, value])
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(rows)
    return [float(r[1]) for r in rows]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_oil_signal.py::test_append_series_value -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_oil_signal.py oil_signal.py
git commit -m "feat: add screenshot OCR + history storage"
```

---

### Task 7: Build pipeline + outputs

**Files:**
- Modify: `tests/test_oil_signal.py`
- Modify: `oil_signal.py`
- Modify: `.env.example`

**Step 1: Write failing tests**

```python
# tests/test_oil_signal.py
from oil_signal import compute_signal


def test_signal_scoring_bearish():
    result = compute_signal("down", "down", "crowded_long")
    assert result["score"] == -3
    assert result["label"] == "Bearish"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_oil_signal.py::test_signal_scoring_bearish -v`  
Expected: FAIL (if not implemented)

**Step 3: Write minimal pipeline**

```python
# oil_signal.py (append)
import os
import json
from datetime import datetime


def write_output(path: str | Path, payload: dict):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_oil_signal(config: dict, fetch_10y, ocr_fn):
    teny_values = fetch_10y(config)
    teny_trend = compute_10y_trend(teny_values)

    screenshot_path = pick_latest_screenshot(config["screenshot_dir"])
    legend_text = ocr_fn(screenshot_path)
    legend = parse_legend_text(legend_text)

    crack_values = append_series_value(config["crack_history_path"], config["date"], legend["CRK321M1"])
    cot_values = append_series_value(config["cot_history_path"], config["date"], legend["ICFUBMMN"])

    crack_trend = compute_ma_trend(crack_values)
    cot_state = compute_cot_state(cot_values)

    signal = compute_signal(teny_trend, crack_trend, cot_state)
    payload = {
        "date": config["date"],
        "teny_trend": teny_trend,
        "crack_trend": crack_trend,
        "cot_state": cot_state,
        "signal": signal,
        "inputs": {"legend": legend},
    }
    write_output(config["output_latest"], payload)
    return payload
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_oil_signal.py -v`  
Expected: PASS

**Step 5: Update `.env.example` with new config**

```text
# .env.example
OIL_10Y_SOURCE=fred
OIL_10Y_FRED_SERIES=DGS10
FRED_API_KEY=your_fred_key
OIL_10Y_YAHOO_TICKER=^TNX
OIL_10Y_EXCEL_PATH=C:\\path\\to\\teny.xlsx
OIL_10Y_EXCEL_DATE_COL=Date
OIL_10Y_EXCEL_VALUE_COL=Value
OIL_SCREENSHOT_DIR=C:\\Users\\User\\Documents\\ShareX\\Screenshots\\2026-02
OIL_CRACK_HISTORY=data\\oil_model\\crack.csv
OIL_COT_HISTORY=data\\oil_model\\cot.csv
OIL_OUTPUT_LATEST=output\\oil_signal_latest.json
```

**Step 6: Commit**

```bash
git add tests/test_oil_signal.py oil_signal.py .env.example
git commit -m "feat: add oil signal pipeline"
```

---

### Task 8: Add CLI entry point

**Files:**
- Modify: `oil_signal.py`

**Step 1: Write failing test**

```python
# tests/test_oil_signal.py
from oil_signal import load_env_config


def test_load_env_config_defaults():
    cfg = load_env_config()
    assert "screenshot_dir" in cfg
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_oil_signal.py::test_load_env_config_defaults -v`  
Expected: FAIL (missing `load_env_config`)

**Step 3: Implement CLI**

```python
# oil_signal.py
def load_env_config() -> dict:
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "screenshot_dir": os.getenv("OIL_SCREENSHOT_DIR", ""),
        "output_latest": os.getenv("OIL_OUTPUT_LATEST", "output/oil_signal_latest.json"),
        "crack_history_path": os.getenv("OIL_CRACK_HISTORY", "data/oil_model/crack.csv"),
        "cot_history_path": os.getenv("OIL_COT_HISTORY", "data/oil_model/cot.csv"),
        "teny_source": os.getenv("OIL_10Y_SOURCE", "fred"),
        "teny_fred_series": os.getenv("OIL_10Y_FRED_SERIES", "DGS10"),
        "teny_yahoo_ticker": os.getenv("OIL_10Y_YAHOO_TICKER", "^TNX"),
        "teny_excel_path": os.getenv("OIL_10Y_EXCEL_PATH", ""),
        "teny_excel_date_col": os.getenv("OIL_10Y_EXCEL_DATE_COL", "Date"),
        "teny_excel_value_col": os.getenv("OIL_10Y_EXCEL_VALUE_COL", "Value"),
        "fred_api_key": os.getenv("FRED_API_KEY", ""),
    }


if __name__ == "__main__":
    config = load_env_config()
    # wire in real fetch_10y + OCR here
    # run_oil_signal(config, fetch_10y=..., ocr_fn=...)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_oil_signal.py::test_load_env_config_defaults -v`  
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_oil_signal.py oil_signal.py
git commit -m "feat: add oil signal CLI config"
```

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-02-23-oil-signal-pipeline.md`. Two execution options:

1. **Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration  
2. **Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

Which approach?
