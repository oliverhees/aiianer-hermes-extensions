#!/usr/bin/env python3
"""Traegt ein deutsches Buendel in den Nachrichtenkatalog des Hermes-Bot-Modus.

Warum so und nicht als Dateiersatz: Bot Mode war frueher eine einzelne Datei,
die man komplett uebersetzt austauschen konnte. Hermes hat ihn seither auf 47
Module aufgeteilt und einen eigenen, plugin-lokalen Katalog eingefuehrt
(hermes-bots/i18n.ts, registriert ueber ctx.i18n.register). Damit ist die
Uebersetzung wieder eine additive Sache: EIN 'de'-Buendel dazu, und 'de' in
BOTS_LOCALES eintragen. Alles andere bleibt unberuehrt.

Voraussetzung: 'de' muss eine gueltige Locale sein. Das erledigt die Komponente
german-language (apply-de.py erweitert die Locale-Union in i18n/types.ts). Ohne
sie waere das Buendel zwar registriert, aber nie erreichbar.

Idempotent: ein erneuter Lauf ersetzt nur das de-Buendel. Alles-oder-nichts mit
Restore aus .aiianer-bak. Die Erstsicherung .aiianer-orig entsteht einmalig und
wird nie ueberschrieben - sonst sicherte ein spaeterer Lauf die eigene
Aenderung als vermeintliches Original.
"""

import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".hermes" / "hermes-agent"
BOTS = AGENT / "apps" / "desktop" / "src" / "plugins" / "hermes-bots"
ZIEL = BOTS / "i18n.ts"
QUELLE = HERE / "de-bots.ts"

ANKER_LOCALES = re.compile(
    r"^export const BOTS_LOCALES: PluginLocaleBundles = \{(?P<inhalt>[^}]*)\}\s*$", re.M
)
BLOCK_DE = re.compile(r"^const de: BotsMessages = \{.*?^\}\s*$", re.S | re.M)


def fail(msg: str) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    if not ZIEL.is_file():
        fail(
            f"Nachrichtenkatalog des Bot-Modus nicht gefunden unter {ZIEL}. "
            "Ist Hermes Desktop installiert und aktuell?"
        )
    if not QUELLE.is_file():
        fail(f"de-bots.ts fehlt neben dem Installer ({QUELLE})")

    inhalt = ZIEL.read_text()

    m_loc = ANKER_LOCALES.search(inhalt)
    if not m_loc:
        fail(
            "Anker 'export const BOTS_LOCALES' nicht gefunden. Hermes hat den "
            "Katalog umgebaut - bitte in der AIIANER Community melden."
        )
    if "const en: BotsMessages = {" not in inhalt:
        fail("Anker 'const en: BotsMessages' nicht gefunden (Upstream-Drift)")

    de_block = QUELLE.read_text().rstrip() + "\n"
    if not de_block.startswith("const de: BotsMessages = {"):
        fail("de-bots.ts beginnt nicht mit 'const de: BotsMessages = {'")

    # Erstsicherung: einmalig, und nur von einem nachweislich unverdrahteten
    # Stand. Ein spaeterer Lauf darf sie nie ueberschreiben.
    orig = ZIEL.with_suffix(".ts.aiianer-orig")
    if not orig.exists() and "const de: BotsMessages" not in inhalt:
        shutil.copy2(ZIEL, orig)

    neu = inhalt
    if BLOCK_DE.search(neu):
        neu = BLOCK_DE.sub(de_block.rstrip(), neu, count=1)
        zustand = "aktualisiert"
    else:
        # Vor BOTS_LOCALES einsetzen, damit die Konstante darueber steht.
        pos = neu.index("export const BOTS_LOCALES")
        neu = neu[:pos] + de_block + "\n" + neu[pos:]
        zustand = "neu eingetragen"

    m_loc = ANKER_LOCALES.search(neu)
    if "de," not in m_loc.group("inhalt") and " de " not in m_loc.group("inhalt"):
        alt = m_loc.group(0)
        ersatz = alt.replace("{ en,", "{ en, de,", 1)
        if ersatz == alt:
            fail("BOTS_LOCALES hat eine unerwartete Form, Eintrag nicht moeglich")
        neu = neu.replace(alt, ersatz, 1)

    # Alles-oder-nichts
    bak = ZIEL.with_suffix(".ts.aiianer-bak")
    shutil.copy2(ZIEL, bak)
    try:
        ZIEL.write_text(neu)
        geschrieben = ZIEL.read_text()
        ok = (
            "const de: BotsMessages = {" in geschrieben
            and re.search(r"BOTS_LOCALES: PluginLocaleBundles = \{[^}]*\bde\b", geschrieben)
        )
        if not ok:
            raise RuntimeError("Verifikation nach dem Schreiben fehlgeschlagen")
    except Exception as exc:
        shutil.copy2(bak, ZIEL)
        fail(f"Eintragen fehlgeschlagen, Datei wiederhergestellt: {exc}")

    print(f"OK: Deutsches Bot-Modus-Buendel {zustand} ({ZIEL})")
    print("Hinweis: Hermes Desktop neu starten - die App baut sich einmal neu.")
    print("Die deutsche Sprache muss installiert und ausgewaehlt sein, sonst")
    print("bleibt das Buendel zwar registriert, aber unerreichbar.")


if __name__ == "__main__":
    main()
