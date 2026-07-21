# Bounded Live-Source Runbook

1. Declare the exact public URL, page state, read-only authority, time limit, and evidence to collect.
2. Run `dravux_run.py preflight` with requested mode `RENDERED_DOM`. If it returns `LIMITATION_ACK_REQUIRED`, obtain explicit acceptance before retrieval; if declined, produce no report.
3. In an accepted `SOURCE_TEXT` mode, collect only retrieved-text observations and potential advisory hypotheses. In `RAW_SOURCE`, collect only deterministic source facts supported by the exact source.
4. Do not log in, crawl, submit forms, activate controls, or infer rendered behavior from source alone.
5. Map normative findings only when the captured evidence supports a listed WCAG 2.2 criterion.
6. Validate the complete report with the bundled report validator.
7. Validate the preflight, acquisition receipt, and report with the bundled operational validator.
8. Put the emitted run receipt first. A narrow automated `PASS` with open manual checks is `INCOMPLETE`.
