"""Der Waechter soll nur noch reparieren/neu bauen, was aktuell im Katalog
sichtbar ist.

Hintergrund: group-chat-limits ist seit 10.09.2026 als "unfinished" aus
catalog.json entfernt (Oliver, chore: hide unfinished group chat limits
plugin), aber Nutzer, die es davor installiert hatten, wurden trotzdem fuer
immer automatisch geprueft und repariert - Community-Report vom 16.09.2026
zeigte einen Reparatur-Loop, der zusaetzlich bei jedem Fund den teuren
--build-only-Neubau ausloeste, fuer eine Komponente, die Oliver explizit
nicht mehr pflegt.
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
    spec = importlib.util.spec_from_file_location("aiianer_guard_check_catalog_test", GUARD_CHECK_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextlib.contextmanager
def tempfile_dir():
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


def hermes_heim_mit_group_chat_limits(gc, wurzel: Path, *, katalog_ids) -> Path:
    """Ein Hermes-Stand, bei dem group-chat-limits installiert, aber KAPUTT
    ist (Naht fehlt) - der interessante Fall: greift der Waechter trotzdem
    zu, wenn die Komponente nicht (mehr) im Katalog steht?"""
    heim = wurzel / "hermes-home"
    agent = heim / "hermes-agent"
    bots = agent / "apps" / "desktop" / "src" / "plugins" / "hermes-bots"
    bots.mkdir(parents=True)
    (bots / "group-rounds.ts").write_text("export async function runGroupChatRounds() {}\n")
    (bots / "group-round-members.ts").write_text("// kein aiianer-Marker\n")

    state_dir = heim / "aiianer"
    state_dir.mkdir(parents=True)
    (state_dir / "installed.json").write_text(json.dumps({
        "group-chat-limits": {"version": "2.0.0", "at": "2026-09-09T00:00:00+00:00"},
    }))

    hub_dir = heim / "plugins" / "aiianer-hub"
    hub_dir.mkdir(parents=True)
    if katalog_ids is not None:
        (hub_dir / "catalog.json").write_text(json.dumps({
            "components": [{"id": cid} for cid in katalog_ids],
        }))

    gc.HERMES_HOME = heim
    gc.AGENT = agent
    gc.I18N = agent / "apps" / "desktop" / "src" / "i18n"
    gc.STATE_DIR = state_dir
    gc.LOG_FILE = state_dir / "guard.log"
    gc._CATALOG_PFAD = hub_dir / "catalog.json"
    return heim


class KatalogSichtbarkeitTest(unittest.TestCase):
    def test_versteckte_komponente_wird_nicht_mehr_als_kaputt_gemeldet(self):
        """Der eigentliche Regressionsfall: group-chat-limits ist installiert
        und kaputt, steht aber nicht mehr im Katalog - check_all() darf das
        nicht mehr als 'missing'/'broken' melden."""
        gc = load_guard_check_module()
        with tempfile_dir() as tmp:
            hermes_heim_mit_group_chat_limits(
                gc, tmp, katalog_ids=("german-language", "eurouter-provider")
            )
            status = gc.check_all()
            self.assertTrue(status["ok"])
            self.assertNotIn("group-chat-limits", status["broken"])
            self.assertFalse(any(c["id"] == "group-chat-limits" for c in status["checks"]))

    def test_sichtbare_komponente_wird_weiterhin_gemeldet(self):
        gc = load_guard_check_module()
        with tempfile_dir() as tmp:
            hermes_heim_mit_group_chat_limits(
                gc, tmp, katalog_ids=("german-language", "group-chat-limits")
            )
            status = gc.check_all()
            self.assertFalse(status["ok"])
            self.assertIn("group-chat-limits", status["broken"])

    def test_repair_all_baut_nicht_fuer_versteckte_komponente(self):
        """Nicht nur die Meldung, auch die Reparatur (inkl. teurem Rebuild)
        darf fuer eine versteckte Komponente nicht mehr auslösen."""
        gc = load_guard_check_module()
        with tempfile_dir() as tmp:
            hermes_heim_mit_group_chat_limits(
                gc, tmp, katalog_ids=("german-language",)
            )
            with mock.patch.object(gc, "_rebuild_desktop") as rebuild, \
                    mock.patch.object(gc, "repair_group_limits") as repair:
                ergebnis = gc.repair_all(rebuild_desktop=True)

            repair.assert_not_called()
            rebuild.assert_not_called()
            self.assertTrue(ergebnis["ok"])

    def test_fehlender_katalog_faellt_offen_auf_alte_pruefung_zurueck(self):
        """Kein Katalog lesbar (z. B. sehr alte Installation) darf NICHT
        dazu fuehren, dass ploetzlich gar nichts mehr geprueft wird - das
        waere schlimmer als das urspruengliche Problem."""
        gc = load_guard_check_module()
        with tempfile_dir() as tmp:
            hermes_heim_mit_group_chat_limits(gc, tmp, katalog_ids=None)
            status = gc.check_all()
            self.assertFalse(status["ok"])
            self.assertIn("group-chat-limits", status["broken"])


if __name__ == "__main__":
    unittest.main()
