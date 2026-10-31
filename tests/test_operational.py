import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
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
    """Run contract 1.1.0: acquiring a page and finishing an audit are separate events."""

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
            "post-acquisition execution failure requires report ERROR | INCOMPLETE",
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
        envelope["report"]["evidence_log"].append(
            {
                "type": "MANUAL_OBSERVATION",
                "description": "Synthetic completion evidence for the bounded regression.",
                "locator": "test fixture manual completion",
            }
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
