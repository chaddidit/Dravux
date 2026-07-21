# GitHub Live Beta Kit

This synthetic, stage-safe demo shows a real contract transition without a remote repository or token.

1. `broken/index.html` contains five bounded deterministic WCAG 2.2 failures, including explicit target-spacing geometry and explicit focus-indicator suppression so the demo does not infer either failure from absence alone.
2. `scripts/audit_demo_html.py` produces a valid Dravux report and automated `FAIL`.
3. The scoped repair in `repaired/index.html` removes those deterministic failures.
4. The rerun produces automated `PASS` with final `INCOMPLETE` because manual checks remain.

The default path is fully offline. `github/accessibility-scanner` is documented only as an optional advanced adapter because its current workflow requires a write-capable fine-grained PAT.

Start with `runbook-5-7-minutes.md`.
