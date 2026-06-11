# SPCX Newsletter — Netlify deploy

Self-contained static newsletter: **SPCX 上市前夜：三波買盤、五段解禁**.

- `index.html` — the full newsletter (single self-contained file, no external build).

## Deploy (Git-based)

1. In the Netlify dashboard: **Add new site → Import an existing project** and
   connect the `traderx888/notion-autopublish` repo.
2. Pick the branch you want to publish (this work lives on
   `claude/spcx-newsletter-netlify-ep3g53`; merge to `main` to publish from there).
3. Build settings are read from the repo root [`netlify.toml`](../../netlify.toml):
   - Build command: *(none — static site)*
   - Publish directory: `outputs/spcx-newsletter`
4. Deploy. Every push to the connected branch re-publishes automatically.
