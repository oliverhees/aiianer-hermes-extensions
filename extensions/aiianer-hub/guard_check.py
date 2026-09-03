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


def check_plugin(comp_id: str) -> dict:
    """Liegt ein sauberes Plugin noch an seinem Platz?"""
    if comp_id not in _installed():
        return {"id": comp_id, "state": "not-installed"}
    for candidate in (
        HERMES_HOME / "plugins" / comp_id,
        HERMES_HOME / "plugins" / "model-providers" / "eurouter",
        HERMES_HOME / "desktop-plugins" / comp_id,
    ):
        if candidate.exists():
            return {"id": comp_id, "state": "ok"}
    return {"id": comp_id, "state": "missing"}


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


def repair_all() -> dict:
    status = check_all()
    results = []
    for c in status["checks"]:
        if c["state"] != "missing":
            continue
        if c["id"] == "german-language":
            results.append(repair_german())
        else:
            results.append({
                "id": c["id"], "repaired": False,
                "hint": "Im AIIANER-Marktplatz erneut installieren.",
            })
    if not results:
        _log("Pruefung ok, nichts zu tun")
    return {"ok": all(r.get("repaired") for r in results) if results else True,
            "results": results}
