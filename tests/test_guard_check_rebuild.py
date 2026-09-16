"""Der Waechter muss auch dann neu bauen, wenn ER SELBST in diesem Durchlauf
nichts am Quellcode zu reparieren findet.

Community-Befund nach v1.3.37 (Mac-Nutzer): ein FRUEHERER Lauf (noch mit
einer aelteren Hub-Version ohne automatischen Rebuild) reparierte den
Quellcode und entfernte dabei den Build-Stempel. Der Hub aktualisierte sich
DANACH selbst auf 1.3.37 und der Gateway startete neu. Der neue Waechter fand
den Quellcode bereits korrekt vor (state == 'ok' fuer alle Komponenten) und
brach - vor diesem Fix - sofort ab, ohne je zu pruefen, dass der Build-
Stempel immer noch fehlte. Ergebnis: die fertige Desktop-App blieb dauerhaft
auf altem Stand, obwohl der Quellcode laengst wieder stimmte.
"""
from __future__ import annotations

import contextlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_CHECK_PATH = REPO_ROOT / "guard_check.py"


def load_guard_check_module():
    spec = importlib.util.spec_from_file_location("aiianer_guard_check_test", GUARD_CHECK_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def tempfile_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def hermes_heim(gc, wurzel: Path) -> Path:
    """Verdrahtet das Modul auf ein Test-Hermes um, mit bereits korrekt
    verdrahteter deutscher Sprachdatei (der Zustand NACH einer erfolgreichen
    Reparatur, VOR einem Neubau)."""
    heim = wurzel / "hermes-home"
    agent = heim / "hermes-agent"
    i18n = agent / "apps" / "desktop" / "src" / "i18n"
    i18n.mkdir(parents=True)
    (i18n / "types.ts").write_text("export type Locale = 'en' | 'de'\n")
    (i18n / "catalog.ts").write_text("import { de } from './de'\nexport const TRANSLATIONS = { en, de }\n")
    (i18n / "languages.ts").write_text("export const LOCALE_OPTIONS = [{ id: 'en' }, { id: 'de' }]\n")
    (i18n / "de.ts").write_text("export const de = {}\n")

    state_dir = heim / "aiianer"
    state_dir.mkdir(parents=True)
    (state_dir / "installed.json").write_text(json.dumps({
        "german-language": {"version": "2026.09.01", "at": "2026-09-15T00:00:00+00:00"},
    }))

    gc.HERMES_HOME = heim
    gc.AGENT = agent
    gc.I18N = i18n
    gc.STATE_DIR = state_dir
    gc.LOG_FILE = state_dir / "guard.log"
    return heim


class DesktopBuildStampMissingTest(unittest.TestCase):
    def test_true_when_stamp_absent(self):
        gc = load_guard_check_module()
        with tempfile_dir() as tmp:
            hermes_heim(gc, tmp)
            self.assertTrue(gc._desktop_build_stamp_missing())

    def test_false_when_stamp_present(self):
        gc = load_guard_check_module()
        with tempfile_dir() as tmp:
            heim = hermes_heim(gc, tmp)
            (heim / "desktop-build-stamp.json").write_text("{}")
            self.assertFalse(gc._desktop_build_stamp_missing())


class RepairAllRebuildsOnOrphanedStampTest(unittest.TestCase):
    """Das eigentliche Regressions-Szenario: Quellcode ist ok, Stempel fehlt,
    nichts wurde in DIESEM Durchlauf repariert - trotzdem muss neu gebaut
    werden, wenn rebuild_desktop=True gilt."""

    def test_rebuild_triggered_even_without_source_repair(self):
        gc = load_guard_check_module()
        with tempfile_dir() as tmp:
            hermes_heim(gc, tmp)
            # Quellcode ist bereits korrekt verdrahtet (siehe check_german oben) -
            # kein Reparaturbedarf. Kein desktop-build-stamp.json angelegt.
            self.assertEqual(gc.check_all()["ok"], True)

            with mock.patch.object(gc, "_rebuild_desktop", return_value={"rebuilt": True, "detail": ""}) as rebuild:
                ergebnis = gc.repair_all(rebuild_desktop=True)

            rebuild.assert_called_once()
            self.assertEqual(ergebnis["desktopRebuild"], {"rebuilt": True, "detail": ""})

    def test_no_rebuild_when_stamp_present_and_nothing_missing(self):
        gc = load_guard_check_module()
        with tempfile_dir() as tmp:
            heim = hermes_heim(gc, tmp)
            (heim / "desktop-build-stamp.json").write_text("{}")

            with mock.patch.object(gc, "_rebuild_desktop") as rebuild:
                gc.repair_all(rebuild_desktop=True)

            rebuild.assert_not_called()

    def test_no_rebuild_when_nothing_installed(self):
        gc = load_guard_check_module()
        with tempfile_dir() as tmp:
            heim = hermes_heim(gc, tmp)
            (heim / "aiianer" / "installed.json").write_text("{}")

            with mock.patch.object(gc, "_rebuild_desktop") as rebuild:
                gc.repair_all(rebuild_desktop=True)

            rebuild.assert_not_called()

    def test_rebuild_desktop_false_does_not_call_rebuild(self):
        """Der Standardfall (kein explizites rebuild_desktop=True) loest
        weiterhin keinen Neubau aus, auch wenn der Stempel fehlt - nur der
        Log-Hinweis aendert sich."""
        gc = load_guard_check_module()
        with tempfile_dir() as tmp:
            hermes_heim(gc, tmp)

            with mock.patch.object(gc, "_rebuild_desktop") as rebuild:
                gc.repair_all(rebuild_desktop=False)

            rebuild.assert_not_called()


if __name__ == "__main__":
    unittest.main()
