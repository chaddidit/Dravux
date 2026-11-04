import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/dravux/skills/dravux"
LEGAL_FILES = ("LICENSE", "THIRD_PARTY_NOTICES.md")
sys.path.insert(0, str(ROOT / "scripts"))
import build_release
import verify_distribution


class Packaging104Tests(unittest.TestCase):
    def test_skill_legal_files_are_byte_identical_to_root(self):
        for name in LEGAL_FILES:
            with self.subTest(name=name):
                self.assertEqual((SKILL / name).read_bytes(), (ROOT / name).read_bytes())

    def test_inventory_declares_all_104_additions(self):
        expected = {
            "plugins/dravux/skills/dravux/LICENSE",
            "plugins/dravux/skills/dravux/THIRD_PARTY_NOTICES.md",
            "tests/test_installer_104.py",
            "tests/test_validator_104.py",
            "tests/test_packaging_104.py",
            "docs/install.md",
            "docs/troubleshooting.md",
            "docs/cli-reference.md",
        }
        self.assertTrue(expected.issubset(build_release.SHIPPED_FILES),
                        sorted(expected - set(build_release.SHIPPED_FILES)))
        self.assertEqual(verify_distribution.SHIPPED_FILES, build_release.SHIPPED_FILES)

    def test_surface_archives_include_skill_legal_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            claude = base / "dravux.zip"
            openai = base / "Dravux-OpenAI-Plugin-Source.zip"
            build_release.build_zip(claude, "dravux", build_release.subtree_files(SKILL), SKILL)
            build_release.build_openai_source(openai)
            for archive_path, prefixes in (
                (claude, ("dravux/",)),
                (openai, ("Dravux-OpenAI-Plugin-Source/plugins/dravux/",
                          "Dravux-OpenAI-Plugin-Source/plugins/dravux/skills/dravux/")),
            ):
                with zipfile.ZipFile(archive_path) as archive:
                    for prefix in prefixes:
                        for name in LEGAL_FILES:
                            with self.subTest(archive=archive_path.name, member=prefix + name):
                                self.assertEqual(archive.read(prefix + name), (ROOT / name).read_bytes())

    def test_project_install_includes_legal_files(self):
        with tempfile.TemporaryDirectory(prefix="dravux packaging ") as tmp:
            base = Path(tmp)
            home = base / "home"
            home.mkdir()
            env = dict(os.environ, HOME=str(home), PYTHONDONTWRITEBYTECODE="1",
                       DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
            for platform, folder in (("--claude", ".claude"), ("--codex", ".agents")):
                with self.subTest(platform=platform):
                    installed = subprocess.run(
                        ["sh", str(ROOT / "install.sh"), platform, "--project-dir", str(base)],
                        cwd=home, env=env, capture_output=True, text=True,
                    )
                    self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
                    for name in LEGAL_FILES:
                        self.assertEqual((base / folder / "skills/dravux" / name).read_bytes(),
                                         (ROOT / name).read_bytes())

    @unittest.skipUnless(shutil.which("npm"), "npm is required for the offline package inventory")
    def test_npm_dry_run_matches_allow_list_and_includes_skill_legal_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            packed = subprocess.run(
                ["npm", "pack", "--dry-run", "--json", "--ignore-scripts", "--offline", "--cache", tmp],
                cwd=ROOT, env=dict(os.environ, DISABLE_TELEMETRY="1", DO_NOT_TRACK="1"),
                capture_output=True, text=True,
            )
        self.assertEqual(packed.returncode, 0, packed.stdout + packed.stderr)
        package = json.loads(packed.stdout)[0]
        actual = {item["path"] for item in package["files"]}
        manifest = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        expected = {"package.json", "README.md", "LICENSE"}
        for entry in manifest["files"]:
            path = ROOT / entry
            if path.is_dir():
                expected.update(item.relative_to(ROOT).as_posix() for item in path.rglob("*")
                                if item.is_file())
            else:
                expected.add(entry)
        self.assertEqual(actual, expected)
        for name in LEGAL_FILES:
            self.assertIn("plugins/dravux/skills/dravux/" + name, actual)
        self.assertEqual(package["entryCount"], 34)
        self.assertEqual(len(actual), package["entryCount"])


if __name__ == "__main__":
    unittest.main()
