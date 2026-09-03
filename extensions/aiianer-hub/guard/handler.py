"""AIIANER Waechter.

Feuert auf gateway:startup. Prueft, ob ein Hermes-Update die deutschen
Erweiterungen aus dem Checkout entfernt hat, und stellt sie wieder her.
Faellt still aus, wenn nichts installiert ist. Fehler werden geloggt und
nie weitergeworfen, damit der Gateway-Start nie an uns scheitert.
"""

import os
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
STATE_DIR = HERMES_HOME / "aiianer"

if str(STATE_DIR) not in sys.path:
    sys.path.insert(0, str(STATE_DIR))


async def handle(event_type: str, context: dict):
    try:
        import guard_check  # liegt unter ~/.hermes/aiianer/
    except Exception:
        return

    try:
        status = guard_check.check_all()
        if status.get("ok"):
            return
        guard_check.repair_all()
    except Exception as exc:
        try:
            guard_check._log(f"Waechter abgebrochen: {exc}")
        except Exception:
            pass
