"""Der Marktplatz-Knopf muss auch auf Windows installieren.

Hintergrund: Bis 1.3.32 rief das Backend ["bash", "C:\\...\\install.sh"] auf.
Auf Windows ohne Bash endete das in einem 500er, und mit Git-/MSYS2-Bash
ebenfalls - fuer eine Bash ist der Backslash ein Fluchtzeichen, sie meldete
"No such file or directory" fuer eine Datei, die sehr wohl da lag.

Diese Tests halten beides fest: den nativen Windows-Weg (kein bash, kein
python3) und die Bash-Aufrufe, die es weiter gibt (relativer Skriptname,
Pfade in Posix-Schreibweise).
"""
from __future__ import annotations

import asyncio
import gzip
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
API_PATH = REPO_ROOT / "dashboard" / "plugin_api.py"


def load_api_module():
    spec = importlib.util.spec_from_file_location("aiianer_plugin_api_win_test", API_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Ein Patcher-Ersatz: schreibt seine Argumente mit, damit der Test sieht,
# WIE er aufgerufen wurde - und legt eine Spur, damit er nachweislich lief.
PATCHER_STUB = """import json, sys
from pathlib import Path
Path(__file__).with_name("patcher-lief.json").write_text(
    json.dumps({"argv": sys.argv[1:], "cwd": str(Path.cwd()), "exe": sys.executable})
)
print("Patcher gelaufen")
"""


def hermes_heim(api, wurzel: Path) -> Path:
    """Verdrahtet das Modul auf ein Test-Hermes um."""
    heim = wurzel / "hermes-home"
    agent = heim / "hermes-agent"
    i18n = agent / "apps" / "desktop" / "src" / "i18n"
    bots = agent / "apps" / "desktop" / "src" / "plugins" / "hermes-bots"
    i18n.mkdir(parents=True)
    bots.mkdir(parents=True)
    (i18n / "types.ts").write_text("export type Locale = 'en' | 'de'\n")
    (bots / "i18n.ts").write_text("export const MESSAGES = {}\n")
    (bots / "group-rounds.ts").write_text("export const MAX_ROUNDS = 3\n")
    api.HERMES_HOME = heim
    api.PLUGINS = heim / "plugins"
    api.STATE_DIR = heim / "aiianer"
    api.EXT_STORE = heim / "aiianer-extensions"
    api.AGENT_DIR = agent
    api.I18N_DIR = i18n
    api.BOTS_DIR = bots
    api.BOTS_KATALOG = bots / "i18n.ts"
    api.BOTS_ROUNDS = bots / "group-rounds.ts"
    return heim


class NativeGermanInstallTest(unittest.TestCase):
    def test_installs_german_without_bash_and_without_python3(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            heim = hermes_heim(api, wurzel)
            src = wurzel / "extensions" / "german-language"
            src.mkdir(parents=True)
            with gzip.open(src / "de.ts.gz", "wb") as fh:
                fh.write(b"export const de = {}\n")
            (src / "apply-de.py").write_text(PATCHER_STUB)

            # Ein Bash-Aufruf waere hier schon der Fehler von 1.3.32.
            with mock.patch.object(api, "_ist_windows", return_value=True), mock.patch.object(
                api, "_run_bash_installer", side_effect=AssertionError("bash darf nicht laufen")
            ):
                log = api._run_extension_installer("german-language", src)

            store = heim / "aiianer-extensions" / "german-language"
            self.assertEqual((store / "de.ts").read_text(), "export const de = {}\n")
            self.assertTrue((store / "apply-de.py").is_file())
            # de.ts muss auch in src liegen: /install sichert die Payload von
            # dort nach ~/.hermes/aiianer/, damit der Waechter sie wiederfindet.
            self.assertTrue((src / "de.ts").is_file())
            self.assertIn("Patcher gelaufen", log)

            spur = json.loads((store / "patcher-lief.json").read_text())
            self.assertEqual(spur["argv"], [str(api.AGENT_DIR)])
            self.assertEqual(Path(spur["cwd"]), store)
            self.assertEqual(spur["exe"], sys.executable)

    def test_reports_missing_payload_instead_of_crashing(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            hermes_heim(api, wurzel)
            src = wurzel / "extensions" / "german-language"
            src.mkdir(parents=True)
            (src / "apply-de.py").write_text(PATCHER_STUB)
            with self.assertRaises(api.HTTPException) as fall:
                api._install_german_native(src)
            self.assertIn("de.ts.gz", str(fall.exception.detail))

    def test_failing_patcher_becomes_readable_error(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            hermes_heim(api, wurzel)
            src = wurzel / "extensions" / "german-language"
            src.mkdir(parents=True)
            with gzip.open(src / "de.ts.gz", "wb") as fh:
                fh.write(b"export const de = {}\n")
            (src / "apply-de.py").write_text(
                "import sys\nprint('FEHLER: Anker weg', file=sys.stderr)\nsys.exit(1)\n"
            )
            with self.assertRaises(api.HTTPException) as fall:
                api._install_german_native(src)
            self.assertEqual(fall.exception.status_code, 500)
            self.assertIn("Anker weg", str(fall.exception.detail))


class NativeBotsAndLimitsTest(unittest.TestCase):
    def test_installs_bot_bundle_natively(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            heim = hermes_heim(api, wurzel)
            src = wurzel / "extensions" / "bot-mode-german"
            src.mkdir(parents=True)
            (src / "de-bots.ts").write_text("export const deBots = {}\n")
            (src / "apply-bots-de.py").write_text(PATCHER_STUB)

            api._install_bots_native(src)

            store = heim / "aiianer-extensions" / "bot-mode-german"
            self.assertTrue((store / "de-bots.ts").is_file())
            spur = json.loads((store / "patcher-lief.json").read_text())
            self.assertEqual(spur["argv"], [str(api.AGENT_DIR)])

    def test_bot_bundle_refuses_without_german_locale(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            hermes_heim(api, wurzel)
            (api.I18N_DIR / "types.ts").write_text("export type Locale = 'en'\n")
            src = wurzel / "extensions" / "bot-mode-german"
            src.mkdir(parents=True)
            (src / "de-bots.ts").write_text("export const deBots = {}\n")
            (src / "apply-bots-de.py").write_text(PATCHER_STUB)
            with self.assertRaises(api.HTTPException) as fall:
                api._install_bots_native(src)
            self.assertIn("Deutsche Sprache", str(fall.exception.detail))

    def test_limits_keeps_existing_configuration(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            heim = hermes_heim(api, wurzel)
            api.STATE_DIR.mkdir(parents=True)
            eigen = '{"default": {"maxRounds": 99}}\n'
            (api.STATE_DIR / "gruppen-grenzen.json").write_text(eigen)

            src = wurzel / "extensions" / "group-chat-limits"
            src.mkdir(parents=True)
            (src / "aiianer-group-limits.ts").write_text("export const grenzen = {}\n")
            (src / "apply-limits.py").write_text(PATCHER_STUB)
            (src / "gruppen-grenzen.beispiel.json").write_text('{"default": {"maxRounds": 8}}\n')

            api._install_limits_native(src)

            # Eigene Grenzen bleiben stehen.
            self.assertEqual((api.STATE_DIR / "gruppen-grenzen.json").read_text(), eigen)
            store = heim / "aiianer-extensions" / "group-chat-limits"
            self.assertTrue((store / "gruppen-grenzen.beispiel.json").is_file())
            # Der Waechter braucht Modul und Patcher unter ~/.hermes/aiianer/.
            self.assertTrue((api.STATE_DIR / "aiianer-group-limits.ts").is_file())
            self.assertTrue((api.STATE_DIR / "apply-limits.py").is_file())
            spur = json.loads((store / "patcher-lief.json").read_text())
            self.assertEqual(spur["argv"], [str(api.AGENT_DIR), str(api.STATE_DIR)])

    def test_limits_seeds_example_configuration_once(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            hermes_heim(api, wurzel)
            src = wurzel / "extensions" / "group-chat-limits"
            src.mkdir(parents=True)
            (src / "aiianer-group-limits.ts").write_text("export const grenzen = {}\n")
            (src / "apply-limits.py").write_text(PATCHER_STUB)
            (src / "gruppen-grenzen.beispiel.json").write_text('{"default": {"maxRounds": 8}}\n')

            api._install_limits_native(src)

            self.assertEqual(
                json.loads((api.STATE_DIR / "gruppen-grenzen.json").read_text()),
                {"default": {"maxRounds": 8}},
            )


class NativeBackupInstallTest(unittest.TestCase):
    def test_installs_runner_and_seeds_state_once(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            heim = hermes_heim(api, wurzel)
            src = wurzel / "extensions" / "aiianer-backup"
            src.mkdir(parents=True)
            (src / "backup_runner.py").write_text("# runner\n")

            api._install_backup_native(src)

            runner = heim / "scripts" / "aiianer-backup-runner.py"
            self.assertEqual(runner.read_text(), "# runner\n")
            zustand = json.loads((api.STATE_DIR / "backup-state.json").read_text())
            self.assertFalse(zustand["enabled"])
            self.assertEqual(zustand["state"], "never_run")

            # Zweiter Lauf darf eine eingerichtete Sicherung nicht zuruecksetzen.
            zustand["enabled"] = True
            zustand["target_dir"] = str(wurzel / "ziel")
            (api.STATE_DIR / "backup-state.json").write_text(json.dumps(zustand))
            api._install_backup_native(src)
            self.assertTrue(
                json.loads((api.STATE_DIR / "backup-state.json").read_text())["enabled"]
            )


class BashAufrufTest(unittest.TestCase):
    """Wo es weiter per Bash laeuft, darf kein Windows-Pfad hineingehen."""

    def test_passes_relative_script_name_and_posix_paths(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            hermes_heim(api, wurzel)
            # Ein Heim, wie Windows es liefert: mit Backslashes.
            api.HERMES_HOME = Path(r"C:\Users\emanu\AppData\Local\hermes")
            api.AGENT_DIR = Path(r"C:\Users\emanu\AppData\Local\hermes\hermes-agent")
            src = wurzel / "extensions" / "eurouter-provider"
            src.mkdir(parents=True)
            (src / "install.sh").write_text("#!/usr/bin/env bash\necho ok\n")

            gesehen = {}

            def falscher_lauf(argv, **kwargs):
                gesehen["argv"] = argv
                gesehen["kwargs"] = kwargs
                return subprocess.CompletedProcess(argv, 0, "ok\n", "")

            with mock.patch.object(api, "_bash_binaer", return_value="/usr/bin/bash"), \
                    mock.patch.object(api.subprocess, "run", falscher_lauf):
                api._run_bash_installer("kuenftige-komponente", src)

            self.assertEqual(gesehen["argv"], ["/usr/bin/bash", "./install.sh"])
            self.assertEqual(Path(gesehen["kwargs"]["cwd"]), src)
            self.assertFalse(gesehen["kwargs"]["shell"])
            for argument in gesehen["argv"][1:]:
                self.assertNotIn("\\", argument)
            env = gesehen["kwargs"]["env"]
            self.assertEqual(env["HERMES_HOME"], "C:/Users/emanu/AppData/Local/hermes")
            self.assertEqual(
                env["HERMES_AGENT_DIR"], "C:/Users/emanu/AppData/Local/hermes/hermes-agent"
            )

    def test_missing_bash_names_the_remedy(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "extensions" / "eurouter-provider"
            src.mkdir(parents=True)
            (src / "install.sh").write_text("#!/usr/bin/env bash\necho ok\n")
            with mock.patch.object(api, "_bash_binaer", return_value=None):
                with self.assertRaises(api.HTTPException) as fall:
                    api._run_bash_installer("kuenftige-komponente", src)
            self.assertIn("git-scm.com", str(fall.exception.detail))

    def test_ignores_the_wsl_launcher_in_system32(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            system32 = Path(tmp) / "Windows" / "System32"
            system32.mkdir(parents=True)
            wsl = system32 / "bash.exe"
            wsl.write_text("")
            with mock.patch.object(api, "_ist_windows", return_value=True), \
                    mock.patch.object(api.shutil, "which", return_value=str(wsl)):
                self.assertIsNone(api._bash_binaer())

    def test_uses_git_bash_when_it_exists(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            git_bash = Path(tmp) / "Git" / "bin" / "bash.exe"
            git_bash.parent.mkdir(parents=True)
            git_bash.write_text("")
            with mock.patch.object(api, "_ist_windows", return_value=True), \
                    mock.patch.object(api.shutil, "which", return_value=None), \
                    mock.patch.dict(api.os.environ, {"ProgramFiles": tmp}, clear=False):
                self.assertEqual(api._bash_binaer(), str(git_bash))


class VerfuegbarkeitTest(unittest.TestCase):
    def test_hides_bash_only_component_on_windows_without_bash(self):
        api = load_api_module()
        with mock.patch.object(api, "_ist_windows", return_value=True), \
                mock.patch.object(api, "_bash_binaer", return_value=None):
            ok, grund, grund_en = api._verfuegbar("kuenftige-komponente")
        self.assertFalse(ok)
        self.assertIn("Bash", grund)
        self.assertIn("bash", grund_en)

    def test_native_components_stay_available_without_bash(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            hermes_heim(api, Path(tmp))
            with mock.patch.object(api, "_ist_windows", return_value=True), \
                    mock.patch.object(api, "_bash_binaer", return_value=None):
                for comp_id in ("german-language", "bot-mode-german", "group-chat-limits",
                                "aiianer-backup", "eurouter-provider"):
                    ok, grund, _ = api._verfuegbar(comp_id)
                    self.assertTrue(ok, f"{comp_id}: {grund}")


class PayloadVorhandenTest(unittest.TestCase):
    """Drift-Schutz: die nativen Installer kopieren Dateien beim Namen. Wird
    eine umbenannt, muss dieser Test rot werden - nicht der Rechner eines
    Community-Mitglieds."""

    ERWARTET = {
        "german-language": ("de.ts.gz", "apply-de.py"),
        "bot-mode-german": ("de-bots.ts", "apply-bots-de.py"),
        "group-chat-limits": (
            "aiianer-group-limits.ts", "apply-limits.py", "gruppen-grenzen.beispiel.json",
        ),
        "aiianer-backup": ("backup_runner.py",),
        # Der EU-Router bringt seine Payload aus einem eigenen Repo mit, hier
        # liegt nur der Installer. Geprueft wird deshalb nur dessen Existenz.
        "eurouter-provider": (),
    }

    def test_every_native_installer_finds_its_payload_in_the_repo(self):
        api = load_api_module()
        self.assertEqual(set(api.NATIVE_INSTALLER), set(self.ERWARTET))
        for comp_id, dateien in self.ERWARTET.items():
            ordner = REPO_ROOT / "extensions" / comp_id
            self.assertTrue((ordner / "install.sh").is_file(), comp_id)
            for name in dateien:
                self.assertTrue((ordner / name).is_file(), f"{comp_id}/{name}")


class InstallRouteAufWindowsTest(unittest.TestCase):
    """Der Fall aus dem Fehlerbericht: Windows 11, Klick auf „Installieren“.

    Früher lief das in einen HTTP 500 mit
    "/bin/bash: C:\\Users\\...\\install.sh: No such file or directory".
    Jetzt muss es durchlaufen - auch wenn auf dem Rechner gar keine Bash ist."""

    def test_installs_german_language_end_to_end_without_any_bash(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            heim = hermes_heim(api, wurzel)

            # Ein "heruntergeladenes" Repo, wie _download es auspackt.
            repo = wurzel / "aiianer-hermes-extensions-main"
            src = repo / "extensions" / "german-language"
            src.mkdir(parents=True)
            with gzip.open(src / "de.ts.gz", "wb") as fh:
                fh.write(b"export const de = {}\n")
            (src / "apply-de.py").write_text(PATCHER_STUB)
            (src / "install.sh").write_text("#!/usr/bin/env bash\nexit 7\n")

            zustand: dict = {}
            api._download = lambda _tmp: repo
            api._load_catalog = lambda: {
                "catalogVersion": "test",
                "components": [{"id": "german-language", "version": "2026.09.01"}],
            }
            api._read_state = lambda: dict(zustand)
            api._write_state = zustand.update
            api._premium_berechtigt = lambda _entry: (True, "", "")

            with mock.patch.object(api, "_ist_windows", return_value=True), \
                    mock.patch.object(api, "_bash_binaer", return_value=None):
                antwort = asyncio.run(api.install({"id": "german-language"}))

            self.assertTrue(antwort["ok"])
            self.assertEqual(antwort["version"], "2026.09.01")
            self.assertIn("Patcher gelaufen", antwort["log"])
            # Payload liegt im Store UND unter ~/.hermes/aiianer/ fuer den Waechter.
            self.assertTrue(
                (heim / "aiianer-extensions" / "german-language" / "de.ts").is_file()
            )
            self.assertTrue((api.STATE_DIR / "de.ts").is_file())
            self.assertTrue((api.STATE_DIR / "apply-de.py").is_file())

    def test_install_route_reports_missing_bash_for_bash_only_component(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            hermes_heim(api, wurzel)
            repo = wurzel / "aiianer-hermes-extensions-main"
            src = repo / "extensions" / "kuenftige-komponente"
            src.mkdir(parents=True)
            (src / "install.sh").write_text("#!/usr/bin/env bash\necho ok\n")

            api._download = lambda _tmp: repo
            api._load_catalog = lambda: {
                "components": [{"id": "kuenftige-komponente", "version": "1.0.0"}]
            }
            api._read_state = lambda: {}
            api._write_state = lambda _state: None
            api._premium_berechtigt = lambda _entry: (True, "", "")

            with mock.patch.object(api, "_ist_windows", return_value=True), \
                    mock.patch.object(api, "_bash_binaer", return_value=None):
                with self.assertRaises(api.HTTPException) as fall:
                    asyncio.run(api.install({"id": "kuenftige-komponente"}))
            # 409 statt 500: die Pruefung greift, bevor irgendetwas laeuft.
            self.assertEqual(fall.exception.status_code, 409)
            self.assertIn("Bash", str(fall.exception.detail))


class NativeEurouterTest(unittest.TestCase):
    """Der EU-Router wohnt in einem eigenen Repo. Unter Windows wird sein
    install.sh nachgebaut, statt eine Bash zu verlangen."""

    def eurouter_repo(self, wurzel: Path) -> Path:
        repo = wurzel / "hermes-eurouter-plugin-main"
        quelle = repo / "model-providers" / "eurouter"
        quelle.mkdir(parents=True)
        (quelle / "__init__.py").write_text("# eurouter provider\n")
        (quelle / "plugin.yaml").write_text("name: eurouter\nversion: 2.1.0\n")
        return repo

    def test_installs_provider_files_and_clears_the_model_cache(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            heim = hermes_heim(api, wurzel)
            api.PLUGINS = heim / "plugins"
            repo = self.eurouter_repo(wurzel)

            # Ein Cache mit fremden Eintraegen - die muessen stehen bleiben.
            cache = heim / "provider_models_cache.json"
            cache.write_text(json.dumps({"eurouter": ["alt"], "openai": ["bleibt"]}))

            # Ein altes __pycache__, das ein Update ueberleben wuerde.
            alt = api.PLUGINS / "model-providers" / "eurouter" / "__pycache__"
            alt.mkdir(parents=True)
            (alt / "__init__.cpython-311.pyc").write_text("stale")

            with mock.patch.object(api, "_download_tarball", return_value=repo):
                log = api._install_eurouter_native(wurzel / "egal")

            ziel = api.PLUGINS / "model-providers" / "eurouter"
            self.assertEqual((ziel / "__init__.py").read_text(), "# eurouter provider\n")
            self.assertTrue((ziel / "plugin.yaml").is_file())
            self.assertFalse((ziel / "__pycache__").exists())
            self.assertEqual(json.loads(cache.read_text()), {"openai": ["bleibt"]})
            self.assertTrue(any("Cache" in z for z in log), log)

    def test_reports_incomplete_remote_repo(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            heim = hermes_heim(api, wurzel)
            api.PLUGINS = heim / "plugins"
            repo = wurzel / "hermes-eurouter-plugin-main"
            (repo / "model-providers" / "eurouter").mkdir(parents=True)
            with mock.patch.object(api, "_download_tarball", return_value=repo):
                with self.assertRaises(api.HTTPException) as fall:
                    api._install_eurouter_native(wurzel / "egal")
            self.assertIn("__init__.py", str(fall.exception.detail))

    def test_says_it_plainly_when_hermes_home_is_missing(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            api.HERMES_HOME = Path(tmp) / "gibt-es-nicht"
            with self.assertRaises(api.HTTPException) as fall:
                api._install_eurouter_native(Path(tmp))
            self.assertIn("Ist Hermes installiert", str(fall.exception.detail))

    def test_windows_never_reaches_for_bash(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            wurzel = Path(tmp)
            heim = hermes_heim(api, wurzel)
            api.PLUGINS = heim / "plugins"
            repo = self.eurouter_repo(wurzel)
            with mock.patch.object(api, "_ist_windows", return_value=True), \
                    mock.patch.object(api, "_download_tarball", return_value=repo), \
                    mock.patch.object(
                        api, "_run_bash_installer",
                        side_effect=AssertionError("bash darf nicht laufen")):
                api._run_extension_installer("eurouter-provider", wurzel / "egal")
            self.assertTrue(
                (api.PLUGINS / "model-providers" / "eurouter" / "plugin.yaml").is_file()
            )

    def test_posix_keeps_the_canonical_shell_installer(self):
        api = load_api_module()
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "extensions" / "eurouter-provider"
            src.mkdir(parents=True)
            (src / "install.sh").write_text("#!/usr/bin/env bash\necho ok\n")
            with mock.patch.object(api, "_ist_windows", return_value=False), \
                    mock.patch.object(
                        api, "_run_bash_installer", return_value=["ok"]) as bash_weg:
                self.assertEqual(
                    api._run_extension_installer("eurouter-provider", src), ["ok"]
                )
            bash_weg.assert_called_once()


if __name__ == "__main__":
    unittest.main()
