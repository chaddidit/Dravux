import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is required to test the optional npx launcher")
class NpxTests(unittest.TestCase):
    def run_cli(self, *args, home=None, path=None):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if home is not None:
            env["HOME"] = str(home)
        if path is not None:
            env["PATH"] = path
        return subprocess.run(
            [NODE, str(ROOT / "bin/dravux.js"), *map(str, args)],
            cwd="/",
            env=env,
            capture_output=True,
            text=True,
        )

    def test_help_needs_no_shell_and_invalid_arguments_keep_exit_code(self):
        for args in ((), ("--help",), ("verify", "--help")):
            result = self.run_cli(*args, path="")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Usage: dravux", result.stdout)
        self.assertEqual(self.run_cli("--unknown").returncode, 2)
        self.assertEqual(self.run_cli("verify", "--unknown").returncode, 2)

    def test_real_install_verify_and_refusal_through_wrapper(self):
        with tempfile.TemporaryDirectory(prefix="dravux npx ") as tmp:
            home = Path(tmp) / "Home with spaces"
            project = Path(tmp) / "Project Ω ; literal"
            home.mkdir()
            project.mkdir()
            for platform in ("--claude", "--codex"):
                for scope in (("--personal",), ("--project-dir", project)):
                    args = (platform, *scope)
                    with self.subTest(args=args):
                        installed = self.run_cli(*args, home=home)
                        self.assertEqual(installed.returncode, 0, installed.stderr)
                        verified = self.run_cli("verify", *args, home=home)
                        self.assertEqual(verified.returncode, 0, verified.stderr)
                        self.assertIn("byte-identical", verified.stdout)
                        self.assertEqual(self.run_cli(*args, home=home).returncode, 4)
            skill = project / ".agents/skills/dravux/SKILL.md"
            original = skill.read_bytes()
            skill.write_bytes(original + b"\ntampered\n")
            self.assertEqual(
                self.run_cli("verify", "--codex", "--project-dir", project, home=home).returncode, 5
            )
            self.assertEqual(skill.read_bytes(), original + b"\ntampered\n")

    def test_missing_shell_fails_cleanly(self):
        result = self.run_cli("--codex", "--personal", path="")
        self.assertEqual(result.returncode, 1)
        self.assertIn("ENOENT", result.stderr)
