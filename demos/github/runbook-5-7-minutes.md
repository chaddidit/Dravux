# GitHub Demo Runbook - 5 to 7 Minutes

Run from the Dravux package root.

## 0:00-0:45 - Set the boundary

Say: "This is a synthetic page with known failures. The scanner can prove only the rules it runs. Manual checks remain separate."

Reset the live page:

```bash
python3 demos/github/reset_demo.py --state broken
```

## 0:45-1:45 - Show FAIL

```bash
python3 scripts/audit_demo_html.py demos/github/live/index.html --state broken --output out/github-demo/broken-report.json
python3 scripts/validate_report.py out/github-demo/broken-report.json
```

Show the five evidence-backed findings: page language, image alternative, text contrast, two undersized adjacent targets whose 24px spacing circles intersect, and an explicit focus-outline suppression with no replacement.

## 1:45-3:15 - Audience verdict and AI explanation

Ask the room which findings are normative versus advisory. Have the AI explain one scoped issue using evidence, user impact, repair, and verification. Do not ask it to "make the page accessible."

## 3:15-4:30 - Apply the scoped repair

Use the documented patch or copy the repaired state:

```bash
python3 demos/github/reset_demo.py --state repaired
```

Narrate the changes: `lang`, explicit decorative `alt`, higher contrast, two 44px targets with spacing, and a visible focus rule.

## 4:30-5:30 - Rerun

```bash
python3 scripts/audit_demo_html.py demos/github/live/index.html --state repaired --output out/github-demo/repaired-report.json
python3 scripts/validate_report.py out/github-demo/repaired-report.json
```

The expected result is `PASS | INCOMPLETE`.

## 5:30-6:30 - Manual boundary

Open `manual-verification-checklist.md`. Explain that keyboard, screen-reader, zoom/reflow, real state coverage, and content-purpose checks are still required.

## 6:30-7:00 - Close

Say: "We proved the scoped repair. We did not prove the whole page accessible."

If anything fails live, use `offline-fallback.md` and the checked-in expected reports.
