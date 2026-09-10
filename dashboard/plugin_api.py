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
I18N_DIR = AGENT_DIR / "apps" / "desktop" / "src" / "i18n"
BOTS_DIR = AGENT_DIR / "apps" / "desktop" / "src" / "plugins" / "hermes-bots"
BOTS_PLUGIN = BOTS_DIR / "plugin.js"
BOTS_KATALOG = BOTS_DIR / "i18n.ts"
BOTS_ROUNDS = BOTS_DIR / "group-rounds.ts"


def _bots_ziel():
    """Upstream hat die Datei von plugin.js auf plugin.tsx umbenannt. Fest auf
    einen Namen zu setzen hiesse, nach dem naechsten Umbenennen ins Leere zu
    schreiben."""
    for name in ("plugin.js", "plugin.tsx"):
        kandidat = BOTS_DIR / name
        if kandidat.is_file():
            return kandidat
    return None
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
        "install": ["Hermes komplett beenden und neu starten. Der Bot-Modus ist danach auf Deutsch."],
        "uninstall": ["Hermes komplett beenden und neu starten. Der Bot-Modus ist wieder englisch."],
    },
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
    if comp_id == "bot-mode-german":
        if not BOTS_KATALOG.is_file():
            return (
                False,
                "Der Nachrichtenkatalog des Bot-Modus liegt nicht an der "
                f"erwarteten Stelle ({BOTS_KATALOG}). Aktualisiere Hermes "
                "Desktop.",
                "Bot Mode's message catalog is not where it is expected "
                f"({BOTS_KATALOG}). Update Hermes Desktop.",
            )
        # Harte Abhaengigkeit: ohne 'de' als gueltige Locale waere das Buendel
        # eingetragen, aber nie auswaehlbar. Lieber vorher sagen als hinterher
        # ein "installiert, aber nichts passiert".
        try:
            verdrahtet = bool(
                re.search(
                    r"^export type Locale = .*'de'", (I18N_DIR / "types.ts").read_text(), re.M
                )
            )
        except Exception:
            verdrahtet = False
        if not verdrahtet:
            return (
                False,
                "Zuerst „Deutsche Sprache“ installieren. Der Bot-Modus haengt "
                "daran: ohne Deutsch als gueltige Sprache waere das Buendel "
                "zwar eingetragen, aber Hermes koennte es nie auswaehlen.",
                "Install “Deutsche Sprache” first. Bot Mode depends on it: "
                "without German as a valid locale the bundle would be "
                "registered but never selectable.",
            )

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
    if comp_id == "german-language":
        if not (I18N_DIR / "types.ts").is_file():
            return (
                False,
                "Der Hermes-Quellordner liegt nicht an der erwarteten Stelle "
                f"({I18N_DIR}). Ohne ihn lässt sich die Sprache nicht "
                "einspielen.",
                "Hermes' source folder is not where it is expected "
                f"({I18N_DIR}). Without it the language cannot be installed.",
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


# ---------------------------------------------------------------- Backup-Außenposten

def _backup_state_file() -> Path: return STATE_DIR / "backup-state.json"
def _backup_runner() -> Path: return HERMES_HOME / "scripts" / "aiianer-backup-runner.py"
RESTORE_CONFIRM = "HERMES-IMPORT {name} ÜBERSCHREIBEN"

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

def _backup_target(raw: str, create: bool = True) -> Path:
    if not isinstance(raw, str) or not raw.strip(): raise ValueError("TARGET_REQUIRED")
    p = Path(raw).expanduser()
    if not p.is_absolute() or ".." in p.parts: raise ValueError("TARGET_ABSOLUTE_REQUIRED")
    if create: p.mkdir(parents=True, exist_ok=True)
    target = p.resolve(strict=True); home = hermes_home().resolve(strict=False)
    try: target.relative_to(home)
    except ValueError: pass
    else: raise ValueError("TARGET_INSIDE_HERMES_HOME")
    if not target.is_dir() or not os.access(target, os.W_OK): raise ValueError("TARGET_NOT_WRITABLE")
    if os.name == "nt" and str(target).startswith("\\\\"): raise ValueError("TARGET_NETWORK_OR_UNSUPPORTED")
    return target


def _backup_schedule_expression(schedule: str, at: str, weekday: int) -> str:
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", at):
        raise ValueError("SCHEDULE_TIME_INVALID")
    if not isinstance(weekday, int) or isinstance(weekday, bool) or not 0 <= weekday <= 6:
        raise ValueError("SCHEDULE_WEEKDAY_INVALID")
    hour, minute = at.split(":")
    if schedule == "daily": return f"{int(minute)} {int(hour)} * * *"
    if schedule == "weekly": return f"{int(minute)} {int(hour)} * * {weekday}"
    raise ValueError("SCHEDULE_INVALID")


def _backup_browse_path(raw: str | None) -> Path:
    if not raw:
        return Path.home().resolve()
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("BROWSER_PATH_INVALID")
    path = candidate.resolve(strict=True)
    home = HERMES_HOME.resolve(strict=False)
    try: path.relative_to(home)
    except ValueError: pass
    else: raise ValueError("BROWSER_INSIDE_HERMES_HOME")
    if not path.is_dir(): raise ValueError("BROWSER_PATH_INVALID")
    return path


def _backup_public(state: dict) -> dict:
    retention = state.get("retention") if isinstance(state.get("retention"), dict) else {}
    history = state.get("history") if isinstance(state.get("history"), list) else []
    return {"configured": bool(state.get("target_dir")), "enabled": bool(state.get("enabled")), "targetDir": state.get("target_dir") or None, "schedule": state.get("schedule", "manual"), "scheduleTime": state.get("scheduleTime", "02:00"), "scheduleWeekday": state.get("scheduleWeekday", 0), "retention": {"enabled": bool(retention.get("enabled")), "keep": int(retention.get("keep", 5))}, "state": state.get("state", "never_run"), "lastRun": state.get("lastRun"), "lastArchive": state.get("lastArchive"), "lastErrorCode": state.get("lastErrorCode"), "scheduleErrorCode": state.get("scheduleErrorCode"), "nextRun": None, "archiveCount": _archive_count(state.get("target_dir")), "history": history[:20]}

def _archive_is_valid(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip() is None and bool(archive.namelist())
    except (OSError, zipfile.BadZipFile):
        return False


def _archive_count(raw) -> int:
    try: return sum(1 for p in _backup_target(raw, False).iterdir() if p.is_file() and p.name.startswith("aiianer-backup-") and p.name.endswith(".zip"))
    except (ValueError, OSError, TypeError): return 0

@router.get("/backup/status")
async def backup_status() -> dict: return _backup_public(_backup_state())

@router.get("/backup/config")
async def backup_config() -> dict: return _backup_public(_backup_state())

def _backup_cron_args(expression: str, action: str, job_id: str | None = None) -> list[str]:
    base = [shutil.which("hermes") or "hermes", "cron", action]
    if job_id: base.append(job_id)
    base.extend([expression, "--name", "aiianer-backup", "--script", "aiianer-backup-runner.py", "--no-agent", "--deliver", "local"])
    if action == "edit":
        base.remove(expression)
        base.extend(["--schedule", expression])
    return base


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


def _ensure_backup_cron(schedule: str, at: str = "02:00", weekday: int = 0) -> None:
    expression = _backup_schedule_expression(schedule, at, weekday)
    job = _backup_cron_job()
    job_id = job[0] if job else None
    action = "edit" if job_id else "create"
    argv = _backup_cron_args(expression, action, job_id)
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30, shell=False, check=False)
        if result.returncode != 0: raise RuntimeError("CRON_SETUP_FAILED")
        if job and job[1] == "paused":
            result = subprocess.run([shutil.which("hermes") or "hermes", "cron", "resume", job[0]], capture_output=True, text=True, timeout=30, shell=False, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("CRON_SETUP_FAILED") from exc
    if result.returncode != 0: raise RuntimeError("CRON_SETUP_FAILED")


def _pause_backup_cron() -> None:
    job_id = _backup_cron_id()
    if not job_id: return
    try:
        result = subprocess.run([shutil.which("hermes") or "hermes", "cron", "pause", job_id], capture_output=True, text=True, timeout=30, shell=False, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("CRON_SETUP_FAILED") from exc
    if result.returncode != 0: raise RuntimeError("CRON_SETUP_FAILED")


@router.put("/backup/settings")
async def backup_settings(body: dict) -> dict:
    body = body or {}; schedule = body.get("schedule", "manual")
    if schedule not in {"manual", "daily", "weekly"}: raise HTTPException(422, "SCHEDULE_INVALID")
    schedule_time = body.get("scheduleTime", "02:00")
    schedule_weekday = body.get("scheduleWeekday", 0)
    if schedule != "manual":
        try: _backup_schedule_expression(schedule, schedule_time, schedule_weekday)
        except ValueError as exc: raise HTTPException(422, str(exc))
    retention = body.get("retention") or {}; keep = retention.get("keep", 5)
    if not isinstance(keep, int) or isinstance(keep, bool) or not 1 <= keep <= 100: raise HTTPException(422, "RETENTION_INVALID")
    target = body.get("target_dir", body.get("targetDir", ""))
    try: canonical = str(_backup_target(target)) if target else ""
    except ValueError as exc: raise HTTPException(422, str(exc))
    settings = {"schemaVersion": 1, "enabled": bool(body.get("enabled", False)), "target_dir": canonical, "schedule": schedule, "scheduleTime": schedule_time, "scheduleWeekday": schedule_weekday, "retention": {"enabled": bool(retention.get("enabled", False)), "keep": keep}}
    _backup_save({**_backup_state(), **settings})
    try:
        if settings["enabled"] and schedule != "manual":
            _ensure_backup_cron(schedule, schedule_time, schedule_weekday)
        else:
            _pause_backup_cron()
        state = {**_backup_state(), **settings}
        state.pop("scheduleErrorCode", None)
        _backup_save(state)
    except RuntimeError:
        state = {**_backup_state(), **settings, "scheduleErrorCode": "CRON_SETUP_FAILED"}
        _backup_save(state)
    return _backup_public(_backup_state())


@router.post("/backup/browse")
async def backup_browse(body: dict) -> dict:
    try: path = _backup_browse_path((body or {}).get("path"))
    except (ValueError, OSError) as exc: raise HTTPException(422, str(exc))
    directories = []
    try:
        for child in sorted(path.iterdir(), key=lambda p: p.name.casefold()):
            if child.is_dir(): directories.append({"name": child.name, "path": str(child.resolve())})
            if len(directories) >= 200: break
    except OSError: raise HTTPException(422, "BROWSER_PATH_UNREADABLE")
    return {"path": str(path), "parent": str(path.parent) if path.parent != path else None, "directories": directories}

@router.get("/backup/archives")
async def backup_archives() -> dict:
    state = _backup_state(); result=[]
    try:
        for p in sorted(_backup_target(state.get("target_dir"), False).glob("aiianer-backup-*.zip"), key=lambda x:x.stat().st_mtime, reverse=True):
            if p.is_file(): result.append({"name": p.name, "bytes": p.stat().st_size, "modified": datetime.datetime.fromtimestamp(p.stat().st_mtime, datetime.timezone.utc).isoformat(), "valid": _archive_is_valid(p)})
    except (ValueError, OSError, TypeError): pass
    return {"archives": result}

@router.post("/backup/run")
async def backup_run() -> dict:
    state = _backup_state()
    if not state.get("target_dir"): raise HTTPException(409, "NOT_CONFIGURED")
    if not _backup_runner().is_file(): raise HTTPException(500, "RUNNER_NOT_INSTALLED")
    try:
        proc = subprocess.run([sys.executable, str(_backup_runner())], capture_output=True, text=True, timeout=3600, shell=False)
    except subprocess.TimeoutExpired: raise HTTPException(504, "BACKUP_TIMEOUT")
    if proc.returncode != 0:
        fresh = _backup_state(); return {"ok": False, **_backup_public(fresh)}
    fresh = _backup_state(); return {"ok": True, **_backup_public(fresh)}

@router.post("/backup/restore/prepare")
async def backup_restore_prepare(body: dict) -> dict:
    name = (body or {}).get("name", "")
    if not re.fullmatch(r"aiianer-backup-[A-Za-z0-9T_-]+\.zip", name): raise HTTPException(422, "ARCHIVE_INVALID_NAME")
    state = _backup_state()
    try:
        target = _backup_target(state.get("target_dir"), False).resolve()
        archive = (target / name).resolve(strict=True)
        archive.relative_to(target)
    except (ValueError, OSError): raise HTTPException(404, "ARCHIVE_MISSING_OR_INVALID")
    if not archive.is_file() or not _archive_is_valid(archive): raise HTTPException(404, "ARCHIVE_MISSING_OR_INVALID")
    nonce = os.urandom(16).hex()
    state["restoreNonce"] = nonce
    _backup_save(state)
    return {"name": name, "bytes": archive.stat().st_size, "targetHome": str(hermes_home()), "confirmationText": RESTORE_CONFIRM.format(name=name), "confirmationToken": nonce, "warning": "Der Import kann bestehende Hermes-Daten überschreiben."}

@router.post("/backup/restore/confirm")
async def backup_restore_confirm(body: dict) -> dict:
    body = body or {}; name = body.get("name", ""); state = _backup_state()
    if not isinstance(name, str) or not re.fullmatch(r"aiianer-backup-[A-Za-z0-9T_-]+\.zip", name): raise HTTPException(422, "ARCHIVE_INVALID_NAME")
    expected = RESTORE_CONFIRM.format(name=name)
    if not state.get("restoreNonce") or body.get("confirmationToken") != state.get("restoreNonce") or body.get("confirmationText") != expected or not body.get("acknowledged"): raise HTTPException(409, "RESTORE_CONFIRMATION_REQUIRED")
    try:
        target = _backup_target(state.get("target_dir"), False).resolve()
        archive = (target / name).resolve(strict=True)
        archive.relative_to(target)
    except (ValueError, OSError): raise HTTPException(404, "ARCHIVE_MISSING_OR_INVALID")
    proc = subprocess.run([shutil.which("hermes") or "hermes", "import", "--force", str(archive)], capture_output=True, text=True, timeout=3600, shell=False)
    state.pop("restoreNonce", None); state["state"] = "success" if proc.returncode == 0 else "failed"; state["lastErrorCode"] = None if proc.returncode == 0 else "RESTORE_FAILED"; _backup_save(state)
    if proc.returncode != 0: raise HTTPException(500, "RESTORE_FAILED")
    return {"ok": True, **_backup_public(_backup_state())}

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

    with tempfile.TemporaryDirectory() as tmp:
        root = _download(tmp)
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
            install_log = [z for z in (proc.stdout or "").splitlines() if z.strip()][-12:]

            # Sprachdatei zusaetzlich als Quelle sichern, damit der Waechter sie
            # nach einem Hermes-Update erneut einspielen kann.
            if comp_id in ("german-language", "bot-mode-german", "group-chat-limits"):
                STATE_DIR.mkdir(parents=True, exist_ok=True)
                for name in ("de.ts", "apply-de.py", "de-bots.ts", "apply-bots-de.py",
                             "aiianer-group-limits.ts", "apply-limits.py"):
                    if (src / name).is_file():
                        shutil.copy2(src / name, STATE_DIR / name)

    with _state_lock():
        state = _read_state()
        vorher = previous_version
        state[comp_id] = {"version": entry["version"], "at": _now()}
        _write_state(state)
    return {
        "ok": True,
        "id": comp_id,
        "action": "update" if vorher else "install",
        "version": entry["version"],
        "previousVersion": vorher,
        "log": install_log,
        "nextSteps": _steps(comp_id, "install", entry),
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

    # Auch nach der Vorpruefung kann die Kopiersequenz mittendrin brechen
    # (kein Platz, read-only, Rechte). Deshalb vorher den Ist-Zustand
    # festhalten und im Fehlerfall alles zuruecknehmen - dieselbe
    # Alles-oder-nichts-Zusage, die apply-de.py fuer die Gegenrichtung gibt.
    vorher = {}
    for name in namen:
        ziel = I18N_DIR / name
        if ziel.is_file():
            vorher[name] = ziel.read_bytes()
    try:
        for name in namen:
            _restore(quellen[name], I18N_DIR / name, protokoll)
    except Exception as exc:
        for name, inhalt in vorher.items():
            try:
                (I18N_DIR / name).write_bytes(inhalt)
            except Exception:
                pass
        raise HTTPException(
            status_code=500,
            detail=(
                f"Rueckbau abgebrochen beim Schreiben: {exc}. Der vorherige "
                "Zustand wurde wiederhergestellt."
            ),
        )

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
                f"{EXT_STORE / comp_id}. Es wurde nichts veraendert."
            ),
        )

    ziel = BOTS_PLUGIN if BOTS_PLUGIN.is_file() else _bots_ziel()
    if ziel is None:
        raise HTTPException(
            status_code=409,
            detail=(
                "Rueckbau abgebrochen: die Bot-Mode-Datei liegt nicht mehr an "
                "ihrem Platz. Es wurde nichts veraendert."
            ),
        )

    # Rueckgabewert AUSWERTEN. Pruefung und Kopie sind zwei Operationen - faellt
    # die Sicherung dazwischen weg oder ist sie unlesbar, wuerde sonst gleich
    # darauf der ganze Sicherungsordner geloescht. Danach laege die gepatchte
    # Datei unveraendert da, ohne jede Moeglichkeit zum Rueckbau.
    if not _restore(sicherung, ziel, protokoll):
        raise HTTPException(
            status_code=500,
            detail=(
                f"Die Sicherung {sicherungsname} liess sich nicht einspielen. "
                "Der Sicherungsordner bleibt deshalb erhalten, damit der "
                "Rueckbau spaeter erneut versucht werden kann."
            ),
        )
    _drop(EXT_STORE / comp_id, protokoll)


def _uninstall_bots_katalog(protokoll: list) -> None:
    """Rueckbau des deutschen Bot-Modus-Buendels.

    Bevorzugt die Erstsicherung. Fehlt sie, wird der de-Block chirurgisch aus
    dem Katalog geschnitten und der Eintrag aus BOTS_LOCALES entfernt - das ist
    hier vertretbar, weil beide Aenderungen exakt bekannt sind und der Rest der
    Datei nie angefasst wurde."""
    if not BOTS_KATALOG.is_file():
        raise HTTPException(
            status_code=409,
            detail="Der Nachrichtenkatalog des Bot-Modus liegt nicht mehr da. Es wurde nichts veraendert.",
        )

    orig = BOTS_KATALOG.with_suffix(".ts.aiianer-orig")
    if orig.is_file() and "const de: BotsMessages" not in orig.read_text():
        _restore(orig, BOTS_KATALOG, protokoll)
    else:
        inhalt = BOTS_KATALOG.read_text()
        ohne = re.sub(r"^const de: BotsMessages = \{.*?^\}\s*\n+", "", inhalt, count=1,
                      flags=re.S | re.M)
        ohne = re.sub(r"(BOTS_LOCALES: PluginLocaleBundles = \{ en,)\s*de,", r"\1", ohne, count=1)
        if ohne == inhalt:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Weder eine brauchbare Erstsicherung noch ein erkennbarer "
                    "de-Block gefunden. Es wurde nichts veraendert."
                ),
            )
        vorher = BOTS_KATALOG.read_bytes()
        try:
            BOTS_KATALOG.write_text(ohne)
            gepr = BOTS_KATALOG.read_text()
            if "const de: BotsMessages" in gepr or re.search(
                r"BOTS_LOCALES[^}]*\bde\b", gepr
            ):
                raise RuntimeError("de-Eintrag nach dem Schreiben noch vorhanden")
        except Exception as exc:
            BOTS_KATALOG.write_bytes(vorher)
            raise HTTPException(
                status_code=500,
                detail=f"Rueckbau fehlgeschlagen, Datei wiederhergestellt: {exc}",
            )
        protokoll.append("de-Block aus dem Katalog entfernt")

    _drop(BOTS_KATALOG.with_suffix(".ts.aiianer-bak"), protokoll)
    _drop(orig, protokoll)
    kritisch = []
    for pfad in (STATE_DIR / "de-bots.ts", STATE_DIR / "apply-bots-de.py"):
        _drop(pfad, protokoll)
        if pfad.exists():
            kritisch.append(str(pfad))
    _drop(EXT_STORE / "bot-mode-german", protokoll)
    if kritisch:
        raise HTTPException(
            status_code=500,
            detail=(
                "Zurueckgesetzt, aber diese Quellen des Waechters blieben liegen: "
                + ", ".join(kritisch)
                + ". Er wuerde das Buendel beim naechsten Start erneut einspielen."
            ),
        )


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
    if comp_id == "german-language":
        _uninstall_german(protokoll)
    elif comp_id == "bot-mode-german":
        _uninstall_bots_katalog(protokoll)
    elif comp_id == "group-chat-limits":
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

        # Erst wenn der Rueckbau durchlief, faellt der Zustandseintrag. Der
        # Waechter richtet sich danach und spielt sonst alles wieder ein.
        # Frisch lesen: unter der Sperre kann sich zwischenzeitlich nichts
        # geaendert haben, aber so bleibt die Regel "lesen, aendern,
        # schreiben in einem Zug" sichtbar.
        zustand = _read_state()
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
        # Warnungen gehoeren NICHT in die Schritteliste - dort stehen Dinge,
        # die der Nutzer tun soll, nicht Dinge, die schiefgingen. Beide
        # Oberflaechen rendern "warnings" in einem eigenen Kasten.
        "nextSteps": _steps(comp_id, "uninstall", entry),
    }


@router.post("/repair")
async def repair() -> dict:
    """Erzwingt, was der Waechter beim Start automatisch tut."""
    return _guard().repair_all()


# ---------------------------------------------------------------- Helfer

def _download(tmp: str) -> Path:
    archive = Path(tmp) / "repo.tar.gz"
    # Ohne Timeout haengt der Download unbegrenzt und blockiert damit die
    # ganze Route.
    with urllib.request.urlopen(TARBALL, timeout=60) as resp, open(archive, "wb") as fh:
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
