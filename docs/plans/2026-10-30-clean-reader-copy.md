# Reader-facing copy cleanup
Owner: Codex. Branch: codex/idea-clean-reader-copy-20261030.
Scope: student.html and all 15 draft pages (all *draft*.html in output).
Remove internal numbering, batch descriptions, extraction labels, production dates and tool references. Retain source filenames, report dates and substantive uncertainty in reader-facing language. Keep URLs and authentication unchanged. No downstream schema impact.
Verification: BeautifulSoup visible-text audit PASS (only remaining batch word refers to bond tranches); all links and scripts match baseline across 16 pages; git diff --check PASS. Scoped secret scan PASS. Deployment pending.
Deployment COMPLETE: PR 8, commit 744381619b1ca5010fdaac503641bcc5bb5de6c4; Actions 40989353859 success. Public HTTP read-back of all 16 pages matches local verified text after CRLF normalization. Initial byte comparison differed only by line endings. No remaining task work.
