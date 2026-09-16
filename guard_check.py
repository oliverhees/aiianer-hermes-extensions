"""Prueft und repariert, was ein Hermes-Update aus dem Checkout entfernt.

Wird von zwei Stellen benutzt:
  - dem Waechter-Hook auf gateway:startup
  - der Route /api/plugins/aiianer-hub/health im Dashboard

Alles Noetige liegt unter ~/.hermes/aiianer/. Der Hermes-Checkout wird nur
gelesen und, wenn Deutsch fehlt, ueber den mitgelieferten Patcher ergaenzt.
Faellt der Patcher aus, wird das laut gemeldet statt still geschluckt.
"""

from __future__ import annotations

import json
import re
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

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
AGENT = HERMES_HOME / "hermes-agent"
I18N = AGENT / "apps" / "desktop" / "src" / "i18n"
STATE_DIR = HERMES_HOME / "aiianer"
LOG_FILE = STATE_DIR / "guard.log"


def _log(msg: str) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write(f"{stamp}  {msg}\n")
    except Exception:
        pass


def _installed() -> dict:
    try:
        return json.loads((STATE_DIR / "installed.json").read_text())
    except Exception:
        return {}


# Komponenten, die apps/desktop/ selbst veraendern. Nach jeder Reparatur einer
# von ihnen muss der Content-Hash-Stempel weg, sonst haelt Hermes Desktop die
# eigene, noch unreparierte Fassung fuer aktuell und baut nicht neu - genau das
# Muster hinter "Neustart bringt nichts, erst ein manueller Eingriff hilft".
_DESKTOP_TOUCHING = {"german-language", "bot-mode-german", "group-chat-limits"}


def _invalidate_desktop_build_stamp() -> None:
    """Zwingt den naechsten 'hermes desktop'/'hermes gui'-Start zum Neubau.

    Hermes vergleicht dafuer einen SHA-256 ueber apps/desktop/ mit einem
    Stempel unter $HERMES_HOME/desktop-build-stamp.json (siehe
    hermes_cli/main_desktop.py, _stamp_is_current). Fehlt die Datei, gilt der
    Stand automatisch als veraltet - dieselbe Technik, die Hermes' eigener
    Self-Heal bei einem zerrissenen Bundle benutzt. Best-effort: eine
    fehlende oder nicht loeschbare Datei ist kein Fehler, nur ein
    uebersprungener Neubau-Zwang.
    """
    try:
        stamp = HERMES_HOME / "desktop-build-stamp.json"
        if stamp.is_file():
            stamp.unlink()
    except Exception:
        pass


def _desktop_build_stamp_missing() -> bool:
    """Unabhaengiges Signal fuer 'muss neu gebaut werden' - losgeloest davon,
    ob DER AKTUELLE Pruefpass selbst gerade etwas am Quellcode repariert hat.

    Community-Befund nach v1.3.37: der Stempel wurde in einem FRUEHEREN Lauf
    schon korrekt entfernt (Quellcode war damals kaputt und wurde repariert),
    aber KEIN Neubau fand statt (alte Hub-Version ohne rebuild_desktop, oder
    rebuild_desktop=False). Ein SPAETERER Lauf findet den Quellcode dann
    bereits intakt vor (state == 'ok' fuer alle Komponenten) und bricht bisher
    sofort ab, ohne je zu pruefen, ob der fehlende Stempel noch fuer sich
    alleine einen Neubau rechtfertigt. Ergebnis: die fertige App bleibt
    dauerhaft auf altem Stand, obwohl der Quellcode laengst wieder stimmt.
    Diese Funktion schliesst genau diese Luecke - sie wird IMMER geprueft,
    nicht nur wenn im selben Durchlauf etwas repariert wurde."""
    return not (HERMES_HOME / "desktop-build-stamp.json").is_file()


def _rebuild_desktop() -> dict:
    """Baut die Desktop-App JETZT neu, statt nur auf den naechsten Start zu
    hoffen.

    Der entscheidende Befund (Community-Meldung nach v1.3.35): ein normales
    Oeffnen ueber das App-Symbol startet die bereits gepackte Electron-App
    direkt und ruehrt dabei nie die Python-CLI an, die den Content-Hash-
    Stempel prueft und bei Bedarf neu baut - nur 'hermes desktop'/'hermes
    gui' im TERMINAL tut das. Ohne diesen Schritt bleibt eine frisch
    gepatchte Sprachdatei fuer die meisten Nutzer unsichtbar, bis irgendwer
    zufaellig einmal ueber das Terminal startet. Der Loesung: den Neubau
    selbst anstossen, mit demselben Befehl, den 'hermes update' intern
    benutzt (--build-only). --force-build zusaetzlich, damit ein zufaellig
    schon wieder passender Stempel den Neubau nicht ueberspringt.

    Kann mehrere zig Sekunden bis wenige Minuten dauern (npm/vite/
    electron-builder). Nicht fatal, wenn es fehlschlaegt oder 'hermes' nicht
    aufrufbar ist: Stempel wurde vorher schon entfernt, ein spaeterer
    Terminal-Start (oder ein erneuter Klick auf 'Neu einspielen') baut dann
    trotzdem neu.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "hermes_cli.main", "desktop", "--build-only", "--force-build"],
            capture_output=True, text=True, timeout=300, cwd=str(AGENT),
        )
    except Exception as exc:
        _log(f"Desktop-Neubau nicht gestartet: {exc}")
        return {"rebuilt": False, "detail": str(exc)}
    ok = proc.returncode == 0
    detail = (proc.stdout or proc.stderr or "").strip()[-500:]
    _log(f"Desktop-Neubau {'erfolgreich' if ok else 'fehlgeschlagen'}: {detail[:200]}")
    return {"rebuilt": ok, "detail": detail}


# ------------------------------------------------------------- Pruefungen

def check_german() -> dict:
    """Ist Deutsch noch im Checkout verdrahtet?"""
    if "german-language" not in _installed():
        return {"id": "german-language", "state": "not-installed"}
    if not I18N.is_dir():
        return {"id": "german-language", "state": "no-checkout",
                "detail": f"{I18N} nicht gefunden"}
    try:
        types_s = (I18N / "types.ts").read_text()
        catalog_s = (I18N / "catalog.ts").read_text()
        langs_s = (I18N / "languages.ts").read_text()
    except Exception as exc:
        return {"id": "german-language", "state": "unreadable", "detail": str(exc)}

    wired = (
        "'de'" in types_s.split("export type Locale")[-1].split("\n")[0]
        and "./de'" in catalog_s
        and "id: 'de'" in langs_s
        and (I18N / "de.ts").is_file()
    )
    return {"id": "german-language", "state": "ok" if wired else "missing"}


# Jede Komponente hat ihren EIGENEN Nachweis. Eine gemeinsame Kandidatenliste
# waere falsch: sie enthielt model-providers/eurouter fuer jede comp_id, und
# sobald der EU-Router lag, meldete auch bot-mode-german "ok" - selbst wenn ein
# Hermes-Update es laengst weggeraeumt hatte. /health sagte dann ok, obwohl
# etwas fehlte, und der Waechter reparierte nichts.
def _bots_katalog():
    """Der plugin-eigene Nachrichtenkatalog des Bot-Modus."""
    agent = Path(os.environ.get("HERMES_AGENT_DIR") or (HERMES_HOME / "hermes-agent"))
    k = agent / "apps" / "desktop" / "src" / "plugins" / "hermes-bots" / "i18n.ts"
    return k if k.is_file() else None


def _bots_plugin():
    """Upstream hat die Datei zwischenzeitlich von plugin.js auf plugin.tsx
    umbenannt. Fest auf einen Namen zu pruefen hiesse, nach dem naechsten
    Umbenennen still 'missing' zu melden. Beide werden geprueft."""
    agent = Path(os.environ.get("HERMES_AGENT_DIR") or (HERMES_HOME / "hermes-agent"))
    basis = agent / "apps" / "desktop" / "src" / "plugins" / "hermes-bots"
    for name in ("plugin.js", "plugin.tsx"):
        kandidat = basis / name
        if kandidat.is_file():
            return kandidat
    return None


def _liegt_noch(comp_id: str) -> bool:
    if comp_id == "eurouter-provider":
        return (HERMES_HOME / "plugins" / "model-providers" / "eurouter").exists()

    if comp_id == "bot-mode-german":
        # Seit dem Umbau ist der Nachweis ein Eintrag im plugin-eigenen
        # Nachrichtenkatalog, nicht mehr eine ersetzte Datei.
        katalog = _bots_katalog()
        if katalog is None:
            return False
        try:
            t = katalog.read_text(errors="ignore")
        except Exception:
            return False
        return "const de: BotsMessages" in t and bool(
            re.search(r"BOTS_LOCALES[^}]*\bde\b", t)
        )

    if comp_id == "group-chat-limits":
        # Nachweis ist die Naht in der Rundenschleife, nicht mehr die alte
        # Einzeldatei.
        agent = Path(os.environ.get("HERMES_AGENT_DIR") or (HERMES_HOME / "hermes-agent"))
        ziel = agent / "apps/desktop/src/plugins/hermes-bots/group-rounds.ts"
        if not ziel.is_file():
            return False
        mitglieder = agent / "apps/desktop/src/plugins/hermes-bots/group-round-members.ts"
        try:
            return (
                "aiianerCaps(group)" in ziel.read_text(errors="ignore")
                and "aiianer-group-limits-history" in mitglieder.read_text(errors="ignore")
                and "aiianerCaps(context.group).history" in mitglieder.read_text(errors="ignore")
            )
        except Exception:
            return False

    marker = None
    if marker is None:
        return (HERMES_HOME / "plugins" / comp_id).exists() or (
            HERMES_HOME / "desktop-plugins" / comp_id
        ).exists()
    ziel = _bots_plugin()
    if ziel is None:
        return False
    try:
        return marker in ziel.read_text(errors="ignore")
    except Exception:
        return False


def check_plugin(comp_id: str) -> dict:
    """Liegt die Komponente noch an ihrem Platz?"""
    if comp_id not in _installed():
        return {"id": comp_id, "state": "not-installed"}
    return {"id": comp_id, "state": "ok" if _liegt_noch(comp_id) else "missing"}


# Der Katalog entscheidet, was ueberhaupt noch aktiv gepflegt wird. Stand
# 2026-09: group-chat-limits ist als "unfinished" aus catalog.json entfernt
# (Oliver, 10.09.), aber Nutzer, die es davor installiert hatten, bekamen es
# trotzdem fuer immer automatisch repariert - inklusive dem teuren
# --build-only-Neubau aus v1.3.36+. Eine versteckte, nicht mehr gepflegte
# Komponente soll den Waechter nicht mehr beschaeftigen.
_CATALOG_PFAD = HERMES_HOME / "plugins" / "aiianer-hub" / "catalog.json"


def _katalog_ids() -> set | None:
    """IDs der aktuell im Katalog sichtbaren Komponenten. None = Katalog nicht
    lesbar (z. B. sehr alte Installation) - dann bewusst ALLES weiter pruefen
    statt riskant nichts mehr zu reparieren, nur weil die Datei fehlt."""
    try:
        daten = json.loads(_CATALOG_PFAD.read_text(encoding="utf-8"))
        return {c["id"] for c in daten.get("components", []) if "id" in c}
    except Exception:
        return None


def check_all() -> dict:
    checks = [check_german()]
    kandidaten = ("eurouter-provider", "bot-mode-german", "group-chat-limits")
    sichtbar = _katalog_ids()
    if sichtbar is not None:
        kandidaten = tuple(c for c in kandidaten if c in sichtbar)
    for comp_id in kandidaten:
        checks.append(check_plugin(comp_id))
    broken = [c for c in checks if c["state"] in ("missing", "unreadable", "no-checkout")]
    return {"ok": not broken, "checks": checks, "broken": [c["id"] for c in broken]}


# ------------------------------------------------------------- Reparatur

def repair_german() -> dict:
    patcher = STATE_DIR / "apply-de.py"
    source = STATE_DIR / "de.ts"
    if not patcher.is_file() or not source.is_file():
        msg = ("Deutsch fehlt, aber die Quelle unter ~/.hermes/aiianer/ ist "
               "unvollstaendig. Bitte im AIIANER-Marktplatz neu installieren.")
        _log(f"FEHLER german-language: {msg}")
        return {"id": "german-language", "repaired": False, "detail": msg}

    proc = subprocess.run(
        [sys.executable, str(patcher), str(AGENT)],
        capture_output=True, text=True, timeout=120, cwd=str(STATE_DIR),
    )
    if proc.returncode == 0:
        _log("german-language nach Update erneut eingespielt")
        return {"id": "german-language", "repaired": True}

    detail = (proc.stderr or proc.stdout or "").strip()[-500:]
    _log(f"FEHLER german-language: Anker passt nicht mehr. {detail}")
    return {
        "id": "german-language",
        "repaired": False,
        "detail": detail,
        "hint": ("Hermes hat die i18n-Dateien umgebaut. Bitte in der AIIANER "
                 "Community melden, der Patcher braucht eine Anpassung."),
    }


def repair_bots_german() -> dict:
    """Spielt das deutsche Bot-Modus-Buendel erneut ein. Gleiche Quelle wie der
    Marktplatz, damit es nur einen Weg gibt."""
    patcher = STATE_DIR / "apply-bots-de.py"
    quelle = STATE_DIR / "de-bots.ts"
    if not patcher.is_file() or not quelle.is_file():
        msg = f"Quellen fehlen unter {STATE_DIR} - im Marktplatz neu installieren."
        _log(f"bot-mode-german: {msg}")
        return {"id": "bot-mode-german", "repaired": False, "detail": msg}
    agent = Path(os.environ.get("HERMES_AGENT_DIR") or (HERMES_HOME / "hermes-agent"))
    proc = subprocess.run(
        [sys.executable, str(patcher), str(agent)],
        capture_output=True, text=True, timeout=120, cwd=str(STATE_DIR),
    )
    ok = proc.returncode == 0
    _log(f"bot-mode-german repariert={ok}: {(proc.stdout or proc.stderr).strip()[:200]}")
    return {"id": "bot-mode-german", "repaired": ok,
            "detail": (proc.stdout or proc.stderr).strip()[-300:]}


def repair_group_limits() -> dict:
    """Haengt die Gruppenchat-Grenzen erneut ein. Der Patcher erzeugt dabei
    auch die Werte neu, eine geaenderte gruppen-grenzen.json wird also
    mitgenommen."""
    patcher = STATE_DIR / "apply-limits.py"
    modul = STATE_DIR / "aiianer-group-limits.ts"
    if not patcher.is_file() or not modul.is_file():
        msg = f"Quellen fehlen unter {STATE_DIR} - im Marktplatz neu installieren."
        _log(f"group-chat-limits: {msg}")
        return {"id": "group-chat-limits", "repaired": False, "detail": msg}
    agent = Path(os.environ.get("HERMES_AGENT_DIR") or (HERMES_HOME / "hermes-agent"))
    proc = subprocess.run(
        [sys.executable, str(patcher), str(agent), str(STATE_DIR)],
        capture_output=True, text=True, timeout=120, cwd=str(STATE_DIR),
    )
    ok = proc.returncode == 0
    _log(f"group-chat-limits repariert={ok}: {(proc.stdout or proc.stderr).strip()[:200]}")
    return {"id": "group-chat-limits", "repaired": ok,
            "detail": (proc.stdout or proc.stderr).strip()[-300:]}


def repair_all(rebuild_desktop: bool = False) -> dict:
    """rebuild_desktop=True baut die Desktop-App sofort neu (--build-only),
    statt nur den Stempel zu entfernen und auf einen spaeteren Terminal-Start
    zu hoffen. Sowohl der Waechter-Hook (gateway:startup) als auch die
    interaktive /repair-Route setzen es inzwischen auf True: Gateway-Hooks
    laufen laut Hermes' eigener Doku, ohne die Gateway-Pipeline zu blockieren,
    und gateway:startup nach einem Update ist ohnehin der Moment, in dem der
    Nutzer schon durch Hermes' eigenen Update-Bildschirm gewartet hat - ein
    zusaetzlicher Neubau dort faellt nicht mehr auf, als noch einmal manuell
    auf 'Reparieren' klicken zu muessen. Default bleibt False fuer
    Aufrufer, die diese Abwaegung nicht automatisch treffen wollen."""
    status = check_all()
    results = []
    for c in status["checks"]:
        if c["state"] != "missing":
            continue
        if c["id"] == "german-language":
            results.append(repair_german())
        elif c["id"] == "bot-mode-german":
            results.append(repair_bots_german())
        elif c["id"] == "group-chat-limits":
            results.append(repair_group_limits())
        else:
            results.append({
                "id": c["id"], "repaired": False,
                "hint": "Im AIIANER-Marktplatz erneut installieren.",
            })
    repaired_desktop = any(r.get("repaired") and r.get("id") in _DESKTOP_TOUCHING for r in results)
    # UNABHAENGIG von results pruefen: ein frueherer Lauf kann den Stempel
    # schon entfernt haben, ohne dass DIESER Lauf noch etwas am Quellcode
    # zu reparieren findet (siehe _desktop_build_stamp_missing). Ohne diese
    # zweite Bedingung bliebe die App nach einem Hub-Selbstupdate, das
    # zwischen Reparatur und naechstem Pruefpass liegt, dauerhaft veraltet.
    sichtbar = _katalog_ids()
    aktive_desktop_touching = (
        _DESKTOP_TOUCHING if sichtbar is None else (_DESKTOP_TOUCHING & sichtbar)
    )
    stamp_missing = (
        not repaired_desktop
        and any(cid in _installed() for cid in aktive_desktop_touching)
        and _desktop_build_stamp_missing()
    )

    rebuild_result = None
    if not results and not stamp_missing:
        _log("Pruefung ok, nichts zu tun")
    elif repaired_desktop or stamp_missing:
        if repaired_desktop:
            _invalidate_desktop_build_stamp()
        if rebuild_desktop:
            rebuild_result = _rebuild_desktop()
        elif repaired_desktop:
            _log("Desktop-Build-Stempel entfernt, naechster Terminal-Start baut neu")
        else:
            _log("Desktop-Build-Stempel fehlt noch von einem frueheren Lauf, naechster Terminal-Start baut neu")
    out = {"ok": all(r.get("repaired") for r in results) if results else True,
           "results": results}
    if rebuild_result is not None:
        out["desktopRebuild"] = rebuild_result
    return out


# --------------------------------------------------------------- Diagnose

# Copy-paste-fertiges Support-Buendel fuer ein GitHub-Issue. Der Anlass: bei
# den ersten beiden gemeldeten Fehlern (Windows-500er, Linux-GUI-Absturz)
# brauchte es mehrere Runden Rueckfragen, um ueberhaupt an die Zustandsdaten
# zu kommen, die hier stehen - vor allem wenn die GUI selbst nicht mehr geht
# und der Marktplatz-Reiter unerreichbar ist. Enthaelt keine Geheimnisse:
# installed.json/guard.log tragen nur Komponenten-IDs, Versionen und
# Patch-Ergebnisse, nie Tokens oder Pfade mit Nutzerdaten darin.


def _hermes_version(agent: Path) -> str:
    """Best-effort - Hermes hat keine einzelne Versionsdatei, die immer
    stimmt (package.json im Monorepo-Root bleibt oft bei "1.0.0" stehen).
    Der Git-Stand des Checkouts ist der ehrlichste verfuegbare Nachweis."""
    if not (agent / ".git").exists():
        return "unbekannt (kein Git-Checkout unter " + str(agent) + ")"
    for cmd in (["git", "-C", str(agent), "describe", "--tags", "--always"],
                ["git", "-C", str(agent), "rev-parse", "--short", "HEAD"]):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if proc.returncode == 0 and proc.stdout.strip():
                return proc.stdout.strip()
        except Exception:
            continue
    return "unbekannt (Git-Befehl fehlgeschlagen)"


def _log_tail(n: int = 25) -> list:
    try:
        zeilen = LOG_FILE.read_text(encoding="utf-8").splitlines()
        return zeilen[-n:]
    except Exception:
        return []


def diagnostics() -> str:
    """Baut den Text-Report. Reine Textausgabe (kein JSON), damit er sich
    ohne Umweg in ein GitHub-Issue einfuegen laesst."""
    zeilen = []
    zeilen.append("## AIIANER Marktplatz - Diagnose")
    zeilen.append("")
    zeilen.append(f"Erzeugt: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    zeilen.append(f"Plattform: {sys.platform} / Python {sys.version.split()[0]}")
    zeilen.append(f"HERMES_HOME: {HERMES_HOME}")
    zeilen.append(f"Hermes-Checkout-Stand: {_hermes_version(AGENT)}")
    zeilen.append("")

    zeilen.append("### Installierte Komponenten")
    installiert = _installed()
    if installiert:
        for comp_id, info in sorted(installiert.items()):
            zeilen.append(f"- {comp_id}: v{info.get('version', '?')} (seit {info.get('at', '?')})")
    else:
        zeilen.append("- keine (installed.json leer oder nicht gefunden)")
    zeilen.append("")

    zeilen.append("### Pruefung (check_all)")
    status = check_all()
    for c in status["checks"]:
        zusatz = f" - {c['detail']}" if "detail" in c else ""
        zeilen.append(f"- {c['id']}: {c['state']}{zusatz}")
    zeilen.append(f"- Gesamt: {'ok' if status['ok'] else 'NICHT ok - betroffen: ' + ', '.join(status['broken'])}")
    zeilen.append("")

    zeilen.append("### Desktop-Build-Stempel")
    stamp = HERMES_HOME / "desktop-build-stamp.json"
    if stamp.is_file():
        try:
            inhalt = json.loads(stamp.read_text())
            zeilen.append(f"- vorhanden, gebaut: {inhalt.get('builtAt', '?')}")
        except Exception:
            zeilen.append("- vorhanden, aber nicht lesbar (kaputtes JSON)")
    else:
        zeilen.append("- fehlt -> naechster 'hermes desktop'-Start baut in jedem Fall neu")
    zeilen.append("")

    zeilen.append("### Waechter-Log (letzte 25 Zeilen)")
    log = _log_tail()
    if log:
        zeilen.extend(f"    {z}" for z in log)
    else:
        zeilen.append("- guard.log leer oder nicht gefunden")

    zeilen.append("")
    zeilen.append("*Enthaelt keine Tokens, Passwoerter oder Datei-Inhalte - nur "
                   "Komponenten-IDs, Versionsnummern und Patch-Ergebnisse.*")
    return "\n".join(zeilen)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("diagnostics", "diagnose", "--diagnostics"):
        print(diagnostics())
    elif len(sys.argv) > 1 and sys.argv[1] in ("health", "check"):
        print(json.dumps(check_all(), indent=2, ensure_ascii=False))
    elif len(sys.argv) > 1 and sys.argv[1] in ("repair",):
        print(json.dumps(repair_all(), indent=2, ensure_ascii=False))
    else:
        print("Verwendung: python3 guard_check.py {diagnostics|health|repair}", file=sys.stderr)
        print("  diagnostics  Copy-paste-fertiger Text-Report fuer ein GitHub-Issue", file=sys.stderr)
        print("  health       Rohe JSON-Pruefung (wie /api/plugins/aiianer-hub/health)", file=sys.stderr)
        print("  repair       Erzwingt eine Reparatur (wie der Waechter beim Gateway-Start)", file=sys.stderr)
        sys.exit(1)
