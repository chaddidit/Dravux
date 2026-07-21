import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "dravux" / "skills" / "dravux"
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
            if not path.is_file() or "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".webp"}:
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
        self.assertEqual(report["properties"]["contract_version"]["const"], "0.1.0")
        self.assertEqual(report["properties"]["automated_result"]["enum"], ["PASS", "FAIL", "ERROR"])
        self.assertEqual(
            report["properties"]["final_status"]["enum"],
            ["VERIFIED PASS", "VERIFIED FAIL", "INCOMPLETE", "NOT APPLICABLE"],
        )

    def test_package_version_and_contract_versions_are_explicit(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "1.0.1")
        preflight = json.loads((ROOT / "schemas" / "dravux-preflight.schema.json").read_text(encoding="utf-8"))
        run = json.loads((ROOT / "schemas" / "dravux-run.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(preflight["properties"]["package_version"]["const"], "1.0.1")
        self.assertEqual(preflight["properties"]["preflight_version"]["const"], "1.0.0")
        self.assertEqual(run["properties"]["package_version"]["const"], "1.0.1")
        self.assertEqual(run["properties"]["run_contract_version"]["const"], "1.0.0")
        for item in json.loads((ROOT / "fixtures" / "manifest.json").read_text(encoding="utf-8"))["fixtures"]:
            report = json.loads((ROOT / "fixtures" / item["path"]).read_text(encoding="utf-8"))
            if item["path"] == "hostile/invalid-semver.invalid.json":
                continue
            if item["path"] == "hostile/unsupported-contract-version.invalid.json":
                self.assertEqual(report["contract_version"], "2.0.0")
            elif "contract_version" in report:
                self.assertEqual(report["contract_version"], "0.1.0")

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
        self.assertIn("only after preflight is `READY`", skill)
        self.assertIn("explicitly accepted lower mode", skill)
        self.assertIn("do not crawl, log in, submit forms, activate controls", skill)
        self.assertIn("NOT APPLICABLE — no repair authorized or performed", gates)
        self.assertIn("## Source-only live mode", inputs)
        self.assertIn("redirect chain", inputs)

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
        self.assertIn("set `requested_mode` to `RENDERED_DOM`", skill)
        self.assertIn("Do not silently replace it", skill)
        self.assertIn("Installing a skill answers only the first question", surfaces)
        self.assertIn("Upload the dedicated custom-skill ZIP", surfaces)
        self.assertIn("The pre-publication plugin-source ZIP is not a one-click web installer", surfaces)
        self.assertIn("Customize > Skills", claude)

    def test_active_package_never_uses_literal_1_01(self):
        forbidden = "1" + "." + "01"
        for path in ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".webp"}:
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

    def test_public_package_has_no_private_vault_path(self):
        forbidden = [
            "/" + "Users" + "/",
            "Chad" + " Ops Vault",
            "02_Areas/" + "Legal_Admin",
            "Billing" + " and Financial",
        ]
        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".webp"}
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
            if not path.is_file() or "__pycache__" in path.parts or path.suffix.lower() == ".pyc":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in patterns:
                self.assertIsNone(pattern.search(text), f"secret-like value in {path.relative_to(ROOT)}")

    def test_no_nested_git_or_symlinks(self):
        self.assertFalse(any(path.name == ".git" for path in ROOT.rglob(".git")))
        self.assertFalse(any(path.is_symlink() for path in ROOT.rglob("*")))

    def test_package_has_no_removed_design_tool_references(self):
        # Forbidden tokens are constructed at runtime so this test file cannot match itself.
        product = "fig" + "ma"
        binary_extension = re.compile(r"\." + "fig" + r"\b", re.IGNORECASE)
        removed_tools = [
            re.compile(r"\b" + "st" + "ark" + r"\b", re.IGNORECASE),
            re.compile(r"\b" + "Ab" + "le" + r"\b", re.IGNORECASE),
            re.compile(r"\b" + "a11y " + "focus " + "orderer" + r"\b", re.IGNORECASE),
            re.compile(r"\b" + "axe for " + "designers" + r"\b", re.IGNORECASE),
        ]
        self.assertFalse((ROOT / "demos" / product).exists(), f"removed demo directory demos/{product} still exists")
        for path in ROOT.rglob("*"):
            if (
                not path.is_file()
                or "__pycache__" in path.parts
                or path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".webp"}
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
