import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class Release103Tests(unittest.TestCase):
    def test_release_metadata_and_deferred_work(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "1.0.3")
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["version"], version)
        self.assertEqual(package["repository"], {
            "type": "git", "url": "git+https://github.com/chaddidit/Dravux.git"
        })
        self.assertIn("SECURITY.md", package["files"])
        for name in (".claude-plugin/marketplace.json", "plugins/dravux/.claude-plugin/plugin.json", "plugins/dravux/.codex-plugin/plugin.json"):
            manifest = json.loads((ROOT / name).read_text(encoding="utf-8"))
            if "plugins" in manifest:
                self.assertEqual(manifest["metadata"]["version"], version)
                self.assertEqual(manifest["plugins"][0]["version"], version)
            else:
                self.assertEqual(manifest["version"], version)
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        release = changelog.split("## 1.0.3 — 2026-11-02\n", 1)[1].split("## 1.0.2", 1)[0]
        self.assertIn("npx launcher", release)
        self.assertIn("### Security hardening", release)
        tracked = (ROOT / "docs/tracked-work.md").read_text(encoding="utf-8").split("## Deferred to 1.0.4", 1)[1].split("## Next", 1)[0]
        for item in ("setuid", "ownership", "0775", "glibc 2.28", "preflight errors", "DNS names", "internal IPs"):
            self.assertIn(item, tracked)


if __name__ == "__main__":
    unittest.main()
