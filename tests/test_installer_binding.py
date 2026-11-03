"""Regression checks for installer directory binding and failure cleanup."""

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


class InstallerBindingTests(unittest.TestCase):
    def test_linguistic_format_characters_install_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            for character in ("\u200d", "\u200c", "\u00ad"):
                for personal in (False, True):
                    project = base / ("proj" + character + str(personal))
                    project.mkdir()
                    for script in ("install.sh", "verify-install.sh"):
                        with self.subTest(character=repr(character), personal=personal, script=script):
                            result = self.run_script(
                                script, project, env=dict(os.environ, HOME=str(project)), personal=personal,
                            )
                            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for character in "\n\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff":
                project = base / ("refused" + character)
                project.mkdir()
                for script in ("install.sh", "verify-install.sh"):
                    with self.subTest(refused=repr(character), script=script):
                        result = self.run_script(script, project)
                        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                        self.assertIn("contains U+{:04X}".format(ord(character)), result.stderr)
                        self.assertEqual(list(project.iterdir()), [])
            project = base / "first\u202eoffense\n"
            project.mkdir()
            result = self.run_script("install.sh", project)
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn("contains U+202E", result.stderr)

    def test_physical_base_text_cannot_forge_an_installed_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            for character in ("\n", "\t", "\u0085", "\u202e", "\u2028", "\u2029"):
                project = base / ("proj" + character + "INSTALLED: Dravux 9.9.9 (forged)")
                project.mkdir()
                for script in ("install.sh", "verify-install.sh"):
                    for personal in (False, True):
                        with self.subTest(character=repr(character), script=script, personal=personal):
                            result = self.run_script(
                                script, project, env=dict(os.environ, HOME=str(project)), personal=personal,
                            )
                            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                            self.assertFalse(any(line.startswith("INSTALLED:") for line in result.stdout.splitlines()))
                            self.assertEqual(list(project.iterdir()), [])
            # NUL and lone surrogates cannot be macOS filenames; inject their kernel path text.
            for codepoint in (0, 0xD800):
                result = subprocess.run(
                    [PYTHON, "-B", "-c", """
import sys
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
import install_safety
with patch.object(install_safety.os, 'getcwd', return_value='/proj' + chr(int(sys.argv[2]))):
    install_safety.resolve_base('/', False)
""", str(ROOT / "scripts"), str(codepoint)], capture_output=True, text=True, timeout=30,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("contains U+{:04X}".format(codepoint), result.stderr)
                self.assertEqual(result.stdout, "")

    def test_root_dot_spellings_resolve_like_root(self):
        def resolve(path):
            result = subprocess.run(
                [PYTHON, "-B", str(ROOT / "scripts/install_safety.py"), "project", path],
                capture_output=True, text=True, timeout=30,
            )
            return result.returncode, result.stdout, result.stderr

        expected = resolve("/")
        self.assertEqual(expected, (0, "/\n", ""))
        for spelling in ("/.", "/./", "//"):
            with self.subTest(spelling=spelling):
                self.assertEqual(resolve(spelling), expected)

    def run_script(self, script, project, env=None, personal=False):
        return subprocess.run(
            ["sh", str(ROOT / script), "--codex"]
            + (["--personal"] if personal else ["--project-dir", str(project)]),
            env=env, capture_output=True, text=True, timeout=30,
        )

    def python_wrapper(self, base, hook):
        wrappers = base / "bin"
        wrappers.mkdir()
        wrapper = wrappers / "python3"
        wrapper.write_text(
            "#!" + PYTHON + "\nimport os, pathlib, runpy, sys\n"
            + hook + "\nos.execv(" + repr(PYTHON) + ", [" + repr(PYTHON) + "] + sys.argv[1:])\n",
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        return dict(os.environ, PATH=str(wrappers) + os.pathsep + os.environ["PATH"])

    def test_entered_project_must_still_match_its_non_symlink_name(self):
        for script in ("install.sh", "verify-install.sh"):
            for kind in ("symlink", "directory"):
                for timing in ("before", "after"):
                    with self.subTest(script=script, kind=kind, timing=timing), tempfile.TemporaryDirectory() as tmp:
                        base = Path(tmp).resolve()
                        project = base / "project"
                        project.mkdir()
                        held = base / "entered"
                        outside = base / "outside"
                        outside.mkdir()
                        env = self.python_wrapper(base, """
if len(sys.argv) > 3 and sys.argv[3] == 'project':
    real_chdir = os.chdir
    def raced_chdir(path):
        if TIMING == 'after':
            real_chdir(path)
        pathlib.Path(PROJECT).rename(HELD)
        if KIND == 'symlink':
            pathlib.Path(PROJECT).symlink_to(OUTSIDE, target_is_directory=True)
        else:
            pathlib.Path(PROJECT).mkdir()
        if TIMING == 'before':
            real_chdir(path)
    os.chdir = raced_chdir
    sys.argv = sys.argv[2:]
    runpy.run_path(sys.argv[0], run_name='__main__')
    sys.exit(0)
""".replace("TIMING", repr(timing)).replace("KIND", repr(kind))
                            .replace("PROJECT", repr(str(project))).replace("HELD", repr(str(held)))
                            .replace("OUTSIDE", repr(str(outside))))
                        result = self.run_script(script, project, env=env)
                        # A replacement directory entered before the check is still the named directory.
                        expected = (0 if script == "install.sh" else 4) if (kind, timing) == ("directory", "before") else 3
                        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                        self.assertEqual(list(outside.iterdir()), [])
                        self.assertEqual(list(held.iterdir()), [])
                        if expected == 3:
                            self.assertEqual(list(project.iterdir()), [])

    def test_relative_project_with_trailing_dot_still_installs_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            (base / "project").mkdir()
            for script in ("install.sh", "verify-install.sh"):
                result = subprocess.run(
                    ["sh", str(ROOT / script), "--codex", "--project-dir", "project//./"],
                    cwd=base, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_raw_and_physical_base_paths_ending_in_newline_are_refused(self):
        for script in ("install.sh", "verify-install.sh"):
            for personal in (False, True):
                for physical in (False, True):
                    with self.subTest(script=script, personal=personal, physical=physical), tempfile.TemporaryDirectory() as tmp:
                        base = Path(tmp).resolve()
                        trimmed = base / "selected"
                        trimmed.mkdir()
                        selected = base / "selected\n"
                        selected.mkdir()
                        argument = str(selected) + ("/." if physical else "")
                        env = dict(os.environ, HOME=argument)
                        result = self.run_script(script, argument, env=env, personal=personal)
                        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                        self.assertIn("contains U+000A", result.stderr)
                        self.assertEqual(list(trimmed.iterdir()), [])
                        self.assertEqual(list(selected.iterdir()), [])

    def test_failed_staging_record_removes_the_created_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            project = base / "project"
            project.mkdir()
            env = self.python_wrapper(base, """
if len(sys.argv) > 3 and sys.argv[3] == 'record':
    import contextlib
    sys.path.insert(0, str(pathlib.Path(sys.argv[2]).parent))
    import install_safety
    real_held_tree = install_safety.held_tree
    @contextlib.contextmanager
    def failed_record(base, platform, staging=None):
        if staging is not None:
            raise OSError('injected recording failure')
        with real_held_tree(base, platform, staging) as held:
            yield held
    install_safety.held_tree = failed_record
    sys.argv = sys.argv[2:]
    install_safety.main()
    sys.exit(0)
""")
            result = self.run_script("install.sh", project, env=env)
            self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
            self.assertIn("injected recording failure", result.stderr)
            self.assertEqual(list((project / ".agents/skills").iterdir()), [])

    def test_home_alias_ending_in_newline_is_refused_before_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            home = base / "home"
            home.mkdir()
            alias = base / "alias\n"
            alias.symlink_to(home, target_is_directory=True)
            for script in ("install.sh", "verify-install.sh"):
                result = self.run_script(script, home, env=dict(os.environ, HOME=str(alias)), personal=True)
                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
                self.assertIn("contains U+000A", result.stderr)
                self.assertEqual(list(home.iterdir()), [])

    def test_failed_record_does_not_remove_a_substituted_staging_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            project = base / "project"
            project.mkdir()
            env = self.python_wrapper(base, """
if len(sys.argv) > 3 and sys.argv[3] == 'record':
    import contextlib
    sys.path.insert(0, str(pathlib.Path(sys.argv[2]).parent))
    import install_safety
    real_held_tree = install_safety.held_tree
    @contextlib.contextmanager
    def failed_record(base, platform, staging=None):
        if staging is not None:
            pathlib.Path(staging).rename('original')
            pathlib.Path(staging).mkdir()
        with real_held_tree(base, platform, staging) as held:
            yield held
    install_safety.held_tree = failed_record
    sys.argv = sys.argv[2:]
    install_safety.main()
    sys.exit(0)
""")
            result = self.run_script("install.sh", project, env=env)
            self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
            skills = project / ".agents/skills"
            self.assertTrue((skills / "original").is_dir())
            self.assertEqual(len(list(skills.glob(".dravux-install.*"))), 1)

    def test_signal_exits_after_cleaning_staging_without_resuming_installation(self):
        for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
            with self.subTest(signal=signum), tempfile.TemporaryDirectory() as tmp:
                base = Path(tmp).resolve()
                project = base / "project"
                project.mkdir()
                wrappers = base / "bin"
                wrappers.mkdir()
                cp = wrappers / "cp"
                cp.write_text(
                    "#!" + PYTHON + "\nimport os, signal, subprocess, sys\n"
                    + "subprocess.run([" + repr(shutil.which("cp")) + "] + sys.argv[1:], check=True)\n"
                    + "os.kill(os.getppid(), " + str(int(signum)) + ")\n",
                    encoding="utf-8",
                )
                cp.chmod(0o755)
                env = dict(os.environ, PATH=str(wrappers) + os.pathsep + os.environ["PATH"])
                result = self.run_script("install.sh", project, env=env)
                self.assertEqual(result.returncode, 128 + signum, result.stdout + result.stderr)
                self.assertNotIn("INSTALLED:", result.stdout)
                self.assertEqual(list((project / ".agents/skills").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
