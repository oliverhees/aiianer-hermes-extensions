"""AIIANER Marktplatz - Backend.

Liest den Katalog, vergleicht ihn mit dem lokal Installierten und installiert
oder aktualisiert Komponenten. Alles landet unter ~/.hermes/, nie im
Hermes-Checkout, mit einer Ausnahme: die Sprachdatei, weil Hermes keine
Laufzeit-Registrierung fuer Sprachen anbietet. Die uebernimmt der Waechter.

Routen liegen unter /api/plugins/aiianer-hub/ und damit hinter dem Auth-Gate
des Dashboards.
"""

from __future__ import annotations

import json
import re
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

REPO = "oliverhees/aiianer-hermes-extensions"
TARBALL = f"https://github.com/{REPO}/archive/refs/heads/main.tar.gz"
CATALOG_URL = (
    f"https://raw.githubusercontent.com/{REPO}/main/"
    "extensions/aiianer-hub/catalog.json"
)

def hermes_home() -> Path:
    """Wo Hermes seine Daten haelt, plattformuebergreifend.

    Reihenfolge wie in Hermes' eigenem scripts/install.ps1:
      1. HERMES_HOME, wenn gesetzt (gilt ueberall, auch fuer Profile)
      2. natives Windows: %LOCALAPPDATA%\\hermes
      3. sonst (Linux, macOS, WSL): ~/.hermes
    """
    env = os.environ.get("HERMES_HOME", "").strip()
    if env:
        return Path(env)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if local:
            return Path(local) / "hermes"
        return Path.home() / "AppData" / "Local" / "hermes"
    return Path.home() / ".hermes"


HERMES_HOME = hermes_home()
PLUGINS = HERMES_HOME / "plugins"
STATE_DIR = HERMES_HOME / "aiianer"
STATE_FILE = STATE_DIR / "installed.json"
LOCAL_CATALOG = Path(__file__).resolve().parent.parent / "catalog.json"
AGENT_DIR = Path(os.environ.get("HERMES_AGENT_DIR") or (HERMES_HOME / "hermes-agent"))
I18N_DIR = AGENT_DIR / "apps" / "desktop" / "src" / "i18n"
BOTS_PLUGIN = AGENT_DIR / "apps" / "desktop" / "src" / "plugins" / "hermes-bots" / "plugin.js"
EXT_STORE = HERMES_HOME / "aiianer-extensions"

# Was der Nutzer NACH einer Aktion tun muss. Bewusst hier im lokalen Code und
# nicht im Katalog: der Katalog kommt aus dem Netz, und Anweisungstexte, die
# jemand von aussen setzen kann, sind eine Einladung zum Missbrauch. Der
# Katalog darf sie ueberschreiben, muss aber nicht.
NEXT_STEPS = {
    "german-language": {
        "install": [
            "Hermes komplett beenden und neu starten. Beim ersten Start baut die App sich einmal neu, das dauert einen Moment.",
            "Danach: Settings -> Language -> Deutsch auswählen.",
            "Erst danach ist die Oberfläche auf Deutsch. Vorher ändert sich nichts.",
        ],
        "uninstall": [
            "Hermes komplett beenden und neu starten.",
            "Falls die Sprache noch auf Deutsch stand: Settings -> Language -> English.",
        ],
    },
    "bot-mode-german": {
        "install": ["Hermes neu starten. Der Bot-Modus ist danach auf Deutsch."],
        "uninstall": ["Hermes neu starten. Der Bot-Modus ist wieder englisch."],
    },
    "group-chat-limits": {
        "install": ["Hermes neu starten. Die Grenzen stehen dann in den Gruppenchat-Einstellungen."],
        "uninstall": ["Hermes neu starten. Es gelten wieder die eingebauten Grenzen."],
    },
    "eurouter-provider": {
        "install": [
            "Hermes neu starten.",
            "Der EU-Router taucht dann im Modell-Auswahlmenü als eigene Gruppe auf.",
        ],
        "uninstall": [
            "Hermes neu starten.",
            "Der Start-Helfer unter ~/.local/bin/hermes bleibt absichtlich liegen, weil er auch andere Reparaturen macht.",
        ],
    },
}


def _steps(comp_id: str, aktion: str, entry: dict | None = None) -> list:
    """Katalog darf ueberschreiben, sonst der lokale Standard."""
    vom_katalog = (entry or {}).get("nextSteps", {}).get(aktion)
    if isinstance(vom_katalog, list) and vom_katalog:
        return [str(x) for x in vom_katalog]
    return NEXT_STEPS.get(comp_id, {}).get(aktion, [])


# ---------------------------------------------------------------- Zustand

def _read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def _write_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _load_catalog() -> dict:
    """Katalog aus dem Netz, mit der mitgelieferten Fassung als Rueckfall."""
    try:
        with urllib.request.urlopen(CATALOG_URL, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return json.loads(LOCAL_CATALOG.read_text())


# ---------------------------------------------------------------- Routen

@router.get("/catalog")
async def catalog() -> dict:
    """Katalog plus lokaler Zustand pro Komponente."""
    cat = _load_catalog()
    state = _read_state()
    items = []
    for c in cat.get("components", []):
        local = state.get(c["id"], {})
        installed = local.get("version")
        items.append(
            {
                **c,
                "installed": installed,
                "installedAt": local.get("at"),
                "nextSteps": _steps(c["id"], "install", c),
                "uninstallSteps": _steps(c["id"], "uninstall", c),
                "status": (
                    "missing"
                    if not installed
                    else "outdated"
                    if installed != c["version"]
                    else "current"
                ),
            }
        )
    return {"catalogVersion": cat.get("catalogVersion"), "components": items}


def _guard():
    """guard_check liegt unter ~/.hermes/aiianer/, dieselbe Datei, die auch
    der Waechter-Hook benutzt. Ein Ort, eine Wahrheit."""
    if str(STATE_DIR) not in sys.path:
        sys.path.insert(0, str(STATE_DIR))
    import guard_check  # type: ignore

    return guard_check


@router.get("/health")
async def health() -> dict:
    """Sitzt alles noch? Der Waechter nutzt dieselbe Pruefung."""
    return _guard().check_all()


@router.post("/install")
async def install(body: dict) -> dict:
    comp_id = (body or {}).get("id", "")
    cat = _load_catalog()
    entry = next((c for c in cat.get("components", []) if c["id"] == comp_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unbekannte Komponente: {comp_id}")

    with tempfile.TemporaryDirectory() as tmp:
        root = _download(tmp)
        src = root / "extensions" / comp_id
        if not src.is_dir():
            raise HTTPException(
                status_code=500, detail=f"{comp_id} fehlt im heruntergeladenen Repo"
            )
        installer = src / "install.sh"
        if not installer.is_file():
            raise HTTPException(status_code=500, detail=f"{comp_id} hat kein install.sh")
        os.chmod(installer, 0o755)
        proc = subprocess.run(
            ["bash", str(installer)],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(src),
        )
        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=(proc.stderr or proc.stdout or "Installation fehlgeschlagen")[-800:],
            )

        # Sprachdatei zusaetzlich als Quelle sichern, damit der Waechter sie
        # nach einem Hermes-Update erneut einspielen kann.
        if comp_id == "german-language":
            STATE_DIR.mkdir(parents=True, exist_ok=True)
            for name in ("de.ts", "apply-de.py"):
                if (src / name).is_file():
                    shutil.copy2(src / name, STATE_DIR / name)

    state = _read_state()
    vorher = state.get(comp_id, {}).get("version")
    state[comp_id] = {"version": entry["version"], "at": _now()}
    _write_state(state)
    return {
        "ok": True,
        "id": comp_id,
        "action": "update" if vorher else "install",
        "version": entry["version"],
        "previousVersion": vorher,
        "log": [z for z in (proc.stdout or "").splitlines() if z.strip()][-12:],
        "nextSteps": _steps(comp_id, "install", entry),
    }


# ------------------------------------------------------- Rueckbau

# Jeder Installer legt sein Backup selbst an. Der Rueckbau spielt genau
# dieses Backup zurueck - nichts wird geraten und nichts pauschal geloescht.
# Deshalb steht die Logik hier im lokalen Code und nicht im Katalog aus dem
# Netz: wer das Repo kontrolliert, soll nicht kontrollieren, welche Dateien
# auf fremden Rechnern verschwinden.


def _restore(quelle: Path, ziel: Path, protokoll: list) -> bool:
    if not quelle.is_file():
        protokoll.append(f"Backup fehlt: {quelle}")
        return False
    shutil.copy2(quelle, ziel)
    protokoll.append(f"wiederhergestellt: {ziel.name}")
    return True


def _drop(pfad: Path, protokoll: list) -> bool:
    """Gibt zurueck, ob danach wirklich nichts mehr da liegt. Der Aufrufer
    MUSS das auswerten - ein Rueckbau, der still scheitert und trotzdem
    ok: true meldet, ist schlimmer als einer, der abbricht."""
    try:
        if pfad.is_dir():
            shutil.rmtree(pfad)
            protokoll.append(f"entfernt: {pfad}")
        elif pfad.exists():
            pfad.unlink()
            protokoll.append(f"entfernt: {pfad.name}")
        return not pfad.exists()
    except Exception as exc:
        protokoll.append(f"KONNTE NICHT ENTFERNEN: {pfad} ({exc})")
        return False


def _verdrahtet(name: str, inhalt: str) -> bool:
    """Traegt die Datei noch die Deutsch-Verdrahtung? Pro Datei ihr Anker."""
    if name == "types.ts":
        m = re.search(r"^export type Locale = (.+)$", inhalt, re.M)
        return bool(m and "'de'" in m.group(1))
    if name == "catalog.ts":
        return "./de'" in inhalt
    if name == "languages.ts":
        return "id: 'de'" in inhalt
    return False


def _sicherung_fuer(name: str) -> Path | None:
    """Nur eine nachweislich UNVERDRAHTETE Sicherung taugt zum Rueckbau.

    apply-de.py legt .aiianer-orig einmalig an und ruehrt es nie wieder an.
    .aiianer-bak wird bei jedem Lauf ueberschrieben und kann deshalb bereits
    die Verdrahtung enthalten - wer daraus wiederherstellt und danach de.ts
    loescht, hinterlaesst ein Hermes, das nicht mehr baut."""
    for endung in (".aiianer-orig", ".aiianer-bak"):
        kandidat = I18N_DIR / (name + endung)
        if not kandidat.is_file():
            continue
        try:
            if not _verdrahtet(name, kandidat.read_text()):
                return kandidat
        except Exception:
            continue
    return None


def _uninstall_german(protokoll: list) -> None:
    namen = ("types.ts", "catalog.ts", "languages.ts")

    # ERST pruefen, DANN schreiben. Andersherum waere der Rueckbau nicht
    # atomar: fehlt nur eine brauchbare Sicherung, waeren die anderen Dateien
    # bereits ueberschrieben und die Meldung "nichts veraendert" gelogen.
    quellen = {n: _sicherung_fuer(n) for n in namen}
    fehlend = [n for n, q in quellen.items() if q is None]
    if fehlend:
        raise HTTPException(
            status_code=409,
            detail=(
                "Rueckbau abgebrochen. Fuer diese Dateien gibt es keine "
                "brauchbare Sicherung des Originalzustands: "
                + ", ".join(fehlend)
                + ". Entweder fehlt sie, oder sie enthaelt selbst schon die "
                "deutsche Verdrahtung. Wuerde ich sie trotzdem einspielen und "
                "de.ts loeschen, wuerde Hermes danach nicht mehr bauen. Es "
                "wurde nichts veraendert."
            ),
        )

    for name in namen:
        _restore(quellen[name], I18N_DIR / name, protokoll)

    # Gegenprobe am Ergebnis, nicht an der Absicht.
    reste = [n for n in namen if _verdrahtet(n, (I18N_DIR / n).read_text())]
    if reste:
        raise HTTPException(
            status_code=500,
            detail=(
                "Rueckbau unvollstaendig: nach dem Wiederherstellen tragen "
                + ", ".join(reste)
                + " immer noch die deutsche Verdrahtung. de.ts wurde deshalb "
                "NICHT geloescht, damit Hermes weiter baut. Bitte in der "
                "AIIANER Community melden."
            ),
        )

    # de.ts erst jetzt, und vorher zur Sicherheit weglegen statt vernichten.
    quelle_de = I18N_DIR / "de.ts"
    if quelle_de.is_file():
        try:
            (EXT_STORE / "german-language").mkdir(parents=True, exist_ok=True)
            shutil.copy2(quelle_de, EXT_STORE / "german-language" / "de.ts.entfernt")
            protokoll.append("de.ts vor dem Entfernen weggelegt")
        except Exception as exc:
            protokoll.append(f"de.ts konnte nicht weggelegt werden: {exc}")
    _drop(quelle_de, protokoll)

    for name in namen:
        _drop(I18N_DIR / (name + ".aiianer-bak"), protokoll)
        _drop(I18N_DIR / (name + ".aiianer-orig"), protokoll)

    # Quellen des Waechters mit entfernen, sonst spielt er beim naechsten
    # Gateway-Start alles wieder ein. Schlaegt das fehl, ist das KEINE
    # Nebensache - der Aufrufer muss es erfahren.
    kritisch = []
    for pfad in (STATE_DIR / "de.ts", STATE_DIR / "apply-de.py"):
        _drop(pfad, protokoll)
        if pfad.exists():
            kritisch.append(str(pfad))
    if kritisch:
        raise HTTPException(
            status_code=500,
            detail=(
                "Die Dateien wurden zurueckgesetzt, aber diese Quellen des "
                "Waechters liessen sich nicht entfernen: "
                + ", ".join(kritisch)
                + ". Er wuerde Deutsch beim naechsten Start erneut einspielen. "
                "Bitte die Dateien von Hand loeschen."
            ),
        )


def _uninstall_bots(comp_id: str, sicherungsname: str, protokoll: list) -> None:
    sicherung = EXT_STORE / comp_id / sicherungsname
    if not sicherung.is_file():
        raise HTTPException(
            status_code=409,
            detail=(
                f"Rueckbau abgebrochen: die Sicherung {sicherungsname} fehlt unter "
                f"{EXT_STORE / comp_id}. Nichts wurde veraendert."
            ),
        )
    _restore(sicherung, BOTS_PLUGIN, protokoll)
    _drop(EXT_STORE / comp_id, protokoll)


def _uninstall_eurouter(protokoll: list) -> None:
    """Liegt ausserhalb des Hermes-Checkouts, deshalb reicht Entfernen.
    Der Start-Helfer unter ~/.local/bin/hermes bleibt bewusst liegen - er
    macht auch Reparaturen, die nichts mit dieser Komponente zu tun haben."""
    _drop(PLUGINS / "model-providers" / "eurouter", protokoll)
    protokoll.append("~/.local/bin/hermes bleibt absichtlich unberuehrt")


def _run_uninstall(comp_id: str, protokoll: list) -> None:
    if comp_id == "german-language":
        _uninstall_german(protokoll)
    elif comp_id == "bot-mode-german":
        _uninstall_bots(comp_id, "plugin.js.upstream-backup", protokoll)
    elif comp_id == "group-chat-limits":
        _uninstall_bots(comp_id, "plugin.js.backup", protokoll)
    elif comp_id == "eurouter-provider":
        _uninstall_eurouter(protokoll)
    else:
        raise HTTPException(
            status_code=404, detail=f"Kein Rueckbau bekannt fuer: {comp_id}"
        )


@router.post("/uninstall")
async def uninstall(body: dict) -> dict:
    comp_id = (body or {}).get("id", "")
    zustand = _read_state()
    if comp_id not in zustand:
        raise HTTPException(
            status_code=409, detail=f"{comp_id} ist gar nicht installiert."
        )

    protokoll: list = []
    _run_uninstall(comp_id, protokoll)

    # Erst wenn der Rueckbau durchlief, faellt der Zustandseintrag. Der
    # Waechter richtet sich danach und spielt sonst alles wieder ein.
    zustand.pop(comp_id, None)
    _write_state(zustand)

    cat = _load_catalog()
    entry = next((c for c in cat.get("components", []) if c["id"] == comp_id), None)
    # Nicht blind ok melden: was sich nicht entfernen liess, gehoert vor die
    # Augen des Nutzers, nicht nur ins Protokoll.
    warnungen = [z for z in protokoll if z.startswith("KONNTE NICHT ENTFERNEN")]
    return {
        "ok": True,
        "id": comp_id,
        "action": "uninstall",
        "log": protokoll,
        "warnings": warnungen,
        "nextSteps": _steps(comp_id, "uninstall", entry) + (
            ["Achtung, Reste sind liegengeblieben: " + "; ".join(warnungen)]
            if warnungen else []
        ),
    }


@router.post("/repair")
async def repair() -> dict:
    """Erzwingt, was der Waechter beim Start automatisch tut."""
    return _guard().repair_all()


# ---------------------------------------------------------------- Helfer

def _download(tmp: str) -> Path:
    archive = Path(tmp) / "repo.tar.gz"
    urllib.request.urlretrieve(TARBALL, archive)
    with tarfile.open(archive) as tf:
        tf.extractall(tmp)
    roots = [p for p in Path(tmp).iterdir() if p.is_dir() and p.name != "__MACOSX"]
    if not roots:
        raise HTTPException(status_code=500, detail="Archiv war leer")
    return roots[0]


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")
