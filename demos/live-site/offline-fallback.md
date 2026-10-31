# Live-Source Offline Fallback

If network or acquisition tooling is unavailable:

1. Record an automated `ERROR` for the blocked acquisition stage, with `execution.completed` false and `execution.failure_stage` `ACQUISITION`.
2. Do not reuse remembered, expected, or invented page evidence.
3. Finish the live-source result `INCOMPLETE` unless the declared input is genuinely unsupported and satisfies the contract's `NOT APPLICABLE` rules.
4. Use the fully offline synthetic example under `../github/` if a deterministic demonstration is needed.

Missing capability is never an automated `PASS`.

If no capability preflight can execute, label any narrative `UNVALIDATED DRAFT — NOT A DRAVUX RESULT` and use the fully offline fixture demonstration instead.
