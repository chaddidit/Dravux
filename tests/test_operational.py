import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "dravux" / "skills" / "dravux"
sys.path.insert(0, str(SKILL / "scripts"))

from dravux_run import preflight_decision, validate_run  # noqa: E402


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


class OperationalContractTests(unittest.TestCase):
    def setUp(self):
        self.preflight = load("plugins/dravux/skills/dravux/assets/preflight-template.json")
        self.run = load("plugins/dravux/skills/dravux/assets/run-envelope-template.json")

    def run_cli(self, command, relative):
        return subprocess.run(
            [sys.executable, str(SKILL / "scripts" / "dravux_run.py"), command, str(ROOT / relative), "--json"],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_generic_website_text_surface_requires_acknowledgement(self):
        result = preflight_decision(self.preflight)
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "LIMITATION_ACK_REQUIRED")
        self.assertEqual(result["exit_code"], 3)
        self.assertEqual(result["validator_self_test"], "PASS")
        self.assertIn("Raw HTML and DOM attributes.", result["excluded_claims"])

    def test_explicit_text_limitation_acceptance_is_ready(self):
        profile = copy.deepcopy(self.preflight)
        profile["limitation_acknowledged"] = True
        result = preflight_decision(profile)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["exit_code"], 0)

    def test_website_cannot_self_declare_a_lower_requested_mode(self):
        profile = copy.deepcopy(self.preflight)
        profile["requested_mode"] = "SOURCE_TEXT"
        profile["selected_mode"] = "SOURCE_TEXT"
        profile["limitation_acknowledged"] = False
        result = preflight_decision(profile)
        self.assertFalse(result["valid"])
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(
            "WEBSITE preflight.requested_mode must require rendered-page evidence",
            result["errors"],
        )

    def test_missing_execution_or_validator_is_unsupported(self):
        profile = load("fixtures/operational/validator-unavailable.preflight.json")
        result = preflight_decision(profile)
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertEqual(result["exit_code"], 4)

    def test_valid_accepted_source_text_run_returns_receipt(self):
        self.assertEqual(validate_run(self.run), [])
        proc = self.run_cli("validate", "plugins/dravux/skills/dravux/assets/run-envelope-template.json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["valid"])
        self.assertEqual(payload["receipt"]["evidence_mode"], "SOURCE_TEXT")
        self.assertEqual(payload["receipt"]["validator"], "PASS (exit 0)")
        self.assertEqual(payload["receipt"]["automated_result"], "PASS")
        self.assertEqual(payload["receipt"]["final_status"], "INCOMPLETE")
        self.assertTrue(payload["receipt"]["manual_checks_remaining"])

        text_proc = subprocess.run(
            [
                sys.executable,
                str(SKILL / "scripts" / "dravux_run.py"),
                "validate",
                str(ROOT / "plugins/dravux/skills/dravux/assets/run-envelope-template.json"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(text_proc.returncode, 0, text_proc.stderr)
        self.assertIn("Limitation acknowledgement: accepted", text_proc.stdout)

    def test_bare_valid_report_is_not_an_established_run(self):
        proc = self.run_cli("validate", "fixtures/passing/automation-pass-manual-incomplete.json")
        self.assertEqual(proc.returncode, 1)
        payload = json.loads(proc.stdout)
        self.assertFalse(payload["valid"])
        self.assertIn("run missing required fields", "\n".join(payload["errors"]))

    def test_silent_downgrade_is_rejected_at_run_gate(self):
        envelope = copy.deepcopy(self.run)
        envelope["preflight"]["limitation_acknowledged"] = False
        self.assertIn("run preflight must be READY, received LIMITATION_ACK_REQUIRED", validate_run(envelope))

    def test_manual_completion_requires_declared_capability_and_observation_evidence(self):
        envelope = copy.deepcopy(self.run)
        envelope["preflight"]["requested_mode"] = "RENDERED_DOM"
        envelope["preflight"]["selected_mode"] = "RENDERED_DOM"
        envelope["preflight"]["capabilities"]["acquisition"] = "RENDERED_DOM"
        envelope["preflight"]["capabilities"]["manual_evidence"] = False
        envelope["acquisition"]["method"] = "RENDERED_DOM"
        envelope["report"]["scope"]["manual_checks_completed"] = copy.deepcopy(
            envelope["report"]["scope"]["required_manual_checks"]
        )
        envelope["report"]["final_status"] = "VERIFIED PASS"
        envelope["report"]["evidence_log"].append(
            {
                "type": "MANUAL_OBSERVATION",
                "description": "Synthetic completion evidence for the bounded regression.",
                "locator": "test fixture manual completion",
            }
        )

        errors = validate_run(envelope)
        self.assertIn(
            "report cannot complete manual checks when preflight.capabilities.manual_evidence is false",
            errors,
        )
        self.assertIn(
            "report cannot contain MANUAL_OBSERVATION evidence when preflight.capabilities.manual_evidence is false",
            errors,
        )

        envelope["preflight"]["capabilities"]["manual_evidence"] = True
        self.assertEqual(validate_run(envelope), [])

        envelope["report"]["evidence_log"] = [
            item for item in envelope["report"]["evidence_log"] if item["type"] != "MANUAL_OBSERVATION"
        ]
        self.assertIn("completed manual checks require MANUAL_OBSERVATION evidence", validate_run(envelope))

    def test_successful_accepted_source_acquisition_cannot_claim_error(self):
        envelope = copy.deepcopy(self.run)
        envelope["report"]["automated_result"] = "ERROR"
        envelope["report"]["errors"] = [
            {"code": "UNSUPPORTED_EVIDENCE", "message": "Rendered DOM was unavailable.", "stage": "automated_check"}
        ]
        errors = validate_run(envelope)
        self.assertIn("successful selected-mode acquisition cannot end automated ERROR", errors)

    def test_failed_acquisition_requires_error_incomplete_and_structured_code(self):
        envelope = copy.deepcopy(self.run)
        envelope["acquisition"].update(
            {
                "succeeded": False,
                "final_location": None,
                "response_status": None,
                "acquired_at": None,
                "tool": None,
                "content_sha256": None,
                "error": "The target could not be retrieved.",
            }
        )
        errors = validate_run(envelope)
        self.assertIn("failed acquisition requires report ERROR | INCOMPLETE", errors)
        self.assertIn("failed acquisition requires structured ACQUISITION_FAILED error", errors)

    def test_source_text_findings_must_be_potential_low_confidence_advisories(self):
        envelope = copy.deepcopy(self.run)
        finding = load("fixtures/ambiguous/advisory-only.json")["findings"][0]
        finding["evidence"] = [
            {"type": "SOURCE", "description": "Converted text repeated a label.", "locator": "retrieved text line 4"}
        ]
        envelope["report"]["findings"] = [finding]
        errors = validate_run(envelope)
        joined = "\n".join(errors)
        self.assertIn("confidence must be LOW", joined)
        self.assertIn("title must begin 'Potential: '", joined)

    def test_preflight_cli_exit_codes_are_stable(self):
        limitation = self.run_cli("preflight", "plugins/dravux/skills/dravux/assets/preflight-template.json")
        unsupported = self.run_cli("preflight", "fixtures/operational/validator-unavailable.preflight.json")
        self.assertEqual(limitation.returncode, 3)
        self.assertEqual(json.loads(limitation.stdout)["status"], "LIMITATION_ACK_REQUIRED")
        self.assertEqual(unsupported.returncode, 4)
        self.assertEqual(json.loads(unsupported.stdout)["status"], "UNSUPPORTED")

    def test_hostile_top_level_input_is_rejected_without_traceback(self):
        proc = subprocess.run(
            [sys.executable, str(SKILL / "scripts" / "dravux_run.py"), "validate", "-", "--json"],
            input="[]",
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("Traceback", proc.stderr + proc.stdout)
        self.assertFalse(json.loads(proc.stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
