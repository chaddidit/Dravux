import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "plugins" / "dravux" / "skills" / "dravux"
SCRIPTS = ROOT / "scripts"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()


def tree_digest(root):
    values = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file() and not path.is_symlink():
            values.append((relative, hashlib.sha256(path.read_bytes()).hexdigest()))
        else:
            values.append((relative + "/", ""))
    return values


class DistributionTests(unittest.TestCase):
    def test_end_user_docs_match_raw_and_plugin_routes(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        claude_adapter = (ROOT / "adapters" / "claude" / "README.md").read_text(encoding="utf-8")
        codex_adapter = (ROOT / "adapters" / "codex" / "README.md").read_text(encoding="utf-8")

        for expected in (
            "/dravux:dravux",
            "$dravux:dravux",
            'cp -R fixtures "$DRAVUX_TEST_PROJECT/fixtures"',
            "claude plugin uninstall dravux@dravux",
            "codex plugin remove dravux@dravux",
            "## Troubleshooting",
        ):
            self.assertIn(expected, readme)
        self.assertIn("/dravux:dravux", claude_adapter)
        self.assertIn("$dravux:dravux", codex_adapter)
        self.assertIn('cd "$DRAVUX_COPY"', claude_adapter)
        self.assertIn('cd "$DRAVUX_COPY"', codex_adapter)
        self.assertIn("plugins/dravux/skills/dravux", claude_adapter)
        self.assertIn("plugins/dravux/skills/dravux", codex_adapter)
        quickstart = (ROOT / "docs" / "quickstart.md").read_text(encoding="utf-8")
        operational_readme = (ROOT / "fixtures" / "operational" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("skill/dravux/", quickstart)
        self.assertNotIn("skill/dravux/", operational_readme)
        self.assertIn("plugins/dravux/skills/dravux/", quickstart)

        marketplace = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["policy"]["authentication"], "ON_INSTALL")
        self.assertEqual(entry["category"], "Productivity")

    def test_archive_builder_excludes_local_and_private_state(self):
        import sys

        sys.path.insert(0, str(SCRIPTS))
        from build_release import should_exclude

        excluded = (
            Path("config/local-paths.json"),
            Path("config/example.private.json"),
            Path(".env"),
            Path(".env.local"),
            Path(".claude/settings.local.json"),
            Path(".claude/skills/dravux/SKILL.md"),
            Path(".codex/config.toml"),
            Path(".agents/skills/dravux/SKILL.md"),
            Path("out/generated.json"),
            Path("session.log"),
        )
        for path in excluded:
            with self.subTest(path=path):
                self.assertTrue(should_exclude(path))
        self.assertFalse(should_exclude(Path(".agents/plugins/marketplace.json")))
        self.assertFalse(should_exclude(Path(".claude-plugin/marketplace.json")))

    def run_script(self, name, *args, cwd=None, home=None):
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        if home is not None:
            env["HOME"] = str(home)
        return subprocess.run(
            ["sh", str(ROOT / name), *map(str, args)],
            cwd=cwd,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_all_raw_install_destinations_and_unrelated_working_directory(self):
        with tempfile.TemporaryDirectory(prefix="dravux install space ") as tmp:
            base = Path(tmp)
            unrelated = base / "unrelated Ω directory"
            unrelated.mkdir()
            project = base / "Project With Spaces Ω"
            project.mkdir()
            home = base / "Home With Spaces Ω"
            home.mkdir()
            cases = (
                ("--claude", "--project-dir", project, project / ".claude/skills/dravux"),
                ("--codex", "--project-dir", project, project / ".agents/skills/dravux"),
                ("--claude", "--personal", None, home / ".claude/skills/dravux"),
                ("--codex", "--personal", None, home / ".agents/skills/dravux"),
            )
            for platform, scope, scope_value, destination in cases:
                with self.subTest(platform=platform, scope=scope):
                    args = [platform, scope]
                    if scope_value is not None:
                        args.append(scope_value)
                    installed = self.run_script("install.sh", *args, cwd=unrelated, home=home)
                    self.assertEqual(installed.returncode, 0, installed.stderr)
                    self.assertTrue(destination.is_dir())
                    self.assertEqual(tree_digest(SOURCE), tree_digest(destination))
                    before = tree_digest(destination)
                    verified = self.run_script("verify-install.sh", *args, cwd=unrelated, home=home)
                    self.assertEqual(verified.returncode, 0, verified.stderr)
                    self.assertIn("VERIFIED: installed Dravux", verified.stdout)
                    self.assertEqual(before, tree_digest(destination), "verification must be read-only")

    def test_existing_destinations_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            cases = ("file", "directory", "symlink", "broken-symlink")
            for kind in cases:
                with self.subTest(kind=kind):
                    project = base / kind
                    project.mkdir()
                    destination = project / ".claude/skills/dravux"
                    destination.parent.mkdir(parents=True)
                    if kind == "file":
                        destination.write_text("keep", encoding="utf-8")
                    elif kind == "directory":
                        destination.mkdir()
                        (destination / "keep.txt").write_text("keep", encoding="utf-8")
                    elif kind == "symlink":
                        target = project / "target"
                        target.mkdir()
                        destination.symlink_to(target, target_is_directory=True)
                    else:
                        destination.symlink_to(project / "missing", target_is_directory=True)
                    marker = os.readlink(destination) if destination.is_symlink() else (
                        destination.read_text(encoding="utf-8") if destination.is_file() else tree_digest(destination)
                    )
                    result = self.run_script("install.sh", "--claude", "--project-dir", project)
                    self.assertEqual(result.returncode, 4, result.stderr)
                    current = os.readlink(destination) if destination.is_symlink() else (
                        destination.read_text(encoding="utf-8") if destination.is_file() else tree_digest(destination)
                    )
                    self.assertEqual(marker, current)

    def test_second_install_refuses_and_preserves_first_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            args = ("--codex", "--project-dir", project)
            first = self.run_script("install.sh", *args)
            self.assertEqual(first.returncode, 0, first.stderr)
            destination = project / ".agents/skills/dravux"
            before = tree_digest(destination)
            second = self.run_script("install.sh", *args)
            self.assertEqual(second.returncode, 4, second.stderr)
            self.assertEqual(before, tree_digest(destination))

    def test_invalid_scope_preflight_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            missing = base / "missing"
            result = self.run_script("install.sh", "--claude", "--project-dir", missing)
            self.assertEqual(result.returncode, 3)
            self.assertFalse(missing.exists())

            for home in ("", "relative-home", "/"):
                with self.subTest(home=home):
                    result = self.run_script("install.sh", "--codex", "--personal", home=home)
                    self.assertEqual(result.returncode, 3)

    def test_verifier_rejects_tampered_and_extra_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            args = ("--claude", "--project-dir", project)
            self.assertEqual(self.run_script("install.sh", *args).returncode, 0)
            destination = project / ".claude/skills/dravux"
            (destination / "SKILL.md").write_text("tampered", encoding="utf-8")
            tampered = self.run_script("verify-install.sh", *args)
            self.assertEqual(tampered.returncode, 5)

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            args = ("--codex", "--project-dir", project)
            self.assertEqual(self.run_script("install.sh", *args).returncode, 0)
            destination = project / ".agents/skills/dravux"
            (destination / "unexpected.txt").write_text("extra", encoding="utf-8")
            extra = self.run_script("verify-install.sh", *args)
            self.assertEqual(extra.returncode, 5)

    def test_release_scripts_are_executable_but_work_through_sh(self):
        for name in ("install.sh", "verify-install.sh", "verify-release.sh"):
            self.assertTrue(os.access(ROOT / name, os.X_OK), name)

    def test_release_verifier_detects_manifest_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            copied = Path(tmp) / f"Dravux-{VERSION}"
            subprocess.run(["cp", "-R", str(ROOT), str(copied)], check=True)
            readme = copied / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            proc = subprocess.run(
                ["python3", "-B", str(copied / "scripts" / "verify_distribution.py")],
                cwd=copied,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("release manifest hash mismatch: README.md", proc.stdout + proc.stderr)

    def test_builder_creates_deterministic_engineering_and_surface_archives(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            outputs = []
            for destination in (Path(first), Path(second)):
                proc = subprocess.run(
                    [sys.executable, "-B", str(SCRIPTS / "build_release.py"), "--output-dir", str(destination)],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                outputs.append(destination)

            expected = (
                f"Dravux-{VERSION}.zip",
                "dravux.zip",
                "Dravux-OpenAI-Plugin-Source.zip",
                "SHA256SUMS.txt",
            )
            for name in expected:
                self.assertEqual((outputs[0] / name).read_bytes(), (outputs[1] / name).read_bytes(), name)

            checksum_lines = (outputs[0] / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(checksum_lines), 3)

            with zipfile.ZipFile(outputs[0] / f"Dravux-{VERSION}.zip") as archive:
                names = archive.namelist()
                self.assertTrue(all(name.startswith(f"Dravux-{VERSION}/") for name in names))
            with zipfile.ZipFile(outputs[0] / "dravux.zip") as archive:
                names = archive.namelist()
                self.assertIn("dravux/SKILL.md", names)
                self.assertIn("dravux/fixtures/passing/known-pass.json", names)
                self.assertIn("dravux/fixtures/hostile/unknown-property.invalid.json", names)
                self.assertTrue(all(name.startswith("dravux/") for name in names))
            with zipfile.ZipFile(outputs[0] / "Dravux-OpenAI-Plugin-Source.zip") as archive:
                names = archive.namelist()
                self.assertIn("Dravux-OpenAI-Plugin-Source/.agents/plugins/marketplace.json", names)
                self.assertIn("Dravux-OpenAI-Plugin-Source/plugins/dravux/.codex-plugin/plugin.json", names)

            for archive_path in outputs[0].glob("*.zip"):
                with zipfile.ZipFile(archive_path) as archive:
                    for name in archive.namelist():
                        parts = Path(name).parts
                        self.assertNotIn("..", parts)
                        self.assertNotIn(".DS_Store", parts)
                        self.assertNotIn("__MACOSX", parts)

    def test_version_surfaces_match_version_file(self):
        manifest = json.loads((ROOT / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
        claude = json.loads((ROOT / "plugins/dravux/.claude-plugin/plugin.json").read_text(encoding="utf-8"))
        codex = json.loads((ROOT / "plugins/dravux/.codex-plugin/plugin.json").read_text(encoding="utf-8"))
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["package_version"], VERSION)
        self.assertEqual(manifest["archive_root"], f"Dravux-{VERSION}")
        self.assertEqual(claude["version"], VERSION)
        self.assertEqual(codex["version"], VERSION)
        self.assertEqual(marketplace["plugins"][0]["version"], VERSION)


if __name__ == "__main__":
    unittest.main()
