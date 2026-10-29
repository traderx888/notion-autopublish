# Student portal October newsletter batch

- Owner: Codex
- Branch: `codex/idea-student-newsletter-batch-20261030`
- Status: STATIC VERIFIED / READY TO DEPLOY
- Authorization: user requested publishing the generated batch to the existing student portal, in addition to the illustrated edition already published.

## Scope

Publish the remaining 15 articles from the completed 16-draft October snapshot batch. Draft 02 is represented by the revised six-chart edition already at the top of the portal. Preserve that article, its PDF, all 178 existing cards and login behavior. The earlier prepared-batch page was a preparation index, not the completed articles.

Public copies retain source dates, draft status, excerpt limits and OCR qualifications. Remove local file links, file modification timestamps and local delivery metadata. Do not upload source PDFs, manifests or model inputs. Use date-based draft slugs without assigning canonical issue numbers.

## Plan and verification

1. Prepare public HTML and add 15 cards below the existing illustrated article.
2. Verify article body preservation, all new relative links, unchanged gate/scripts and archive cards, desktop/mobile layout and scoped secret scan.
3. Commit and push only scoped files to the dedicated branch; publish through PR merge.
4. Verify Pages deployment, HTTP responses and SHA-256 for all 16 changed public files.

## Handoff

No changes to schedules, pipeline state, source files, other publishing channels or downstream schemas. `fundman-jarvis` has no consumer contract change. Live verification pending.

- `python publish_batch.py`: PASS; 15 public articles created, all article bodies preserved, 178 old cards retained, 193 total cards; login scripts and gate unchanged.
- `python verify_batch.py`: PASS; 120 source entries preserved, relative links and anchors resolve, unique IDs, one heading per article, explicit draft restrictions, no scripts/forms or event handlers in articles; scoped secret/email/subscriber/local-path scan passed.
- `git diff --check`: PASS. Public files use UTF-8/LF bytes for deployment hash verification.
- Local browser preview was not performed because the browser policy disallowed file URLs. Responsive browser verification is pending on the deployed public HTTPS pages.
- Existing authenticated browser session was refreshed and its top illustrated article opened successfully.
