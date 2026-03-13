#!/usr/bin/env python3
"""Generate CiovaccoCapital presentation — focused on intermarket ratios & signals."""

from reportlab.lib.units import inch
from reportlab.lib.colors import Color, white, HexColor
from reportlab.pdfgen import canvas
from pathlib import Path

SLIDE_W = 13.333 * inch
SLIDE_H = 7.5 * inch

# Dark financial green theme
BG_TOP = HexColor("#0b1a14")
BG_BOT = HexColor("#0f2318")
ACCENT = HexColor("#4ecdc4")
ACCENT2 = HexColor("#f7b733")
SUBTITLE_CLR = HexColor("#8ecdc4")
BULLET_CLR = HexColor("#e0eee8")
MUTED = HexColor("#7ba69c")
SLIDE_NUM_CLR = HexColor("#3a6b5e")

TOTAL_SLIDES = 12

SLIDES = [
    {
        "num": "01",
        "title": "The Ratio Framework",
        "bullets": [
            "Core method: compare asset A / asset B ratios on multiple timeframes",
            "Upper-left to lower-right = underperformance (avoid); Lower-left to upper-right = leadership (own)",
            "AVWAP (Anchored VWAP) lines as dynamic support/resistance on ratio charts",
            "Weight of evidence: 136 charts, 489 questions across daily/weekly/monthly frames",
        ],
        "accent": ACCENT,
    },
    {
        "num": "02",
        "title": "Credit Market Health Signals",
        "bullets": [
            "JNK (Junk Bonds): MA stack order (20d/50d/100d/200d) \u2014 blue on top = bullish, flipped = bear",
            "LQD (IG Corporate Bonds): above converging AVWAP = no recession/inflation fear",
            "IEF (US Treasuries): breakout above AVWAP cluster = inflation expectations contained",
            "IEF/LQD ratio: spikes during panic (2008, COVID) \u2014 currently flat = no systemic fear",
        ],
        "accent": HexColor("#e74c3c"),
    },
    {
        "num": "03",
        "title": "Risk-On vs Risk-Off Ratios",
        "bullets": [
            "XLY/XLP (Discretionary vs Staples): new all-time high Oct 2025 = risk appetite strong",
            "SP Low Vol / SP High Beta: defensive ratio near 52-week LOW = bullish for stocks",
            "In 2022 peak: Low Vol/High Beta turned up + XLY/XLP broke down \u2014 neither happening now",
            "VIX: down 40% in 10 days \u2192 historically S&P +16% one year later (100% hit rate)",
        ],
        "accent": ACCENT2,
    },
    {
        "num": "04",
        "title": "Tech Leadership Ratios",
        "bullets": [
            "XLK/SPY: uptrend intact, new all-time high \u2014 prior resistance now acts as AVWAP support",
            "QQQ/SPY (NASDAQ vs S&P): above all AVWAP lines, constructive breakout held",
            "SMH/SPY (Semis vs S&P): above rising 50d/100d/200d MAs \u2014 not in \"big trouble\"",
            "SPYG/SPY (Growth vs S&P): series of higher highs/lows since 2022, above AVWAP cluster",
        ],
        "accent": HexColor("#3498db"),
    },
    {
        "num": "05",
        "title": "Rotation Traps: Don't Chase",
        "bullets": [
            "RSP/XLK (Equal-Weight vs Tech): last thing it did = new all-time LOW \u2192 don't dump tech",
            "IWM/XLK (Small Caps vs Tech): long-term downtrend, counter-trend rallies get given back",
            "ACWX/SPY (Foreign vs S&P): improving but below key resistance from 2018 & 2022 reversals",
            "FNDF/SPYG (Foreign Div vs Growth): new all-time low \u2014 counter-trend move, not trend change",
        ],
        "accent": HexColor("#9b59b6"),
    },
    {
        "num": "06",
        "title": "Gold, Silver & Bitcoin Ratios",
        "bullets": [
            "GLD/SPY: improving since 2022 low, but 2011 peak resistance + multiple AVWAP hurdles remain",
            "SLV/SPY: resistance at same levels that reversed in 2013, 2016, 2020 \u2014 \"may\" hold again",
            "GLD/GBTC (Gold vs Bitcoin): long-term downtrend, late-2024 new lower low \u2014 hold both",
            "Gold sentiment: 9 straight up weeks = historically rare \u2192 near-parabolic, due for breather",
        ],
        "accent": HexColor("#f39c12"),
    },
    {
        "num": "07",
        "title": "Sector Relative Strength Map",
        "bullets": [
            "XLF/XLK (Financials vs Tech): still in long-term downtrend",
            "XLI/XLK (Industrials vs Tech): same pattern \u2014 tech continues to lead",
            "XLV/Large Cap Growth (Healthcare vs Growth): underperforming",
            "KRE/SPY (Regional Banks vs S&P): upper-left to lower-right \u2192 avoided for \"quite some time\"",
        ],
        "accent": HexColor("#2ecc71"),
    },
    {
        "num": "08",
        "title": "European & Foreign Stock Signals",
        "bullets": [
            "ACWX/XLK: long-term downtrend \u2014 Jan 2025 rally ended when tariff news became less bad",
            "EUFN/SPY (Euro Financials vs S&P): higher high in price BUT lower high in RSI = divergence",
            "Key hurdles: 2018 Christmas Eve reversal level + 2022 bear market reversal level",
            "Incremental adds OK, but wholesale rotation premature until AVWAP lines cleared",
        ],
        "accent": HexColor("#1abc9c"),
    },
    {
        "num": "09",
        "title": "SVM Scoring & Quantitative Signals",
        "bullets": [
            "Vulnerability Score (0-100): Dec 2025 near 100 vs July 2001 at 9.45 before -35% drop",
            "Breadth composite buy signal for XLK: 20 signals since 1952, 100% win 1yr, avg +37.7%",
            "4th year of cyclical bull market: historical avg S&P gain +14.6%",
            "Fed rate cut with S&P near all-time high: +14.2% avg next 12 months, 100% win rate",
        ],
        "accent": HexColor("#e67e22"),
    },
    {
        "num": "10",
        "title": "AVWAP: The Key Technical Tool",
        "bullets": [
            "Anchored to major pivots: Oct 2022 low, Apr 2025 tariff low, Feb 2025 high, etc.",
            "Converging AVWAP cluster = major support/resistance zone (like Bollinger squeeze)",
            "Ratio above rising & converging AVWAPs = strong trend; below = deteriorating",
            "Used on absolute price AND ratio charts \u2014 same technique across all asset classes",
        ],
        "accent": HexColor("#e74c3c"),
    },
    {
        "num": "11",
        "title": "Secular Trend & Monthly Bollinger Bands",
        "bullets": [
            "Monthly BB slope: rising = secular bull (1950-68, 1982-2000); flat = stagnation (1969-79)",
            "Key rule: secular bulls never closed below lower monthly BB \u2014 1969 break = regime change",
            "Present day S&P 500: monthly BBs rising, price above bands = secular bull intact",
            "Transition signals are incremental \u2014 SVM detects shifts before they become obvious",
        ],
        "accent": HexColor("#27ae60"),
    },
    {
        "num": "12",
        "title": "Demographics: The Millennial Tailwind",
        "bullets": [
            "2022-2027: median Millennial age = 36 (same as Boomers 1988-94 \u2192 S&P gained 86%)",
            "2028-2034: median Millennial = 42.5 (same as Boomers 1995-2000 \u2192 S&P gained 232%)",
            "\"Double Boom\": 100% of Millennials + growing Gen Z in 25-54 prime working window",
            "Homebuilders/SPY breakout: aligns with secular bull + stronger economy thesis",
        ],
        "accent": HexColor("#3498db"),
    },
]


def draw_gradient_bg(c, w, h):
    steps = 80
    for i in range(steps):
        ratio = i / steps
        r = BG_TOP.red + (BG_BOT.red - BG_TOP.red) * ratio
        g = BG_TOP.green + (BG_BOT.green - BG_TOP.green) * ratio
        b = BG_TOP.blue + (BG_BOT.blue - BG_TOP.blue) * ratio
        c.setFillColor(Color(r, g, b))
        y = h - (i * h / steps)
        c.rect(0, y - h / steps, w, h / steps + 1, fill=1, stroke=0)


def draw_accent_bar(c, accent, w):
    c.setFillColor(accent)
    c.rect(0, 7.5 * inch - 4, w, 4, fill=1, stroke=0)


def draw_slide_number(c, num):
    c.setFont("Helvetica", 11)
    c.setFillColor(SLIDE_NUM_CLR)
    c.drawRightString(SLIDE_W - 0.6 * inch, 0.4 * inch, f"{num} / {TOTAL_SLIDES}")


def draw_decorative_dots(c, accent, x, y):
    c.setFillColor(Color(accent.red, accent.green, accent.blue, 0.15))
    for row in range(3):
        for col in range(3):
            c.circle(x + col * 12, y - row * 12, 3, fill=1, stroke=0)


def draw_title_slide(c):
    draw_gradient_bg(c, SLIDE_W, SLIDE_H)

    c.setFillColor(Color(ACCENT.red, ACCENT.green, ACCENT.blue, 0.08))
    c.circle(SLIDE_W * 0.82, SLIDE_H * 0.55, 3 * inch, fill=1, stroke=0)
    c.circle(SLIDE_W * 0.12, SLIDE_H * 0.25, 1.5 * inch, fill=1, stroke=0)

    c.setFillColor(ACCENT)
    c.rect(0, SLIDE_H - 5, SLIDE_W, 5, fill=1, stroke=0)

    # Title
    c.setFont("Helvetica-Bold", 46)
    c.setFillColor(white)
    c.drawString(1.2 * inch, SLIDE_H - 2.4 * inch, "Ciovacco Capital")
    c.drawString(1.2 * inch, SLIDE_H - 3.1 * inch, "Intermarket Ratio Signals")

    # Subtitle
    c.setFont("Helvetica", 20)
    c.setFillColor(SUBTITLE_CLR)
    c.drawString(1.2 * inch, SLIDE_H - 3.8 * inch,
                 "Cross-Asset Ratios, AVWAP Analysis & Secular Trend Framework")

    # Divider
    c.setStrokeColor(Color(ACCENT.red, ACCENT.green, ACCENT.blue, 0.4))
    c.setLineWidth(1.5)
    c.line(1.2 * inch, SLIDE_H - 4.1 * inch, 9 * inch, SLIDE_H - 4.1 * inch)

    # Author
    c.setFont("Helvetica", 16)
    c.setFillColor(MUTED)
    c.drawString(1.2 * inch, SLIDE_H - 4.7 * inch,
                 "Based on content by Chris Ciovacco  |  CiovaccoCapital.com")

    # Source
    c.setFont("Helvetica", 12)
    c.setFillColor(SLIDE_NUM_CLR)
    c.drawString(1.2 * inch, 0.8 * inch,
                 "Source: 4 YouTube transcripts  |  Processed via Claude Code")

    c.setFillColor(ACCENT)
    c.rect(0, 0, SLIDE_W, 3, fill=1, stroke=0)


def draw_content_slide(c, slide):
    draw_gradient_bg(c, SLIDE_W, SLIDE_H)
    accent = slide["accent"]

    draw_accent_bar(c, accent, SLIDE_W)

    c.setFillColor(Color(accent.red, accent.green, accent.blue, 0.06))
    c.circle(SLIDE_W * 0.85, SLIDE_H * 0.55, 2.5 * inch, fill=1, stroke=0)

    # Slide number badge
    c.setFillColor(Color(accent.red, accent.green, accent.blue, 0.2))
    c.roundRect(0.8 * inch, SLIDE_H - 1.4 * inch, 0.65 * inch, 0.4 * inch,
                5, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(accent)
    c.drawCentredString(1.125 * inch, SLIDE_H - 1.3 * inch, slide["num"])

    # Title
    c.setFont("Helvetica-Bold", 34)
    c.setFillColor(white)
    c.drawString(1.7 * inch, SLIDE_H - 1.4 * inch, slide["title"])

    # Accent underline
    c.setStrokeColor(accent)
    c.setLineWidth(2.5)
    title_width = c.stringWidth(slide["title"], "Helvetica-Bold", 34)
    c.line(1.7 * inch, SLIDE_H - 1.6 * inch,
           1.7 * inch + min(title_width, 8 * inch), SLIDE_H - 1.6 * inch)

    # Bullets (4 per slide, slightly smaller font)
    y = SLIDE_H - 2.4 * inch
    for bullet in slide["bullets"]:
        c.setFillColor(accent)
        c.circle(1.5 * inch, y + 7, 5, fill=1, stroke=0)

        c.setFont("Helvetica", 18)
        c.setFillColor(BULLET_CLR)

        words = bullet.split()
        lines = []
        current_line = ""
        for word in words:
            test = current_line + " " + word if current_line else word
            if c.stringWidth(test, "Helvetica", 18) < 9.5 * inch:
                current_line = test
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)

        for line in lines:
            c.drawString(1.85 * inch, y, line)
            y -= 27
        y -= 15

    draw_decorative_dots(c, accent, SLIDE_W - 1.2 * inch, 1.5 * inch)
    draw_slide_number(c, slide["num"])

    c.setFillColor(accent)
    c.rect(0, 0, SLIDE_W, 3, fill=1, stroke=0)


def main():
    output_path = Path(__file__).parent / "ciovacco_capital_slides.pdf"
    c_pdf = canvas.Canvas(str(output_path), pagesize=(SLIDE_W, SLIDE_H))

    draw_title_slide(c_pdf)
    c_pdf.showPage()

    for slide in SLIDES:
        draw_content_slide(c_pdf, slide)
        c_pdf.showPage()

    c_pdf.save()
    print(f"Created: {output_path}")
    print(f"Slides: {len(SLIDES) + 1} (title + {len(SLIDES)} content)")


if __name__ == "__main__":
    main()
