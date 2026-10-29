# Remove internal production notices
Owner: Codex
Branch: codex/idea-remove-internal-notices-20261030
Scope: 15 published October draft HTML pages.
Removed the internal production aside requested by the user. Source dates, substantive uncertainty qualifications and article content remain intact. No downstream schema changes.
Verification: Python asserted exactly 15 pages and one notice removed per page; PASS. git diff --check and scoped secret scan required before push.
Deployment: pending.
