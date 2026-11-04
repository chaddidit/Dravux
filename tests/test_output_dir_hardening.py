import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugins" / "dravux" / "skills" / "dravux" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import dravux_run  # noqa: E402


class OutputDirectoryHardeningTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Path(temporary.name).resolve()
        self.root = self.workspace / "dravux-audits"
        self.child = self.root / "audit-001"

    def assert_refused(self, result):
        self.assertEqual(result["status"], "REFUSED", result)
        self.assertEqual(result["exit_code"], dravux_run.OUTPUT_DIR_REFUSED_EXIT)
        self.assertFalse(result["created"])

    def patch_os_function(self, name, side_effect):
        patched = self.enter_patch(mock.patch.object(os, name, side_effect=side_effect))
        self.enter_patch(mock.patch.object(os, "supports_dir_fd", os.supports_dir_fd | {patched}))
        return patched

    def enter_patch(self, patcher):
        patched = patcher.start()
        self.addCleanup(patcher.stop)
        return patched

    def test_raw_base_controls_are_rejected_before_resolution(self):
        for character in ("\n", "\t", "\x00", "\u0085", "\u202e", "\ud800", "\u2028", "\u2029"):
            with self.subTest(character=repr(character)):
                raw = str(self.workspace / ("bad" + character) / "..")
                with mock.patch.object(Path, "resolve", side_effect=AssertionError("raw path was resolved")):
                    result = dravux_run.resolve_output_dir(raw, "audit-001")
                self.assertEqual(result["status"], "INVALID")
                self.assertEqual(result["exit_code"], 2)
                self.assertIsNone(result["output_dir"])
        self.assertFalse(self.root.exists())

    def test_cli_rejects_control_component_removed_by_dot_dot(self):
        raw = str(self.workspace / "bad\n" / "..")
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / "dravux_run.py"), "output-dir", "--base", raw],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertIn("line break", proc.stderr)
        self.assertFalse(self.root.exists())

    def test_resolved_base_is_still_checked(self):
        destination = self.workspace / "bad\u202e"
        destination.mkdir()
        alias = self.workspace / "alias"
        alias.symlink_to(destination, target_is_directory=True)
        result = dravux_run.resolve_output_dir(alias, "audit-001")
        self.assertEqual(result["status"], "INVALID")
        self.assertEqual(list(destination.iterdir()), [])

    def test_path_format_characters_allow_joiners_and_name_first_refused_codepoint(self):
        for character in ("\u200d", "\u200c", "\u00ad"):
            with self.subTest(allowed=repr(character)):
                base = self.workspace / ("allowed" + character)
                base.mkdir()
                result = dravux_run.resolve_output_dir(base, "audit-001")
                self.assertEqual(result["status"], "CREATED", result)
                self.assertEqual(result["exit_code"], 0)
                self.assertEqual(result["output_dir"], str(base / "dravux-audits" / "audit-001"))
                self.assertTrue(Path(result["output_dir"]).is_dir())
        for characters in ("\n", "\u202e", "\ufeff", "\n\u202e\ud800", "\u202e\n"):
            with self.subTest(refused=repr(characters)):
                base = self.workspace / ("refused" + characters)
                result = dravux_run.resolve_output_dir(base, "audit-001")
                self.assertEqual(result["status"], "INVALID", result)
                self.assertEqual(result["exit_code"], 2)
                self.assertIn(f"contains U+{ord(characters[0]):04X}", result["message"])
                self.assertEqual(result["message"].count("U+"), 1)
                self.assertIsNone(result["output_dir"])
                self.assertFalse(result["created"])

    def test_ancestor_renamed_to_forge_receipt_is_refused_and_cleaned_up(self):
        base = self.workspace / "base"
        base.mkdir()
        moved = self.workspace / "base\nDRAVUX RUN RECEIPT: forged"
        real_resolve = Path.resolve

        def rename_ancestor(path, *args, **kwargs):
            if path == base / "dravux-audits" and not moved.exists():
                base.rename(moved)
                base.symlink_to(moved, target_is_directory=True)
            return real_resolve(path, *args, **kwargs)

        with mock.patch.object(Path, "resolve", autospec=True, side_effect=rename_ancestor):
            result = dravux_run.resolve_output_dir(base, "run1")
        self.assert_refused(result)
        self.assertIn("line break", result["message"])
        self.assertTrue(result["message"].endswith("Nothing was created."))
        self.assertEqual(list(moved.iterdir()), [])
        self.assertFalse((base / "dravux-audits").exists())

    def test_non_utf8_base_has_an_encoding_diagnostic(self):
        raw = str(self.workspace) + "/bad\udcff"
        result = dravux_run.resolve_output_dir(raw, "audit-001")
        self.assertEqual(result["status"], "INVALID")
        self.assertIn("not valid UTF-8", result["message"])
        self.assertNotIn("text-direction", result["message"])
        self.assertFalse(self.root.exists())

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux byte-valued folder names")
    def test_linux_non_utf8_folder_is_refused_by_cli(self):
        raw = os.fsencode(self.workspace) + b"/bad\xff"
        os.mkdir(raw)
        proc = subprocess.run(
            [os.fsencode(sys.executable), b"-B", os.fsencode(SCRIPTS / "dravux_run.py"),
             b"output-dir", b"--base", raw],
            capture_output=True, check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn(b"not valid UTF-8", proc.stderr)
        self.assertEqual(os.listdir(raw), [])

    def test_child_is_opened_relative_to_root_without_following_symlinks(self):
        real_open = os.open
        child_opens = []

        def observe(path, flags, *args, **kwargs):
            if kwargs.get("dir_fd") is not None:
                self.assertIn(path, ("dravux-audits", "audit-001"))
                self.assertEqual(flags & os.O_NOFOLLOW, os.O_NOFOLLOW)
                self.assertEqual(flags & os.O_DIRECTORY, os.O_DIRECTORY)
                if path == "audit-001":
                    child_opens.append(kwargs["dir_fd"])
            return real_open(path, flags, *args, **kwargs)

        self.patch_os_function("open", observe)
        result = dravux_run.resolve_output_dir(self.workspace, "audit-001")
        self.assertEqual(result["status"], "CREATED", result)
        self.assertEqual(len(child_opens), 1)

    def test_missing_relative_open_support_refuses_before_creation(self):
        with mock.patch.object(os, "supports_dir_fd", os.supports_dir_fd - {os.open}):
            result = dravux_run.resolve_output_dir(self.workspace, "audit-001")
        self.assert_refused(result)
        self.assertFalse(self.root.exists())

    def test_missing_directory_or_nofollow_flags_refuses_before_creation(self):
        for flag in ("O_DIRECTORY", "O_NOFOLLOW"):
            with self.subTest(flag=flag):
                with mock.patch.object(os, flag, 0):
                    result = dravux_run.resolve_output_dir(self.workspace, "audit-001")
                self.assert_refused(result)
                self.assertFalse(self.root.exists())

    def test_child_replaced_between_creation_stat_and_open_is_refused(self):
        self.root.mkdir()
        real_open = os.open

        def replace_child(path, flags, *args, **kwargs):
            if path == "audit-001" and kwargs.get("dir_fd") is not None:
                self.child.rename(self.root / "original-child")
                self.child.mkdir()
            return real_open(path, flags, *args, **kwargs)

        self.patch_os_function("open", replace_child)
        result = dravux_run.resolve_output_dir(self.workspace, "audit-001")
        self.assert_refused(result)
        self.assertTrue(self.child.is_dir())
        self.assertTrue((self.root / "original-child").is_dir())
        self.assertNotIn("Nothing was created.", result["message"])

    def test_symlink_substituted_before_child_open_is_preserved_on_refusal(self):
        self.root.mkdir()
        guarded = self.workspace / "guarded"
        guarded.mkdir()
        (guarded / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        real_open = os.open

        def replace_child(path, flags, *args, **kwargs):
            if path == "audit-001" and kwargs.get("dir_fd") is not None:
                self.child.rename(self.root / "original-child")
                self.child.symlink_to(guarded, target_is_directory=True)
            return real_open(path, flags, *args, **kwargs)

        self.patch_os_function("open", replace_child)
        result = dravux_run.resolve_output_dir(self.workspace, "audit-001")
        self.assert_refused(result)
        self.assertTrue(self.child.is_symlink())
        self.assertEqual([p.name for p in guarded.iterdir()], ["SKILL.md"])

    def test_child_kernel_location_is_checked_after_it_moves_into_guarded_tree(self):
        self.root.mkdir()
        guarded = self.workspace / "guarded"
        guarded.mkdir()
        (guarded / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        descriptor_path = dravux_run._descriptor_path

        def move_child(descriptor):
            held = descriptor_path(descriptor)
            if held == self.child:
                self.child.rename(guarded / "moved-child")
                self.child.mkdir()
            return descriptor_path(descriptor)

        with mock.patch.object(dravux_run, "_descriptor_path", side_effect=move_child):
            result = dravux_run.resolve_output_dir(self.workspace, "audit-001")
        self.assert_refused(result)
        self.assertIn("guarded Dravux files", result["message"])
        self.assertTrue(self.child.is_dir())
        self.assertTrue((guarded / "moved-child").is_dir())

    def test_refusal_cleanup_does_not_remove_a_replacement_child(self):
        self.root.mkdir()
        guarded = self.workspace / "guarded"
        guarded.mkdir()
        (guarded / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        moved_root = guarded / "moved-root"
        descriptor_path = dravux_run._descriptor_path

        def move_root(descriptor):
            if not moved_root.exists():
                self.root.rename(moved_root)
                (moved_root / "audit-001").rename(moved_root / "original-child")
                (moved_root / "audit-001").mkdir()
                self.root.mkdir()
            return descriptor_path(descriptor)

        with mock.patch.object(dravux_run, "_descriptor_path", side_effect=move_root):
            result = dravux_run.resolve_output_dir(self.workspace, "audit-001")
        self.assert_refused(result)
        self.assertTrue((moved_root / "audit-001").is_dir())
        self.assertTrue((moved_root / "original-child").is_dir())
        self.assertNotIn("Nothing was created.", result["message"])

    @unittest.skipUnless(sys.platform == "darwin", "macOS F_GETPATH fallback")
    def test_macos_output_directory_succeeds_without_f_getpath_constant(self):
        import fcntl

        with mock.patch.dict(fcntl.__dict__):
            fcntl.__dict__.pop("F_GETPATH", None)
            result = dravux_run.resolve_output_dir(self.workspace, "audit-001")
        self.assertEqual(result["status"], "CREATED", result)
        self.assertEqual(result["output_dir"], str(self.child))
        self.assertTrue(self.child.is_dir())

    def test_missing_kernel_location_refuses_and_removes_new_root_and_child(self):
        for audit_id in (None, "audit-001"):
            with self.subTest(audit_id=audit_id):
                with mock.patch.object(dravux_run, "_descriptor_path", return_value=None):
                    result = dravux_run.resolve_output_dir(self.workspace, audit_id)
                self.assert_refused(result)
                self.assertIn("kernel", result["message"])
                self.assertFalse(self.root.exists())

    def test_missing_child_kernel_location_refuses_and_cleans_up(self):
        descriptor_path = dravux_run._descriptor_path

        def unavailable_child(descriptor):
            held = descriptor_path(descriptor)
            return None if held == self.child else held

        with mock.patch.object(dravux_run, "_descriptor_path", side_effect=unavailable_child):
            result = dravux_run.resolve_output_dir(self.workspace, "audit-001")
        self.assert_refused(result)
        self.assertIn("kernel", result["message"])
        self.assertFalse(self.root.exists())

    def test_new_root_is_removed_when_its_open_fails(self):
        open_directory = dravux_run._open_stable_directory

        def refuse_root(path, dir_fd=None):
            if str(path) == "dravux-audits":
                raise PermissionError("refused")
            return open_directory(path, dir_fd)

        with mock.patch.object(dravux_run, "_open_stable_directory", side_effect=refuse_root):
            result = dravux_run.resolve_output_dir(self.workspace, "audit-001")
        self.assert_refused(result)
        self.assertFalse(self.root.exists())

    def test_new_root_replaced_before_open_is_refused_and_preserved(self):
        open_directory = dravux_run._open_stable_directory

        def replace_root(path, dir_fd=None):
            if str(path) == "dravux-audits":
                self.root.rename(self.workspace / "original-root")
                self.root.mkdir()
            return open_directory(path, dir_fd)

        with mock.patch.object(dravux_run, "_open_stable_directory", side_effect=replace_root):
            result = dravux_run.resolve_output_dir(self.workspace, None)
        self.assert_refused(result)
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertTrue((self.workspace / "original-root").is_dir())
        self.assertNotIn("Nothing was created.", result["message"])

    def test_preexisting_root_survives_refusal(self):
        self.root.mkdir()
        with mock.patch.object(dravux_run, "_descriptor_path", return_value=None):
            result = dravux_run.resolve_output_dir(self.workspace, "audit-001")
        self.assert_refused(result)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_root_cleanup_preserves_a_replacement_inode(self):
        def replace_root(*args):
            self.root.rename(self.workspace / "original-root")
            self.root.mkdir()
            return None, "Refused. Nothing was created."

        with mock.patch.object(dravux_run, "_check_output_target", side_effect=replace_root):
            result = dravux_run.resolve_output_dir(self.workspace, None)
        self.assert_refused(result)
        self.assertTrue(self.root.is_dir())
        self.assertTrue((self.workspace / "original-root").is_dir())
        self.assertNotIn("Nothing was created.", result["message"])

    def test_root_cleanup_preserves_concurrently_added_contents(self):
        def add_file(*args):
            (self.root / "other-writer.txt").write_text("keep", encoding="utf-8")
            return None, "Refused. Nothing was created."

        with mock.patch.object(dravux_run, "_check_output_target", side_effect=add_file):
            result = dravux_run.resolve_output_dir(self.workspace, None)
        self.assert_refused(result)
        self.assertEqual((self.root / "other-writer.txt").read_text(encoding="utf-8"), "keep")
        self.assertNotIn("Nothing was created.", result["message"])

    def test_root_cleanup_cannot_follow_a_swapped_base_to_another_directory(self):
        base = self.workspace / "base"
        base.mkdir()
        moved = self.workspace / "original-base"
        other = self.workspace / "other"
        other_root = other / "dravux-audits"
        other_root.mkdir(parents=True)
        real_stat = os.stat
        cleanup = False
        swapped = False

        def unavailable_location(descriptor):
            nonlocal cleanup
            cleanup = True
            return None

        def swap_after_stat(path, *args, **kwargs):
            nonlocal swapped
            current = real_stat(path, *args, **kwargs)
            if cleanup and not swapped and str(path) in ("dravux-audits", str(base / "dravux-audits")):
                base.rename(moved)
                base.symlink_to(other, target_is_directory=True)
                swapped = True
            return current

        self.patch_os_function("stat", swap_after_stat)
        with mock.patch.object(dravux_run, "_descriptor_path", side_effect=unavailable_location):
            result = dravux_run.resolve_output_dir(base)
        self.assert_refused(result)
        self.assertTrue(swapped)
        self.assertTrue(other_root.is_dir(), "cleanup removed the other writer's directory")
        self.assertEqual(list(other_root.iterdir()), [])
        self.assertFalse((moved / "dravux-audits").exists())

    def test_refusal_quotes_home_with_newline_and_bidi_characters(self):
        from contextlib import redirect_stderr
        from io import StringIO

        guarded = self.workspace / "guarded"
        guarded.mkdir()
        (guarded / "SKILL.md").write_text("# skill\n", encoding="utf-8")
        hostile_home = self.workspace / "home\nDRAVUX RUN RECEIPT: forged\u202e"
        hostile_home.mkdir()
        with mock.patch.dict(os.environ, {"HOME": str(hostile_home)}):
            result = dravux_run.resolve_output_dir(guarded, strict=True)
        self.assert_refused(result)
        self.assertNotIn("\n", result["message"])
        self.assertNotIn("\u202e", result["message"])
        self.assertIn(r"\n", result["message"])
        self.assertIn(r"\u202e", result["message"])
        stderr = StringIO()
        with redirect_stderr(stderr):
            dravux_run._print_output_dir(result, False)
        self.assertEqual(stderr.getvalue().splitlines(), [result["message"]])
        self.assertEqual([p.name for p in guarded.iterdir()], ["SKILL.md"])

    def test_package_version_is_1_0_3(self):
        self.assertEqual(dravux_run.PACKAGE_VERSION, "1.0.4")


if __name__ == "__main__":
    unittest.main()
