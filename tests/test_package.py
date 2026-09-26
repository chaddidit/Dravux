import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# Every test module and method counts towards this number; a deleted test must change it, never vanish.
EXPECTED_TEST_COUNT = 199
SKILL = ROOT / "plugins" / "dravux" / "skills" / "dravux"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
sys.path.insert(0, str(SKILL / "scripts"))

from dravux_contract import INPUT_TYPES, validate_report  # noqa: E402


class PackageTests(unittest.TestCase):
    def test_every_json_file_parses(self):
        for path in ROOT.rglob("*.json"):
            with self.subTest(path=path.relative_to(ROOT)):
                json.loads(path.read_text(encoding="utf-8"))

    def test_generated_demo_reports_use_current_contract(self):
        script = ROOT / "scripts" / "audit_demo_html.py"
        cases = (("broken", "broken-report.json"), ("repaired", "repaired-report.json"))
        with tempfile.TemporaryDirectory() as tmp:
            for state, name in cases:
                path = Path(tmp) / name
                proc = subprocess.run(
                    [sys.executable, str(script), str(ROOT / "demos" / "github" / state / "index.html"), "--state", state, "--output", str(path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                with self.subTest(state=state):
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    report = json.loads(path.read_text(encoding="utf-8"))
                    self.assertEqual(validate_report(report), [])
                    self.assertNotIn("$schema", report, "external generated reports must not contain a dangling schema path")

    def test_package_contains_no_legacy_product_identity(self):
        forbidden = ("gate" + "breaker", "GB" + "-")
        for path in ROOT.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".webp", ".zip"}:
                continue
            relative = str(path.relative_to(ROOT))
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in forbidden:
                self.assertNotIn(marker.lower(), relative.lower(), f"legacy identity in path: {relative}")
                self.assertNotIn(marker.lower(), text.lower(), f"legacy identity in {relative}")

    def test_schema_contract_fields(self):
        finding = json.loads((ROOT / "schemas" / "finding.schema.json").read_text(encoding="utf-8"))
        report = json.loads((ROOT / "schemas" / "dravux-report.schema.json").read_text(encoding="utf-8"))
        expected_finding = {
            "finding_id",
            "target_and_state",
            "input_type",
            "standard",
            "classification",
            "severity",
            "title",
            "evidence",
            "reproduction_steps",
            "user_impact",
            "recommended_repair",
            "verification_steps",
            "confidence",
            "manual_review_required",
            "source",
            "status",
        }
        self.assertEqual(set(finding["required"]), expected_finding)
        self.assertIn("automated_result", report["required"])
        self.assertIn("final_status", report["required"])
        self.assertEqual(report["properties"]["contract_version"]["const"], "0.2.0")
        self.assertEqual(report["properties"]["automated_result"]["enum"], ["PASS", "FAIL", "ERROR"])
        self.assertEqual(
            report["properties"]["final_status"]["enum"],
            ["VERIFIED PASS", "VERIFIED FAIL", "INCOMPLETE", "NOT APPLICABLE"],
        )

    def test_package_version_and_contract_versions_are_explicit(self):
        self.assertRegex(VERSION, r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
        preflight = json.loads((ROOT / "schemas" / "dravux-preflight.schema.json").read_text(encoding="utf-8"))
        run = json.loads((ROOT / "schemas" / "dravux-run.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(preflight["properties"]["package_version"]["const"], VERSION)
        self.assertEqual(preflight["properties"]["preflight_version"]["const"], "1.0.0")
        self.assertEqual(run["properties"]["package_version"]["const"], VERSION)
        declared = re.search(
            r'^RUN_CONTRACT_VERSION\s*=\s*"([^"]+)"',
            (SKILL / "scripts" / "dravux_run.py").read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        self.assertIsNotNone(declared, "dravux_run.py must declare RUN_CONTRACT_VERSION")
        self.assertRegex(declared.group(1), r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
        self.assertEqual(run["properties"]["run_contract_version"]["const"], declared.group(1))
        expected_tooling = f"Dravux demo HTML audit {VERSION}"
        for name in ("broken-report.json", "repaired-report.json"):
            demo = json.loads((ROOT / "demos" / "github" / "expected" / name).read_text(encoding="utf-8"))
            self.assertIn(expected_tooling, demo["run"]["tooling"], name)
        for item in json.loads((ROOT / "fixtures" / "manifest.json").read_text(encoding="utf-8"))["fixtures"]:
            report = json.loads((ROOT / "fixtures" / item["path"]).read_text(encoding="utf-8"))
            for tool in report.get("run", {}).get("tooling", []):
                self.assertNotRegex(
                    tool,
                    r"\bDravux\b.*\b1\.0\.1\b",
                    f"{item['path']} claims legacy tooling in the active 1.0.2 fixture set",
                )
            if item["path"] == "hostile/invalid-semver.invalid.json":
                continue
            if item["path"] == "hostile/unsupported-contract-version.invalid.json":
                self.assertEqual(report["contract_version"], "2.0.0")
            elif "contract_version" in report:
                self.assertEqual(report["contract_version"], "0.2.0")

    def test_beginner_entry_point_names_all_four_routes_before_architecture(self):
        start = (ROOT / "START_HERE.md").read_text(encoding="utf-8")
        self.assertIn(f"VERIFIED: Dravux {VERSION} release tree passed all offline checks", start)
        for route in (
            "Claude Chat or Cowork (no terminal)",
            "Codex or ChatGPT desktop app",
            "Claude Code or Codex command line",
            "Maintainer or developer",
        ):
            self.assertIn(route, start, route)
        for promise in ("What to open", "What success looks like", "Where reports go"):
            self.assertIn(promise, start, promise)
        self.assertIn("dravux-audits", start)
        self.assertIn("It does not give Claude a web", start)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertLess(
            readme.index("## Choose your path"),
            readme.index("# Installation and reference"),
            "the beginner path must come before installation and architecture",
        )
        self.assertLess(readme.index("## Choose your path"), readme.index("## Requirements"))
        self.assertLess(readme.index("## The 60-second self-test"), readme.index("## Troubleshooting"))
        self.assertLess(readme.index("## Troubleshooting"), readme.index("## Reference and architecture"))
        self.assertIn("docs/capabilities.md", readme)
        self.assertIn("START_HERE.md", readme)

    def test_troubleshooting_is_symptom_led_and_explains_the_correct_stop(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for symptom in (
            "### Claude stopped before the audit and said `LIMITATION_ACK_REQUIRED`",
            "### I only got source text, not the real page",
            "### Where did my report go?",
            "### The ZIP will not install",
            "### I need evidence from GitHub",
        ):
            self.assertIn(symptom, readme, symptom)
        self.assertIn("**This is Dravux working correctly.** It is not an error", readme)
        self.assertIn("Your next action:", readme)
        self.assertIn("scripts/dravux_run.py output-dir", readme)
        self.assertIn("dravux-audits", readme)
        self.assertIn("single folder named `dravux` containing `SKILL.md`", readme)
        self.assertIn("Installing Dravux never grants network access", readme)

    def test_installer_projection_guides_are_tracked_sources(self):
        guides = {
            "INSTALLERS/README.md": ("Claude-Chat-Cowork/", "Codex-ChatGPT/"),
            "INSTALLERS/Claude-Chat-Cowork/README.md": ("dravux.zip", "Customize > Skills"),
            "INSTALLERS/Codex-ChatGPT/README.md": ("Dravux-OpenAI-Plugin-Source.zip", "$dravux"),
        }
        for name, expected in guides.items():
            path = ROOT / name
            with self.subTest(guide=name):
                self.assertTrue(path.is_file())
                text = path.read_text(encoding="utf-8")
                for token in expected:
                    self.assertIn(token, text)
                self.assertIn("does not", text.lower(), "each installer guide must state its limits")
        # In a source checkout there are no archives here at all; in an extracted release the only
        # archives present are the two injected at build time.
        allowed = {
            "INSTALLERS/Claude-Chat-Cowork/dravux.zip",
            "INSTALLERS/Codex-ChatGPT/Dravux-OpenAI-Plugin-Source.zip",
        }
        present = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "INSTALLERS").rglob("*")
            if path.suffix == ".zip"
        }
        self.assertTrue(present <= allowed, f"unexpected archive under INSTALLERS/: {present - allowed}")

    def test_tester_docs_state_the_self_test_and_truthful_claims(self):
        expected_line = f"VERIFIED: Dravux {VERSION} release tree passed all offline checks"
        quickstart = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")
        checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")
        self.assertIn("dravux_run.py output-dir", quickstart)
        self.assertIn("START_HERE.md", quickstart)
        for name, text in (("quickstart.md", quickstart), ("release-checklist.md", checklist)):
            self.assertIn("sh verify-release.sh", text, name)
            self.assertIn(expected_line, text, name)
        self.assertIn("Unicode line/paragraph separators", checklist)
        self.assertIn("Bounded JSON ingress is a shipped operational control", checklist)
        self.assertIn("262,144 characters", checklist)
        self.assertNotIn("- [x]", checklist)
        self.assertIn("git status", checklist)

    def test_artifact_guides_put_integrity_before_use_without_authenticity_overclaim(self):
        disclosure = "Publisher authenticity was not independently verified."
        guides = {
            "README.md": ("## Verify a downloaded artifact before using it", "## The 60-second self-test"),
            "START_HERE.md": ("## Verify the artifact before any route", "## Path 1"),
            "SECURITY.md": ("## Before you extract, upload, install, or run a download", "## What the integrity checks prove"),
            "docs/quickstart.md": ("## Artifact integrity gate", "## Quick self-test"),
            "INSTALLERS/README.md": ("## Integrity gate", "Using Claude Code or the Codex command line"),
            "INSTALLERS/Claude-Chat-Cowork/README.md": ("## Integrity gate", "## Steps"),
            "INSTALLERS/Codex-ChatGPT/README.md": ("## Integrity gate", "## Install from this package"),
            "docs/release-checklist.md": ("## Artifact order and authenticity", "## Quick self-test"),
        }
        for name, (gate, first_use) in guides.items():
            text = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(guide=name):
                self.assertIn(disclosure, text)
                self.assertIn("no cryptographic publisher signature", text.lower())
                self.assertLess(text.index(gate), text.index(first_use))
                self.assertNotRegex(
                    text.lower(),
                    r"checksums?[^.\n]{0,120}prove[^.\n]{0,120}(?:untampered|authentic)",
                )
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("source checkout intentionally has no installer ZIPs", readme)
        self.assertIn("SECURITY.md", readme)
        self.assertNotIn("dravux.com", readme.lower())
        self.assertIn("SECURITY.md", (ROOT / "START_HERE.md").read_text(encoding="utf-8"))
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("No DNS in the offline validator", security)
        self.assertIn("docs/portability.md", security)

        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("report contract from `0.1.0` to `0.2.0`", changelog)
        self.assertIn("operational run contract from `1.1.0` to `1.2.0`", changelog)
        reset = (ROOT / "demos" / "github" / "reset-instructions.md").read_text(encoding="utf-8")
        self.assertIn("Do not rewrite the tracked demo in place", reset)
        self.assertLess(reset.index("--destination"), reset.index("Maintainer-only in-place reset"))

    def test_every_relative_json_schema_reference_resolves(self):
        for path in ROOT.rglob("*.json"):
            if "__pycache__" in path.parts:
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            reference = payload.get("$schema")
            if not isinstance(reference, str) or reference.startswith(("http://", "https://")):
                continue
            with self.subTest(path=path.relative_to(ROOT), reference=reference):
                self.assertTrue((path.parent / reference).resolve().is_file())

    def test_published_schema_contains_representable_semantic_guards(self):
        finding = json.loads((ROOT / "schemas" / "finding.schema.json").read_text(encoding="utf-8"))
        report = json.loads((ROOT / "schemas" / "dravux-report.schema.json").read_text(encoding="utf-8"))
        run = json.loads((ROOT / "schemas" / "dravux-run.schema.json").read_text(encoding="utf-8"))
        encoded_report = json.dumps(report, sort_keys=True)
        encoded_finding = json.dumps(finding, sort_keys=True)
        encoded_run = json.dumps(run, sort_keys=True)
        self.assertIn('"UNSUPPORTED"', encoded_report)
        self.assertIn('"NOT_APPLICABLE"', encoded_report)
        self.assertIn('"MANUAL_OBSERVATION"', encoded_report)
        self.assertIn('"manual_check_id"', encoded_report)
        self.assertIn('"manual_check_id"', encoded_finding)
        self.assertIn('"maxItems": 0', encoded_report)
        self.assertIn('"Web Content Accessibility Guidelines"', encoded_finding)
        self.assertIn('"version": {"const": "2.2"}', encoded_finding)
        self.assertIn('"https://www.w3.org/TR/WCAG22/#contrast-minimum"', encoded_finding)
        self.assertIn('"status": {"const": "OPEN"}', encoded_report)
        self.assertIn('"automated_result": {"const": "PASS"}', encoded_report)
        self.assertIn('"final_status": {"not": {"const": "VERIFIED FAIL"}}', encoded_report)
        self.assertIn('"classification": {"const": "NORMATIVE"}', encoded_report)
        self.assertIn('"manual_evidence": {"const": false}', encoded_run)
        self.assertIn('"manual_checks_completed": {"maxItems": 0}', encoded_run)
        self.assertIn('"screenshots": {"const": true}', encoded_run)
        self.assertIn('"type": {"const": "SCREENSHOT"}', encoded_run)
        self.assertIn('"selected_mode": {"const": "CONTRACT_ONLY"}', encoded_run)
        self.assertIn('"final_status": {"const": "INCOMPLETE"}', encoded_run)
        self.assertIn('"errors": {"maxItems": 0}', encoded_run)

    def test_every_schema_free_text_field_excludes_line_breaking_characters(self):
        """Every base string property in the published schemas carries the control-character exclusion.

        Closed-alphabet fields (identifiers, hashes, URLs, date-times) have their own stricter shape.
        Conditional refinements under allOf/if/then only narrow a base property and are not walked.
        """
        closed_alphabet = {"audit_id", "finding_id", "content_sha256", "url", "started_at", "completed_at", "acquired_at"}
        fragment = "\\u2028\\u2029"

        def walk(node, path, found):
            if isinstance(node, dict):
                declared = node.get("type")
                declared = declared if isinstance(declared, list) else [declared]
                if "string" in declared and not any(key in node for key in ("enum", "const")):
                    found.append((path, node))
                for key, value in node.items():
                    if key in ("allOf", "if", "then", "else", "oneOf"):
                        continue
                    walk(value, f"{path}/{key}", found)
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{path}[{index}]", found)

        for name in ("dravux-preflight.schema.json", "dravux-run.schema.json", "dravux-report.schema.json", "finding.schema.json"):
            schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            found = []
            walk(schema, name, found)
            self.assertTrue(found, name)
            for path, node in found:
                leaf = path.rsplit("/", 1)[-1]
                if leaf in closed_alphabet or (leaf == "items" and path.rsplit("/", 2)[-2] in closed_alphabet):
                    continue
                with self.subTest(field=path):
                    self.assertIn(fragment, node.get("pattern", ""), f"{path} lacks the control-character pattern")

    def test_suite_size_is_declared(self):
        suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
        self.assertEqual(suite.countTestCases(), EXPECTED_TEST_COUNT, "update EXPECTED_TEST_COUNT when tests are added or removed")

    def test_run_schema_publishes_the_execution_invariants(self):
        run = json.loads((ROOT / "schemas" / "dravux-run.schema.json").read_text(encoding="utf-8"))
        self.assertIn("execution", run["required"])
        execution = run["properties"]["execution"]
        self.assertEqual(set(execution["required"]), {"completed", "failure_stage", "error"})
        self.assertFalse(execution["additionalProperties"])
        clauses = [clause for clause in run["allOf"] if "execution" in json.dumps(clause.get("if", {}))]
        self.assertEqual(len(clauses), 2, "both the completed-true and completed-false clauses must be published")
        branches = {
            json.dumps(clause["if"]["properties"]["execution"]["properties"]["completed"]["const"]): clause["then"]
            for clause in clauses
        }
        self.assertEqual(branches["true"]["properties"]["execution"]["properties"]["failure_stage"], {"const": None})
        self.assertEqual(branches["true"]["properties"]["execution"]["properties"]["error"], {"const": None})
        incomplete = branches["false"]["properties"]["report"]["properties"]
        self.assertEqual(incomplete["automated_result"], {"not": {"const": "PASS"}})
        self.assertIn("VERIFIED PASS", incomplete["final_status"]["not"]["enum"])

    def test_published_report_schema_requires_completed_manual_checks_for_verified_pass(self):
        report = json.loads((ROOT / "schemas" / "dravux-report.schema.json").read_text(encoding="utf-8"))
        branch = next(
            clause["then"]
            for clause in report["allOf"]
            if clause.get("if", {}).get("properties", {}).get("final_status") == {"const": "VERIFIED PASS"}
        )
        scope = branch["properties"]["scope"]["properties"]
        self.assertEqual(scope["required_manual_checks"], {"minItems": 1})
        self.assertEqual(scope["manual_checks_completed"], {"minItems": 1})

    def test_operational_tooling_strings_name_the_current_run_contract(self):
        declared = re.search(
            r'^RUN_CONTRACT_VERSION\s*=\s*"([^"]+)"',
            (SKILL / "scripts" / "dravux_run.py").read_text(encoding="utf-8"),
            re.MULTILINE,
        ).group(1)
        checked = 0
        for path in sorted((SKILL / "assets").glob("*.json")) + sorted((ROOT / "fixtures" / "operational").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            report = payload.get("report", payload)
            tooling = report.get("run", {}).get("tooling", []) if isinstance(report, dict) else []
            for entry in tooling:
                if isinstance(entry, str) and entry.startswith("Dravux operational contract "):
                    checked += 1
                    with self.subTest(path=path.relative_to(ROOT)):
                        self.assertEqual(entry, f"Dravux operational contract {declared}")
        self.assertGreater(checked, 0)

    def test_skill_has_clean_frontmatter_and_gotchas(self):
        skill = SKILL / "SKILL.md"
        text = skill.read_text(encoding="utf-8")
        self.assertNotIn("TODO", text)
        self.assertIn("## Gotchas", text)
        self.assertIn("Do not create or use subagents, delegated workers, verifiers", text)
        self.assertLess(len(text.splitlines()), 500)
        frontmatter = text.split("---", 2)[1]
        keys = [line.split(":", 1)[0] for line in frontmatter.splitlines() if ":" in line]
        self.assertEqual(keys, ["name", "description"])

    def test_invalid_report_is_error_not_accessibility_failure(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        verdict = (SKILL / "references" / "verdict-and-evidence.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("contract/schema validation failure is an execution/contract `ERROR`", skill)
        self.assertIn("do not credit claims inside it", skill)
        self.assertIn("automated `ERROR` with final `INCOMPLETE`", skill)
        self.assertIn("contract/schema validation failure as an execution/contract `ERROR`", verdict)
        self.assertIn("Invalid report content cannot establish automated `FAIL` or final `VERIFIED FAIL`", verdict)

    def test_response_only_results_require_bundled_validation(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        verdict = (SKILL / "references" / "verdict-and-evidence.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("<skill-root>/scripts/dravux_contract.py -", skill)
        self.assertIn("interpret or summarize it only after exit `0`", skill)
        self.assertIn("UNVALIDATED DRAFT — NOT A DRAVUX RESULT", skill)
        self.assertIn("live-URL reports through the bundled validator", verdict)
        self.assertIn("<skill-root>/scripts/dravux_run.py validate -", skill)
        self.assertIn("Only operational-validator exit `0` establishes a Dravux run", skill)

    def test_live_url_and_no_repair_execution_defaults_are_bounded(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        gates = (SKILL / "references" / "execution-gates.md").read_text(encoding="utf-8")
        inputs = (SKILL / "references" / "input-capabilities.md").read_text(encoding="utf-8")
        runbook = (ROOT / "demos" / "live-site" / "README.md").read_text(encoding="utf-8")
        self.assertIn("only after preflight is `READY`", skill)
        self.assertIn("explicitly accepted lower mode", skill)
        self.assertIn("do not crawl, log in, submit forms, activate controls", skill)
        self.assertIn("NOT APPLICABLE — no repair authorized or performed", gates)
        self.assertIn("## Source-only live mode", inputs)
        self.assertIn("redirect chain", inputs)
        self.assertIn("requested and selected evidence modes", skill)
        for name, text in (("skill", skill), ("inputs", inputs), ("runbook", runbook)):
            with self.subTest(dns_policy=name):
                self.assertIn("disable automatic redirect following", text.lower())
                self.assertIn("initial URL", text)
                self.assertIn("A and AAAA", text)
                self.assertIn("globally routable", text)
                self.assertIn("ACQUISITION_FAILED", text)
                self.assertIn("performs no DNS", text)
                self.assertIn("cannot prove that the recorded redirect chain is complete", text)
                self.assertIn("cannot eliminate DNS rebinding", text)

    def test_required_platform_adapters_exist(self):
        required = [
            ROOT / "adapters" / "codex" / "README.md",
            ROOT / "adapters" / "claude" / "README.md",
            ROOT / "adapters" / "chatgpt" / "README.md",
            ROOT / "adapters" / "github-copilot" / "copilot-instructions.md",
        ]
        self.assertTrue(all(path.is_file() for path in required))

    def test_chatgpt_chat_attachment_is_not_described_as_installation(self):
        adapter = (ROOT / "adapters" / "chatgpt" / "README.md").read_text(encoding="utf-8")
        self.assertIn("Plugins are not available in ordinary Chat mode", adapter)
        self.assertIn("supplies conversation context only", adapter)
        self.assertIn("UNVALIDATED DRAFT — NOT A DRAVUX RESULT", adapter)
        self.assertNotIn("attach the complete `skill/dravux/` folder", adapter)

    def test_surface_docs_require_preflight_and_truthful_distribution(self):
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        surfaces = (SKILL / "references" / "surface-modes.md").read_text(encoding="utf-8")
        claude = (ROOT / "adapters" / "claude" / "README.md").read_text(encoding="utf-8")
        self.assertIn("audit a website is at least `RENDERED_DOM`", skill)
        self.assertIn("do not silently replace it", skill.lower())
        self.assertIn("Installing a skill answers only the first question", surfaces)
        self.assertIn("Upload the dedicated custom-skill ZIP", surfaces)
        self.assertIn("The pre-publication plugin-source ZIP is not a one-click web installer", surfaces)
        self.assertIn("Customize > Skills", claude)

    def test_active_package_never_uses_literal_1_01(self):
        forbidden = "1" + "." + "01"
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".webp", ".zip"}:
                continue
            self.assertNotIn(forbidden, path.read_text(encoding="utf-8", errors="ignore"), str(path))

    def test_manual_check_guidance_matches_verified_fail_rule(self):
        for path in (
            SKILL / "references" / "manual-checks.md",
            ROOT / "docs" / "manual-verification-checklist.md",
        ):
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIn("Pending checks block `VERIFIED PASS`", text)
                self.assertIn("do not erase an independently established `VERIFIED FAIL`", text)

    def test_duplicate_detection_uses_linear_counting(self):
        validator = (SKILL / "scripts" / "dravux_contract.py").read_text(encoding="utf-8")
        self.assertIn("Counter(strings)", validator)
        self.assertIn("Counter(ids)", validator)
        self.assertNotIn("strings.count(", validator)
        self.assertNotIn("ids.count(", validator)

    def test_public_package_has_no_private_workspace_markers(self):
        forbidden = [
            "/" + "Users" + "/",
            "/example/" + "private-workspace/",
            "restricted/" + "legal-records",
            "restricted/" + "billing-records",
        ]
        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".webp", ".zip"}
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in forbidden:
                self.assertNotIn(marker, text, f"{marker} leaked in {path.relative_to(ROOT)}")

    def test_no_secret_like_values(self):
        patterns = [
            re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
            re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
            re.compile(r"AKIA[0-9A-Z]{16}"),
            re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
        ]
        for path in ROOT.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".zip"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                self.assertIsNone(pattern.search(text), f"secret-like value in {path.relative_to(ROOT)}")

    def test_no_nested_git_or_symlinks(self):
        nested = [str(path.relative_to(ROOT)) for path in ROOT.rglob(".git") if path.parent != ROOT]
        self.assertEqual(nested, [], f"nested git repositories present: {nested}")
        self.assertFalse(any(path.is_symlink() for path in ROOT.rglob("*")))

    def test_package_has_no_removed_design_tool_references(self):
        # Forbidden tokens are constructed at runtime so this test file cannot match itself.
        product = "fig" + "ma"
        binary_extension = re.compile(r"\." + "fig" + r"\b", re.IGNORECASE)
        removed_tools = [
            re.compile(r"\b" + "st" + "ark" + r"\b", re.IGNORECASE),
            # Product name only: case-sensitive so ordinary English ("usually able to") is not a hit.
            re.compile(r"\b" + "Ab" + "le" + r"\b"),
            re.compile(r"\b" + "a11y " + "focus " + "orderer" + r"\b", re.IGNORECASE),
            re.compile(r"\b" + "axe for " + "designers" + r"\b", re.IGNORECASE),
        ]
        self.assertFalse((ROOT / "demos" / product).exists(), f"removed demo directory demos/{product} still exists")
        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".webp", ".zip"}
            ):
                continue
            relative = str(path.relative_to(ROOT))
            self.assertNotIn(product, relative.lower(), f"removed product name in path: {relative}")
            text = path.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn(product, text.lower(), f"removed product reference in {relative}")
            self.assertIsNone(binary_extension.search(text), f"proprietary design extension in {relative}")
            for pattern in removed_tools:
                self.assertIsNone(pattern.search(text), f"removed tool reference in {relative}")

    def test_validator_and_all_bundled_schemas_share_exact_supported_input_types(self):
        expected = [
            "WEBSITE",
            "SOURCE_CODE",
            "MARKDOWN",
            "STRUCTURED_CONTENT",
            "SVG",
            "IMAGE_METADATA",
            "PDF",
            "SCREENSHOT",
            "GITHUB_ARTIFACT",
            "UNSUPPORTED",
        ]
        self.assertEqual(sorted(INPUT_TYPES), sorted(expected))
        self.assertEqual(len(INPUT_TYPES), len(expected))
        schema_paths = [
            ROOT / "schemas" / "dravux-report.schema.json",
            ROOT / "schemas" / "finding.schema.json",
            SKILL / "schemas" / "dravux-report.schema.json",
            SKILL / "schemas" / "finding.schema.json",
        ]
        for path in schema_paths:
            with self.subTest(schema=path.relative_to(ROOT)):
                schema = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(schema["$defs"]["inputType"]["enum"], expected)


if __name__ == "__main__":
    unittest.main()
