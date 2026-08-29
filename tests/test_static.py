import unittest
from pathlib import Path

import yaml

import iot_syslog


ROOT = Path(__file__).parents[1]


class StaticInterfaceTests(unittest.TestCase):
    def test_patch_versions_are_consistent(self):
        config = yaml.safe_load((ROOT / "iot_syslog/config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["version"], "0.2.0")
        self.assertEqual(iot_syslog.__version__, config["version"])
        self.assertEqual(config["name"], "IoT Syslog")
        self.assertEqual(config["panel_title"], "IoT Syslog")

    def test_interface_uses_shared_iot_brand_shell(self):
        page = (ROOT / "iot_syslog/rootfs/app/static/index.html").read_text(encoding="utf-8")
        self.assertIn('<header class="topbar">', page)
        self.assertIn('<span class="brand-mark">SL</span><span>IoT Syslog</span>', page)
        self.assertIn('<nav aria-label="Primary">', page)
        self.assertIn('data-page-link="overview"', page)
        self.assertIn('data-page-link="events"', page)
        self.assertIn('data-page-link="settings"', page)
        self.assertIn('data-page="overview"', page)
        self.assertIn('data-page="events"', page)
        self.assertIn('data-page="settings"', page)

    def test_event_table_auto_refreshes_without_resetting_query_or_offset(self):
        script = (ROOT / "iot_syslog/rootfs/app/static/app.js").read_text(encoding="utf-8")
        self.assertIn("EVENT_REFRESH_INTERVAL_MS = 5000", script)
        self.assertIn("window.setInterval(refreshVisibleEvents, EVENT_REFRESH_INTERVAL_MS)", script)
        self.assertIn('document.addEventListener("visibilitychange", refreshVisibleEvents)', script)
        refresh_function = script.split("function refreshVisibleEvents()", 1)[1].split("}\n", 1)[0]
        self.assertIn("loadEvents()", refresh_function)
        self.assertNotIn("state.query =", refresh_function)
        self.assertNotIn("state.offset =", refresh_function)

    def test_stale_event_responses_are_ignored(self):
        script = (ROOT / "iot_syslog/rootfs/app/static/app.js").read_text(encoding="utf-8")
        self.assertIn("const requestSequence = ++eventRequestSequence", script)
        self.assertGreaterEqual(script.count("requestSequence !== eventRequestSequence"), 2)


if __name__ == "__main__":
    unittest.main()
