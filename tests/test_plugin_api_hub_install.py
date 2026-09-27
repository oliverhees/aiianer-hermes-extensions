from __future__ import annotations

import importlib.util
import asyncio
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
API_PATH = REPO_ROOT / "dashboard" / "plugin_api.py"


def load_api_module():
    spec = importlib.util.spec_from_file_location("aiianer_plugin_api_test", API_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HubRootInstallTest(unittest.TestCase):
    def test_installs_root_hybrid_plugin_to_agent_and_desktop_targets(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded-repo"
            hermes_home = root / "hermes-home"
            (source / "dashboard" / "dist").mkdir(parents=True)
            (source / "desktop").mkdir()
            (source / "guard").mkdir()
            (source / "plugin.yaml").write_text("name: aiianer-hub\nversion: 9.9.9\n")
            (source / "__init__.py").write_text("def register(ctx): pass\n")
            (source / "catalog.json").write_text('{"components": []}\n')
            (source / "releases.json").write_text('{"releases": []}\n')
            (source / "guard_check.py").write_text("# guard\n")
            (source / "dashboard" / "manifest.json").write_text('{"name": "aiianer-hub"}\n')
            (source / "dashboard" / "plugin_api.py").write_text("# backend\n")
            (source / "dashboard" / "dist" / "index.js").write_text("// dashboard\n")
            (source / "desktop" / "plugin.js").write_text("// desktop\n")
            (source / "guard" / "HOOK.yaml").write_text("name: guard\n")
            (source / "guard" / "handler.py").write_text("# hook\n")

            api.HERMES_HOME = hermes_home
            api.PLUGINS = hermes_home / "plugins"
            api.STATE_DIR = hermes_home / "aiianer"

            legacy_desktop = hermes_home / "desktop-plugins" / "aiianer-hermes-extensions"
            legacy_desktop.mkdir(parents=True)
            (legacy_desktop / "plugin.js").write_text("// stale desktop\n")

            api._install_hub_from_root(source)

            self.assertEqual(
                (hermes_home / "plugins" / "aiianer-hub" / "plugin.yaml").read_text(),
                "name: aiianer-hub\nversion: 9.9.9\n",
            )
            self.assertTrue((hermes_home / "plugins" / "aiianer-hub" / "dashboard" / "plugin_api.py").is_file())
            self.assertTrue((hermes_home / "plugins" / "aiianer-hub" / "releases.json").is_file())
            expected_desktop = (source / "desktop" / "plugin.js").read_text()
            self.assertEqual(
                (hermes_home / "plugins" / "aiianer-hub" / "desktop" / "plugin.js").read_text(),
                expected_desktop,
            )
            self.assertFalse(legacy_desktop.exists())
            self.assertFalse((hermes_home / "plugins" / "aiianer-hub" / "desktop" / "plugin.js.neu").exists())
            self.assertTrue((hermes_home / "hooks" / "aiianer-guard" / "handler.py").is_file())


class HubVersionSourceTest(unittest.TestCase):
    def test_live_manifest_wins_over_stale_installed_state(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "hermes"
            manifest = home / "plugins" / "aiianer-hub" / "plugin.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("name: aiianer-hub\nversion: 1.3.24\n")
            api.HERMES_HOME = home
            self.assertEqual(api._local_plugin_version("aiianer-hub", {"aiianer-hub": {"version": "1.3.21"}}), "1.3.24")


class ReleaseNormalizationTest(unittest.TestCase):
    def test_normalizes_github_and_local_release_shapes(self):
        api = load_api_module()
        releases = api._normalize_releases([
            {
                "tag_name": "v1.3.12",
                "name": "Version 1.3.12",
                "body": "- Katalog synchronisiert",
                "published_at": "2026-09-09T20:30:00Z",
                "html_url": "https://example.invalid/releases/v1.3.12",
            },
            {"tag_name": ""},
        ])
        self.assertEqual(len(releases), 1)
        self.assertEqual(releases[0]["tagName"], "v1.3.12")
        self.assertEqual(releases[0]["publishedAt"], "2026-09-09T20:30:00Z")
        self.assertEqual(releases[0]["url"], "https://example.invalid/releases/v1.3.12")


class BackupUninstallTest(unittest.TestCase):
    def test_backup_uninstall_removes_runner_but_preserves_external_archive(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            api.HERMES_HOME = root / "hermes"
            api.STATE_DIR = api.HERMES_HOME / "aiianer"
            runner = api.HERMES_HOME / "scripts" / "aiianer-backup-runner.py"
            runner.parent.mkdir(parents=True)
            runner.write_text("# runner")
            archive = root / "external" / "aiianer-backup-test.zip"
            archive.parent.mkdir()
            archive.write_bytes(b"keep")
            api._backup_save({
                "target_dir": str(archive.parent), "enabled": True, "schedule": "daily",
                "history": [{"state": "success"}], "retention": {"enabled": False, "keep": 5},
            })
            log = []
            with mock.patch.object(api, "_pause_backup_cron") as pause:
                api._run_uninstall("aiianer-backup", log)
            pause.assert_called_once_with()
            self.assertFalse(runner.exists())
            self.assertFalse(api._backup_state()["enabled"])
            self.assertEqual(api._backup_state()["schedule"], "manual")
            self.assertTrue(archive.exists())
            self.assertIn({"state": "success"}, api._backup_state()["history"])


class HubCatalogUpdateStatusTest(unittest.TestCase):
    def test_legacy_hub_manifest_is_reported_outdated_after_catalog_bump(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            hermes_home = Path(tmp) / "hermes"
            manifest = hermes_home / "plugins" / "aiianer-hub" / "plugin.yaml"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("name: aiianer-hub\nversion: 1.3.12\n")
            api.HERMES_HOME = hermes_home
            api._load_catalog = lambda: json.loads((REPO_ROOT / "catalog.json").read_text())
            api._read_state = lambda: {}
            api._verfuegbar = lambda _comp_id: (True, None, None)
            api._premium_berechtigt = lambda _component: (True, None, None)

            result = asyncio.run(api.catalog())

        hub = next(component for component in result["components"] if component["id"] == "aiianer-hub")
        # Die Soll-Version kommt aus dem Katalog selbst - eine fest
        # eingetippte Zahl hier waere bei jedem Release ein falscher Alarm.
        katalog = json.loads((REPO_ROOT / "catalog.json").read_text())
        soll = next(c["version"] for c in katalog["components"] if c["id"] == "aiianer-hub")
        self.assertEqual(hub["installed"], "1.3.12")
        self.assertEqual(hub["version"], soll)
        self.assertEqual(hub["status"], "outdated")


class VersionKonsistenzTest(unittest.TestCase):
    """plugin.yaml, dashboard/manifest.json und catalog.json tragen dieselbe
    Hub-Version. Laufen sie auseinander, sieht ein Nutzer "aktuell", obwohl
    sein Hub alt ist - oder umgekehrt."""

    def test_hub_version_is_identical_in_all_three_places(self):
        katalog = json.loads((REPO_ROOT / "catalog.json").read_text())
        hub = next(c for c in katalog["components"] if c["id"] == "aiianer-hub")
        manifest = json.loads((REPO_ROOT / "dashboard" / "manifest.json").read_text())
        plugin_yaml = (REPO_ROOT / "plugin.yaml").read_text()
        self.assertEqual(manifest["version"], hub["version"])
        self.assertIn(f"version: {hub['version']}", plugin_yaml)

    def test_release_notes_mention_the_catalog_version(self):
        katalog = json.loads((REPO_ROOT / "catalog.json").read_text())
        hub = next(c for c in katalog["components"] if c["id"] == "aiianer-hub")
        tags = [r["tagName"] for r in json.loads((REPO_ROOT / "releases.json").read_text())["releases"]]
        self.assertIn(f"v{hub['version']}", tags)


if __name__ == "__main__":
    unittest.main()
