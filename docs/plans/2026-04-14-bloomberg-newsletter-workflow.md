# Bloomberg Newsletter Pipeline — Operator Runbook

**Owner:** Claude agent (notion-autopublish)
**Last updated:** 2026-04-14
**Status:** Active — 35 newsletters published (#1–#35)

---

## Overview

End-to-end pipeline that converts Bloomberg PDF research into bilingual (中文/EN)
newsletter HTML pages, published to GitHub Pages with two access tiers:

| Tier | URL | Access |
|------|-----|--------|
| **Student** | `student.html` | Password-gated, browse all issues |
| **Public** | `public.html?issue=<slug>` | Single issue per link, no password |

---

## Pipeline Steps

### Step 0 — Tag new PDFs (manual)

New PDFs land in `C:\blp\data\`. Files with cryptic names (e.g. `TCJ9INT9...pdf`)
or missing topic tags need renaming before conversion.

**Valid topic hashtags:** `#rates` `#china` `#japan` `#geopolitics` `#oil` `#trade`
`#growth` `#metals` `#inflation` `#policy` `#valuations` `#volatility`
`#semiconductor` `#credit` `#space`

**Naming convention:**
```
Descriptive Title Here #topic1 #topic2.pdf
```

When Claude runs the pipeline, it:
1. Reads page 1 of each untagged PDF
2. Determines appropriate topic tags from content
3. Renames files with descriptive names + hashtags
4. Proceeds to conversion

### Step 1 — PDF → Markdown conversion

```bash
python tools/bloomberg_pdf_convert.py
```

- Scans `C:\blp\data\` for new PDFs not yet in state
- Extracts text via `pypdf`, strips Bloomberg disclaimers
- Parses `#hashtag` topics from filename
- Writes `.md` files to `C:\blp\data\md_converted\`
- State tracked in `outputs/ops/bloomberg_pipeline_state.json`

**Dry run:** `python tools/bloomberg_pdf_convert.py --dry-run`

### Step 2 — Newsletter build (Claude editorial synthesis)

```bash
python tools/bloomberg_newsletter_build.py
```

- Groups unprocessed articles by topic
- Requires minimum 3 articles per topic to generate a newsletter
- Calls Claude API for editorial synthesis (stat grids, investment implications, bilingual summaries)
- Generates newsletter HTML in `output/newsletter_<N>_<topic>.html`
- Auto-updates `output/student.html` with new issue cards
- Continues numbering from `lastNewsletterNumber` in state

**Dry run:** `python tools/bloomberg_newsletter_build.py --dry-run`

### Step 3 — Commit & push

```bash
git add output/newsletter_*.html output/student.html outputs/ops/bloomberg_pipeline_state.json
git commit -m "feat: newsletters #N-#M from latest Bloomberg PDFs (X new articles)"
git push origin HEAD:main
```

GitHub Pages auto-deploys from `main`.

---

## Key Files

| File | Purpose |
|------|---------|
| `tools/bloomberg_pdf_convert.py` | Step 1: PDF → Markdown |
| `tools/bloomberg_newsletter_build.py` | Step 2: Markdown → Newsletter HTML |
| `tools/bloomberg_weekly_digest.py` | Weekly digest builder (separate flow) |
| `outputs/ops/bloomberg_pipeline_state.json` | Pipeline state (processed files, newsletter counter) |
| `output/student.html` | Student portal — all issues |
| `output/public.html` | Public viewer — single issue per link |
| `output/newsletter_*.html` | Individual newsletter pages |
| `C:\blp\data\` | Source PDFs |
| `C:\blp\data\md_converted\` | Converted markdown files |

---

## Access Tiers

### Student tier (`student.html`)
- Password-gated via `sessionStorage("student_auth")`
- Can browse all 35+ issues freely
- Links to dashboards (SMM, P-Model, etc.)

### Public tier (`public.html`)
- No password required
- Shows only ONE issue per link via `?issue=` query param
- No navigation to other issues
- Banner links to student tier for upgrade

### Auth protection on newsletter pages
- Each `newsletter_*.html` includes a `<script>` tag that checks `sessionStorage("student_auth")`
- If accessed directly (not from student portal), redirects to `student.html`
- The build script auto-injects this protection

---

## Current Issue Index (as of 2026-04-14)

| Range | Topics |
|-------|--------|
| #1–#5 | Trade, Japan, Tech/Macro, Iran/Oil, Central Banks/China |
| #6–#10 | Geopolitics, Growth, Rates, Trade |
| #11–#15 | Inflation, China, Policy, Metals, Oil |
| #16–#19 | Japan, Valuations, Volatility, Credit |
| #20–#23 | China, Growth, Japan/Inflation, Oil/Geopolitics |
| #24–#30 | Oil, Credit, Misc, Geopolitics, China, Growth/Trade, Rates/Japan |
| #31–#35 | Growth, Volatility, Geopolitics, Oil, Trade/China |

**Skipped topics** (below 3-article threshold): semiconductor (2), space (1), metals (1), rates (1)

---

## Troubleshooting

### f-string escape error in build script
JavaScript `{}` braces in the HTML template must be escaped as `{{}}` inside
Python f-strings. Both `bloomberg_newsletter_build.py` and `bloomberg_weekly_digest.py`
have auth check scripts that need this escaping.

### Windows encoding
Always set `PYTHONIOENCODING=utf-8` or the scripts auto-reconfigure stdout
for CJK filename support.

### Duplicate TCx files
Bloomberg terminal sometimes produces English + Chinese versions of the same
report. Both get converted — the build script deduplicates by content during
synthesis.
