#!/usr/bin/env python3
"""Notausstieg ohne Hermes Desktop: setzt types.ts/catalog.ts/languages.ts auf
den Stand VOR der deutschen Sprachdatei zurueck und entfernt de.ts.

Fuer genau den Fall, dass die GUI nach der Installation nicht mehr aufgeht
(gemeldet in GitHub-Issue #1) und der normale Weg - Deinstallieren im
Marktplatz-Reiter - deshalb nicht erreichbar ist. Spiegelt exakt die
Rueckbau-Logik aus dashboard/plugin_api.py::_uninstall_german, nur ohne
FastAPI/Backend, direkt vom Terminal aus lauffaehig:

    python3 restore-original.py [Pfad-zu-hermes-agent]

Ohne Argument wird $HERMES_HOME/hermes-agent bzw. ~/.hermes/hermes-agent
angenommen. Alles-oder-nichts: entweder alle drei Dateien lassen sich aus
einer nachweislich unverdrahteten Sicherung wiederherstellen, oder es wird
NICHTS veraendert.
"""
import os
import re
import shutil
import sys
from pathlib import Path


def hermes_home() -> Path:
    env = os.environ.get("HERMES_HOME", "").strip()
    if env:
        return Path(env)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "").strip()
        if local:
            return Path(local) / "hermes"
        return Path.home() / "AppData" / "Local" / "hermes"
    return Path.home() / ".hermes"


AGENT = Path(sys.argv[1]) if len(sys.argv) > 1 else hermes_home() / "hermes-agent"
I18N = AGENT / "apps" / "desktop" / "src" / "i18n"
NAMEN = ("types.ts", "catalog.ts", "languages.ts")


def fail(msg: str) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(1)


def verdrahtet(name: str, inhalt: str) -> bool:
    if name == "types.ts":
        m = re.search(r"^export type Locale = (.+)$", inhalt, re.M)
        return bool(m and "'de'" in m.group(1))
    if name == "catalog.ts":
        return "./de'" in inhalt
    if name == "languages.ts":
        return "id: 'de'" in inhalt
    return False


def sicherung_fuer(name: str) -> Path | None:
    for endung in (".aiianer-orig", ".aiianer-bak"):
        kandidat = I18N / (name + endung)
        if not kandidat.is_file():
            continue
        try:
            if not verdrahtet(name, kandidat.read_text()):
                return kandidat
        except Exception:
            continue
    return None


def main() -> None:
    if not I18N.is_dir():
        fail(f"i18n-Verzeichnis nicht gefunden: {I18N} - Pfad zu hermes-agent als Argument mitgeben?")

    quellen = {n: sicherung_fuer(n) for n in NAMEN}
    fehlend = [n for n, q in quellen.items() if q is None]
    if fehlend:
        fail(
            "Keine brauchbare Sicherung des Originalzustands fuer: "
            + ", ".join(fehlend)
            + ". Es wurde nichts veraendert. Bitte in der AIIANER Community "
            "melden (mit dem Inhalt von " + str(I18N) + ")."
        )

    for name in NAMEN:
        shutil.copy2(quellen[name], I18N / name)
        print(f"wiederhergestellt: {name}")

    reste = [n for n in NAMEN if verdrahtet(n, (I18N / n).read_text())]
    if reste:
        fail(
            "Nach dem Wiederherstellen tragen diese Dateien immer noch die "
            "deutsche Verdrahtung, de.ts wurde deshalb NICHT geloescht, damit "
            "Hermes weiter baut: " + ", ".join(reste) + ". Bitte in der "
            "AIIANER Community melden."
        )

    de = I18N / "de.ts"
    if de.is_file():
        de.unlink()
        print("entfernt: de.ts")

    for name in NAMEN:
        for endung in (".aiianer-bak", ".aiianer-orig"):
            p = I18N / (name + endung)
            if p.is_file():
                p.unlink()

    stamp = hermes_home() / "desktop-build-stamp.json"
    if stamp.is_file():
        stamp.unlink()
        print("Desktop-Build-Stempel entfernt - naechster Start baut neu")

    print("\nFertig. Hermes Desktop jetzt komplett beenden (auch den Gateway-Prozess, "
          "z. B. per Taskmanager/'hermes gateway stop', falls er separat laeuft) "
          "und neu starten.")


if __name__ == "__main__":
    main()
