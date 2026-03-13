#!/usr/bin/env python3
"""Generate a professional 16:9 dark-theme presentation PDF."""

from reportlab.lib.pagesizes import landscape
from reportlab.lib.units import inch
from reportlab.lib.colors import Color, white, HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_LEFT
from pathlib import Path

# 16:9 slide dimensions
SLIDE_W = 13.333 * inch
SLIDE_H = 7.5 * inch

# Colors
BG_TOP = HexColor("#0a1628")
BG_BOT = HexColor("#111d35")
ACCENT = HexColor("#6c9fff")
ACCENT2 = HexColor("#ff9f43")
SUBTITLE_CLR = HexColor("#8eaadc")
BULLET_CLR = HexColor("#e0e6f0")
MUTED = HexColor("#7b8da6")
SLIDE_NUM_CLR = HexColor("#4a6080")

SLIDES = [
    {
        "num": "01",
        "title": "Introduction to Claude Code",
        "icon": "{}",
        "bullets": [
            "AI agent inside VS Code via extension (Pro/Max subscription)",
            'Agentic workspace: reads, writes, and executes code autonomously',
            '"Bypass Permissions" mode for fully autonomous execution',
        ],
        "accent": ACCENT,
    },
    {
        "num": "02",
        "title": "The Brain: CLAUDE.md",
        "icon": "{}",
        "bullets": [
            "System prompt file \u2014 Claude reads it before every interaction",
            "Teaches file organization, brand assets, workflow structure",
            "Keep under 150\u2013200 lines for token efficiency",
        ],
        "accent": ACCENT2,
    },
    {
        "num": "03",
        "title": "Mastering Claude Code Skills",
        "icon": "{}",
        "bullets": [
            "Markdown files with YAML front matter for custom instructions",
            "Capability uplift vs Encoded preference skills",
            'Official "Skill Creator" auto-builds and benchmarks skills',
        ],
        "accent": HexColor("#9b59b6"),
    },
    {
        "num": "04",
        "title": "Building Professional Websites",
        "icon": "{}",
        "bullets": [
            'Front-End Design Skill prevents "AI slop" look',
            "Brand assets folder for logos, fonts, guidelines",
            "Clone competitor sites from screenshots + HTML",
        ],
        "accent": HexColor("#2ecc71"),
    },
    {
        "num": "05",
        "title": "Screenshot Loop & Deployment",
        "icon": "{}",
        "bullets": [
            "Puppeteer screenshots for visual self-correction",
            'Claude "sees" mismatches and fixes them autonomously',
            "Push to GitHub \u2192 auto-deploy via Vercel",
        ],
        "accent": HexColor("#e74c3c"),
    },
    {
        "num": "06",
        "title": "Agentic Workflows (WAT Framework)",
        "icon": "{}",
        "bullets": [
            "W = Workflows: Markdown SOPs for the AI",
            "A = Agents: Claude coordinates tasks and handles errors",
            "T = Tools: Modular Python scripts for specific actions",
        ],
        "accent": HexColor("#f39c12"),
    },
    {
        "num": "07",
        "title": "Practical Agentic Examples",
        "icon": "{}",
        "bullets": [
            "API integrations via .env keys (Firecrawl, Perplexity)",
            "Self-healing code: auto-fixes errors and resumes",
            "Single prompt \u2192 scrape, analyze, output branded PDF",
        ],
        "accent": HexColor("#1abc9c"),
    },
    {
        "num": "08",
        "title": "AI Executive Assistant",
        "icon": "{}",
        "bullets": [
            "Phase 1: Organized folder structure for context",
            "Phase 2: AI interview to learn your preferences",
            'Phase 3: Custom skills like "Morning Coffee" planner',
        ],
        "accent": HexColor("#3498db"),
    },
    {
        "num": "09",
        "title": "Sub-Agents & Cost Optimization",
        "icon": "{}",
        "bullets": [
            "Spin up parallel sub-agents for simultaneous tasks",
            "Cheap models (Haiku) for research, Opus for synthesis",
            'Prevents "context rot" in main conversation',
        ],
        "accent": HexColor("#e67e22"),
    },
    {
        "num": "10",
        "title": "Monetization Opportunities",
        "icon": "{}",
        "bullets": [
            "Sell specialized agentic workflows to businesses",
            "Launch an AI Automation Agency",
            "25 min manual tasks \u2192 1\u20132 min with AI assistant",
        ],
        "accent": HexColor("#27ae60"),
    },
]


def draw_gradient_bg(c, w, h):
    """Draw a vertical gradient background."""
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
    """Draw thin accent bar at top of slide."""
    c.setFillColor(accent)
    c.rect(0, 7.5 * inch - 4, w, 4, fill=1, stroke=0)


def draw_slide_number(c, num, accent):
    """Draw slide number in bottom-right."""
    c.setFont("Helvetica", 11)
    c.setFillColor(SLIDE_NUM_CLR)
    c.drawRightString(SLIDE_W - 0.6 * inch, 0.4 * inch, f"{num} / 10")


def draw_decorative_dots(c, accent, x, y):
    """Draw subtle decorative dots."""
    c.setFillColor(Color(accent.red, accent.green, accent.blue, 0.15))
    for row in range(3):
        for col in range(3):
            c.circle(x + col * 12, y - row * 12, 3, fill=1, stroke=0)


def draw_title_slide(c):
    """Special title slide (slide 0)."""
    draw_gradient_bg(c, SLIDE_W, SLIDE_H)

    # Large accent circle decoration
    c.setFillColor(Color(ACCENT.red, ACCENT.green, ACCENT.blue, 0.08))
    c.circle(SLIDE_W * 0.8, SLIDE_H * 0.6, 3 * inch, fill=1, stroke=0)
    c.circle(SLIDE_W * 0.15, SLIDE_H * 0.2, 1.5 * inch, fill=1, stroke=0)

    # Accent bar
    c.setFillColor(ACCENT)
    c.rect(0, SLIDE_H - 5, SLIDE_W, 5, fill=1, stroke=0)

    # Title
    c.setFont("Helvetica-Bold", 52)
    c.setFillColor(white)
    c.drawString(1.2 * inch, SLIDE_H - 2.8 * inch, "Mastering Claude Code")

    # Subtitle
    c.setFont("Helvetica", 22)
    c.setFillColor(SUBTITLE_CLR)
    c.drawString(1.2 * inch, SLIDE_H - 3.5 * inch,
                 "Skills, Workflows & Automation Strategies")

    # Divider line
    c.setStrokeColor(Color(ACCENT.red, ACCENT.green, ACCENT.blue, 0.4))
    c.setLineWidth(1.5)
    c.line(1.2 * inch, SLIDE_H - 3.8 * inch, 7 * inch, SLIDE_H - 3.8 * inch)

    # Author
    c.setFont("Helvetica", 16)
    c.setFillColor(MUTED)
    c.drawString(1.2 * inch, SLIDE_H - 4.4 * inch,
                 "Based on content by Nate Herk  |  AI Automation")

    # Source info
    c.setFont("Helvetica", 12)
    c.setFillColor(SLIDE_NUM_CLR)
    c.drawString(1.2 * inch, 0.8 * inch,
                 "Source: 4 YouTube transcripts  |  Processed via NotebookLM + Claude Code")

    # Bottom accent
    c.setFillColor(ACCENT)
    c.rect(0, 0, SLIDE_W, 3, fill=1, stroke=0)


def draw_content_slide(c, slide):
    """Draw a standard content slide."""
    draw_gradient_bg(c, SLIDE_W, SLIDE_H)
    accent = slide["accent"]

    # Top accent bar
    draw_accent_bar(c, accent, SLIDE_W)

    # Decorative circle
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
    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(white)
    c.drawString(1.7 * inch, SLIDE_H - 1.4 * inch, slide["title"])

    # Accent underline
    c.setStrokeColor(accent)
    c.setLineWidth(2.5)
    title_width = c.stringWidth(slide["title"], "Helvetica-Bold", 36)
    c.line(1.7 * inch, SLIDE_H - 1.6 * inch,
           1.7 * inch + min(title_width, 8 * inch), SLIDE_H - 1.6 * inch)

    # Bullets
    y = SLIDE_H - 2.5 * inch
    for j, bullet in enumerate(slide["bullets"]):
        # Bullet dot
        c.setFillColor(accent)
        c.circle(1.5 * inch, y + 8, 6, fill=1, stroke=0)

        # Bullet text
        c.setFont("Helvetica", 20)
        c.setFillColor(BULLET_CLR)

        # Word wrap if needed
        words = bullet.split()
        lines = []
        current_line = ""
        for word in words:
            test = current_line + " " + word if current_line else word
            if c.stringWidth(test, "Helvetica", 20) < 9 * inch:
                current_line = test
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)

        for line in lines:
            c.drawString(1.9 * inch, y, line)
            y -= 30
        y -= 20  # Extra spacing between bullets

    # Decorative dots
    draw_decorative_dots(c, accent, SLIDE_W - 1.2 * inch, 1.5 * inch)

    # Slide number
    draw_slide_number(c, slide["num"], accent)

    # Bottom accent line
    c.setFillColor(accent)
    c.rect(0, 0, SLIDE_W, 3, fill=1, stroke=0)


def main():
    output_path = Path(__file__).parent / "mastering_claude_code_slides.pdf"
    c_pdf = canvas.Canvas(str(output_path), pagesize=(SLIDE_W, SLIDE_H))

    # Title slide
    draw_title_slide(c_pdf)
    c_pdf.showPage()

    # Content slides
    for slide in SLIDES:
        draw_content_slide(c_pdf, slide)
        c_pdf.showPage()

    c_pdf.save()
    print(f"Created: {output_path}")
    print(f"Slides: {len(SLIDES) + 1} (title + {len(SLIDES)} content)")


if __name__ == "__main__":
    main()
