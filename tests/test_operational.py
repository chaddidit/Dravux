import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "dravux" / "skills" / "dravux"
sys.path.insert(0, str(SKILL / "scripts"))

from dravux_run import (  # noqa: E402
    OUTPUT_DIR_REFUSED_EXIT,
    preflight_decision,
    resolve_output_dir,
    validate_run,
)


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

    def test_unsupported_input_precedes_limitation_routing(self):
        profile = load("fixtures/operational/unsupported-input.preflight.json")
        result = preflight_decision(profile)
        self.assertTrue(result["valid"])
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertEqual(result["exit_code"], 4)

    def test_rendered_browser_requires_screenshot_capability(self):
        profile = copy.deepcopy(self.preflight)
        profile["requested_mode"] = "RENDERED_BROWSER"
        profile["selected_mode"] = "RENDERED_BROWSER"
        profile["capabilities"]["acquisition"] = "RENDERED_BROWSER"
        profile["limitation_acknowledged"] = False
        result = preflight_decision(profile)
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("RENDERED_BROWSER requires preflight.capabilities.screenshots true", result["errors"])
        profile["capabilities"]["screenshots"] = True
        self.assertEqual(preflight_decision(profile)["status"], "READY")

    def test_genuine_not_applicable_requires_completed_supported_run(self):
        envelope = load("fixtures/operational/genuine-not-applicable.run.json")
        self.assertEqual(validate_run(envelope), [])
        proc = self.run_cli("validate", "fixtures/operational/genuine-not-applicable.run.json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(proc.stdout)["receipt"]
        self.assertEqual(receipt["final_status"], "NOT APPLICABLE")
        self.assertIn("genuinely not applicable", receipt["meaning"])

        incomplete = copy.deepcopy(envelope)
        incomplete["execution"] = {
            "completed": False,
            "failure_stage": "AUDIT_EXECUTION",
            "error": "The audit did not complete.",
        }
        self.assertIn(
            "NOT APPLICABLE requires successful acquisition and completed execution",
            validate_run(incomplete),
        )

    def test_error_verified_fail_receipt_credits_bound_manual_evidence(self):
        envelope = load("fixtures/operational/post-acquisition-interaction-failure.run.json")
        report = load("fixtures/failing/manual-fail-after-automation-pass.json")
        report["automated_result"] = "ERROR"
        report["errors"] = [
            {"code": "EXECUTION_FAILED", "message": "The scripted interaction failed.", "stage": "interaction"}
        ]
        report["target"]["location"] = envelope["preflight"]["target"]["location"]
        report["target"]["input_type"] = envelope["preflight"]["target"]["input_type"]
        report["run"] = copy.deepcopy(envelope["report"]["run"])
        envelope["preflight"]["capabilities"]["manual_evidence"] = True
        report["scope"]["required_manual_checks"] = copy.deepcopy(envelope["preflight"]["required_manual_checks"])
        report["scope"]["manual_checks_completed"] = ["focus-order"]
        for finding in report["findings"]:
            for evidence in finding["evidence"]:
                if evidence["type"] == "MANUAL_OBSERVATION":
                    evidence["manual_check_id"] = "focus-order"
        for evidence in report["evidence_log"]:
            if evidence["type"] == "MANUAL_OBSERVATION":
                evidence["manual_check_id"] = "focus-order"
        envelope["report"] = report
        self.assertEqual(validate_run(envelope), [])
        proc = subprocess.run(
            [sys.executable, "-B", str(SKILL / "scripts" / "dravux_run.py"), "validate", "-", "--json"],
            input=json.dumps(envelope), check=False, capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("completed manual evidence established", json.loads(proc.stdout)["receipt"]["meaning"])

    def validate_cli(self, envelope, json_output=False):
        arguments = [sys.executable, "-B", str(SKILL / "scripts" / "dravux_run.py"), "validate", "-"]
        if json_output:
            arguments.append("--json")
        return subprocess.run(arguments, input=json.dumps(envelope), check=False, capture_output=True, text=True)

    def contract_only_envelope(self):
        """A structure-only self-test run: the only honest CONTRACT_ONLY shape."""
        envelope = copy.deepcopy(self.run)
        location = "fixtures/passing/known-pass.json"
        envelope["preflight"]["target"] = {"input_type": "SOURCE_CODE", "location": location}
        envelope["preflight"]["requested_mode"] = "CONTRACT_ONLY"
        envelope["preflight"]["selected_mode"] = "CONTRACT_ONLY"
        envelope["preflight"]["capabilities"]["acquisition"] = "NONE"
        envelope["preflight"]["limitation_acknowledged"] = False
        envelope["preflight"]["required_manual_checks"] = ["keyboard", "screen-reader"]
        envelope["acquisition"] = {
            "attempted": False,
            "succeeded": False,
            "method": "NONE",
            "requested_location": location,
            "final_location": None,
            "redirect_chain": [],
            "response_status": None,
            "acquired_at": None,
            "tool": None,
            "content_sha256": None,
            "error": None,
        }
        envelope["execution"] = {"completed": True, "failure_stage": None, "error": None}
        report = envelope["report"]
        report["target"] = {
            "name": "Bundled contract self-test",
            "state": "structure-only validation",
            "location": location,
            "input_type": "SOURCE_CODE",
        }
        report["scope"]["included"] = ["Report contract structure only."]
        report["scope"]["excluded"] = ["Every target accessibility claim; no target was acquired."]
        report["scope"]["required_manual_checks"] = ["keyboard", "screen-reader"]
        report["scope"]["manual_checks_completed"] = []
        report["automated_result"] = "PASS"
        report["final_status"] = "INCOMPLETE"
        report["findings"] = []
        report["errors"] = []
        # The template's inherited SOURCE item describes a retrieved page; a contract-only run has none.
        report["evidence_log"] = [
            {
                "type": "COMMAND_OUTPUT",
                "description": "The bundled report validator exited 0 for the named fixture; no target was acquired.",
                "locator": "scripts/dravux_contract.py fixtures/passing/known-pass.json",
            }
        ]
        return envelope

    def test_contract_only_runs_establish_structure_only(self):
        laundering = (
            "CONTRACT_ONLY runs may only report structure-only PASS | INCOMPLETE; "
            "no target accessibility verdict can be established without acquisition"
        )
        honest = self.contract_only_envelope()
        self.assertEqual(validate_run(honest), [])
        proc = self.validate_cli(honest)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Final status: INCOMPLETE", proc.stdout)
        self.assertIn("Only the report contract structure was validated", proc.stdout)
        self.assertIn("no target accessibility conclusion was established", proc.stdout)

        # Evidence about a target is contradictory when no target was acquired; only diagnostics may be cited.
        diagnostic = "CONTRACT_ONLY runs may carry only TOOL_OUTPUT or COMMAND_OUTPUT diagnostic evidence"
        for evidence_type in ("SOURCE", "DOM", "SCREENSHOT", "DOCUMENT_STRUCTURE"):
            with self.subTest(evidence_type=evidence_type):
                contradictory = self.contract_only_envelope()
                contradictory["report"]["evidence_log"].append(
                    {"type": evidence_type, "description": "Inherited target evidence.", "locator": "synthetic"}
                )
                joined = "\n".join(validate_run(contradictory))
                self.assertIn(diagnostic, joined)
                self.assertIn(f'"{evidence_type}"', joined)
        tool_only = self.contract_only_envelope()
        tool_only["report"]["evidence_log"].append(
            {"type": "TOOL_OUTPUT", "description": "Validator self-test output.", "locator": "dravux_run.py preflight"}
        )
        self.assertEqual(validate_run(tool_only), [])

        # A JSON-valid but non-string type is reported once by the report layer and never raises here.
        for malformed in (["SOURCE"], {"type": "SOURCE"}):
            with self.subTest(malformed=malformed):
                unhashable = self.contract_only_envelope()
                unhashable["report"]["evidence_log"].append(
                    {"type": malformed, "description": "Malformed evidence type.", "locator": "synthetic"}
                )
                errors = validate_run(unhashable)
                self.assertIsInstance(errors, list)
                self.assertIn("report: evidence_log[1].type is invalid", errors)
                self.assertFalse(any(diagnostic in error for error in errors), errors)

        # The Loop-3 reproduction: a VERIFIED PASS fixture wrapped in a CONTRACT_ONLY envelope.
        laundered = self.contract_only_envelope()
        laundered["preflight"]["capabilities"]["manual_evidence"] = True
        known_pass = load("fixtures/passing/known-pass.json")
        known_pass.pop("$schema", None)
        laundered["report"] = known_pass
        self.assertIn(laundering, validate_run(laundered))
        proc = self.validate_cli(laundered)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertNotIn("Final status: VERIFIED PASS", proc.stdout + proc.stderr)

        failing = self.contract_only_envelope()
        known_fail = load("fixtures/failing/known-fail.json")
        known_fail.pop("$schema", None)
        failing["preflight"]["target"]["location"] = known_fail["target"]["location"]
        failing["acquisition"]["requested_location"] = known_fail["target"]["location"]
        failing["preflight"]["required_manual_checks"] = list(known_fail["scope"]["required_manual_checks"])
        failing["report"] = known_fail
        joined = "\n".join(validate_run(failing))
        self.assertIn(laundering, joined)
        self.assertIn("CONTRACT_ONLY runs cannot carry findings or errors", joined)

        errored = self.contract_only_envelope()
        errored["report"]["automated_result"] = "ERROR"
        errored["report"]["errors"] = [{"code": "TOOL_CRASH", "message": "The validator crashed.", "stage": "contract"}]
        joined = "\n".join(validate_run(errored))
        self.assertIn(laundering, joined)
        self.assertIn("CONTRACT_ONLY runs cannot carry findings or errors", joined)

        not_applicable = self.contract_only_envelope()
        not_applicable["report"]["automated_result"] = "ERROR"
        not_applicable["report"]["final_status"] = "NOT APPLICABLE"
        not_applicable["report"]["scope"]["applicability_reason"] = "Nothing applies."
        not_applicable["report"]["errors"] = [{"code": "NOT_APPLICABLE", "message": "Nothing applies.", "stage": "scope"}]
        self.assertIn(laundering, validate_run(not_applicable))

    def test_selected_mode_must_equal_the_strongest_available_mode(self):
        message = (
            "preflight.selected_mode must equal the strongest mode at or below both the requested mode "
            "and the declared acquisition ceiling; acknowledgement cannot authorize a weaker mode"
        )
        voluntary = copy.deepcopy(self.preflight)
        voluntary["capabilities"]["acquisition"] = "RENDERED_DOM"
        voluntary["selected_mode"] = "SOURCE_TEXT"
        for acknowledged in (False, True):
            with self.subTest(acknowledged=acknowledged):
                voluntary["limitation_acknowledged"] = acknowledged
                result = preflight_decision(voluntary)
                self.assertEqual(result["status"], "INVALID")
                self.assertIn(message, result["errors"])

        # Weaker than a ceiling that is itself below the request is just as voluntary.
        below_ceiling = copy.deepcopy(self.preflight)
        below_ceiling["selected_mode"] = "CONTRACT_ONLY"
        below_ceiling["limitation_acknowledged"] = True
        result = preflight_decision(below_ceiling)
        self.assertEqual(result["status"], "INVALID")
        self.assertIn(message, result["errors"])

        # Positive controls: a genuine lower ceiling still stops for, and accepts, the acknowledgement...
        genuine = copy.deepcopy(self.preflight)
        self.assertEqual(preflight_decision(genuine)["status"], "LIMITATION_ACK_REQUIRED")
        genuine["limitation_acknowledged"] = True
        self.assertEqual(preflight_decision(genuine)["status"], "READY")
        # ...and a ceiling above the request routes to the request itself with nothing to acknowledge.
        above = copy.deepcopy(self.preflight)
        above["capabilities"]["acquisition"] = "INTERACTIVE_BROWSER"
        above["selected_mode"] = "RENDERED_DOM"
        above["limitation_acknowledged"] = False
        self.assertEqual(preflight_decision(above)["status"], "READY")

        envelope = copy.deepcopy(self.run)
        envelope["preflight"]["capabilities"]["acquisition"] = "RENDERED_DOM"
        self.assertIn("run preflight must be READY, received INVALID", validate_run(envelope))

    def test_rendered_browser_runs_require_recorded_screenshot_evidence(self):
        envelope = copy.deepcopy(self.run)
        envelope["preflight"]["requested_mode"] = "RENDERED_BROWSER"
        envelope["preflight"]["selected_mode"] = "RENDERED_BROWSER"
        envelope["preflight"]["capabilities"]["acquisition"] = "RENDERED_BROWSER"
        envelope["preflight"]["capabilities"]["screenshots"] = True
        envelope["preflight"]["limitation_acknowledged"] = False
        envelope["acquisition"]["method"] = "RENDERED_BROWSER"
        missing = "completed RENDERED_BROWSER runs require at least one SCREENSHOT item in report.evidence_log"
        self.assertIn(missing, validate_run(envelope))
        envelope["report"]["evidence_log"].append(
            {
                "type": "SCREENSHOT",
                "description": "Recorded rendering of the homepage at 1280x800.",
                "locator": "screenshots/homepage-1280x800.png",
            }
        )
        self.assertEqual(validate_run(envelope), [])
        proc = self.validate_cli(envelope)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Evidence mode: RENDERED_BROWSER", proc.stdout)
        self.assertIn("Limitation acknowledgement: not required", proc.stdout)

        # A browser acquisition that failed cannot honestly produce a screenshot and is not asked for one.
        unacquired = copy.deepcopy(envelope)
        unacquired["acquisition"].update(
            {
                "succeeded": False,
                "final_location": None,
                "response_status": None,
                "acquired_at": None,
                "tool": None,
                "content_sha256": None,
                "error": "The browser session could not load the page.",
            }
        )
        unacquired["execution"] = {
            "completed": False,
            "failure_stage": "ACQUISITION",
            "error": "The browser session could not load the page.",
        }
        unacquired["report"]["automated_result"] = "ERROR"
        unacquired["report"]["final_status"] = "INCOMPLETE"
        unacquired["report"]["errors"] = [
            {"code": "ACQUISITION_FAILED", "message": "Nothing was retrieved.", "stage": "acquisition"}
        ]
        unacquired["report"]["evidence_log"] = [
            {
                "type": "TOOL_OUTPUT",
                "description": "The browser driver reported a navigation timeout before any render.",
                "locator": "browser session log, navigation step 1",
            }
        ]
        self.assertEqual(validate_run(unacquired), [])
        self.assertNotIn(missing, validate_run(unacquired))
        proc = self.validate_cli(unacquired)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Execution: did not complete (failure stage: ACQUISITION)", proc.stdout)

    def test_genuine_not_applicable_fixture_records_the_shipped_decorative_spacer(self):
        envelope = load("fixtures/operational/genuine-not-applicable.run.json")
        relative = envelope["acquisition"]["requested_location"]
        self.assertEqual(relative, "fixtures/operational/decorative-spacer.svg")
        self.assertEqual(envelope["acquisition"]["final_location"], relative)
        asset = ROOT / relative
        self.assertTrue(asset.is_file(), "the genuine NOT APPLICABLE fixture must point at a shipped asset")
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        self.assertEqual(envelope["acquisition"]["content_sha256"], digest)
        self.assertLess(asset.stat().st_size, 4096, "the asset is a bounded decorative spacer")
        text = asset.read_text(encoding="utf-8")
        self.assertIn('aria-hidden="true"', text)
        self.assertIn('role="presentation"', text)
        manifest = load("fixtures/manifest.json")
        assets = {item["path"]: item for item in manifest["operational_assets"]}
        entry = assets["operational/decorative-spacer.svg"]
        self.assertEqual(entry["sha256"], digest)
        self.assertEqual(entry["referenced_by"], "operational/genuine-not-applicable.run.json")
        # The offline validator never opens target paths; this test, not the validator, binds the hash.
        unopened = copy.deepcopy(envelope)
        unopened["acquisition"]["content_sha256"] = "0" * 64
        self.assertEqual(validate_run(unopened), [])

    def test_verified_fail_receipt_meaning_branches_on_automated_result(self):
        base = load("fixtures/operational/post-acquisition-interaction-failure.run.json")
        base["preflight"]["capabilities"]["manual_evidence"] = True

        def adapt(report):
            report.pop("$schema", None)
            report["target"]["location"] = base["preflight"]["target"]["location"]
            report["target"]["input_type"] = base["preflight"]["target"]["input_type"]
            report["run"] = copy.deepcopy(base["report"]["run"])
            report["scope"]["required_manual_checks"] = copy.deepcopy(base["preflight"]["required_manual_checks"])
            for finding in report["findings"]:
                finding["input_type"] = base["preflight"]["target"]["input_type"]
            return report

        automated = copy.deepcopy(base)
        automated["execution"] = {"completed": True, "failure_stage": None, "error": None}
        automated["report"] = adapt(load("fixtures/failing/known-fail.json"))
        automated["report"]["scope"]["manual_checks_completed"] = []
        self.assertEqual(validate_run(automated), [])

        overridden = copy.deepcopy(base)
        overridden["execution"] = {"completed": True, "failure_stage": None, "error": None}
        overridden["report"] = adapt(load("fixtures/failing/manual-fail-after-automation-pass.json"))
        overridden["report"]["scope"]["manual_checks_completed"] = ["focus-order"]
        for item in overridden["report"]["findings"][0]["evidence"] + overridden["report"]["evidence_log"]:
            if item["type"] == "MANUAL_OBSERVATION":
                item["manual_check_id"] = "focus-order"
        self.assertEqual(validate_run(overridden), [])

        errored = copy.deepcopy(overridden)
        errored["execution"] = copy.deepcopy(base["execution"])
        errored["report"]["automated_result"] = "ERROR"
        errored["report"]["errors"] = [
            {"code": "EXECUTION_FAILED", "message": "The scripted interaction failed.", "stage": "interaction"}
        ]
        self.assertEqual(validate_run(errored), [])

        passed = copy.deepcopy(self.run)
        passed["preflight"]["requested_mode"] = "RENDERED_DOM"
        passed["preflight"]["selected_mode"] = "RENDERED_DOM"
        passed["preflight"]["capabilities"]["acquisition"] = "RENDERED_DOM"
        passed["preflight"]["capabilities"]["manual_evidence"] = True
        passed["acquisition"]["method"] = "RENDERED_DOM"
        passed["report"]["scope"]["manual_checks_completed"] = list(passed["report"]["scope"]["required_manual_checks"])
        passed["report"]["final_status"] = "VERIFIED PASS"
        passed["report"]["evidence_log"].extend(
            {
                "type": "MANUAL_OBSERVATION",
                "manual_check_id": check,
                "description": "Synthetic completion evidence for the bounded regression.",
                "locator": f"test fixture manual completion: {check}",
            }
            for check in passed["report"]["scope"]["manual_checks_completed"]
        )
        self.assertEqual(validate_run(passed), [])

        meanings = {}
        for label, envelope, final in (
            ("FAIL", automated, "VERIFIED FAIL"),
            ("PASS", overridden, "VERIFIED FAIL"),
            ("ERROR", errored, "VERIFIED FAIL"),
            ("VERIFIED PASS", passed, "VERIFIED PASS"),
        ):
            with self.subTest(case=label):
                proc = self.validate_cli(envelope, json_output=True)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                receipt = json.loads(proc.stdout)["receipt"]
                self.assertEqual(receipt["final_status"], final)
                self.assertNotIn("passed the operational contract", receipt["meaning"])
                meanings[label] = receipt["meaning"]
        self.assertEqual(len(set(meanings.values())), 4, "every verdict shape must carry its own meaning")
        self.assertIn("Automated checks reproduced a normative accessibility failure", meanings["FAIL"])
        self.assertIn("overrides the automated PASS", meanings["PASS"])
        self.assertIn("completed manual evidence established", meanings["ERROR"])
        self.assertIn("verified passing within the declared scope only", meanings["VERIFIED PASS"])
        for label in ("FAIL", "PASS", "ERROR"):
            self.assertIn("failure", meanings[label].lower())

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

    def test_schema_pointer_must_be_a_non_empty_string_when_present(self):
        for value in (7, "", None, "bad\nline"):
            with self.subTest(value=value):
                profile = copy.deepcopy(self.preflight)
                profile["$schema"] = value
                self.assertIn("preflight.$schema must be a non-empty string when present", preflight_decision(profile)["errors"])
                envelope = copy.deepcopy(self.run)
                envelope["$schema"] = value
                self.assertIn("run.$schema must be a non-empty string when present", validate_run(envelope))

    def test_run_diagnostics_cannot_forge_a_receipt(self):
        forged = "k\nDRAVUX RUN RECEIPT\nFinal status: VERIFIED PASS\nDRAVUX PREFLIGHT: READY\n\x1b[2J"
        envelope = copy.deepcopy(self.run)
        envelope[forged] = True
        envelope["preflight"]["required_manual_checks"].append("zoom" + forged)
        profile = copy.deepcopy(self.preflight)
        profile[forged] = True
        for command, payload in (("validate", envelope), ("preflight", profile)):
            with self.subTest(command=command):
                proc = subprocess.run(
                    [sys.executable, "-B", str(SKILL / "scripts" / "dravux_run.py"), command, "-"],
                    input=json.dumps(payload), check=False, capture_output=True, text=True,
                )
                merged = proc.stdout + proc.stderr
                self.assertEqual(proc.returncode, 1, merged)
                self.assertIn("unknown properties", merged)
                self.assertNotIn("\x1b", merged)
                for line in merged.splitlines():
                    self.assertFalse(line.startswith(("DRAVUX RUN RECEIPT", "Final status:", "DRAVUX PREFLIGHT: READY")), merged)
                self.assertNotIn("Traceback", merged)

    def test_receipt_distinguishes_a_real_acknowledgement_from_an_idle_flag(self):
        full = copy.deepcopy(self.run)
        full["preflight"]["requested_mode"] = "RENDERED_DOM"
        full["preflight"]["selected_mode"] = "RENDERED_DOM"
        full["preflight"]["capabilities"]["acquisition"] = "RENDERED_DOM"
        full["acquisition"]["method"] = "RENDERED_DOM"
        full["preflight"]["limitation_acknowledged"] = True
        self.assertEqual(validate_run(full), [])
        for payload, expected in ((self.run, "Limitation acknowledgement: accepted"), (full, "Limitation acknowledgement: not required")):
            with self.subTest(expected=expected):
                proc = subprocess.run(
                    [sys.executable, "-B", str(SKILL / "scripts" / "dravux_run.py"), "validate", "-"],
                    input=json.dumps(payload), check=False, capture_output=True, text=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertIn(expected, proc.stdout)
                self.assertIn(f"Requested mode: {payload['preflight']['requested_mode']}", proc.stdout)

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
        envelope["report"]["evidence_log"].extend(
            {
                "type": "MANUAL_OBSERVATION",
                "manual_check_id": check,
                "description": "Synthetic completion evidence for the bounded regression.",
                "locator": f"test fixture manual completion: {check}",
            }
            for check in envelope["report"]["scope"]["manual_checks_completed"]
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

    def test_completed_run_after_successful_acquisition_cannot_claim_error(self):
        envelope = copy.deepcopy(self.run)
        envelope["report"]["automated_result"] = "ERROR"
        envelope["report"]["errors"] = [
            {"code": "UNSUPPORTED_EVIDENCE", "message": "Rendered DOM was unavailable.", "stage": "automated_check"}
        ]
        errors = validate_run(envelope)
        self.assertIn("successful acquisition with completed execution cannot end automated ERROR", errors)

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
        envelope["execution"] = {
            "completed": False,
            "failure_stage": "ACQUISITION",
            "error": "The target could not be retrieved.",
        }
        errors = validate_run(envelope)
        self.assertIn("failed acquisition requires report ERROR | INCOMPLETE", errors)
        self.assertIn("failed acquisition requires structured ACQUISITION_FAILED error", errors)

    def test_failed_acquisition_cannot_carry_content_evidence(self):
        failed = copy.deepcopy(self.run)
        failed["acquisition"].update(
            {"succeeded": False, "final_location": None, "acquired_at": None, "tool": None, "error": "The target refused the retrieval attempt."}
        )
        failed["execution"] = {"completed": False, "failure_stage": "ACQUISITION", "error": "The target refused the retrieval attempt."}
        failed["report"]["automated_result"] = "ERROR"
        failed["report"]["errors"] = [{"code": "ACQUISITION_FAILED", "message": "Nothing was retrieved.", "stage": "acquisition"}]
        errors = validate_run(failed)
        self.assertIn("unsuccessful acquisition requires acquisition.content_sha256 to be null", errors)
        self.assertIn("unsuccessful acquisition requires acquisition.response_status to be null", errors)
        failed["acquisition"]["content_sha256"] = None
        failed["acquisition"]["response_status"] = None
        # The template's inherited SOURCE item describes a retrieved page that this run never retrieved.
        diagnostic = "failed acquisition may carry only TOOL_OUTPUT or COMMAND_OUTPUT diagnostic evidence"
        inherited = "\n".join(validate_run(failed))
        self.assertIn(diagnostic, inherited)
        self.assertIn('"SOURCE"', inherited)
        for evidence_type in ("TOOL_OUTPUT", "COMMAND_OUTPUT"):
            with self.subTest(evidence_type=evidence_type):
                truthful = copy.deepcopy(failed)
                truthful["report"]["evidence_log"] = [
                    {
                        "type": evidence_type,
                        "description": "The retrieval tool reported a refused connection; nothing was retrieved.",
                        "locator": "retrieval tool log, attempt 1",
                    }
                ]
                self.assertEqual(validate_run(truthful), [])
                with_finding = copy.deepcopy(truthful)
                finding = load("fixtures/ambiguous/advisory-only.json")["findings"][0]
                finding["evidence"] = [
                    {"type": "TOOL_OUTPUT", "description": "Diagnostic only.", "locator": "retrieval tool log"}
                ]
                with_finding["report"]["findings"] = [finding]
                self.assertIn("failed acquisition cannot carry findings", validate_run(with_finding))
        failed["report"]["evidence_log"] = [
            {"type": "TOOL_OUTPUT", "description": "The retrieval tool reported a refused connection.", "locator": "retrieval tool log"}
        ]
        self.assertEqual(validate_run(failed), [])

        # A JSON-valid but non-string type is reported once by the report layer and never raises here.
        for malformed in (["SOURCE"], {"type": "SOURCE"}):
            with self.subTest(malformed=malformed):
                unhashable = copy.deepcopy(failed)
                unhashable["report"]["evidence_log"].append(
                    {"type": malformed, "description": "Malformed evidence type.", "locator": "synthetic"}
                )
                errors = validate_run(unhashable)
                self.assertIsInstance(errors, list)
                self.assertIn("report: evidence_log[1].type is invalid", errors)
                self.assertFalse(any(diagnostic in error for error in errors), errors)

        redirected = copy.deepcopy(self.run)
        redirected["acquisition"]["final_location"] = "https://evil.test/"
        self.assertIn(
            "a final location that differs from the requested location requires a recorded redirect_chain",
            validate_run(redirected),
        )
        redirected["acquisition"]["redirect_chain"] = ["https://evil.test/"]
        self.assertEqual(validate_run(redirected), [])

    def test_website_redirect_chain_rejects_every_special_destination(self):
        unsafe = (
            "http://127.0.0.1/",
            "http://169.254.169.254/latest/meta-data/",
            "http://[::1]/",
            "http://[fe80::1%25en0]/",
            "http://metadata.google.internal/",
            "http://sub.localhost/",
            "http://2130706433/",
            "http://127.1/",
            "http://0177.0.0.1/",
            "http://0x7f.0.0.1/",
        )
        for location in unsafe:
            with self.subTest(location=location):
                envelope = copy.deepcopy(self.run)
                envelope["acquisition"]["redirect_chain"] = [location, "https://example.org/final"]
                envelope["acquisition"]["final_location"] = "https://example.org/final"
                errors = "\n".join(validate_run(envelope))
                self.assertIn("acquisition.redirect_chain[0]", errors)

    def test_website_requested_and_final_locations_receive_the_same_safety_check(self):
        requested = copy.deepcopy(self.run)
        requested["preflight"]["target"]["location"] = "http://127.1/"
        requested["report"]["target"]["location"] = "http://127.1/"
        requested["acquisition"]["requested_location"] = "http://127.1/"
        errors = "\n".join(validate_run(requested))
        self.assertIn("acquisition.requested_location", errors)

        final = copy.deepcopy(self.run)
        final["acquisition"]["final_location"] = "http://[::1]/"
        final["acquisition"]["redirect_chain"] = ["http://[::1]/"]
        errors = "\n".join(validate_run(final))
        self.assertIn("acquisition.final_location", errors)

    def test_website_redirect_chain_allows_global_ips_and_lettered_dns(self):
        envelope = copy.deepcopy(self.run)
        envelope["acquisition"]["redirect_chain"] = [
            "https://example.net/next",
            "https://[2606:4700:4700::1111]/hop",
            "https://example.org/final",
        ]
        envelope["acquisition"]["final_location"] = "https://example.org/final"
        self.assertEqual(validate_run(envelope), [])

    def test_redirect_chain_must_end_at_final_location(self):
        envelope = copy.deepcopy(self.run)
        envelope["acquisition"]["redirect_chain"] = ["https://example.net/not-final"]
        envelope["acquisition"]["final_location"] = "https://example.org/final"
        self.assertIn(
            "acquisition.redirect_chain must end at acquisition.final_location",
            validate_run(envelope),
        )

    def test_acquisition_timestamp_must_fall_inside_report_run(self):
        for acquired_at in ("2026-07-20T20:59:59Z", "2026-07-20T21:00:06Z"):
            with self.subTest(acquired_at=acquired_at):
                envelope = copy.deepcopy(self.run)
                envelope["acquisition"]["acquired_at"] = acquired_at
                self.assertIn(
                    "acquisition.acquired_at must fall within report.run started_at through completed_at",
                    validate_run(envelope),
                )

    def test_bundle_self_test_requires_its_hostile_fixture_to_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / "dravux"
            shutil.copytree(SKILL, copied)
            hostile = copied / "fixtures" / "hostile" / "unknown-property.invalid.json"
            hostile.write_bytes((copied / "fixtures" / "passing" / "known-pass.json").read_bytes())
            proc = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(copied / "scripts" / "dravux_run.py"),
                    "preflight",
                    str(copied / "assets" / "preflight-template.json"),
                    "--json",
                ],
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(proc.returncode, 4, proc.stdout + proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["status"], "UNSUPPORTED")
        self.assertEqual(result["validator_self_test"], "FAIL")
        self.assertIn("hostile fixture was unexpectedly accepted", result["validator_detail"])
        self.assertNotIn("Traceback", proc.stderr)

    def test_failed_acquisition_must_be_recorded_as_an_acquisition_stage_failure(self):
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
        envelope["execution"] = {
            "completed": False,
            "failure_stage": "TOOLING",
            "error": "The target could not be retrieved.",
        }
        self.assertIn(
            "failed acquisition requires execution.failure_stage ACQUISITION",
            validate_run(envelope),
        )

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

    def test_duplicate_json_key_in_run_envelope_is_rejected(self):
        # A duplicate key lets a reader see one value while the parser silently keeps
        # the last one, so the operational entry point must reject it exactly like the
        # report entry point. The duplicate cannot survive a parsed fixture, so the
        # malformed text is built here and written to a temporary file.
        valid = json.dumps(self.run, indent=2)
        forged = valid.replace(
            '"run_contract_version"',
            '"run_contract_version": "0.0.0-decoy",\n  "run_contract_version"',
            1,
        )
        self.assertNotEqual(forged, valid)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "duplicate-key-run.json"
            target.write_text(forged, encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(SKILL / "scripts" / "dravux_run.py"), "validate", str(target)],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("duplicate JSON key", proc.stderr + proc.stdout)
        self.assertNotIn("Traceback", proc.stderr + proc.stdout)


class ExecutionFailureContractTests(unittest.TestCase):
    """Run contract 1.2.0: acquiring a page and finishing an audit are separate events."""

    def setUp(self):
        self.run = load("plugins/dravux/skills/dravux/assets/run-envelope-template.json")
        self.manifest = load("fixtures/manifest.json")

    def test_execution_block_is_required(self):
        envelope = copy.deepcopy(self.run)
        del envelope["execution"]
        self.assertIn("run missing required fields: execution", validate_run(envelope))

    def test_acquired_target_with_failed_interaction_is_a_valid_run(self):
        # The real incident this case exists for: the homepage was acquired, the
        # scripted keyboard interaction then malfunctioned, and the old contract
        # had no honest envelope for it.
        envelope = load("fixtures/operational/post-acquisition-interaction-failure.run.json")
        self.assertEqual(validate_run(envelope), [])
        self.assertTrue(envelope["acquisition"]["succeeded"])
        self.assertFalse(envelope["execution"]["completed"])
        self.assertEqual(envelope["execution"]["failure_stage"], "INTERACTION")
        self.assertEqual(envelope["report"]["automated_result"], "ERROR")
        self.assertEqual(envelope["report"]["final_status"], "INCOMPLETE")

        proc = subprocess.run(
            [
                sys.executable,
                str(SKILL / "scripts" / "dravux_run.py"),
                "validate",
                str(ROOT / "fixtures/operational/post-acquisition-interaction-failure.run.json"),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        receipt = json.loads(proc.stdout)["receipt"]
        self.assertFalse(receipt["execution_completed"])
        self.assertEqual(receipt["execution_failure_stage"], "INTERACTION")
        self.assertEqual(
            receipt["meaning"],
            "The page was acquired, but the audit itself failed before completion. "
            "No accessibility conclusion is established.",
        )

    def test_post_acquisition_failure_requires_its_exact_shape(self):
        base = load("fixtures/operational/post-acquisition-interaction-failure.run.json")

        without_code = copy.deepcopy(base)
        without_code["report"]["errors"] = [
            {"code": "SOMETHING_ELSE", "message": "An unstructured excuse.", "stage": "interaction"}
        ]
        self.assertIn(
            "post-acquisition execution failure requires structured EXECUTION_FAILED error",
            validate_run(without_code),
        )

        wrong_stage = copy.deepcopy(base)
        wrong_stage["execution"]["failure_stage"] = "ACQUISITION"
        self.assertIn(
            "acquired target cannot record execution.failure_stage ACQUISITION",
            validate_run(wrong_stage),
        )

        wrong_verdict = copy.deepcopy(base)
        wrong_verdict["report"]["automated_result"] = "FAIL"
        wrong_verdict["report"]["final_status"] = "VERIFIED FAIL"
        self.assertIn(
            "post-acquisition execution failure requires report ERROR | INCOMPLETE or ERROR | VERIFIED FAIL",
            validate_run(wrong_verdict),
        )

    def test_incomplete_execution_can_never_carry_a_pass_or_a_verified_pass(self):
        envelope = copy.deepcopy(self.run)
        envelope["preflight"]["requested_mode"] = "RENDERED_DOM"
        envelope["preflight"]["selected_mode"] = "RENDERED_DOM"
        envelope["preflight"]["capabilities"]["acquisition"] = "RENDERED_DOM"
        envelope["preflight"]["capabilities"]["manual_evidence"] = True
        envelope["acquisition"]["method"] = "RENDERED_DOM"
        envelope["report"]["scope"]["manual_checks_completed"] = copy.deepcopy(
            envelope["report"]["scope"]["required_manual_checks"]
        )
        envelope["report"]["final_status"] = "VERIFIED PASS"
        envelope["report"]["evidence_log"].extend(
            {
                "type": "MANUAL_OBSERVATION",
                "manual_check_id": check,
                "description": "Synthetic completion evidence for the bounded regression.",
                "locator": f"test fixture manual completion: {check}",
            }
            for check in envelope["report"]["scope"]["manual_checks_completed"]
        )
        self.assertEqual(validate_run(envelope), [], "baseline VERIFIED PASS envelope must be valid")

        envelope["execution"] = {
            "completed": False,
            "failure_stage": "AUDIT_EXECUTION",
            "error": "The analyzer stopped halfway through the run.",
        }
        errors = validate_run(envelope)
        self.assertIn("an execution that did not complete cannot report an automated PASS", errors)
        self.assertIn("an execution that did not complete cannot end VERIFIED PASS", errors)

        underscored = copy.deepcopy(envelope)
        underscored["report"]["final_status"] = "VERIFIED_PASS"
        self.assertIn(
            "an execution that did not complete cannot end VERIFIED PASS",
            validate_run(underscored),
        )

    def test_contract_only_runs_must_record_a_completed_execution(self):
        envelope = copy.deepcopy(self.run)
        envelope["preflight"]["target"] = {
            "input_type": "SOURCE_CODE",
            "location": "fixtures/passing/known-pass.json",
        }
        envelope["preflight"]["requested_mode"] = "CONTRACT_ONLY"
        envelope["preflight"]["selected_mode"] = "CONTRACT_ONLY"
        envelope["preflight"]["capabilities"]["acquisition"] = "NONE"
        envelope["acquisition"].update(
            {
                "attempted": False,
                "succeeded": False,
                "method": "NONE",
                "requested_location": "fixtures/passing/known-pass.json",
                "final_location": None,
                "response_status": None,
                "acquired_at": None,
                "tool": None,
                "content_sha256": None,
                "error": None,
            }
        )
        envelope["execution"] = {
            "completed": False,
            "failure_stage": "REPORT_ASSEMBLY",
            "error": "Report assembly stopped early.",
        }
        self.assertIn("CONTRACT_ONLY runs must record execution.completed true", validate_run(envelope))

    def test_manifest_operational_fixtures_match_their_declared_outcome(self):
        indexed = self.manifest["operational_fixtures"]
        self.assertTrue(indexed)
        for item in indexed:
            with self.subTest(path=item["path"]):
                payload = load(f"fixtures/{item['path']}")
                if item["kind"] == "preflight":
                    decision = preflight_decision(payload)
                    self.assertEqual(decision["status"], item["preflight_status"])
                    self.assertEqual(decision["exit_code"], item["exit_code"])
                    continue
                violations = validate_run(payload)
                self.assertEqual(not violations, item["run_valid"], violations)
                if item["run_valid"]:
                    self.assertEqual(payload["report"]["automated_result"], item["automated_result"])
                    self.assertEqual(payload["report"]["final_status"], item["final_status"])
                    self.assertEqual(payload["execution"]["completed"], item["execution_completed"])
                    self.assertEqual(payload["execution"]["failure_stage"], item["failure_stage"])
                else:
                    self.assertIn(item["expected_violation"], violations)


class OutputDirectoryContractTests(unittest.TestCase):
    """A tester once wrote audit files into an extracted release and broke its own verification."""

    def output_dir_cli(self, arguments, cwd=None):
        return subprocess.run(
            [sys.executable, "-B", str(SKILL / "scripts" / "dravux_run.py"), "output-dir"] + arguments,
            cwd=None if cwd is None else str(cwd),
            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            check=False,
            capture_output=True,
            text=True,
        )

    def test_guarded_tree_redirects_beside_the_installation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            installed = workspace / "dravux-1.0.2"
            nested = installed / "plugins" / "dravux" / "skills" / "dravux"
            nested.mkdir(parents=True)
            (installed / "RELEASE_MANIFEST.json").write_text("{}", encoding="utf-8")
            (nested / "SKILL.md").write_text("# skill", encoding="utf-8")

            result = resolve_output_dir(nested, "homepage-audit", False)
            self.assertEqual(result["status"], "REDIRECTED")
            self.assertEqual(result["exit_code"], 0)
            self.assertTrue(result["guarded"])
            # The outermost marker wins, so output never lands between two guarded roots.
            self.assertEqual(result["guarded_root"], str(installed))
            self.assertEqual(result["output_dir"], str(workspace / "dravux-audits" / "homepage-audit"))
            self.assertTrue(Path(result["output_dir"]).is_dir())
            self.assertEqual(sorted(path.name for path in installed.rglob("dravux-audits")), [])

    def test_strict_mode_refuses_and_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            installed = workspace / "extracted-release"
            installed.mkdir()
            (installed / "SKILL.md").write_text("# skill", encoding="utf-8")
            before = sorted(str(path) for path in workspace.rglob("*"))

            proc = self.output_dir_cli(["--base", str(installed), "--strict"])
            self.assertEqual(proc.returncode, OUTPUT_DIR_REFUSED_EXIT)
            self.assertEqual(proc.stdout, "")
            self.assertIn(str(installed), proc.stderr)
            self.assertIn("Nothing was created.", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertEqual(sorted(str(path) for path in workspace.rglob("*")), before)

    def test_unguarded_base_creates_the_audit_folder_and_prints_it_last(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            proc = self.output_dir_cli(["--base", str(workspace), "--audit-id", "run-001"])
            self.assertEqual(proc.returncode, 0, proc.stderr)
            expected = workspace / "dravux-audits" / "run-001"
            self.assertEqual(proc.stdout.strip().splitlines()[-1], str(expected))
            self.assertTrue(expected.is_dir())

    def test_preexisting_output_symlink_is_refused_without_redirected_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            redirected = workspace / "redirected"
            redirected.mkdir()
            (workspace / "dravux-audits").symlink_to(redirected, target_is_directory=True)
            before = sorted(redirected.iterdir())
            result = resolve_output_dir(workspace, "run-001", False)
            self.assertEqual(result["status"], "REFUSED")
            self.assertEqual(result["exit_code"], OUTPUT_DIR_REFUSED_EXIT)
            self.assertEqual(sorted(redirected.iterdir()), before)

    def test_raced_output_symlink_is_refused_without_redirected_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            redirected = workspace / "redirected"
            redirected.mkdir()
            original_mkdir = Path.mkdir

            def race(path, *args, **kwargs):
                path.symlink_to(redirected, target_is_directory=True)
                raise FileExistsError(str(path))

            with mock.patch("pathlib.Path.mkdir", autospec=True, side_effect=race):
                result = resolve_output_dir(workspace, "run-001", False)
            self.assertEqual(result["status"], "REFUSED")
            self.assertEqual(result["exit_code"], OUTPUT_DIR_REFUSED_EXIT)
            self.assertEqual(sorted(redirected.iterdir()), [])
            self.assertIsNotNone(original_mkdir)

    def test_audit_child_alias_into_guarded_tree_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            guarded = workspace / "guarded"
            guarded.mkdir()
            (guarded / "SKILL.md").write_text("# skill\n", encoding="utf-8")
            root = workspace / "dravux-audits"
            root.mkdir()
            (root / "run-001").symlink_to(guarded, target_is_directory=True)
            result = resolve_output_dir(workspace, "run-001", False)
            self.assertEqual(result["status"], "REFUSED")
            self.assertEqual(result["exit_code"], OUTPUT_DIR_REFUSED_EXIT)
            self.assertEqual(sorted(path.name for path in guarded.iterdir()), ["SKILL.md"])

    def test_audit_id_is_a_closed_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            for rejected in ("../escape", "Upper", "with space", "a" * 65, ""):
                with self.subTest(audit_id=rejected):
                    result = resolve_output_dir(workspace, rejected, False)
                    self.assertEqual(result["status"], "INVALID")
                    self.assertNotEqual(result["exit_code"], 0)
                    self.assertIsNone(result["output_dir"])
            self.assertEqual(sorted(workspace.rglob("*")), [])

    def test_documented_workflow_leaves_the_skill_tree_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp).resolve()
            copied = workspace / "dravux"
            shutil.copytree(SKILL, copied)
            before = self.tree_digest(copied)
            self.assertTrue(before)

            # Bytecode writing is deliberately left on: the workflow must keep the tree
            # identical the way an ordinary user runs it, not only under python3 -B.
            env = {key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"}
            script = str(copied / "scripts" / "dravux_run.py")
            steps = (
                (["preflight", "assets/preflight-template.json", "--json"], 3),
                (["validate", "assets/run-envelope-template.json", "--json"], 0),
                (["output-dir", "--json"], 0),
            )
            outputs = []
            for arguments, expected_code in steps:
                proc = subprocess.run(
                    [sys.executable, script] + arguments,
                    cwd=str(copied),
                    env=env,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, expected_code, proc.stderr)
                outputs.append(json.loads(proc.stdout))

            self.assertEqual(outputs[0]["status"], "LIMITATION_ACK_REQUIRED")
            self.assertTrue(outputs[1]["valid"], outputs[1])
            self.assertEqual(outputs[2]["status"], "REDIRECTED")
            written = Path(outputs[2]["output_dir"])
            self.assertEqual(written, workspace / "dravux-audits")
            self.assertNotIn(copied, written.parents)
            self.assertTrue(written.is_dir())

            self.assertEqual(self.tree_digest(copied), before)

    @staticmethod
    def tree_digest(root):
        return {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*"))
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()
