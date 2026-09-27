"""AIIANER Marktplatz - Backend.

Liest den Katalog, vergleicht ihn mit dem lokal Installierten und installiert
oder aktualisiert Komponenten. Alles landet unter ~/.hermes/, nie im
Hermes-Checkout, mit einer Ausnahme: die Sprachdatei, weil Hermes keine
Laufzeit-Registrierung fuer Sprachen anbietet. Die uebernimmt der Waechter.

Routen liegen unter /api/plugins/aiianer-hub/ und damit hinter dem Auth-Gate
des Dashboards.
"""

from __future__ import annotations

import contextlib
import datetime
import json
import re
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

REPO = "oliverhees/aiianer-hermes-extensions"
TARBALL = f"https://github.com/{REPO}/archive/refs/heads/main.tar.gz"
# Der EU-Router wohnt in einem eigenen Repo. Sein install.sh ist der
# kanonische Weg; der native Windows-Weg unten holt denselben Stand als
# Tarball, weil es dort keine Bash gibt, die das Skript ausfuehren koennte.
EUROUTER_REPO = "oliverhees/hermes-eurouter-plugin"
EUROUTER_TARBALL = f"https://github.com/{EUROUTER_REPO}/archive/refs/heads/main.tar.gz"
# Bot-Mode Advanced (vormals extensions/group-chat-limits) wohnt seit
# 2026-09-27 in einem eigenen Repo, aus demselben Grund wie EU-Router:
# sein install.sh ist der kanonische Weg, der native Windows-Weg holt
# denselben Stand als Tarball.
BOTMODE_ADVANCED_REPO = "oliverhees/hermes-botmode-advanced"
BOTMODE_ADVANCED_TARBALL = f"https://github.com/{BOTMODE_ADVANCED_REPO}/archive/refs/heads/main.tar.gz"
# Hermes Backup wohnt seit 2026-09-27 in einem eigenen Repo (voller Port,
# Backend-Routen + Oberflaeche), aus demselben Grund wie die beiden oben.
BACKUP_REPO = "oliverhees/hermes-backup-plugin"
BACKUP_TARBALL = f"https://github.com/{BACKUP_REPO}/archive/refs/heads/main.tar.gz"
CATALOG_URL = f"https://raw.githubusercontent.com/{REPO}/main/catalog.json"
RELEASES_URL = f"https://api.github.com/repos/{REPO}/releases"
ROADMAP_URL = f"https://raw.githubusercontent.com/{REPO}/main/roadmap.json"

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
LOCAL_RELEASES = Path(__file__).resolve().parent.parent / "releases.json"
LOCAL_ROADMAP = Path(__file__).resolve().parent.parent / "roadmap.json"
AGENT_DIR = Path(os.environ.get("HERMES_AGENT_DIR") or (HERMES_HOME / "hermes-agent"))
BOTS_DIR = AGENT_DIR / "apps" / "desktop" / "src" / "plugins" / "hermes-bots"
BOTS_ROUNDS = BOTS_DIR / "group-rounds.ts"
DESKTOP_BUILD_STAMP = HERMES_HOME / "desktop-build-stamp.json"

# Wer apps/desktop/ selbst veraendert, muss danach den Content-Hash-Stempel
# entfernen, den Hermes Desktop fuer seine Rebuild-Entscheidung fuehrt (siehe
# hermes_cli/main_desktop.py, _stamp_is_current: SHA-256 ueber apps/desktop/,
# verglichen mit $HERMES_HOME/desktop-build-stamp.json). Sonst haelt Hermes
# Desktop die noch unveraenderte Fassung fuer aktuell und baut beim naechsten
# Start NICHT neu - "Neustart bringt nichts" ist genau dieses Muster.
DESKTOP_TOUCHING = {"group-chat-limits"}


def _invalidate_desktop_build_stamp() -> None:
    """Best-effort, wie Hermes' eigener Self-Heal es bei einem zerrissenen
    Bundle macht: fehlt der Stempel, gilt der Stand automatisch als veraltet."""
    try:
        if DESKTOP_BUILD_STAMP.is_file():
            DESKTOP_BUILD_STAMP.unlink()
    except Exception:
        pass


def _rebuild_desktop() -> dict:
    """Baut die Desktop-App JETZT neu (--build-only --force-build), statt nur
    auf den naechsten Terminal-Start zu hoffen.

    Befund aus der Community nach v1.3.35: ein normales Oeffnen ueber das
    App-Symbol startet die bereits gepackte Electron-App direkt und ruehrt
    dabei nie die Python-CLI an, die den Content-Hash-Stempel prueft - nur
    'hermes desktop'/'hermes gui' im TERMINAL tut das. Ohne diesen Schritt
    bleibt eine frisch gepatchte Sprachdatei fuer die meisten Nutzer
    unsichtbar. Dieselbe Route, die 'hermes update' intern fuer den
    Bundle-Swap benutzt. Kann mehrere zig Sekunden bis wenige Minuten
    dauern - deshalb NUR hier (interaktiver Install/Uninstall/Repair-Klick,
    Nutzer sieht einen Ladezustand), nie im passiven Waechter-Hook auf
    gateway:startup, der sonst jeden Hermes-Start ausbremsen wuerde.
    Nicht fatal bei Fehlschlag: der Stempel ist bereits entfernt, ein
    spaeterer Terminal-Start baut trotzdem neu."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "hermes_cli.main", "desktop", "--build-only", "--force-build"],
            capture_output=True, text=True, timeout=300, cwd=str(AGENT_DIR),
        )
    except Exception as exc:
        return {"rebuilt": False, "detail": str(exc)}
    return {
        "rebuilt": proc.returncode == 0,
        "detail": (proc.stdout or proc.stderr or "").strip()[-500:],
    }


EXT_STORE = HERMES_HOME / "aiianer-extensions"

# Was der Nutzer NACH einer Aktion tun muss. Bewusst hier im lokalen Code und
# nicht im Katalog: der Katalog kommt aus dem Netz, und Anweisungstexte, die
# jemand von aussen setzen kann, sind eine Einladung zum Missbrauch. Der
# Katalog darf sie ueberschreiben, muss aber nicht.
NEXT_STEPS = {
    "group-chat-limits": {
        "install": [
            "Hermes komplett beenden und neu starten. Beim ersten Start baut die App einmal neu.",
            "Grenzen ändern: ~/.hermes/aiianer/gruppen-grenzen.json bearbeiten, hier auf „Neu einspielen“, dann wieder neu starten.",
            "Voreingestellt sind 8 Runden und 40 Nachrichten für alle Räume statt Hermes' 3 und 10.",
        ],
        "uninstall": [
            "Hermes komplett beenden und neu starten. Es gelten wieder die eingebauten Grenzen.",
            "Deine gruppen-grenzen.json bleibt liegen, falls du es dir anders überlegst.",
        ],
    },
    "eurouter-provider": {
        "install": [
            "EUROUTER_API_KEY in die Datei .env im Hermes-Verzeichnis eintragen, falls noch nicht geschehen.",
            "Hermes komplett beenden und neu starten.",
            "Der EU-Router taucht dann im Modell-Auswahlmenü als eigene Gruppe auf.",
        ],
        "uninstall": [
            "Hermes komplett beenden und neu starten.",
            "Der Start-Helfer unter ~/.local/bin/hermes bleibt absichtlich liegen, weil er auch andere Reparaturen macht.",
        ],
    },
}


def _verfuegbar(comp_id: str) -> tuple:
    """Kann diese Komponente auf DIESEM Rechner installiert werden?

    Liefert (ok, grund_de, grund_en). Beide Sprachen, weil die Beschriftungen
    der Hermes-Sprache folgen: ein deutscher Absatz unter einer englischen
    Ueberschrift sieht nach Fehler aus, nicht nach Erklaerung.

    Wird vor dem Anbieten geprueft, nicht erst beim Klick. Ein Knopf, der
    zuverlaessig in einen 500er laeuft, ist schlimmer als gar kein Knopf: der
    Nutzer haelt sein System fuer kaputt statt die Komponente fuer veraltet.

    Absichtlich hier im lokalen Code und nicht im Katalog aus dem Netz - die
    Pruefung entscheidet, was auf fremden Rechnern ausgefuehrt werden darf."""
    if comp_id == "group-chat-limits":
        if not BOTS_ROUNDS.is_file():
            return (
                False,
                "Die Rundenschleife des Gruppenchats liegt nicht an der "
                f"erwarteten Stelle ({BOTS_ROUNDS}). Aktualisiere Hermes "
                "Desktop.",
                "The group chat round loop is not where it is expected "
                f"({BOTS_ROUNDS}). Update Hermes Desktop.",
            )

    # Ein Knopf, der zuverlaessig in einen 500er laeuft, ist schlimmer als
    # gar kein Knopf: Komponenten, fuer die es nur den Bash-Weg gibt, brauchen
    # auf Windows eine echte Bash (Git-Bash oder MSYS2).
    if _ist_windows() and _braucht_bash(comp_id) and _bash_binaer() is None:
        return (
            False,
            "Diese Komponente bringt einen Bash-Installer mit, auf diesem "
            "Rechner ist aber keine Bash erreichbar. Installiere Git for "
            "Windows (https://git-scm.com/download/win) und starte Hermes "
            "danach neu.",
            "This component ships a bash installer, but no bash is reachable "
            "on this machine. Install Git for Windows "
            "(https://git-scm.com/download/win), then restart Hermes.",
        )
    return (True, "", "")


def _premium_berechtigt(entry: dict) -> tuple[bool, str, str]:
    """Premium-Komponenten nur fuer Community-Mitglieder mit Aktivierung.

    Lesart der Mitgliedschaftsdatei ~/.hermes/aiianer/mitgliedschaft.json:
    {"level": "mitglied" | "wartung", "gueltigBis": "YYYY-MM-DD"}.
    Fehlt die Datei, ist sie ungueltig oder abgelaufen, sperrt die
    Komponente mit einer freundlichen Meldung. Kein rätselhafter Fehler,
    sondern der klare Hinweis, wo es langgeht.
    """
    if not entry.get("premium"):
        return (True, "", "")
    datei = STATE_DIR / "mitgliedschaft.json"
    try:
        mit = json.loads(datei.read_text(encoding="utf-8"))
        level = mit.get("level", "")
        gueltig_bis = mit.get("gueltigBis", "")
        if level in ("mitglied", "wartung") and gueltig_bis:
            jahr, monat, tag = (int(x) for x in gueltig_bis.split("-")[:3])
            if datetime.date(jahr, monat, tag) >= datetime.date.today():
                return (True, "", "")
    except Exception:
        pass
    return (
        False,
        "Diese Komponente ist exklusiv fuer AIIANER-Community-Mitglieder. "
        "Mitglied werden: https://aiianer.de",
        "This component is exclusive to AIIANER community members. "
        "Become a member: https://aiianer.de",
    )


def _steps(comp_id: str, aktion: str, entry: dict | None = None) -> list:
    """Katalog darf ueberschreiben, sonst der lokale Standard."""
    vom_katalog = (entry or {}).get("nextSteps", {}).get(aktion)
    if isinstance(vom_katalog, list) and vom_katalog:
        return [str(x) for x in vom_katalog]
    return NEXT_STEPS.get(comp_id, {}).get(aktion, [])


# ---------------------------------------------------------------- Zustand

@contextlib.contextmanager
def _state_lock():
    """Lesen-Aendern-Schreiben auf installed.json muss unter einer Sperre
    laufen. Ohne sie verliert bei zwei gleichzeitigen Aktionen einer der
    beiden Eintraege: die Komponente liegt dann auf der Platte, aber der
    Zustand kennt sie nicht - der Waechter meldet not-installed und ein
    spaeteres Deinstallieren wird mit 409 abgelehnt. Die Komponente waere
    nicht mehr sauber zu entfernen.

    fcntl gibt es auf Windows nicht; dort laeuft es ohne Sperre weiter,
    statt den Dienst zu verweigern."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    sperre = STATE_DIR / "installed.lock"
    try:
        import fcntl
    except ImportError:
        yield
        return
    with open(sperre, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def _local_plugin_version(comp_id: str, state: dict) -> str | None:
    """Liest die Version des Marktplatzes auch bei älteren Installationen.

    Frühe Installerstände haben den eigenen Eintrag noch nicht in
    installed.json geschrieben. Das lokale Manifest ist dafür die belastbare
    Quelle, damit der Marktplatz nicht fälschlich als "nicht installiert"
    erscheint.
    """
    if comp_id != "aiianer-hub":
        return state.get(comp_id, {}).get("version")
    manifest = HERMES_HOME / "plugins" / "aiianer-hub" / "plugin.yaml"
    try:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return state.get(comp_id, {}).get("version")


def _write_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    # Erst daneben schreiben, dann umbenennen: ein Abbruch mittendrin darf
    # keine halbe JSON-Datei hinterlassen.
    tmp = STATE_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    tmp.replace(STATE_FILE)


def _load_catalog() -> dict:
    """Katalog aus dem Netz, mit der mitgelieferten Fassung als Rueckfall."""
    try:
        with urllib.request.urlopen(CATALOG_URL, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return json.loads(LOCAL_CATALOG.read_text())


def _normalize_releases(payload: object) -> list[dict]:
    """Reduziert GitHub-Antworten auf sichere, UI-taugliche Release-Daten."""
    raw_items = payload.get("releases", []) if isinstance(payload, dict) else payload
    if not isinstance(raw_items, list):
        raise ValueError("GitHub-Releases haben kein gültiges Listenformat")

    releases = []
    for item in raw_items[:12]:
        if not isinstance(item, dict):
            continue
        tag = item.get("tag_name", item.get("tagName", ""))
        if not isinstance(tag, str) or not tag.strip():
            continue
        body = item.get("body", "")
        name = item.get("name", tag)
        published = item.get("published_at", item.get("publishedAt", ""))
        url = item.get("html_url", item.get("url", ""))
        releases.append({
            "tagName": tag.strip()[:80],
            "name": str(name or tag).strip()[:180],
            "body": str(body or "")[:12000],
            "publishedAt": str(published or "")[:80],
            "url": str(url or "")[:500],
        })
    return releases


def _load_releases() -> tuple[list[dict], str]:
    """Lädt veröffentlichte GitHub-Releases; lokale Release-Datei ist Rückfall."""
    request = urllib.request.Request(RELEASES_URL, headers={"Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=8) as resp:
            github_releases = _normalize_releases(json.loads(resp.read().decode("utf-8")))
            if github_releases:
                return github_releases, "github"
    except Exception:
        pass
    return _normalize_releases(json.loads(LOCAL_RELEASES.read_text(encoding="utf-8"))), "lokal"


def _normalize_roadmap(payload: object) -> list[dict]:
    """Reduziert Roadmap-Daten auf sichere, UI-taugliche Einträge."""
    raw_items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(raw_items, list):
        raise ValueError("Roadmap hat kein gültiges Listenformat")
    items = []
    for item in raw_items[:20]:
        if not isinstance(item, dict) or not str(item.get("id", "")).strip():
            continue
        items.append({
            "id": str(item["id"]).strip()[:80],
            "name": str(item.get("name", item["id"])).strip()[:180],
            "status": str(item.get("status", "geplant")).strip()[:40],
            "summary": str(item.get("summary", "")).strip()[:1000],
            "value": str(item.get("value", "")).strip()[:1000],
            "link": str(item.get("link", "")).strip()[:500],
        })
    return items


def _load_roadmap() -> tuple[list[dict], str]:
    """Lädt die Roadmap aus GitHub; lokale Fassung ist Rückfall."""
    request = urllib.request.Request(ROADMAP_URL, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=8) as resp:
            items = _normalize_roadmap(json.loads(resp.read().decode("utf-8")))
            if items:
                return items, "github"
    except Exception:
        pass
    return _normalize_roadmap(json.loads(LOCAL_ROADMAP.read_text(encoding="utf-8"))), "lokal"


def _atomic_copy(source: Path, target: Path) -> None:
    """Schreibt eine Datei erst neben ihr und schaltet sie dann atomar sichtbar.

    Der Desktop-Watcher darf beim Hub-Update niemals eine halb geschriebene
    JavaScript-Datei importieren. ``replace`` ist auf allen unterstützten
    Plattformen für Dateien atomar; die neue Datei erscheint mit einem Schlag.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".neu")
    shutil.copy2(source, temporary)
    temporary.replace(target)


def _install_hub_from_root(source: Path) -> None:
    """Installiert den Marktplatz aus dem Root eines Hybrid-Git-Plugins.

    Ein Hybrid-Plugin besitzt genau eine kanonische Desktop-Quelle unter
    ``plugins/aiianer-hub/desktop``. Die frühere zweite Kopie unter
    ``desktop-plugins`` konnte beim Hot-Reload gegen den neuen Stand gewinnen.
    Alle Backend-Dateien werden vor dem Desktop-Einstieg atomar geschaltet; der
    Watcher sieht daher erst dann eine neue UI, wenn ihr Backend vollständig
    bereitliegt.
    """
    agent_target = PLUGINS / "aiianer-hub"
    legacy_desktop_target = HERMES_HOME / "desktop-plugins" / "aiianer-hermes-extensions"
    hook_target = HERMES_HOME / "hooks" / "aiianer-guard"
    files = (
        ("plugin.yaml", agent_target / "plugin.yaml"),
        ("__init__.py", agent_target / "__init__.py"),
        ("catalog.json", agent_target / "catalog.json"),
        ("releases.json", agent_target / "releases.json"),
        ("guard_check.py", agent_target / "guard_check.py"),
        ("dashboard/manifest.json", agent_target / "dashboard" / "manifest.json"),
        ("dashboard/plugin_api.py", agent_target / "dashboard" / "plugin_api.py"),
        ("dashboard/dist/index.js", agent_target / "dashboard" / "dist" / "index.js"),
        ("guard/HOOK.yaml", hook_target / "HOOK.yaml"),
        ("guard/handler.py", hook_target / "handler.py"),
    )
    desktop_source = source / "desktop" / "plugin.js"
    desktop_target = agent_target / "desktop" / "plugin.js"
    missing = [relative for relative, _ in files if not (source / relative).is_file()]
    if not desktop_source.is_file():
        missing.append("desktop/plugin.js")
    if missing:
        raise HTTPException(
            status_code=500,
            detail="Der heruntergeladene Hub ist unvollständig: " + ", ".join(missing),
        )

    # Backend zuerst, den beobachteten Desktop-Einstieg zuletzt. So ist ein
    # Watcher-Reload immer ein Wechsel von komplett-alt zu komplett-neu.
    for relative, target in files:
        _atomic_copy(source / relative, target)
    _atomic_copy(desktop_source, desktop_target)

    # Nur unseren historischen, eindeutigen Doppelpfad entfernen. Das ist kein
    # allgemeines Aufräumen fremder Plugins, sondern beendet die alte Race-Quelle.
    if legacy_desktop_target.exists():
        shutil.rmtree(legacy_desktop_target)


# ---------------------------------------------------------------- Backup
#
# Die eigentliche Backup-Funktion (Einstellungen, Ordner-Browser, Archive,
# Wiederherstellung) ist seit 2026-09-27 ein eigenstaendiges Plugin:
# https://github.com/oliverhees/hermes-backup-plugin
# Hier bleibt nur, was der Rueckbau (_uninstall_backup) tatsaechlich noch
# braucht: den Cron-Job finden/pausieren und den Zustand lesen/schreiben.
# Die Installations-Routen, Validierung und HTTP-Endpunkte leben jetzt
# ausschliesslich im neuen Repo.

def _backup_state_file() -> Path: return STATE_DIR / "backup-state.json"
def _backup_runner() -> Path: return HERMES_HOME / "scripts" / "aiianer-backup-runner.py"

def _backup_state() -> dict:
    try:
        value = json.loads(_backup_state_file().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {"schemaVersion": 1, "enabled": False, "target_dir": "", "schedule": "manual", "retention": {"enabled": False, "keep": 5}, "state": "never_run", "lastRun": None, "lastArchive": None, "lastErrorCode": None}

def _backup_save(value: dict) -> None:
    _write_json_atomic(_backup_state_file(), value)

def _write_json_atomic(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(value, fh, indent=2, sort_keys=True); fh.write("\n"); fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass


def _backup_cron_job() -> tuple[str, str] | None:
    try:
        listed = subprocess.run([shutil.which("hermes") or "hermes", "cron", "list", "--all"], capture_output=True, text=True, timeout=30, shell=False, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("CRON_SETUP_FAILED") from exc
    if listed.returncode != 0: raise RuntimeError("CRON_SETUP_FAILED")
    matches = list(re.finditer(r"(?m)^[ \t]*([0-9a-f]{12}) \[(active|paused)\]", listed.stdout or ""))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(listed.stdout or "")
        if re.search(r"(?m)^[ \t]*Name:[ \t]+aiianer-backup[ \t]*$", (listed.stdout or "")[match.start():end]): return match.group(1), match.group(2)
    return None


def _backup_cron_id() -> str | None:
    job = _backup_cron_job()
    return job[0] if job else None


def _pause_backup_cron() -> None:
    job_id = _backup_cron_id()
    if not job_id: return
    try:
        result = subprocess.run([shutil.which("hermes") or "hermes", "cron", "pause", job_id], capture_output=True, text=True, timeout=30, shell=False, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("CRON_SETUP_FAILED") from exc
    if result.returncode != 0: raise RuntimeError("CRON_SETUP_FAILED")


# ---------------------------------------------------------------- Routen

@router.get("/catalog")
async def catalog() -> dict:
    """Katalog plus lokaler Zustand pro Komponente."""
    cat = _load_catalog()
    state = _read_state()
    items = []
    for c in cat.get("components", []):
        local = state.get(c["id"], {})
        installed = _local_plugin_version(c["id"], state)
        ok, grund, grund_en = _verfuegbar(c["id"])
        prem_ok, prem_grund, prem_grund_en = _premium_berechtigt(c)
        if not prem_ok:
            ok = False
            grund = prem_grund
            grund_en = prem_grund_en
        items.append(
            {
                **c,
                "installed": installed,
                "installedAt": local.get("at"),
                "selfManaged": c["id"] == "aiianer-hub",
                "nextSteps": _steps(c["id"], "install", c),
                "uninstallSteps": _steps(c["id"], "uninstall", c),
                "available": ok,
                "unavailableReason": grund,
                "unavailableReasonEn": grund_en,
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


@router.get("/releases")
async def releases() -> dict:
    """Versionierte GitHub-Hinweise, mit lokaler Fassung für Offline-Betrieb."""
    items, source = _load_releases()
    return {"releases": items, "source": source}


@router.get("/roadmap")
async def roadmap() -> dict:
    """Geplante Marktplatz-Erweiterungen aus GitHub, mit lokalem Rückfall."""
    items, source = _load_roadmap()
    return {"items": items, "source": source}


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


@router.get("/diagnostics")
async def diagnostics() -> dict:
    """Copy-paste-fertiger Text-Report fuer ein GitHub-Issue. Derselbe Report
    laeuft auch direkt im Terminal, ohne Dashboard: 'python3 guard_check.py
    diagnostics' - wichtig genau dann, wenn die GUI selbst das Problem ist."""
    return {"report": _guard().diagnostics()}


# ------------------------------------------------- Installer je Plattform

# Die Installer der Erweiterungen sind Bash-Skripte. Auf Linux und macOS ist
# das der kurze Weg. Auf Windows ist es ein Irrweg, aus zwei Gruenden:
#
#   1. Dort gibt es meist ueberhaupt keine Bash. Der Aufruf endet dann in
#      einem nackten WinError 2 und die Oberflaeche zeigt einen 500er.
#   2. Und wenn doch eine da ist (Git-Bash, MSYS2), dann bekommt sie von
#      Python einen nativen Windows-Pfad. Fuer eine Bash ist der Backslash
#      ein Fluchtzeichen, also wird aus
#      C:\Users\...\Temp\tmp1234\extensions\group-chat-limits\install.sh
#      beim Einlesen C:Users...install.sh - und sie meldet
#      "No such file or directory" fuer eine Datei, die sehr wohl da liegt.
#      Genau dieser Fehler kam aus der Community (Windows 11, MSYS2-Bash).
#
# Darum bekommt Windows einen eigenen, nativen Weg: dieselben Schritte in
# Python, mit sys.executable als Interpreter fuer die apply-*.py-Patcher.
# Kein bash, kein python3, kein gzip, kein cp im PATH noetig. Genau so
# arbeitet der Waechter (guard_check.repair_*) schon heute - nur der Knopf
# im Marktplatz tat es noch nicht.
#
# WICHTIG: Ein nativer Installer unten und die install.sh seiner Erweiterung
# muessen dieselben Schritte tun. Wer das eine aendert, aendert auch das
# andere. tests/test_plugin_api_windows_install.py haelt die Schritte fest.


def _ist_windows() -> bool:
    """Eine Stelle fuer die Plattformfrage. So ist der Windows-Weg auch auf
    einem Linux-Rechner pruefbar, ohne os.name im ganzen Prozess zu biegen."""
    return os.name == "nt"


def _posix_pfad(pfad) -> str:
    """Pfad in der Schreibweise, die eine Git-/MSYS2-Bash versteht.

    'C:/Users/...' loest eine MSYS2-Bash korrekt auf, 'C:\\Users\\...' nicht."""
    return str(pfad).replace("\\", "/")


def _bash_binaer() -> str | None:
    """Welche Bash darf einen Installer ausfuehren?

    Auf Windows ist shutil.which("bash") eine Falle: es findet zuerst
    C:\\Windows\\System32\\bash.exe, den Starter fuer das Linux-Subsystem. Der
    sieht ein voellig anderes Dateisystem - der Installer wuerde scheinbar
    durchlaufen und am Hermes der Nutzerin nichts aendern. Deshalb auf
    Windows nur Git-Bash und MSYS2, und System32 ausdruecklich nicht."""
    gefunden = shutil.which("bash")
    if not _ist_windows():
        # Wenn PATH mager ist (Dienst-Umgebung), liegt sie trotzdem dort.
        if gefunden is None and Path("/bin/bash").is_file():
            return "/bin/bash"
        return gefunden
    kandidaten: list[str] = []
    if gefunden and Path(gefunden).parent.name.lower() != "system32":
        kandidaten.append(gefunden)
    for basis in (
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("ProgramFiles(x86)", ""),
        os.environ.get("LOCALAPPDATA", ""),
    ):
        if basis:
            kandidaten.append(str(Path(basis) / "Git" / "bin" / "bash.exe"))
            kandidaten.append(str(Path(basis) / "Programs" / "Git" / "bin" / "bash.exe"))
    kandidaten.append(r"C:\msys64\usr\bin\bash.exe")
    for kandidat in kandidaten:
        if Path(kandidat).is_file():
            return kandidat
    return None


def _installer_umgebung() -> dict:
    """Umgebung fuer einen Bash-Installer.

    HERMES_HOME und HERMES_AGENT_DIR in Posix-Schreibweise: sonst setzt die
    Bash daraus Pfade mit Backslashes zusammen und greift ins Leere. Auf
    Linux und macOS ist das eine Kopie derselben Werte, die auch hermes_home()
    liefert - dort aendert sich also nichts."""
    env = dict(os.environ)
    env["HERMES_HOME"] = _posix_pfad(HERMES_HOME)
    env["HERMES_AGENT_DIR"] = _posix_pfad(AGENT_DIR)
    return env


def _ext_store(comp_id: str) -> Path:
    """Dauerablage der Payload - dieselbe Stelle, die auch die install.sh
    benutzen ($HERMES_HOME/aiianer-extensions/<id>)."""
    return HERMES_HOME / "aiianer-extensions" / comp_id


def _protokoll(text: str) -> list[str]:
    return [z for z in (text or "").splitlines() if z.strip()]


def _run_patcher(patcher: Path, argumente: list[str], cwd: Path) -> list[str]:
    """Fuehrt einen apply-*.py-Patcher mit DEM Python aus, das schon laeuft.

    Kein "python3" im PATH noetig - auf Windows gibt es das naemlich nicht."""
    try:
        proc = subprocess.run(
            [sys.executable, str(patcher), *argumente],
            capture_output=True, text=True, timeout=180, cwd=str(cwd), shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=500, detail=f"{patcher.name}: {exc}") from exc
    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=(proc.stderr or proc.stdout or f"{patcher.name} fehlgeschlagen")[-800:],
        )
    return _protokoll(proc.stdout)


def _run_bash_installer(comp_id: str, src: Path) -> list[str]:
    installer = src / "install.sh"
    if not installer.is_file():
        raise HTTPException(status_code=500, detail=f"{comp_id} hat kein install.sh")
    with contextlib.suppress(OSError):
        os.chmod(installer, 0o755)
    bash = _bash_binaer()
    if bash is None:
        raise HTTPException(
            status_code=500,
            detail=(
                f"{comp_id} braucht eine Bash, auf diesem Rechner ist keine "
                "erreichbar. Unter Windows hilft Git for Windows "
                "(https://git-scm.com/download/win), danach Hermes neu starten."
            ),
        )
    # Der Dateiname wird RELATIV uebergeben, der Ordner ueber cwd gesetzt.
    # Damit sieht die Bash nie einen Windows-Pfad mit Backslashes und kann
    # ihn auch nicht falsch auflösen.
    try:
        proc = subprocess.run(
            [bash, "./install.sh"],
            capture_output=True, text=True, timeout=180, cwd=str(src),
            env=_installer_umgebung(), shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise HTTPException(status_code=500, detail=f"{comp_id}: {exc}") from exc
    if proc.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=(proc.stderr or proc.stdout or "Installation fehlgeschlagen")[-800:],
        )
    return _protokoll(proc.stdout)[-12:]


def _install_limits_native(_src: Path) -> list[str]:
    """Schritte aus install.sh des Bot-Mode-Advanced-Repos, ohne Bash.

    Die Payload liegt seit 2026-09-27 im eigenen Repo
    (siehe BOTMODE_ADVANCED_REPO oben), nicht mehr unter
    extensions/group-chat-limits/ in diesem Repo. Sie wird deshalb frisch
    geladen, derselbe Stand, den auch das dortige install.sh zieht."""
    if not BOTS_ROUNDS.is_file():
        raise HTTPException(
            status_code=500,
            detail=(
                "Rundenschleife des Gruppenchats nicht gefunden unter "
                f"{BOTS_ROUNDS}. Ist Hermes Desktop installiert und aktuell?"
            ),
        )
    tmp = tempfile.mkdtemp(prefix="aiianer-botmode-advanced-")
    try:
        try:
            wurzel = _download_tarball(BOTMODE_ADVANCED_TARBALL, tmp)
        except HTTPException:
            raise
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Bot-Mode Advanced konnte nicht geladen werden: {exc}",
            ) from exc
        dateien = ("aiianer-group-limits.ts", "apply-limits.py", "gruppen-grenzen.beispiel.json")
        fehlend = [n for n in dateien if not (wurzel / n).is_file()]
        if fehlend:
            raise HTTPException(
                status_code=500,
                detail="Das Bot-Mode-Advanced-Repo ist unvollständig, es fehlt: " + ", ".join(fehlend),
            )
        store = _ext_store("group-chat-limits")
        store.mkdir(parents=True, exist_ok=True)
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        log: list[str] = []
        # Beispiel-Konfiguration anlegen, aber niemals eine vorhandene ueberschreiben.
        konfig = STATE_DIR / "gruppen-grenzen.json"
        if not konfig.is_file():
            shutil.copy2(wurzel / "gruppen-grenzen.beispiel.json", konfig)
            log.append(f"Beispiel-Konfiguration angelegt: {konfig}")
        for name in dateien:
            _atomic_copy(wurzel / name, store / name)
        for name in ("aiianer-group-limits.ts", "apply-limits.py"):
            _atomic_copy(wurzel / name, STATE_DIR / name)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return log + _run_patcher(
        store / "apply-limits.py", [str(AGENT_DIR), str(STATE_DIR)], store
    )


def _install_backup_native(_src: Path) -> list[str]:
    """Schritte aus install.sh des Backup-Repos, ohne Bash.

    Die Payload liegt seit 2026-09-27 im eigenen Repo (BACKUP_REPO oben),
    nicht mehr unter extensions/aiianer-backup/ in diesem Repo. Installiert
    nur die Agent-Halfte (Runner-Skript); die Desktop-/Dashboard-Halften
    holt sich der Nutzer ueber das Repo-eigene install.sh, weil der native
    Windows-Weg hier nur den ohne-Bash-kritischen Teil abdeckt (Cron braucht
    ohnehin die echte hermes-CLI)."""
    tmp = tempfile.mkdtemp(prefix="aiianer-backup-plugin-")
    try:
        try:
            wurzel = _download_tarball(BACKUP_TARBALL, tmp)
        except HTTPException:
            raise
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Hermes Backup konnte nicht geladen werden: {exc}",
            ) from exc
        quelle = wurzel / "scripts" / "backup_runner.py"
        if not quelle.is_file():
            raise HTTPException(
                status_code=500,
                detail="Das Backup-Repo ist unvollständig, es fehlt: scripts/backup_runner.py",
            )
        ziel = HERMES_HOME / "scripts" / "aiianer-backup-runner.py"
        ziel.parent.mkdir(parents=True, exist_ok=True)
        _atomic_copy(quelle, ziel)
        with contextlib.suppress(OSError):
            os.chmod(ziel, 0o755)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    zustand = STATE_DIR / "backup-state.json"
    if not zustand.exists():
        _write_json_atomic(zustand, {
            "schemaVersion": 1, "enabled": False, "target_dir": "",
            "schedule": "manual", "retention": {"enabled": False, "keep": 5},
            "state": "never_run", "lastRun": None, "lastArchive": None,
            "lastErrorCode": None,
        })
    return [
        f"Backup-Runner installiert nach {ziel}. Vollstaendige Einrichtung "
        "(Oberflaeche, Zeitplan) ueber das eigene install.sh von "
        f"{BACKUP_REPO}."
    ]


def _eurouter_cache_leeren() -> list[str]:
    """Der Modell-Listen-Cache hat eine Stunde TTL. Bleibt der alte Eintrag
    stehen, wirkt ein Update bis zu einer Stunde lang "wie nicht passiert"."""
    cache = HERMES_HOME / "provider_models_cache.json"
    if not cache.is_file():
        return []
    try:
        daten = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(daten, dict) or daten.pop("eurouter", None) is None:
        return []
    _write_json_atomic(cache, daten)
    return ["Modell-Listen-Cache für eurouter geleert."]


def _install_eurouter_native(_src: Path) -> list[str]:
    """Schritte aus install.sh des EU-Router-Repos, ohne Bash.

    Das Skript dort ist der kanonische Weg und bleibt es auf Linux und macOS.
    Es tut genau drei Dinge, die hier nachgebaut sind: die beiden
    Provider-Dateien nach $HERMES_HOME/plugins/model-providers/eurouter
    kopieren, ein altes __pycache__ wegräumen und den Modell-Listen-Cache
    leeren. Der Shim unter ~/.local/bin/hermes gehoert NICHT dazu - den
    installiert nur '--with-shim', und der Marktplatz ruft ohne Argumente auf.

    Die Payload liegt im EU-Router-Repo, nicht in diesem hier. Sie wird
    deshalb frisch geladen - derselbe Stand, den auch das install.sh zieht."""
    if not HERMES_HOME.is_dir():
        raise HTTPException(
            status_code=500,
            detail=f"{HERMES_HOME} existiert nicht. Ist Hermes installiert?",
        )
    tmp = tempfile.mkdtemp(prefix="aiianer-eurouter-")
    try:
        try:
            wurzel = _download_tarball(EUROUTER_TARBALL, tmp)
        except HTTPException:
            raise
        except OSError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"EU-Router konnte nicht geladen werden: {exc}",
            ) from exc
        quelle = wurzel / "model-providers" / "eurouter"
        dateien = ("__init__.py", "plugin.yaml")
        fehlend = [n for n in dateien if not (quelle / n).is_file()]
        if fehlend:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Das EU-Router-Repo ist unvollständig, es fehlt: "
                    + ", ".join(fehlend)
                ),
            )
        ziel = PLUGINS / "model-providers" / "eurouter"
        ziel.mkdir(parents=True, exist_ok=True)
        for name in dateien:
            _atomic_copy(quelle / name, ziel / name)
        # Ein altes __pycache__ kann eine ersetzte Datei ueberleben.
        shutil.rmtree(ziel / "__pycache__", ignore_errors=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return [f"EU-Router-Plugin installiert nach {ziel}"] + _eurouter_cache_leeren()


# Erweiterungen, die ohne Bash installiert werden koennen. Jede Funktion hier
# baut die Schritte der zugehoerigen install.sh nach - nicht mehr und nicht
# weniger.
NATIVE_INSTALLER = {
    "group-chat-limits": _install_limits_native,
    "aiianer-backup": _install_backup_native,
    "eurouter-provider": _install_eurouter_native,
}


def _braucht_bash(comp_id: str) -> bool:
    """Gibt es fuer diese Komponente nur den Bash-Weg?"""
    return comp_id not in NATIVE_INSTALLER and comp_id != "aiianer-hub"


def _run_extension_installer(comp_id: str, src: Path) -> list[str]:
    """Auf Windows nativ, wo es einen nativen Weg gibt - sonst per Bash.

    Auf Linux und macOS bleibt der eingespielte Bash-Weg der Standard: er
    laeuft dort seit Monaten und ist die Fassung, die Nutzer auch von Hand
    starten."""
    nativ = NATIVE_INSTALLER.get(comp_id)
    if nativ is not None and _ist_windows():
        return nativ(src)
    return _run_bash_installer(comp_id, src)


@router.post("/install")
async def install(body: dict) -> dict:
    comp_id = (body or {}).get("id", "")
    cat = _load_catalog()
    entry = next((c for c in cat.get("components", []) if c["id"] == comp_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Unbekannte Komponente: {comp_id}")

    # Auch der direkte Aufruf wird abgefangen, nicht nur der Knopf.
    ok, grund, _ = _verfuegbar(comp_id)
    if not ok:
        raise HTTPException(status_code=409, detail=grund)

    prem_ok, prem_grund, _ = _premium_berechtigt(entry)
    if not prem_ok:
        raise HTTPException(status_code=403, detail=prem_grund)

    previous_version = _local_plugin_version(comp_id, _read_state())

    # Kein TemporaryDirectory-Kontext: unter Windows kann das Aufraeumen an
    # einer noch gehaltenen Datei scheitern (Virenscanner, Indexdienst). Das
    # wuerde eine bereits gelungene Installation als 500er ausgeben - der
    # Nutzer haelt dann sein System fuer kaputt, obwohl alles sitzt.
    tmp = tempfile.mkdtemp(prefix="aiianer-install-")
    try:
        root = _download(tmp, cat)
        install_log: list[str]
        if comp_id == "aiianer-hub":
            _install_hub_from_root(root)
            install_log = ["AIIANER EXTENSION HUB aus dem Repository-Root aktualisiert"]
        else:
            src = root / "extensions" / comp_id
            if not src.is_dir():
                raise HTTPException(
                    status_code=500, detail=f"{comp_id} fehlt im heruntergeladenen Repo"
                )
            install_log = _run_extension_installer(comp_id, src)[-12:]

            if comp_id in DESKTOP_TOUCHING:
                _invalidate_desktop_build_stamp()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    with _state_lock():
        state = _read_state()
        vorher = previous_version
        state[comp_id] = {"version": entry["version"], "at": _now()}
        _write_state(state)

    next_steps = _steps(comp_id, "install", entry)
    rebuild = None
    if comp_id in DESKTOP_TOUCHING:
        rebuild = _rebuild_desktop()
        # Die vorhandenen Schritte unangetastet lassen (jede Komponente
        # formuliert sie unterschiedlich) und nur ergaenzen, statt zu raten,
        # welche Zeile "baut sich neu" meint und ersetzt werden muesste.
        if rebuild["rebuilt"]:
            next_steps = next_steps + [
                "Die Desktop-App wurde bereits automatisch neu gebaut, ein normaler Neustart reicht.",
            ]
        else:
            next_steps = next_steps + [
                "Automatischer Neubau der Desktop-App hat nicht geklappt. Bitte einmal "
                "'hermes desktop' in einem Terminal ausfuehren, das baut dann nach.",
            ]
    return {
        "ok": True,
        "id": comp_id,
        "action": "update" if vorher else "install",
        "version": entry["version"],
        "previousVersion": vorher,
        "log": install_log,
        "nextSteps": next_steps,
        "desktopRebuild": rebuild,
        # Der Hub ersetzt bei einem Self-Update seinen eigenen Python-Code.
        # Der laufende Gateway-Prozess hat diesen aber schon importiert und
        # muss daher kontrolliert neu gestartet werden.
        "requiresGatewayRestart": comp_id == "aiianer-hub",
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


def _uninstall_group_limits(protokoll: list) -> None:
    """Rueckbau der Gruppenchat-Grenzen. Nur die Erstsicherung zaehlt: die
    Naht wieder herauszuschneiden waere Rateroulette, die Sicherung ist der
    Stand von vor dem Eingriff."""
    if not BOTS_ROUNDS.is_file():
        raise HTTPException(
            status_code=409,
            detail="Die Rundenschleife liegt nicht mehr da. Es wurde nichts veraendert.",
        )
    orig = BOTS_ROUNDS.with_suffix(".ts.aiianer-orig")
    if not orig.is_file() or "aiianerCaps(group)" in orig.read_text():
        raise HTTPException(
            status_code=409,
            detail=(
                "Keine brauchbare Erstsicherung der Rundenschleife gefunden. "
                "Ohne sie laesst sich der Originalzustand nicht sauber "
                "herstellen. Es wurde nichts veraendert."
            ),
        )
    _restore(orig, BOTS_ROUNDS, protokoll)
    if "aiianerCaps(group)" in BOTS_ROUNDS.read_text():
        raise HTTPException(
            status_code=500,
            detail="Nach dem Wiederherstellen steckt die Naht immer noch drin.",
        )
    _drop(BOTS_ROUNDS.with_suffix(".ts.aiianer-bak"), protokoll)
    _drop(orig, protokoll)
    _drop(BOTS_DIR / "aiianer-group-limits.ts", protokoll)
    _drop(BOTS_DIR / "aiianer-group-limits.data.ts", protokoll)
    kritisch = []
    for pfad in (STATE_DIR / "apply-limits.py", STATE_DIR / "aiianer-group-limits.ts"):
        _drop(pfad, protokoll)
        if pfad.exists():
            kritisch.append(str(pfad))
    _drop(EXT_STORE / "group-chat-limits", protokoll)
    # gruppen-grenzen.json bleibt absichtlich liegen: das ist die Arbeit des
    # Nutzers, nicht unsere Installation.
    protokoll.append("gruppen-grenzen.json bleibt erhalten")
    if kritisch:
        raise HTTPException(
            status_code=500,
            detail=(
                "Zurueckgesetzt, aber diese Quellen des Waechters blieben liegen: "
                + ", ".join(kritisch)
            ),
        )


def _uninstall_eurouter(protokoll: list) -> None:
    """Liegt ausserhalb des Hermes-Checkouts, deshalb reicht Entfernen.
    Der Start-Helfer unter ~/.local/bin/hermes bleibt bewusst liegen - er
    macht auch Reparaturen, die nichts mit dieser Komponente zu tun haben."""
    _drop(PLUGINS / "model-providers" / "eurouter", protokoll)
    protokoll.append("~/.local/bin/hermes bleibt absichtlich unberuehrt")


def _uninstall_backup(protokoll: list) -> None:
    """Entfernt den lokalen Runner, aber niemals externe Backup-Archive."""
    try:
        _pause_backup_cron()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Backup-Rückbau abgebrochen: der Zeitplan ließ sich nicht pausieren: {exc}",
        ) from exc

    runner = _backup_runner()
    _drop(runner, protokoll)
    if runner.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Backup-Rückbau unvollständig: {runner} ließ sich nicht entfernen.",
        )

    # Konfiguration und Laufhistorie bleiben für eine spätere Neuinstallation
    # erhalten; der Zeitplan ist aber sicher aus, solange der Runner fehlt.
    state = _backup_state()
    state["enabled"] = False
    state["schedule"] = "manual"
    _backup_save(state)
    protokoll.append("Backup-Zeitplan pausiert und lokaler Runner entfernt")
    protokoll.append("Externe Backup-Archive und Laufhistorie bleiben erhalten")


def _run_uninstall(comp_id: str, protokoll: list) -> None:
    if comp_id == "group-chat-limits":
        _uninstall_group_limits(protokoll)
    elif comp_id == "eurouter-provider":
        _uninstall_eurouter(protokoll)
    elif comp_id == "aiianer-backup":
        _uninstall_backup(protokoll)
    else:
        raise HTTPException(
            status_code=404, detail=f"Kein Rueckbau bekannt fuer: {comp_id}"
        )


@router.post("/uninstall")
async def uninstall(body: dict) -> dict:
    comp_id = (body or {}).get("id", "")
    if comp_id == "aiianer-hub":
        raise HTTPException(
            status_code=409,
            detail="Der AIIANER Marktplatz kann nicht über sich selbst deinstalliert werden.",
        )
    protokoll: list = []
    with _state_lock():
        zustand = _read_state()
        if comp_id not in zustand:
            raise HTTPException(
                status_code=409, detail=f"{comp_id} ist gar nicht installiert."
            )

        _run_uninstall(comp_id, protokoll)
        if comp_id in DESKTOP_TOUCHING:
            _invalidate_desktop_build_stamp()

        # Der eigentliche Neubau (kann Minuten dauern) laeuft bewusst NICHT
        # hier drin - sonst haelt er die Zustandssperre fuer jede andere
        # gleichzeitige Install/Uninstall/Repair-Anfrage blockiert.
        # Erst wenn der Rueckbau durchlief, faellt der Zustandseintrag. Der
        # Waechter richtet sich danach und spielt sonst alles wieder ein.
        # Frisch lesen: unter der Sperre kann sich zwischenzeitlich nichts
        # geaendert haben, aber so bleibt die Regel "lesen, aendern,
        # schreiben in einem Zug" sichtbar.
        zustand = _read_state()
        zustand.pop(comp_id, None)
        _write_state(zustand)

    rebuild = _rebuild_desktop() if comp_id in DESKTOP_TOUCHING else None

    cat = _load_catalog()
    entry = next((c for c in cat.get("components", []) if c["id"] == comp_id), None)
    next_steps = _steps(comp_id, "uninstall", entry)
    if rebuild is not None:
        next_steps = next_steps + (
            ["Die Desktop-App wurde bereits automatisch neu gebaut, ein normaler Neustart reicht."]
            if rebuild["rebuilt"] else
            ["Automatischer Neubau der Desktop-App hat nicht geklappt. Bitte einmal "
             "'hermes desktop' in einem Terminal ausfuehren, das baut dann nach."]
        )
    # Nicht blind ok melden: was sich nicht entfernen liess, gehoert vor die
    # Augen des Nutzers, nicht nur ins Protokoll.
    warnungen = [z for z in protokoll if z.startswith("KONNTE NICHT ENTFERNEN")]
    return {
        "ok": True,
        "id": comp_id,
        "action": "uninstall",
        "log": protokoll,
        "warnings": warnungen,
        "desktopRebuild": rebuild,
        # Warnungen gehoeren NICHT in die Schritteliste - dort stehen Dinge,
        # die der Nutzer tun soll, nicht Dinge, die schiefgingen. Beide
        # Oberflaechen rendern "warnings" in einem eigenen Kasten.
        "nextSteps": next_steps,
    }


@router.post("/repair")
async def repair() -> dict:
    """Erzwingt, was der Waechter beim Start automatisch tut - inklusive
    sofortigem Neubau der Desktop-App (rebuild_desktop=True): anders als der
    passive Waechter-Hook auf gateway:startup sieht der Nutzer hier aktiv
    einen Ladezustand, ein mehrminuetiger Neubau ist deshalb vertretbar."""
    return _guard().repair_all(rebuild_desktop=True)


# ---------------------------------------------------------------- Helfer

def _pinned_tarball_url(cat: dict) -> str:
    """Bevorzugt den Git-Tag der aktuell im Katalog gefuehrten Hub-Version
    statt immer den jeweils neuesten main-Stand herunterzuladen.

    Der Katalog selbst kommt weiter frisch von main (er soll sich sofort
    aktualisieren) - aber der Code, der tatsaechlich installiert wird, soll
    aus genau dem Tag stammen, den dieser Katalog gerade als aiianer-hub
    fuehrt. main kann sich zwischen zwei Auslieferungen schon wieder
    weiterbewegt haben; ein Tag ist der reviewte, releaste Stand, auf den
    sich releases.json und die Versionsnummer im Katalog tatsaechlich
    beziehen. Kein neues Feld noetig: die Hub-Version im Katalog IST bereits
    der Tag-Name minus 'v', bei jedem Release synchron gepflegt.

    Faellt main-Tarball zurueck, wenn kein Tag ermittelbar ist oder der Tag
    (noch) nicht existiert - z. B. lokal vor dem ersten Release-Tag, oder
    wenn die Versionsnummer aus irgendeinem Grund nicht zu einem Tag passt.
    Das ist ein Haerten, kein neuer Fehlschlagpfad: schlaegt die
    Tag-Ermittlung fehl, installiert es wie bisher von main."""
    try:
        hub = next((c for c in cat.get("components", []) if c["id"] == "aiianer-hub"), None)
        version = (hub or {}).get("version", "").strip()
        if not version:
            return TARBALL
        tag_url = f"https://github.com/{REPO}/archive/refs/tags/v{version}.tar.gz"
        req = urllib.request.Request(tag_url, method="HEAD")
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status == 200:
                return tag_url
    except Exception:
        pass
    return TARBALL


def _download(tmp: str, cat: dict | None = None) -> Path:
    url = _pinned_tarball_url(cat) if cat is not None else TARBALL
    return _download_tarball(url, tmp)


def _download_tarball(url: str, tmp: str) -> Path:
    """Laedt einen GitHub-Tarball und packt ihn aus. Eine Stelle fuer alle
    Downloads, damit der Tar-Slip-Schutz unten nicht irgendwo fehlt."""
    archive = Path(tmp) / "repo.tar.gz"
    # Ohne Timeout haengt der Download unbegrenzt und blockiert damit die
    # ganze Route.
    with urllib.request.urlopen(url, timeout=60) as resp, open(archive, "wb") as fh:
        shutil.copyfileobj(resp, fh)
    # filter="data" verhindert Tar-Slip (Pfade ausserhalb des Zielordners,
    # Symlinks, absolute Pfade). Vor Python 3.14 ist das NICHT die
    # Voreinstellung, und comp_id stammt aus dem Katalog im Netz.
    with tarfile.open(archive) as tf:
        try:
            tf.extractall(tmp, filter="data")
        except TypeError:
            # Python < 3.12 kennt den Parameter nicht.
            tf.extractall(tmp)
    roots = [p for p in Path(tmp).iterdir() if p.is_dir() and p.name != "__MACOSX"]
    if not roots:
        raise HTTPException(status_code=500, detail="Archiv war leer")
    return roots[0]


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")
