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
CAPABILITY_DOC = ROOT / "docs" / "capabilities.md"
REQUIRED_REFERENCES = (
    "capability-matrix.md",
    "github-evidence.md",
    "surface-modes.md",
    "input-capabilities.md",
    "execution-gates.md",
    "manual-checks.md",
    "verdict-and-evidence.md",
    "wcag-2.2-map.md",
)
CAPABILITY_TOKEN = re.compile(r"^[A-Z][A-Z_]{3,}$")
sys.path.insert(0, str(SKILL_SCRIPTS))

from dravux_contract import validate_report  # noqa: E402


def _markdown_links(text):
    return [
        link
        for link in re.findall(r"\]\(([^)#]+)\)", text)
        if not link.startswith(("http://", "https://"))
    ]


def _capability_prose_paths():
    paths = [path for path in SKILL.rglob("*.md")]
    paths.append(CAPABILITY_DOC)
    paths.extend(sorted((ROOT / "adapters").rglob("*.md")))
    return [path for path in paths if path.is_file()]


def _collect_capability_tokens(node, found):
    if isinstance(node, dict):
        for value in node.values():
            _collect_capability_tokens(value, found)
    elif isinstance(node, list):
        for value in node:
            _collect_capability_tokens(value, found)
    elif isinstance(node, str) and CAPABILITY_TOKEN.match(node):
        found.add(node)


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
            links = _markdown_links(text)
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

    def test_capability_references_travel_inside_a_standalone_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "dravux"
            shutil.copytree(SKILL, copy)
            for name in REQUIRED_REFERENCES:
                with self.subTest(reference=name):
                    reference = copy / "references" / name
                    self.assertTrue(reference.is_file(), f"reference missing from the skill bundle: {name}")
                    for link in _markdown_links(reference.read_text(encoding="utf-8")):
                        self.assertTrue(
                            (reference.parent / link).exists(),
                            f"references/{name} link dangles standalone: {link}",
                        )

    def test_capability_matrix_exists_at_the_documented_project_path(self):
        self.assertTrue(CAPABILITY_DOC.is_file(), "docs/capabilities.md is linked from the project README")
        text = CAPABILITY_DOC.read_text(encoding="utf-8")
        for token in ("LIMITATION_ACK_REQUIRED", "UNSUPPORTED", "output-dir"):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_skill_and_project_capability_copies_cover_the_same_surfaces(self):
        matrix = (SKILL / "references" / "capability-matrix.md").read_text(encoding="utf-8")
        doc = CAPABILITY_DOC.read_text(encoding="utf-8")
        for surface in ("Claude Chat", "Cowork", "Claude Code", "Claude in Chrome", "Codex"):
            with self.subTest(surface=surface):
                self.assertIn(surface, matrix, f"in-skill matrix omits {surface}")
                self.assertIn(surface, doc, f"project capability doc omits {surface}")

    def test_skill_md_documents_the_output_directory_contract(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("output-dir", text, "SKILL.md must document the output-directory subcommand")
        self.assertIn("scripts/dravux_run.py output-dir", text)
        self.assertRegex(
            text,
            r"[Nn]ever write .*into the skill folder",
            "SKILL.md must forbid writing artifacts into the skill or release tree",
        )

    def test_skill_md_documents_the_execution_contract(self):
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for token in ("1.2.0", "`execution`", "completed", "failure_stage", "EXECUTION_FAILED", "ACQUISITION_FAILED"):
            with self.subTest(token=token):
                self.assertIn(token, text, f"SKILL.md must document {token}")

    def test_documented_failure_stages_match_the_run_schema(self):
        schema = json.loads((SKILL / "schemas" / "dravux-run.schema.json").read_text(encoding="utf-8"))
        execution = schema.get("properties", {}).get("execution")
        self.assertTrue(execution, "run schema must define the execution block")
        self.assertIn("execution", schema.get("required", []), "the execution block must be required")
        stages = set()
        _collect_capability_tokens(execution, stages)
        self.assertTrue(stages, "execution block declares no closed failure-stage enum")
        text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        for stage in sorted(stages):
            with self.subTest(stage=stage):
                self.assertIn(stage, text, f"SKILL.md does not document failure stage {stage}")

    def test_output_dir_command_matches_its_documentation(self):
        source = (SKILL_SCRIPTS / "dravux_run.py").read_text(encoding="utf-8")
        self.assertIn("output-dir", source, "dravux_run.py must implement the output-dir subcommand")
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "dravux"
            shutil.copytree(SKILL, copy)
            base = Path(tmp) / "workspace"
            base.mkdir()
            proc = subprocess.run(
                [sys.executable, str(copy / "scripts" / "dravux_run.py"), "output-dir", "--base", str(base)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            final = proc.stdout.strip().splitlines()[-1].strip()
            resolved = Path(final)
            self.assertTrue(resolved.is_absolute(), f"output-dir must print an absolute path, got {final}")
            self.assertTrue(resolved.is_dir(), f"output-dir must create the directory it prints: {final}")
            self.assertFalse(
                str(resolved).startswith(str(copy)),
                "output-dir must never resolve inside the skill tree",
            )

    def test_no_document_claims_the_skill_grants_a_capability(self):
        forbidden_subject = re.compile(r"\b(skill|plugin|install\w*|upload\w*|invok\w*)\b", re.IGNORECASE)
        negation = re.compile(r"\b(no|not|never|none|neither|nothing|cannot|without)\b", re.IGNORECASE)
        for path in _capability_prose_paths():
            text = path.read_text(encoding="utf-8")
            for sentence in re.split(r"(?<=[.;:])\s+|\n", text):
                if "grant" not in sentence.lower():
                    continue
                if not forbidden_subject.search(sentence):
                    continue
                with self.subTest(path=path.relative_to(ROOT), sentence=sentence.strip()[:120]):
                    self.assertTrue(
                        negation.search(sentence),
                        "a skill never grants network, browser, DOM, screenshots, credentials, or GitHub metadata",
                    )

    def test_capability_documents_keep_the_three_layers_separate(self):
        matrix = (SKILL / "references" / "capability-matrix.md").read_text(encoding="utf-8")
        github = (SKILL / "references" / "github-evidence.md").read_text(encoding="utf-8")
        self.assertIn("commit history", github.lower())
        self.assertRegex(
            github,
            r"(?i)file names and contents",
            "github-evidence.md must state that a file integration supplies file contents only",
        )
        for token in ("LIMITATION_ACK_REQUIRED", "UNSUPPORTED", "INVALID"):
            with self.subTest(token=token):
                self.assertIn(token, matrix, f"in-skill matrix must name the {token} outcome")

    def test_admin_disabled_caveat_appears_consistently_before_the_upload_step(self):
        caveat = (
            "some organization plans and admin settings turn custom skills or code execution off entirely"
        )
        for path in (CAPABILITY_DOC, SKILL / "references" / "capability-matrix.md"):
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIn(caveat, text, "the admin-disabled caveat must appear in both capability copies")
                self.assertLess(
                    text.index(caveat),
                    text.index("| Surface | Install path |"),
                    "the caveat must appear before the install instructions, not after them",
                )

    def test_structured_artifact_free_text_is_named_untrusted(self):
        for path in (SKILL / "SKILL.md", SKILL / "references" / "github-evidence.md"):
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                for field in ("execution.error", "acquisition.error", "validator error string"):
                    self.assertIn(field, text, f"{field} must be named as untrusted display data")
                self.assertIn("never let it", text.replace("never let them", "never let it"))

    def test_limitation_stop_copy_states_it_is_not_a_failed_audit(self):
        for path in (SKILL / "SKILL.md", SKILL / "references" / "capability-matrix.md", CAPABILITY_DOC):
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8").lower()
                self.assertIn("not a failed audit", text)

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
