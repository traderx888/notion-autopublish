# Triple Trigger Public Publish Plan

**Goal:** Publish `20260511_triple_trigger_week_newsletter.html` as a public GitHub Pages HTML issue.

**Owner:** Codex

**Branch/worktree:** `codex/2026-05-11-public-newsletter` in `C:\Users\User\Documents\GitHub\notion-autopublish-public-20260511`

**Scope:** Repo-local static public output only. No `fundman-jarvis` artifact or schema impact is expected.

**Architecture:** Copy the reviewed standalone HTML from `C:\Users\User\Documents\2026 公開文章\` into `output/` unchanged so the existing Pages workflow serves it directly from the public site root.

## Tasks

1. Add the HTML issue under `output/` using its source filename.
2. Verify the file is present, parseable as HTML, and contains the expected title and embedded image assets.
3. Run the existing GitHub Pages publication path by committing and pushing the scoped static artifact.
4. Confirm the public URL after deployment.

## Verification Log

- `Get-FileHash -Algorithm SHA256 -LiteralPath <source>, output\20260511_triple_trigger_week_newsletter.html`
  - Result: passed. Source and output hashes both matched `D7B2252A82A613388D9BE579D86110F8DB614B4DA5BC4CC148A9C75351A70429`.
- `Select-String -Path output\20260511_triple_trigger_week_newsletter.html -Pattern '<title>|<body|</html>|data:image|https://www.patreon.com/Aireturn|https://t.me/AIreturn'`
  - Result: passed. Found the expected title, body, closing HTML tag, four embedded `data:image` assets, and public Patreon/Telegram links.
- Local HTTP smoke test with `python -m http.server 8123 --directory output` plus `Invoke-WebRequest http://127.0.0.1:8123/20260511_triple_trigger_week_newsletter.html`
  - Result: passed with HTTP 200 and four embedded image assets.
- Browser render smoke test with installed Chrome headless:
  - Command: `chrome.exe --headless=new --disable-gpu --hide-scrollbars --window-size=1280,1600 --screenshot=<temp screenshot> http://127.0.0.1:8123/20260511_triple_trigger_week_newsletter.html`
  - Result: passed. Screenshot written with 414,684 bytes and visually confirmed the article rendered with Chinese text, masthead, metric cards, and the first embedded table image.
- Playwright note: `npx.cmd --yes playwright screenshot ...` could not run because Playwright's local Chromium browser payload is not installed. The installed Chrome headless check above covered the browser-render verification without downloading a new browser cache.
