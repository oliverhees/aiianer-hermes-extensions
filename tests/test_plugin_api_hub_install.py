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


class BackupSecurityTest(unittest.TestCase):
    def setUp(self):
        self.api = load_api_module()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.api.HERMES_HOME = root / "hermes"
        self.api.STATE_DIR = self.api.HERMES_HOME / "aiianer"
        self.target = root / "backups"
        self.target.mkdir()
        self.api._backup_save({"target_dir": str(self.target), "enabled": True, "schedule": "manual", "retention": {"enabled": False, "keep": 5}})

    def tearDown(self):
        self.tmp.cleanup()

    def test_restore_prepare_rejects_archive_symlink_outside_target(self):
        outside = Path(self.tmp.name) / "outside.zip"
        outside.write_bytes(b"not a backup")
        (self.target / "aiianer-backup-2026T000000Z.zip").symlink_to(outside)
        with self.assertRaises(self.api.HTTPException) as caught:
            asyncio.run(self.api.backup_restore_prepare({"name": "aiianer-backup-2026T000000Z.zip"}))
        self.assertEqual(caught.exception.status_code, 404)

    def test_restore_confirm_uses_force_argv_after_exact_confirmation(self):
        archive = self.target / "aiianer-backup-2026T000000Z.zip"
        archive.write_bytes(b"zip")
        state = self.api._backup_state()
        state["restoreNonce"] = "nonce"
        self.api._backup_save(state)
        with mock.patch.object(self.api.subprocess, "run", return_value=mock.Mock(returncode=0)) as run:
            asyncio.run(self.api.backup_restore_confirm({"name": archive.name, "confirmationToken": "nonce", "confirmationText": self.api.RESTORE_CONFIRM.format(name=archive.name), "acknowledged": True}))
        argv = run.call_args.args[0]
        self.assertEqual(argv[1:4], ["import", "--force", str(archive.resolve())])


class CronDeduplicationTest(unittest.TestCase):
    def test_existing_named_job_is_edited_and_cli_failures_are_reported(self):
        api = load_api_module()
        responses = [mock.Mock(returncode=0, stdout="  abcdef123456 [active]\n    Name:      aiianer-backup\n", stderr=""), mock.Mock(returncode=7, stdout="", stderr="boom")]
        with mock.patch.object(api.subprocess, "run", side_effect=responses) as run:
            with self.assertRaises(RuntimeError) as caught:
                api._ensure_backup_cron("daily")
        self.assertIn("CRON_SETUP_FAILED", str(caught.exception))
        self.assertEqual(run.call_args_list[0].args[0][1:3], ["cron", "list"])
        self.assertEqual(run.call_args_list[1].args[0][1:3], ["cron", "edit"])
        self.assertEqual(run.call_args_list[1].args[0][3], "abcdef123456")


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
        self.assertEqual(hub["installed"], "1.3.12")
        self.assertEqual(hub["version"], "1.3.13")
        self.assertEqual(hub["status"], "outdated")


if __name__ == "__main__":
    unittest.main()
