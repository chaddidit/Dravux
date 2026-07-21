# Expected Results

## Broken state

- Automated result: `FAIL`
- Final status: `VERIFIED FAIL`
- Normative findings: 5
  - 3.1.1 Language of Page
  - 1.1.1 Non-text Content
  - 1.4.3 Contrast (Minimum)
  - 2.5.8 Target Size (Minimum): two undersized targets fail the spacing exception
  - 2.4.7 Focus Visible: focus outline explicitly suppressed without replacement

Machine-readable evidence: `expected/broken-report.json`.

## Repaired state

- Automated result: `PASS`
- Final status: `INCOMPLETE`
- Deterministic findings: 0
- Manual checks still required: keyboard, screen reader, zoom/reflow, and state coverage

Machine-readable evidence: `expected/repaired-report.json`.

## Invariant

The repaired state must never be shown as `VERIFIED PASS` until the declared manual checks are completed and evidenced.
