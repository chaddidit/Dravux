# Verdict and Evidence Contract

## Automated results

- `PASS`: every deterministic check that actually ran met its expectation.
- `FAIL`: at least one reproducible normative deterministic check failed.
- `ERROR`: reliable automated output was not produced.

## Final statuses

- `VERIFIED PASS`: scope and required manual checks are complete; evidence is valid; no unresolved normative failure remains.
- `VERIFIED FAIL`: an unresolved normative failure has reproducible evidence.
- `INCOMPLETE`: scope, evidence, tooling, repair, regression, or manual review remains incomplete.
- `NOT APPLICABLE`: the check genuinely cannot apply to the target or declared scope.

## Invariants

1. Never infer `VERIFIED PASS` from automated `PASS` alone.
2. Never map `ERROR` to `VERIFIED PASS`.
3. Never let advisory-only findings cause automated `FAIL` or `VERIFIED FAIL`.
4. Require at least one reproducible normative finding for `VERIFIED FAIL`.
5. Require all declared manual checks to be completed for `VERIFIED PASS`.
6. Require a non-empty error record for automated `ERROR`.
7. Use `NOT APPLICABLE` only with automated `ERROR`, an explicit applicability reason, and structured errors whose code is `NOT_APPLICABLE`; tooling failure, uncertainty, and missing evidence remain `INCOMPLETE`.
8. Allow `VERIFIED FAIL` after automated `PASS` or `ERROR` only when at least one declared manual check is completed and a normative finding contains `MANUAL_OBSERVATION` evidence; the automated result remains unchanged.
9. Treat a contract/schema validation failure as an execution/contract `ERROR`, not a normative accessibility `FAIL`; return final `INCOMPLETE` unless the check genuinely cannot apply to the declared target or scope.
10. Stop before interpreting an invalid report and do not credit claims inside it. Invalid report content cannot establish automated `FAIL` or final `VERIFIED FAIL`.
11. Validate response-only and live-URL reports through the bundled validator before stating a Dravux result. If validation is unavailable or nonzero, label the output `UNVALIDATED DRAFT — NOT A DRAVUX RESULT` and do not treat its verdict fields as established.
12. Automated `PASS` cannot carry a normative finding unless the final status is `VERIFIED FAIL` backed by completed manual checks and `MANUAL_OBSERVATION` evidence. A deterministic normative failure requires automated `FAIL`.

## Finding fields

| Field | Rule |
|---|---|
| `finding_id` | Stable and unique within the report |
| `target_and_state` | Exact target plus state/build/view where observed |
| `input_type` | One supported input enum |
| `standard` | WCAG 2.2 name/version/criterion with its W3C criterion URL for normative findings; `null` allowed for advisory findings |
| `classification` | `NORMATIVE` or `ADVISORY` |
| `severity` | User-impact prioritization, separate from classification/confidence |
| `title` | Plain-language barrier description |
| `evidence` | One or more typed evidence items with locators |
| `reproduction_steps` | Ordered and independently repeatable |
| `user_impact` | Who is blocked or burdened and how |
| `recommended_repair` | Scoped repair, not a vague aspiration |
| `verification_steps` | Exact rerun plus manual/regression checks |
| `confidence` | `HIGH`, `MEDIUM`, or `LOW` based on evidence quality |
| `manual_review_required` | `true` whenever human judgment or AT/device use remains |
| `source` | Primary HTTP(S) source title and URL; normative sources use an authoritative W3C URL |
| `status` | `OPEN` means the failure remains unresolved; `REPAIRED` means a change awaits verification; `VERIFIED` means the repair was verified. `VERIFIED FAIL` requires an `OPEN` normative finding, and passing reports preserve resolved history in a separate before report. |

## Evidence quality

- Prefer raw artifacts and stable locators over summaries.
- Record tool name/version and target state for scanner output.
- Include before and after evidence for repairs.
- Keep source-backed facts separate from inference.
- Lower confidence or use `INCOMPLETE` when the evidence cannot support a definitive classification.
