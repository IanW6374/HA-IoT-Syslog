import unittest
from pathlib import Path

import yaml

import iot_syslog


ROOT = Path(__file__).parents[1]


class StaticInterfaceTests(unittest.TestCase):
    def test_form_controls_share_portal_alignment_and_height(self):
        css = (ROOT / 'iot_syslog/rootfs/app/static/styles.css').read_text()
        self.assertIn('align-content:start;grid-auto-rows:max-content', css)
        self.assertIn('height:42px;min-height:42px', css)
        self.assertIn('select:not([multiple]):not([size])', css)
        self.assertIn('.search-field input{height:42px;font-size:inherit}', css)

    def test_patch_versions_are_consistent(self):
        config = yaml.safe_load((ROOT / "iot_syslog/config.yaml").read_text(encoding="utf-8"))
        self.assertEqual(config["version"], "0.3.4")
        self.assertEqual(iot_syslog.__version__, config["version"])
        self.assertEqual(config["name"], "IoT Syslog")
        self.assertEqual(config["panel_title"], "IoT Syslog")

    def test_interface_uses_shared_iot_brand_shell(self):
        page = (ROOT / "iot_syslog/rootfs/app/static/index.html").read_text(encoding="utf-8")
        self.assertIn('<header class="topbar">', page)
        self.assertIn('<span class="brand-mark">IoT<br>SL</span><span>IoT Syslog</span>', page)
        self.assertEqual(page.count('class="status-card" href='), 4)
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

    def test_refresh_actions_update_content_in_place(self):
        page = (ROOT / "iot_syslog/rootfs/app/static/index.html").read_text(encoding="utf-8")
        script = (ROOT / "iot_syslog/rootfs/app/static/app.js").read_text(encoding="utf-8")
        self.assertEqual(page.count("data-summary-refresh"), 2)
        self.assertIn('id="refresh-events"', page)
        self.assertIn('id="filter-status" class="portal-status"', page)
        self.assertIn('document.querySelectorAll("[data-summary-refresh]")', script)
        self.assertIn('document.querySelector("#refresh-events").addEventListener', script)
        self.assertNotIn("window.location.reload", script)

    def test_hidden_event_page_is_not_polled(self):
        script = (ROOT / "iot_syslog/rootfs/app/static/app.js").read_text(encoding="utf-8")
        refresh_function = script.split("function refreshVisibleEvents()", 1)[1].split("}\n", 1)[0]
        self.assertIn('activePage === "events"', refresh_function)

    def test_filter_actions_use_consistent_bottom_action_bar(self):
        page = (ROOT / "iot_syslog/rootfs/app/static/index.html").read_text(encoding="utf-8")
        form = page.split('<form id="filters">', 1)[1].split("</form>", 1)[0]
        self.assertIn('<div class="actions">', form)
        self.assertIn('id="reset" class="button secondary"', form)
        self.assertLess(form.index('id="reset"'), form.index('id="search"'))

    def test_downloads_use_applied_filters_without_pagination_or_navigation(self):
        page = (ROOT / "iot_syslog/rootfs/app/static/index.html").read_text()
        script = (ROOT / "iot_syslog/rootfs/app/static/app.js").read_text()
        self.assertIn('Download filtered log</button>', page)
        self.assertIn('id="export-csv"', page)
        helper = script.split('function filteredDownloadURL(', 1)[1].split('\n}', 1)[0]
        self.assertIn('state.query', helper)
        self.assertIn('api/export.log', helper)
        self.assertNotIn('state.offset', helper)
        self.assertNotIn('PAGE_SIZE', helper)
        self.assertNotIn('window.location.assign', script)


if __name__ == "__main__":
    unittest.main()
