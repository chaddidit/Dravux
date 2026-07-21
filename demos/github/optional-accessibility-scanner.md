# Optional github/accessibility-scanner Adapter

Status checked 2026-07-16: public preview, MIT-licensed, current repository release v3.3.0.

Do not use it as the default live demo. Its documented workflow requires a fine-grained personal access token with write access to actions, contents, issues, and pull requests; the default GitHub Actions `GITHUB_TOKEN` is not sufficient.

If an operator later approves a staged remote beta:

1. Use a disposable synthetic repository.
2. Review the current README, release, permissions, and security model.
3. Start with `dry_run: true`.
4. Set `skip_copilot_assignment: true` unless Copilot agent behavior is explicitly in scope.
5. Separate hard WCAG failures from best-practice and experimental findings.
6. Never expose credentials or put a password directly in a workflow.
7. Preserve human review before any issue assignment, patch, or merge.

This optional adapter is a future approved stage, not a hidden dependency of Dravux.
