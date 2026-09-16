"""AIIANER Waechter.

Feuert auf gateway:startup. Prueft, ob ein Hermes-Update die deutschen
Erweiterungen aus dem Checkout entfernt hat, und stellt sie wieder her.
Faellt still aus, wenn nichts installiert ist. Fehler werden geloggt und
nie weitergeworfen, damit der Gateway-Start nie an uns scheitert.

Repariert MIT sofortigem Desktop-Neubau (rebuild_desktop=True): Gateway-Hooks
laufen laut Hermes' eigener Doku "without blocking the main agent pipeline" -
ein mehrminuetiger Neubau haengt den Gateway-Start also nicht auf. Und er
lohnt sich hier besonders: gateway:startup nach einem Hermes-Update ist genau
der Moment, in dem Hermes selbst den Nutzer schon durch seinen eigenen
Update-Bildschirm ("Fenster schliesst sich, Neustart folgt automatisch")
geschickt hat - ein Wartemoment, den der Nutzer ohnehin schon erwartet. Ohne
diesen Schritt bliebe Deutsch bis zum naechsten manuellen Klick auf
"Reparieren" im Marktplatz unsichtbar, obwohl der Quellcode laengst wieder
stimmt (siehe README, Abschnitt Update-Sicherheit).
"""

import os
import sys
from pathlib import Path

def _hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME", "").strip()
    if env:
        return Path(env)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if local:
            return Path(local) / "hermes"
        return Path.home() / "AppData" / "Local" / "hermes"
    return Path.home() / ".hermes"


STATE_DIR = _hermes_home() / "aiianer"

if str(STATE_DIR) not in sys.path:
    sys.path.insert(0, str(STATE_DIR))


async def handle(event_type: str, context: dict):
    try:
        import guard_check  # liegt unter ~/.hermes/aiianer/
    except Exception:
        return

    # Kein Vorab-"check_all().ok -> return" mehr: repair_all() muss IMMER
    # laufen, weil es selbst noch zusaetzlich prueft, ob ein fruehrerer Lauf
    # den Build-Stempel entfernt hat, ohne dass seitdem neu gebaut wurde -
    # genau diese Kombination (Quellcode laengst wieder ok, Stempel aber noch
    # weg) meldete check_all() alleine faelschlich als "nichts zu tun".
    # repair_all() selbst bleibt fuer den haeufigen Fall (wirklich nichts zu
    # tun) billig, kein Grund, hier zusaetzlich vorzufiltern.
    try:
        guard_check.repair_all(rebuild_desktop=True)
    except Exception as exc:
        try:
            guard_check._log(f"Waechter abgebrochen: {exc}")
        except Exception:
            pass
