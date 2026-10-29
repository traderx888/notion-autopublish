# Student portal and October drafts: mobile layout

- Owner: Codex
- Branch: `codex/idea-student-mobile-layout-20261030`
- Status: VERIFIED LOCALLY / READY TO DEPLOY
- Authorization: user requested mobile layout inspection of student.html and all 15 drafts, with fixes and publication when needed.

## Evidence and scope

The 15 drafts passed horizontal-boundary checks at actual browser widths of 320, 390 and 430px (45 checks). All 45 checks reproduced undersized navigation: nested proportional font rules reduce table-of-contents links to 12.3904px and source list text to 11.968px; TOC link rectangles are only 18px high. Navigation links are about 24.5px high.

Inspect all portal cards in an isolated local layout fixture containing only public page markup and CSS, with authentication scripts and the login form omitted from the fixture. Production authentication must remain byte-for-byte unchanged. The browser's existing authenticated tab could not be rebound; no stored credential extraction or production authentication bypass is part of this task.

## Plan

1. Record baseline phone-width measurements and screenshots, including portal long-title cards.
2. Apply scoped phone breakpoint styles for readable text, wrapping and touch target spacing.
3. Test all 16 pages at 320/390/430px and representative desktop width; verify text, links, cards and login scripts are unchanged.
4. Scan scoped changes, commit and push the dedicated branch, merge a PR, and verify deployment plus live files and mobile rendering.

Repo-local presentation change only. No research updates, source data, schedules, canonical issue numbers or fundman-jarvis artifact contracts change.

## Fix and verification

- Added `output/mobile-reading.css`, linked by exactly the 16 requested pages. Rules apply only at widths <=600px. Portal grid headers keep the icon and title together, with the date below the title. Draft TOC and navigation targets are at least 44px high; TOC text is 16px and source entries 14px.
- Portal baseline at 320px: 193 cards, no page overflow, but the narrowest archive title column was 71.296875px; first cards placed the icon 55.5px above the title. After the fix, the narrowest title column is 205px and icons align with titles.
- `python apply_mobile_css.py`: PASS; all body text, links, scripts and production gate remain unchanged across all 16 pages.
- `python mobile_preview.py`: PASS; 16 isolated fixture pages, zero scripts and no authentication code; fixture files are outside the repository and never published. Server binds only to loopback.
- CUA browser layout matrix: PASS, 64 checks (16 pages at actual widths 320/390/430/1440), no document overflow or elements outside the viewport, 193 portal cards, all 45 phone article checks pass the 16px TOC / 44px target / 14px source thresholds.
- Mobile interaction checks: PASS; portal card opens draft, notice expands/collapses, TOC and source anchors navigate correctly, return link reaches the October section.
- Mobile portal and article screenshots reviewed. Desktop rules remain unchanged because the entire stylesheet is inside the phone media query.
- Publication and live hash/browser verification pending.
