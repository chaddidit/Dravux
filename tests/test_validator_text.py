import copy
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins" / "dravux" / "skills" / "dravux"
sys.path.insert(0, str(SKILL / "scripts"))

from dravux_contract import _is_nonempty_string, strict_json_load, validate_report  # noqa: E402
from dravux_run import validate_preflight, validate_run  # noqa: E402


class ValidatorTextTests(unittest.TestCase):
    def test_nonvisible_unicode_categories_do_not_fill_a_string(self):
        # Zs, Zl, Zp, Cc, Cf, Cs, Co, Cn, Mn, Mc, Me respectively.
        for text in ("\u00a0", "\u2028", "\u2029", "\u009b", "\u200b", "\ud800",
                     "\ue000", "\u0378", "\u0301", "\u0903", "\u20dd"):
            with self.subTest(text=ascii(text)):
                self.assertFalse(_is_nonempty_string(text))

    def test_all_specified_ignorable_and_blank_codepoints_do_not_fill_a_string(self):
        codepoints = (
            [0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x2800, 0x3164, 0xFFA0]
            + list(range(0x180B, 0x1810))
            + list(range(0xFE00, 0xFE10))
            + list(range(0xE0100, 0xE01F0))
        )
        for codepoint in codepoints:
            with self.subTest(codepoint=hex(codepoint)):
                self.assertFalse(_is_nonempty_string(chr(codepoint)))

    def test_mixed_invisible_characters_do_not_fill_a_string(self):
        self.assertFalse(_is_nonempty_string(" \u0301\ue000\u0378\u200b\u2800\ufe0f"))

    def test_visible_bases_allow_marks_and_ignorable_characters(self):
        for text in ("e\u0301", "\u0301e", "\u0915\u0903", "x\u20dd", "\u2764\ufe0f",
                     "x\U000e0100", "a\u200b", "\u4e2d", "\U0001f600"):
            with self.subTest(text=ascii(text)):
                self.assertTrue(_is_nonempty_string(text))

    def test_surrogates_are_rejected_even_next_to_visible_text(self):
        for codepoint in (0xD800, 0xDBFF, 0xDC00, 0xDFFF):
            for text in (chr(codepoint), "visible" + chr(codepoint), chr(codepoint) + "visible"):
                with self.subTest(text=ascii(text)):
                    self.assertFalse(_is_nonempty_string(text))

    def test_report_fields_use_the_shared_text_policy(self):
        base = json.loads((SKILL / "assets" / "report-template.json").read_text(encoding="utf-8"))
        self.assertEqual(validate_report(base), [])
        for text in ("\u0301", "\ue000", "\u0378", "name\udfff"):
            with self.subTest(text=ascii(text)):
                report = copy.deepcopy(base)
                report["target"]["name"] = text
                self.assertIn("target.name must be a non-empty string", validate_report(report))
        base["target"]["name"] = "e\u0301"
        self.assertEqual(validate_report(base), [])

    def test_preflight_and_run_fields_use_the_shared_text_policy(self):
        preflight = json.loads((SKILL / "assets" / "preflight-template.json").read_text(encoding="utf-8"))
        run = json.loads((SKILL / "assets" / "run-envelope-template.json").read_text(encoding="utf-8"))
        for text in ("\u0301", "\ue000", "name\ud800"):
            with self.subTest(text=ascii(text)):
                preflight["surface"]["product"] = text
                self.assertIn("preflight.surface.product must be a non-empty string", validate_preflight(preflight))
                run["report"]["target"]["name"] = text
                self.assertIn("report: target.name must be a non-empty string", validate_run(run))

    def test_json_loader_rejects_surrogates_in_values_and_keys_at_any_depth(self):
        for text in ("\ud800", "value\udbff", "\udc00value", "value\udfff"):
            for value in (text, {"nested": [text]}, {text: "value"}, [{"nested": {text: 1}}]):
                with self.subTest(value=ascii(value)):
                    payload = json.dumps(value).encode("ascii")
                    with self.assertRaisesRegex(ValueError, "surrogate"):
                        strict_json_load(io.BytesIO(payload))

    def test_json_loader_accepts_valid_supplementary_characters_and_surrogate_pairs(self):
        expected = {"\U0001f600": "e\u0301\U0001f600"}
        for ensure_ascii in (True, False):
            with self.subTest(ensure_ascii=ensure_ascii):
                payload = json.dumps(expected, ensure_ascii=ensure_ascii).encode("utf-8")
                self.assertEqual(strict_json_load(io.BytesIO(payload)), expected)

    def test_contract_clis_refuse_surrogates_without_tracebacks(self):
        cases = (
            ("dravux_contract.py", ["-", "--json"], "report-template.json"),
            ("dravux_run.py", ["preflight", "-", "--json"], "preflight-template.json"),
            ("dravux_run.py", ["validate", "-", "--json"], "run-envelope-template.json"),
        )
        for script, arguments, template in cases:
            with self.subTest(script=script, arguments=arguments):
                value = json.loads((SKILL / "assets" / template).read_text(encoding="utf-8"))
                value["$schema"] = "schema\ud800"
                proc = subprocess.run(
                    [sys.executable, "-B", str(SKILL / "scripts" / script)] + arguments,
                    input=json.dumps(value), capture_output=True, text=True, check=False,
                )
                self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
                self.assertFalse(json.loads(proc.stdout)["valid"])
                self.assertIn("surrogate", proc.stdout)
                self.assertNotIn("Traceback", proc.stderr)


if __name__ == "__main__":
    unittest.main()
