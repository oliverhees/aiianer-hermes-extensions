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

    def test_schedule_expression_supports_daily_and_weekly_clock_times(self):
        api = load_api_module()
        self.assertEqual(api._backup_schedule_expression("daily", "02:30", 0), "30 2 * * *")
        self.assertEqual(api._backup_schedule_expression("weekly", "04:05", 6), "5 4 * * 6")

    def test_paused_named_job_is_resumed_after_schedule_edit(self):
        api = load_api_module()
        responses = [
            mock.Mock(returncode=0, stdout="  abcdef123456 [paused]\n    Name:      aiianer-backup\n", stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
            mock.Mock(returncode=0, stdout="", stderr=""),
        ]
        with mock.patch.object(api.subprocess, "run", side_effect=responses) as run:
            api._ensure_backup_cron("weekly", "04:05", 6)
        self.assertEqual(run.call_args_list[1].args[0][1:3], ["cron", "edit"])
        self.assertEqual(run.call_args_list[2].args[0][1:3], ["cron", "resume"])
        self.assertEqual(run.call_args_list[2].args[0][3], "abcdef123456")


class BackupBrowserAndHistoryTest(unittest.TestCase):
    def setUp(self):
        self.api = load_api_module()
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.api.HERMES_HOME = root / "hermes"
        self.api.STATE_DIR = self.api.HERMES_HOME / "aiianer"
        self.folder = root / "backup-root"
        (self.folder / "eins").mkdir(parents=True)
        (self.folder / "zwei").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_browser_returns_only_sorted_directories(self):
        (self.folder / "not-a-folder.txt").write_text("ignore")
        result = asyncio.run(self.api.backup_browse({"path": str(self.folder)}))
        self.assertEqual(result["path"], str(self.folder.resolve()))
        self.assertEqual([entry["name"] for entry in result["directories"]], ["eins", "zwei"])

    def test_backup_browser_rejects_hermes_home_and_symlink_into_it(self):
        self.api.HERMES_HOME.mkdir(parents=True)
        private = self.api.HERMES_HOME / "private"
        private.mkdir()
        alias = Path(self.tmp.name) / "alias-to-hermes"
        alias.symlink_to(self.api.HERMES_HOME, target_is_directory=True)
        for path in (self.api.HERMES_HOME, private, alias):
            with self.assertRaises(self.api.HTTPException) as caught:
                asyncio.run(self.api.backup_browse({"path": str(path)}))
            self.assertEqual(caught.exception.status_code, 422)

    def test_settings_preserve_runner_result_written_during_cron_update(self):
        self.api._backup_save({"state": "failed", "lastErrorCode": "HERMES_COMMAND_FAILED", "history": []})

        def runner_finishes(*_args):
            state = self.api._backup_state()
            state.update({"state": "success", "lastRun": "2026-09-10T12:00:00+00:00", "lastArchive": {"name": "aiianer-backup-test.zip"}, "lastErrorCode": None, "history": [{"at": "2026-09-10T12:00:00+00:00", "state": "success"}]})
            self.api._backup_save(state)

        with mock.patch.object(self.api, "_ensure_backup_cron", side_effect=runner_finishes):
            result = asyncio.run(self.api.backup_settings({"enabled": True, "target_dir": str(self.folder), "schedule": "daily", "scheduleTime": "02:30", "scheduleWeekday": 0, "retention": {"enabled": False, "keep": 5}}))
        self.assertEqual(result["state"], "success")
        self.assertEqual(result["history"][0]["state"], "success")
        self.assertEqual(result["lastArchive"]["name"], "aiianer-backup-test.zip")

    def test_backup_status_exposes_newest_first_run_history(self):
        self.api._backup_save({
            "target_dir": str(self.folder),
            "enabled": True,
            "schedule": "daily",
            "scheduleTime": "02:30",
            "scheduleWeekday": 0,
            "history": [
                {"at": "2026-09-10T10:00:00+00:00", "state": "success"},
                {"at": "2026-09-09T10:00:00+00:00", "state": "failed", "errorCode": "HERMES_COMMAND_FAILED"},
            ],
        })
        result = asyncio.run(self.api.backup_status())
        self.assertEqual(result["scheduleTime"], "02:30")
        self.assertEqual(result["history"][0]["state"], "success")
        self.assertEqual(len(result["history"]), 2)


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
        self.assertEqual(hub["installed"], "1.3.12")
        self.assertEqual(hub["version"], "1.3.31")
        self.assertEqual(hub["status"], "outdated")


if __name__ == "__main__":
    unittest.main()
