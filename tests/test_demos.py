import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from audit_demo_html import audit_html  # noqa: E402


class DemoTests(unittest.TestCase):
    def test_github_state_transition_matches_expected_reports(self):
        cases = [
            ("broken", "FAIL", "VERIFIED FAIL", 5),
            ("repaired", "PASS", "INCOMPLETE", 0),
        ]
        script = ROOT / "scripts" / "audit_demo_html.py"
        for state, automated, final, finding_count in cases:
            with self.subTest(state=state):
                source = Path("demos") / "github" / state / "index.html"
                process = subprocess.run(
                    [sys.executable, str(script), str(source), "--state", state],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                report = json.loads(process.stdout)
                expected_path = ROOT / "demos" / "github" / "expected" / f"{state}-report.json"
                expected = json.loads(expected_path.read_text(encoding="utf-8"))
                self.assertEqual((expected_path.parent / expected["$schema"]).resolve(), ROOT / "schemas" / "dravux-report.schema.json")
                report_without_schema = {key: value for key, value in report.items() if key != "$schema"}
                expected_without_schema = {key: value for key, value in expected.items() if key != "$schema"}
                self.assertEqual(report_without_schema, expected_without_schema)
                self.assertEqual(report["automated_result"], automated)
                self.assertEqual(report["final_status"], final)
                self.assertEqual(len(report["findings"]), finding_count)

    def test_fail_on_findings_exit_behavior(self):
        script = ROOT / "scripts" / "audit_demo_html.py"
        broken = subprocess.run(
            [sys.executable, str(script), "demos/github/broken/index.html", "--state", "broken", "--fail-on-findings"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        repaired = subprocess.run(
            [sys.executable, str(script), "demos/github/repaired/index.html", "--state", "repaired", "--fail-on-findings"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(broken.returncode, 1)
        self.assertEqual(repaired.returncode, 0)

    def test_small_isolated_native_button_is_not_a_target_or_focus_failure(self):
        source = '<!doctype html><html lang="en"><button style="color:#fff;background-color:#000;width:20px;height:20px">A</button></html>'
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "isolated.html"
            path.write_text(source, encoding="utf-8")
            report = audit_html(path, "isolated-small-native-button")
        finding_ids = {finding["finding_id"] for finding in report["findings"]}
        self.assertFalse(any("TARGET" in finding_id for finding_id in finding_ids))
        self.assertFalse(any("FOCUS" in finding_id for finding_id in finding_ids))

    def test_broken_target_and_focus_findings_have_explicit_applicability_evidence(self):
        report = audit_html(ROOT / "demos" / "github" / "broken" / "index.html", "broken")
        by_id = {finding["finding_id"]: finding for finding in report["findings"]}
        self.assertIn("centers are 20.0px apart", by_id["DRV-DEMO-TARGET-SPACING-001"]["evidence"][0]["description"])
        self.assertIn("outline: none", by_id["DRV-DEMO-FOCUS-001"]["evidence"][0]["description"])

    def test_reset_script_is_scoped_to_destination(self):
        script = ROOT / "demos" / "github" / "reset_demo.py"
        with tempfile.TemporaryDirectory() as folder:
            destination = Path(folder) / "index.html"
            process = subprocess.run(
                [sys.executable, str(script), "--state", "repaired", "--destination", str(destination)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            expected = (ROOT / "demos" / "github" / "repaired" / "index.html").read_text(encoding="utf-8")
            self.assertEqual(destination.read_text(encoding="utf-8"), expected)

    def test_default_workflow_requires_no_token(self):
        workflow = (ROOT / "demos" / "github" / ".github" / "workflows" / "dravux-demo.yml").read_text(encoding="utf-8")
        self.assertNotIn("GH_TOKEN", workflow)
        self.assertNotIn("secrets.", workflow)
        self.assertIn("permissions:\n  contents: read", workflow)

    def test_workflows_are_pinned_bounded_and_cover_supported_pythons(self):
        root_workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        demo_workflow = (
            ROOT / "demos" / "github" / ".github" / "workflows" / "dravux-demo.yml"
        ).read_text(encoding="utf-8")
        checkout = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1"
        setup = "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97 # v7.0.0"

        for name, workflow in (("root", root_workflow), ("demo", demo_workflow)):
            with self.subTest(workflow=name):
                self.assertEqual(workflow.count(checkout), 1)
                self.assertEqual(workflow.count(setup), 1)
                self.assertEqual(workflow.count("persist-credentials: false"), 1)
                self.assertIn("permissions:\n  contents: read", workflow)
                self.assertNotIn(": write", workflow)
                self.assertRegex(workflow, r"timeout-minutes: [1-9][0-9]*")
                self.assertIn('PYTHONDONTWRITEBYTECODE: "1"', workflow)
                self.assertIn('PYTHONUTF8: "1"', workflow)
                self.assertNotRegex(workflow, r"uses:\s*actions/(?:checkout|setup-python)@v[0-9]")
                for line in workflow.splitlines():
                    if "python3 " in line:
                        self.assertIn("python3 -B ", line, line)

        matrix = root_workflow.split("matrix:", 1)[1].split("steps:", 1)[0]
        self.assertEqual(
            re.findall(r"- os: ([^\s]+)\n\s+python-version: \"([^\"]+)\"", matrix),
            [("ubuntu-latest", "3.8"), ("ubuntu-latest", "3.13"), ("macos-latest", "3.13")],
        )
        self.assertIn("python-version: ${{ matrix.python-version }}", root_workflow)
        self.assertIn("${{ runner.temp }}/dravux-report.json", demo_workflow)
        self.assertNotIn("/tmp/", demo_workflow)


if __name__ == "__main__":
    unittest.main()
