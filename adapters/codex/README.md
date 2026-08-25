# Codex Adapter

Repository discovery: copy the canonical `plugins/dravux/skills/dravux/` folder to `.agents/skills/dravux/`. Personal discovery: copy it to `$HOME/.agents/skills/dravux/`. The skill is self-contained (bundled `schemas/`, stdlib-only scripts). `agents/openai.yaml` supplies optional desktop UI metadata. Prefer repository discovery for isolated testing and personal discovery only when the user wants Dravux available in every Codex project. A native plugin install is invoked as `$dravux:dravux`; a raw skill copy is invoked as `$dravux`. Do not use `$HOME/.codex/skills/dravux` as the public personal-install location.

Invoke explicitly with `$dravux` or let Codex match the skill description.

Codex Desktop uses the same skill locations. Open the containing project, use the Skills UI or explicit `$dravux` invocation to confirm discovery, and start a new session if a newly created skill directory does not appear.

Disposable-copy invocation test (run from the extracted release root before relying on a deployment):

```bash
DRAVUX_COPY="$(mktemp -d)/dravux"
cp -R plugins/dravux/skills/dravux "$DRAVUX_COPY"
cd "$DRAVUX_COPY"
python3 scripts/dravux_contract.py assets/report-template.json
python3 scripts/dravux_run.py preflight assets/preflight-template.json
python3 scripts/dravux_run.py validate assets/run-envelope-template.json
```

Expect `VALID` with exit `0`, `LIMITATION_ACK_REQUIRED` with exit `3`, then a `DRAVUX RUN RECEIPT` with exit `0`. Every reference the skill needs must resolve inside the copy alone.

Do not add Codex-specific verdict rules. The shared skill, bundled schemas, and `references/execution-gates.md` remain authoritative.

Codex must resolve paths from the installed skill's `SKILL.md`, not the repository working directory. For an audit, validate the report and complete operational run before presenting a Dravux result. A missing saved file is not permission to skip validation; both validators accept complete JSON through stdin.

Installing the skill grants no network access, browser, rendered page, DOM, screenshots, repository metadata, or credentials. Sandbox network access is off by default, so a live-site request usually stops at `LIMITATION_ACK_REQUIRED` until the user enables it or moves the audit to a surface with a browser capability; that stop is a correct capability result, not a failed audit. `docs/capabilities.md` holds the per-surface matrix, and the skill carries `references/capability-matrix.md` and `references/github-evidence.md`.

Write audit artifacts outside the skill folder, the repository, and any extracted release tree. Obtain the destination from `python3 <skill-root>/scripts/dravux_run.py output-dir`.

Official references:

- <https://learn.chatgpt.com/docs/build-skills>
- <https://learn.chatgpt.com/docs/build-plugins>
