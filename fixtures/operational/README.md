# Operational fixtures

These files exercise the package-level preflight and run contract. They do not change report contract `0.2.0`.
`fixtures/manifest.json` indexes them under `operational_fixtures`.

- `validator-unavailable.preflight.json` must return `UNSUPPORTED` with exit `4`.
- `unsupported-input.preflight.json` must return `UNSUPPORTED` with exit `4` even when the host validators and file reader are available.
- `genuine-not-applicable.run.json` must return a valid `ERROR` / `NOT APPLICABLE` receipt only because a supported target was acquired and execution completed in the narrow not-applicable shape.
- `plugins/dravux/skills/dravux/assets/preflight-template.json` must return `LIMITATION_ACK_REQUIRED` with exit `3`.
- `plugins/dravux/skills/dravux/assets/run-envelope-template.json` must return a valid run receipt with exit `0`.
- `post-acquisition-interaction-failure.run.json` must return a valid run receipt with exit `0`. It records the case run contract `1.2.0` added: the page was acquired, the scripted keyboard interaction then malfunctioned, and the run ends `ERROR` / `INCOMPLETE` with `execution.completed` false, `execution.failure_stage` `INTERACTION`, and a structured `EXECUTION_FAILED` report error. An acquired target plus an automated `ERROR` is legal only in that exact shape.
- `execution-failure-claims-pass.invalid.json` must be rejected: an execution that never completed cannot report an automated `PASS`.
- `execution-complete-with-error.invalid.json` must be rejected: a completed execution carries no failure stage and no error.
- `acquired-false-execution-complete.invalid.json` must be rejected: a failed acquisition cannot claim a completed execution.
- A bare report, including any structurally valid report in `fixtures/passing/`, must be rejected by the operational `validate` command because it has no preflight, acquisition, or execution receipt.
