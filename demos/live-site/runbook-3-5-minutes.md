# Bounded Live-Source Runbook

1. Declare the exact public URL, page state, read-only authority, time limit, and evidence to collect.
2. Run `dravux_run.py output-dir` and write every audit file into the folder it prints. Never write inside the Dravux files themselves.
3. Run `dravux_run.py preflight` with requested mode `RENDERED_DOM`. If it returns `LIMITATION_ACK_REQUIRED`, obtain explicit acceptance before retrieval; if declined, produce no report.
4. In an accepted `SOURCE_TEXT` mode, collect only retrieved-text observations and potential advisory hypotheses. In `RAW_SOURCE`, collect only deterministic source facts supported by the exact source.
5. Do not log in, crawl, submit forms, activate controls, or infer rendered behavior from source alone.
6. Map normative findings only when the captured evidence supports a listed WCAG 2.2 criterion.
7. Validate the complete report with the bundled report validator.
8. Validate the preflight, acquisition receipt, execution receipt, and report with the bundled operational validator.
9. Put the emitted run receipt first. A narrow automated `PASS` with open manual checks is `INCOMPLETE`. If the page was acquired but the audit itself broke, record `execution.completed` false with its failure stage and an `EXECUTION_FAILED` report error; that run ends `ERROR` / `INCOMPLETE` and establishes nothing.
