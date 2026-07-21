# Operational fixtures

These files exercise the package-level preflight and run contract. They do not change report contract `0.1.0`.

- `validator-unavailable.preflight.json` must return `UNSUPPORTED` with exit `4`.
- `plugins/dravux/skills/dravux/assets/preflight-template.json` must return `LIMITATION_ACK_REQUIRED` with exit `3`.
- `plugins/dravux/skills/dravux/assets/run-envelope-template.json` must return a valid run receipt with exit `0`.
- A bare report, including any structurally valid report in `fixtures/passing/`, must be rejected by the operational `validate` command because it has no preflight or acquisition receipt.
