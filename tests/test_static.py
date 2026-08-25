import unittest
from pathlib import Path

import yaml

import hamd_syslog


ROOT = Path(__file__).parents[1]


class StaticInterfaceTests(unittest.TestCase):
    def test_patch_versions_are_consistent(self):
        config = yaml.safe_load((ROOT / "hamd_syslog/config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["version"], "0.1.2")
        self.assertEqual(hamd_syslog.__version__, config["version"])
        self.assertEqual(config["name"], "IoT Syslog")
        self.assertEqual(config["panel_title"], "IoT Syslog")

    def test_event_table_auto_refreshes_without_resetting_query_or_offset(self):
        script = (ROOT / "hamd_syslog/rootfs/app/static/app.js").read_text(encoding="utf-8")
        self.assertIn("EVENT_REFRESH_INTERVAL_MS = 5000", script)
        self.assertIn("window.setInterval(refreshVisibleEvents, EVENT_REFRESH_INTERVAL_MS)", script)
        self.assertIn('document.addEventListener("visibilitychange", refreshVisibleEvents)', script)
        refresh_function = script.split("function refreshVisibleEvents()", 1)[1].split("}\n", 1)[0]
        self.assertIn("loadEvents()", refresh_function)
        self.assertNotIn("state.query =", refresh_function)
        self.assertNotIn("state.offset =", refresh_function)

    def test_stale_event_responses_are_ignored(self):
        script = (ROOT / "hamd_syslog/rootfs/app/static/app.js").read_text(encoding="utf-8")
        self.assertIn("const requestSequence = ++eventRequestSequence", script)
        self.assertGreaterEqual(script.count("requestSequence !== eventRequestSequence"), 2)


if __name__ == "__main__":
    unittest.main()
