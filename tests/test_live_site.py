import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "demos" / "live-site"


class LiveSiteKitTests(unittest.TestCase):
    def test_public_live_site_kit_contains_only_generic_templates(self):
        required = {
            "README.md",
            "acquisition-evidence-template.md",
            "offline-fallback.md",
            "runbook-3-5-minutes.md",
        }
        self.assertEqual({path.name for path in LIVE.iterdir()}, required)
        self.assertFalse((LIVE / "preflight").exists())

    def test_live_site_kit_states_bounded_accepted_lower_mode_behavior(self):
        text = "\n".join(path.read_text(encoding="utf-8") for path in LIVE.glob("*.md"))
        self.assertIn("LIMITATION_ACK_REQUIRED", text)
        self.assertIn("explicit acceptance", text)
        self.assertIn("operational validator", text)
        self.assertIn("do not log in", text.lower())
        self.assertIn("INCOMPLETE", text)
        self.assertIn("manual", text.lower())

    def test_live_site_kit_has_no_recorded_session_metadata(self):
        for path in LIVE.glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"\b20\d{2}-\d{2}-\d{2}\b", f"dated session metadata in {path.name}")
            self.assertNotIn("recorded session", text.lower(), f"session metadata in {path.name}")


if __name__ == "__main__":
    unittest.main()
