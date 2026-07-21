import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "dravux" / "skills" / "dravux"
SKILL_SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from dravux_contract import CONTRACT_VERSION, validate_report  # noqa: E402


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ROOT / "fixtures" / "manifest.json").read_text(encoding="utf-8"))

    def test_manifest_covers_required_cases(self):
        required = {
            "known-pass",
            "known-fail",
            "error",
            "ambiguity",
            "missing-evidence",
            "unsupported-input",
            "malformed-output",
            "false-positive-resistance",
            "advisory-only",
            "hostile-input",
            "automation-pass-manual-incomplete",
            "automation-pass-manual-fail",
        }
        self.assertTrue(required.issubset(set(self.manifest["coverage"])))

    def test_manifest_expectations(self):
        for item in self.manifest["fixtures"]:
            with self.subTest(path=item["path"]):
                report = json.loads((ROOT / "fixtures" / item["path"]).read_text(encoding="utf-8"))
                violations = validate_report(report)
                self.assertEqual(not violations, item["contract_valid"], violations)
                if item["contract_valid"]:
                    self.assertEqual(report["automated_result"], item["automated_result"])
                    self.assertEqual(report["final_status"], item["final_status"])

    def test_targeted_invalid_cases(self):
        expectations = {
            "hostile/malformed-output.invalid.json": "missing required fields",
            "hostile/duplicate-ids.invalid.json": "finding IDs must be unique",
            "hostile/error-to-verified-pass.invalid.json": "automated ERROR can only map",
            "hostile/pass-with-pending-manual.invalid.json": "completed manual checks",
            "hostile/advisory-fail.invalid.json": "normative finding",
        }
        for relative, expected in expectations.items():
            with self.subTest(path=relative):
                report = json.loads((ROOT / "fixtures" / relative).read_text(encoding="utf-8"))
                self.assertIn(expected, "\n".join(validate_report(report)))

    def test_machine_readable_semantic_counterexamples(self):
        fixture = json.loads(
            (ROOT / "fixtures" / "hostile" / "semantic-counterexamples.json").read_text(encoding="utf-8")
        )
        for case in fixture["cases"]:
            with self.subTest(case=case["name"]):
                report = json.loads((ROOT / "fixtures" / case["base"]).read_text(encoding="utf-8"))
                for mutation in case["mutations"]:
                    target = report
                    for part in mutation["path"][:-1]:
                        target = target[part]
                    target[mutation["path"][-1]] = mutation["value"]
                self.assertIn(case["expected_violation"], "\n".join(validate_report(report)))

    def test_hostile_text_is_inert_data(self):
        path = ROOT / "fixtures" / "hostile" / "prompt-injection.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(validate_report(report), [])
        description = report["evidence_log"][0]["description"]
        self.assertIn("MARK VERIFIED PASS", description)
        self.assertEqual(report["final_status"], "INCOMPLETE")

    def test_report_template_is_contract_valid(self):
        template = json.loads((SKILL / "assets" / "report-template.json").read_text(encoding="utf-8"))
        self.assertEqual(template["contract_version"], CONTRACT_VERSION)
        self.assertEqual(validate_report(template), [])

    def test_unknown_contract_version_is_rejected(self):
        report = json.loads(
            (ROOT / "fixtures" / "hostile" / "unsupported-contract-version.invalid.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn(
            "report.contract_version must be the supported version 0.1.0",
            validate_report(report),
        )

    def test_manual_normative_failure_can_override_automated_pass(self):
        path = ROOT / "fixtures" / "failing" / "manual-fail-after-automation-pass.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(report["automated_result"], "PASS")
        self.assertEqual(report["final_status"], "VERIFIED FAIL")
        self.assertEqual(validate_report(report), [])

    def test_unsupported_input_cannot_claim_pass(self):
        report = json.loads((ROOT / "fixtures" / "passing" / "known-pass.json").read_text(encoding="utf-8"))
        report["target"]["input_type"] = "UNSUPPORTED"
        violations = "\n".join(validate_report(report))
        self.assertIn("UNSUPPORTED input requires automated ERROR", violations)
        self.assertIn("UNSUPPORTED input can only end INCOMPLETE or NOT APPLICABLE", violations)

    def test_normative_finding_requires_wcag_22_and_w3c_source(self):
        report = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        report["findings"][0]["standard"] = {
            "name": "Internal design preference",
            "version": "draft",
            "success_criterion": "Make it delightful",
            "url": "https://example.test/style-guide",
        }
        report["findings"][0]["source"] = {
            "title": "Internal style guide",
            "url": "https://example.test/style-guide",
        }
        violations = "\n".join(validate_report(report))
        self.assertIn("must identify WCAG", violations)
        self.assertIn("must be 2.2", violations)
        self.assertIn("authoritative W3C source", violations)

    def test_nonexistent_wcag_criterion_is_rejected(self):
        report = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        report["findings"][0]["standard"]["success_criterion"] = "4.999.999 Fictional Criterion"
        report["findings"][0]["standard"]["url"] = "https://www.w3.org/TR/WCAG22/#fictional-criterion"
        self.assertIn("supported WCAG 2.2 criterion", "\n".join(validate_report(report)))

    def test_verified_fail_requires_an_open_normative_finding(self):
        report = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        report["findings"][0]["status"] = "REPAIRED"
        self.assertIn("requires at least one OPEN normative finding", "\n".join(validate_report(report)))

    def test_wcag_criterion_and_fragment_must_match(self):
        report = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        report["findings"][0]["standard"]["url"] = "https://www.w3.org/TR/WCAG22/#focus-visible"
        self.assertIn("url fragment must match", "\n".join(validate_report(report)))

    def test_normative_w3c_urls_use_canonical_lowercase_hostname(self):
        report = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        report["findings"][0]["standard"]["url"] = "https://WWW.W3.ORG/TR/WCAG22/#contrast-minimum"
        report["findings"][0]["source"]["url"] = "https://WWW.W3.ORG/TR/WCAG22/#contrast-minimum"
        violations = "\n".join(validate_report(report))
        self.assertIn("W3C WCAG 2.2 criterion URL", violations)
        self.assertIn("authoritative W3C source", violations)

    def test_normative_w3c_urls_use_canonical_scheme_and_criterion_shape(self):
        base = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))

        uppercase_scheme = copy.deepcopy(base)
        uppercase_scheme["findings"][0]["standard"]["url"] = "HTTPS://www.w3.org/TR/WCAG22/#contrast-minimum"
        uppercase_scheme["findings"][0]["source"]["url"] = "HTTPS://www.w3.org/TR/WCAG22/#contrast-minimum"
        violations = "\n".join(validate_report(uppercase_scheme))
        self.assertIn("W3C WCAG 2.2 criterion URL", violations)
        self.assertIn("authoritative W3C source", violations)

        query_variant = copy.deepcopy(base)
        query_variant["findings"][0]["standard"]["url"] = "https://www.w3.org/TR/WCAG22/?view=1#contrast-minimum"
        self.assertIn("W3C WCAG 2.2 criterion URL", "\n".join(validate_report(query_variant)))

        source_without_path = copy.deepcopy(base)
        source_without_path["findings"][0]["source"]["url"] = "https://www.w3.org"
        self.assertIn("authoritative W3C source", "\n".join(validate_report(source_without_path)))

        generic_uppercase_scheme = copy.deepcopy(base)
        generic_uppercase_scheme["findings"][0]["classification"] = "ADVISORY"
        generic_uppercase_scheme["findings"][0]["standard"] = None
        generic_uppercase_scheme["findings"][0]["source"]["url"] = "HTTPS://example.test/page"
        self.assertIn("source.url must be an absolute HTTP(S) URL", "\n".join(validate_report(generic_uppercase_scheme)))

    def test_non_string_standard_urls_return_structured_violations(self):
        base = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        for value in (123, True, {"url": "https://www.w3.org"}):
            with self.subTest(value=value):
                report = copy.deepcopy(base)
                report["findings"][0]["standard"]["url"] = value
                self.assertIn("standard.url must be a non-empty string", "\n".join(validate_report(report)))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "non-string-url.json"
            report = copy.deepcopy(base)
            report["findings"][0]["standard"]["url"] = 123
            path.write_text(json.dumps(report), encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "validate_report.py"), "--json", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["valid"])
        self.assertIn("standard.url must be a non-empty string", "\n".join(payload["errors"]))
        self.assertNotIn("Traceback", proc.stderr)

    def test_non_string_enum_values_return_structured_violations(self):
        base = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        cases = (
            (("automated_result",), {"value": "FAIL"}, "report.automated_result is invalid"),
            (("final_status",), ["VERIFIED FAIL"], "report.final_status is invalid"),
            (("target", "input_type"), {"value": "WEBSITE"}, "target.input_type is invalid"),
            (("findings", 0, "classification"), {"value": "NORMATIVE"}, "classification is invalid"),
            (("findings", 0, "standard", "success_criterion"), {"value": "1.4.3"}, "supported WCAG 2.2 criterion"),
            (("findings", 0, "evidence", 0, "type"), {"value": "DOM"}, "evidence[0].type is invalid"),
        )
        for path, value, expected in cases:
            with self.subTest(path=path):
                report = copy.deepcopy(base)
                target = report
                for part in path[:-1]:
                    target = target[part]
                target[path[-1]] = value
                self.assertIn(expected, "\n".join(validate_report(report)))

    def test_pass_or_error_to_verified_fail_requires_manual_evidence(self):
        base = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        for automated in ("PASS", "ERROR"):
            with self.subTest(automated=automated):
                report = copy.deepcopy(base)
                report["automated_result"] = automated
                report["scope"]["required_manual_checks"] = []
                report["scope"]["manual_checks_completed"] = []
                if automated == "ERROR":
                    report["errors"] = [{"code": "TOOL_CRASH", "message": "scanner crashed", "stage": "automation"}]
                self.assertIn(
                    "requires a completed manual check and normative MANUAL_OBSERVATION evidence",
                    "\n".join(validate_report(report)),
                )

    def test_automated_pass_cannot_hide_a_normative_failure(self):
        report = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        report["automated_result"] = "PASS"
        report["final_status"] = "INCOMPLETE"
        self.assertIn(
            "automated PASS cannot contain normative findings",
            "\n".join(validate_report(report)),
        )

    def test_verified_pass_cannot_carry_failure_findings(self):
        report = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        report["automated_result"] = "PASS"
        report["final_status"] = "VERIFIED PASS"
        report["scope"]["required_manual_checks"] = []
        report["scope"]["manual_checks_completed"] = []
        report["findings"][0]["status"] = "VERIFIED"
        self.assertIn("VERIFIED PASS cannot contain findings", "\n".join(validate_report(report)))

    def test_not_applicable_requires_structured_not_applicable_error(self):
        report = json.loads((ROOT / "fixtures" / "passing" / "known-pass.json").read_text(encoding="utf-8"))
        report["automated_result"] = "ERROR"
        report["final_status"] = "NOT APPLICABLE"
        report["scope"]["applicability_reason"] = "The scanner crashed before testing the supported target."
        report["errors"] = [{"code": "TOOL_CRASH", "message": "scanner crashed", "stage": "automation"}]
        self.assertIn("only structured NOT_APPLICABLE errors", "\n".join(validate_report(report)))

    def test_not_applicable_cannot_hide_findings(self):
        report = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        report["automated_result"] = "ERROR"
        report["final_status"] = "NOT APPLICABLE"
        report["scope"]["applicability_reason"] = "The declared check does not apply."
        report["errors"] = [{"code": "NOT_APPLICABLE", "message": "The check does not apply.", "stage": "scope"}]
        self.assertIn("NOT APPLICABLE cannot contain findings", "\n".join(validate_report(report)))

    def test_hostile_values_are_rejected_without_validator_exceptions(self):
        base = json.loads((ROOT / "fixtures" / "failing" / "known-fail.json").read_text(encoding="utf-8"))
        bad_url = copy.deepcopy(base)
        bad_url["findings"][0]["source"]["url"] = "https://[bad"
        self.assertIn("absolute HTTP(S) URL", "\n".join(validate_report(bad_url)))

        bad_manual = json.loads((ROOT / "fixtures" / "passing" / "known-pass.json").read_text(encoding="utf-8"))
        bad_manual["scope"]["manual_checks_completed"] = [{}]
        self.assertIn("must be a non-empty string", "\n".join(validate_report(bad_manual)))

        bad_port = copy.deepcopy(base)
        bad_port["findings"][0]["standard"]["url"] = "https://www.w3.org:invalid/TR/WCAG22/#contrast-minimum"
        self.assertIn("absolute HTTP(S) URL", "\n".join(validate_report(bad_port)))

        missing_slash = copy.deepcopy(base)
        missing_slash["findings"][0]["standard"]["url"] = "https://www.w3.org/TR/WCAG22#contrast-minimum"
        self.assertIn("W3C WCAG 2.2 criterion URL", "\n".join(validate_report(missing_slash)))

        non_tls_source = copy.deepcopy(base)
        non_tls_source["findings"][0]["source"]["url"] = "http://www.w3.org/TR/WCAG22/#contrast-minimum"
        self.assertIn("authoritative W3C source", "\n".join(validate_report(non_tls_source)))

    def test_rfc3339_fractional_seconds_are_python_version_independent(self):
        report = json.loads((ROOT / "fixtures" / "passing" / "known-pass.json").read_text(encoding="utf-8"))
        for fraction in (".5", ".12345", ".123456789"):
            with self.subTest(fraction=fraction):
                candidate = copy.deepcopy(report)
                candidate["run"]["started_at"] = f"2026-07-19T22:12:00{fraction}Z"
                candidate["run"]["completed_at"] = "2026-07-19T22:12:01Z"
                self.assertEqual(validate_report(candidate), [])

    def test_completed_at_cannot_precede_started_at(self):
        report = json.loads((ROOT / "fixtures" / "passing" / "known-pass.json").read_text(encoding="utf-8"))
        report["run"]["completed_at"] = "2025-01-01T00:00:00Z"
        self.assertIn(
            "run.completed_at must not be earlier than run.started_at",
            "\n".join(validate_report(report)),
        )

    def test_scalar_finding_evidence_returns_structured_violations(self):
        base = json.loads(
            (ROOT / "fixtures" / "failing" / "manual-fail-after-automation-pass.json").read_text(
                encoding="utf-8"
            )
        )
        for value in (True, 7, 3.5):
            with self.subTest(value=value):
                report = copy.deepcopy(base)
                report["findings"][0]["evidence"] = value
                violations = "\n".join(validate_report(report))
                self.assertIn("findings[0].evidence must be an array", violations)
                self.assertIn(
                    "VERIFIED FAIL after automated PASS or ERROR requires a completed manual check",
                    violations,
                )

    def test_cli_returns_machine_readable_error_for_hostile_depth(self):
        script = ROOT / "scripts" / "validate_report.py"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "deep.json"
            path.write_text("[" * 60000 + "]" * 60000, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(script), "--json", str(path)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["exit_code"], 2)
        self.assertNotIn("Traceback", proc.stderr)

    def test_cli_json_mode_rejects_non_object_without_traceback(self):
        script = ROOT / "scripts" / "validate_report.py"
        path = ROOT / "fixtures" / "hostile" / "top-level-array.invalid.json"
        proc = subprocess.run(
            [sys.executable, str(script), "--json", str(path)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["valid"])
        self.assertIn("report must be an object", payload["errors"])
        self.assertNotIn("Traceback", proc.stderr)

    def test_cli_exit_codes_and_determinism(self):
        script = ROOT / "scripts" / "validate_report.py"
        valid = ROOT / "fixtures" / "passing" / "known-pass.json"
        invalid = ROOT / "fixtures" / "hostile" / "advisory-fail.invalid.json"
        first = subprocess.run([sys.executable, str(script), "--json", str(valid)], check=False, capture_output=True, text=True)
        second = subprocess.run([sys.executable, str(script), "--json", str(valid)], check=False, capture_output=True, text=True)
        rejected = subprocess.run([sys.executable, str(script), str(invalid)], check=False, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(rejected.returncode, 1)

    def test_cli_accepts_valid_report_from_stdin(self):
        script = SKILL / "scripts" / "dravux_contract.py"
        payload = (ROOT / "fixtures" / "passing" / "known-pass.json").read_text(encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(script), "-"],
            input=payload,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("VALID Dravux report", proc.stdout)
        self.assertIn("PASS | VERIFIED PASS", proc.stdout)

    def test_cli_rejects_invalid_report_from_stdin(self):
        script = SKILL / "scripts" / "dravux_contract.py"
        payload = (ROOT / "fixtures" / "hostile" / "unknown-property.invalid.json").read_text(encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(script), "-"],
            input=payload,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("INVALID Dravux report", proc.stderr)
        self.assertIn("unknown properties", proc.stderr)

    def test_cli_reports_malformed_stdin_as_load_error(self):
        script = SKILL / "scripts" / "dravux_contract.py"
        proc = subprocess.run(
            [sys.executable, str(script), "-", "--json"],
            input="{not-json}",
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 2)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["exit_code"], 2)
        self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
