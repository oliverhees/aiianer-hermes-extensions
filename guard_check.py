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
        try:
            return "aiianerCaps(group)" in ziel.read_text(errors="ignore")
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


def check_all() -> dict:
    checks = [check_german()]
    for comp_id in ("eurouter-provider", "bot-mode-german", "group-chat-limits"):
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


def repair_all() -> dict:
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
    if not results:
        _log("Pruefung ok, nichts zu tun")
    return {"ok": all(r.get("repaired") for r in results) if results else True,
            "results": results}
