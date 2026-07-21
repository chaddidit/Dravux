import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "dravux" / "skills" / "dravux"
SKILL_SCRIPTS = SKILL / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))

from dravux_contract import validate_report  # noqa: E402


class SkillPortabilityTests(unittest.TestCase):
    def test_bundled_schemas_are_byte_identical_to_top_level(self):
        for name in (
            "dravux-report.schema.json",
            "finding.schema.json",
            "dravux-preflight.schema.json",
            "dravux-run.schema.json",
        ):
            with self.subTest(schema=name):
                self.assertEqual(
                    (SKILL / "schemas" / name).read_bytes(),
                    (ROOT / "schemas" / name).read_bytes(),
                    f"bundled and top-level {name} have drifted",
                )

    def test_report_template_schema_ref_resolves_inside_skill(self):
        template = json.loads((SKILL / "assets" / "report-template.json").read_text(encoding="utf-8"))
        resolved = (SKILL / "assets" / template["$schema"]).resolve()
        self.assertTrue(resolved.is_file(), resolved)
        self.assertEqual(resolved, (SKILL / "schemas" / "dravux-report.schema.json").resolve())
        self.assertIn(str(SKILL.resolve()), str(resolved), "template $schema escapes the skill folder")

    def test_bundled_report_schema_finding_ref_resolves_inside_bundle(self):
        schema = json.loads((SKILL / "schemas" / "dravux-report.schema.json").read_text(encoding="utf-8"))
        self.assertNotIn("$id", schema, "an opaque $id would override the local retrieval base")
        ref = schema["properties"]["findings"]["items"]["$ref"]
        self.assertTrue((SKILL / "schemas" / ref).resolve().is_file(), ref)

    def test_operational_schema_refs_resolve_inside_bundle(self):
        schema = json.loads((SKILL / "schemas" / "dravux-run.schema.json").read_text(encoding="utf-8"))
        for key in ("preflight", "report"):
            ref = schema["properties"][key]["$ref"]
            with self.subTest(ref=ref):
                self.assertTrue((SKILL / "schemas" / ref).resolve().is_file(), ref)

    def test_skill_md_local_references_resolve_in_standalone_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "dravux"
            shutil.copytree(SKILL, copy)
            text = (copy / "SKILL.md").read_text(encoding="utf-8")
            links = [
                link
                for link in re.findall(r"\]\(([^)#]+)\)", text)
                if not link.startswith(("http://", "https://"))
            ]
            links += [
                "scripts/dravux_contract.py",
                "scripts/dravux_run.py",
                "assets/report-template.json",
                "assets/preflight-template.json",
                "assets/run-envelope-template.json",
            ]
            self.assertTrue(links)
            for link in links:
                with self.subTest(link=link):
                    self.assertTrue((copy / link).exists(), f"SKILL.md reference dangles standalone: {link}")

    def test_contract_validator_runs_standalone_on_copied_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "dravux"
            shutil.copytree(SKILL, copy)
            proc = subprocess.run(
                [sys.executable, str(copy / "scripts" / "dravux_contract.py"), str(copy / "assets" / "report-template.json")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("VALID", proc.stdout)

    def test_bundled_acceptance_fixtures_run_standalone(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "dravux"
            shutil.copytree(SKILL, copy)
            valid = subprocess.run(
                [
                    sys.executable,
                    str(copy / "scripts" / "dravux_contract.py"),
                    str(copy / "fixtures" / "passing" / "known-pass.json"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            hostile = subprocess.run(
                [
                    sys.executable,
                    str(copy / "scripts" / "dravux_contract.py"),
                    str(copy / "fixtures" / "hostile" / "unknown-property.invalid.json"),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertIn("PASS | VERIFIED PASS", valid.stdout)
            self.assertEqual(hostile.returncode, 1)
            self.assertIn("unknown properties", hostile.stderr)

    def test_operational_validator_runs_standalone_on_copied_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "dravux"
            shutil.copytree(SKILL, copy)
            limitation = subprocess.run(
                [sys.executable, str(copy / "scripts" / "dravux_run.py"), "preflight", str(copy / "assets" / "preflight-template.json")],
                capture_output=True,
                text=True,
                check=False,
            )
            valid = subprocess.run(
                [sys.executable, str(copy / "scripts" / "dravux_run.py"), "validate", str(copy / "assets" / "run-envelope-template.json")],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(limitation.returncode, 3, limitation.stderr)
            self.assertIn("LIMITATION_ACK_REQUIRED", limitation.stdout)
            self.assertEqual(valid.returncode, 0, valid.stderr)
            self.assertIn("DRAVUX RUN RECEIPT", valid.stdout)

    def test_structural_hostile_fixtures_fail_for_the_reproduced_reason(self):
        expectations = {
            "hostile/unknown-property.invalid.json": "unknown properties",
            "hostile/invalid-semver.invalid.json": "semantic version",
            "hostile/invalid-audit-id.invalid.json": "audit_id must match",
            "hostile/invalid-finding-id.invalid.json": "finding_id must match",
            "hostile/invalid-timestamp.invalid.json": "RFC 3339 date-time",
            "hostile/invalid-uri.invalid.json": "absolute HTTP(S) URL",
            "hostile/duplicate-manual-checks.invalid.json": "duplicate entries",
        }
        for relative, expected in expectations.items():
            with self.subTest(path=relative):
                report = json.loads((ROOT / "fixtures" / relative).read_text(encoding="utf-8"))
                self.assertIn(expected, "\n".join(validate_report(report)))


if __name__ == "__main__":
    unittest.main()
