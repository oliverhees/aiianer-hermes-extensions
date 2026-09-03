#!/usr/bin/env python3
"""Haengt die einstellbaren Gruppenchat-Grenzen in Hermes ein.

Genau EIN Eingriff in Hermes' eigenen Code: die Rundenschleife holt ihre
Deckel nicht mehr aus vier Konstanten, sondern aus einer Funktion, die sie pro
Raum aufloest. Upstream hat diese Naht selbst vorbereitet und die Deckel dafuer
in einen Block gelegt.

Dazu zwei Dateien, die uns gehoeren und niemandem im Weg stehen:

  aiianer-group-limits.ts        die Logik
  aiianer-group-limits.data.ts   die Werte, erzeugt aus
                                 ~/.hermes/aiianer/gruppen-grenzen.json

Warum erzeugt und nicht gelesen: der Code laeuft im Renderer und kommt an
keine Datei. Die Konfiguration wird deshalb beim Einspielen zu Code und beim
naechsten Start mitgebaut.

Idempotent, alles-oder-nichts, Erstsicherung einmalig.
"""

import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".hermes" / "hermes-agent"
BOTS = AGENT / "apps" / "desktop" / "src" / "plugins" / "hermes-bots"
ZIEL = BOTS / "group-rounds.ts"

MARKE = "aiianer-group-limits"

# Die vier Konstanten und ihr Ersatz. Reihenfolge egal, die Namen sind
# eindeutig genug fuer eine wortweise Ersetzung.
ERSATZ = {
    "GROUP_CHAT_MAX_ROUNDS": "aiianerGrenzen.rounds",
    "GROUP_CHAT_MAX_MESSAGES": "aiianerGrenzen.messages",
    "GROUP_CHAT_MAX_CONTINUATIONS": "aiianerGrenzen.continuations",
    "GROUP_CHAT_HISTORY_LIMIT": "aiianerGrenzen.history",
}

ANKER_FN = "export async function runGroupChatRounds(group: string, members: GroupMember[], thread: string) {"
ANKER_EXIT = "  let exitKind: 'capped' | 'settled' = 'settled'"


def fail(msg: str) -> None:
    print(f"FEHLER: {msg}", file=sys.stderr)
    raise SystemExit(1)


def schreibe_daten(zustandsordner: Path) -> int:
    """Erzeugt aiianer-group-limits.data.ts aus der JSON-Datei."""
    quelle = zustandsordner / "gruppen-grenzen.json"
    daten = {}
    if quelle.is_file():
        try:
            geladen = json.loads(quelle.read_text(encoding="utf-8"))
            if isinstance(geladen, dict):
                daten = {str(k): v for k, v in geladen.items() if isinstance(v, dict)}
            else:
                print(f"WARNUNG: {quelle} enthaelt kein Objekt, wird ignoriert.", file=sys.stderr)
        except Exception as exc:
            fail(f"{quelle} ist kein gueltiges JSON: {exc}")

    inhalt = (
        "// ERZEUGT von apply-limits.py aus ~/.hermes/aiianer/gruppen-grenzen.json\n"
        "// Nicht von Hand aendern: der naechste Lauf ueberschreibt die Datei.\n"
        "// Schluessel ist der Gruppenname, '*' gilt fuer alle Raeume ohne\n"
        "// eigenen Eintrag. Achsen: rounds, messages, continuations, history,\n"
        "// safetyRounds, safetyMessages. null heisst aus.\n"
        "export const AIIANER_GROUP_LIMITS: Record<string, Record<string, null | number>> =\n"
        + json.dumps(daten, ensure_ascii=False, indent=2)
        + "\n"
    )
    (BOTS / "aiianer-group-limits.data.ts").write_text(inhalt, encoding="utf-8")

    return len(daten)


def main() -> None:
    if not ZIEL.is_file():
        fail(
            f"Rundenschleife nicht gefunden unter {ZIEL}. "
            "Ist Hermes Desktop installiert und aktuell?"
        )
    for name in ("aiianer-group-limits.ts",):
        if not (HERE / name).is_file():
            fail(f"{name} fehlt neben dem Installer")

    zustand = Path(
        sys.argv[2] if len(sys.argv) > 2 else Path.home() / ".hermes" / "aiianer"
    )
    anzahl = schreibe_daten(zustand)
    shutil.copy2(HERE / "aiianer-group-limits.ts", BOTS / "aiianer-group-limits.ts")

    inhalt = ZIEL.read_text()

    # Erstsicherung: einmalig, und nur von einem nachweislich unveraenderten
    # Stand. Ein spaeterer Lauf darf sie nie ueberschreiben.
    orig = ZIEL.with_suffix(".ts.aiianer-orig")
    if not orig.exists() and MARKE not in inhalt:
        shutil.copy2(ZIEL, orig)

    if MARKE in inhalt:
        # Schon verdrahtet. Nur die Werte wurden neu erzeugt, das reicht.
        print(f"OK: Grenzen aktualisiert ({anzahl} Raeume konfiguriert)")
        print("Hinweis: Hermes Desktop neu starten, damit die Werte greifen.")
        return

    if ANKER_FN not in inhalt:
        fail(
            "Anker 'runGroupChatRounds' nicht gefunden. Hermes hat die "
            "Rundenschleife umgebaut - bitte in der AIIANER Community melden."
        )
    if ANKER_EXIT not in inhalt:
        fail("Anker 'exitKind' nicht gefunden (Upstream-Drift)")
    fehlend = [k for k in ERSATZ if k not in inhalt]
    if fehlend:
        fail("Diese Konstanten fehlen in der Schleife: " + ", ".join(fehlend))

    neu = inhalt

    # 1) Import direkt hinter dem letzten bestehenden Import
    letzte_import_zeile = max(
        m.end() for m in re.finditer(r"^import .*?(?:^\} from '[^']+'|from '[^']+')$", neu, re.M | re.S)
    )
    neu = (
        neu[:letzte_import_zeile]
        + "\n// AIIANER: einstellbare Grenzen pro Gruppenchat.\n"
        + "import { aiianerCaps } from './aiianer-group-limits'"
        + neu[letzte_import_zeile:]
    )

    # 2) Aufloesen, einmal je Lauf, direkt nach exitKind
    neu = neu.replace(
        ANKER_EXIT,
        ANKER_EXIT
        + "\n\n  // AIIANER: Deckel dieses Raums. Einmal aufloesen, nicht in der\n"
        + "  // Schleife: die Werte duerfen sich waehrend eines Laufs nicht aendern.\n"
        + "  const aiianerGrenzen = aiianerCaps(group)",
        1,
    )

    # 3) Die vier Konstanten in der Schleife ersetzen. Wortgrenzen, damit
    #    GROUP_CHAT_MAX_MESSAGES nicht in GROUP_CHAT_MAX_MESSAGES_SOMETHING
    #    hineingreift.
    koerper_start = neu.index(ANKER_FN)
    kopf, koerper = neu[:koerper_start], neu[koerper_start:]

    # Zeilenweise, und Kommentare bleiben unangetastet: sonst steht dort
    # spaeter "All aiianerGrenzen.rounds rounds ran", was niemandem hilft und
    # den naechsten Leser in die Irre fuehrt.
    zeilen = koerper.split("\n")
    for i, zeile in enumerate(zeilen):
        entkleidet = zeile.lstrip()
        if entkleidet.startswith(("//", "*", "/*")):
            continue
        for alt_name, ersatz in ERSATZ.items():
            zeile = re.sub(rf"\b{alt_name}\b", ersatz, zeile)
        zeilen[i] = zeile
    neu = kopf + "\n".join(zeilen)

    # 4) Ungenutzt gewordene Importe entfernen, sonst meckert der Linter
    for alt in ERSATZ:
        if not re.search(rf"\b{alt}\b", neu[neu.index(ANKER_FN):]):
            neu = re.sub(rf"^\s*{alt},\n", "", neu, count=1, flags=re.M)

    bak = ZIEL.with_suffix(".ts.aiianer-bak")
    shutil.copy2(ZIEL, bak)
    try:
        ZIEL.write_text(neu)
        gepr = ZIEL.read_text()
        # Am Ergebnis pruefen, nicht an der Abwesenheit: die Konstanten
        # duerfen in Kommentaren stehen bleiben, dort sind sie richtig.
        koerper_neu = gepr[gepr.index(ANKER_FN):]
        code_zeilen = [
            z for z in koerper_neu.split("\n") if not z.lstrip().startswith(("//", "*", "/*"))
        ]
        rest = [
            k for k in ERSATZ if re.search(rf"\b{k}\b", "\n".join(code_zeilen))
        ]
        ok = (
            "aiianerCaps(group)" in gepr
            and MARKE in gepr
            and not rest
            and len(re.findall(r"\baiianerGrenzen\.", koerper_neu)) >= 8
        )
        if not ok and rest:
            raise RuntimeError("nicht ersetzt: " + ", ".join(rest))
        if not ok:
            raise RuntimeError("Verifikation nach dem Schreiben fehlgeschlagen")
    except Exception as exc:
        shutil.copy2(bak, ZIEL)
        fail(f"Einhaengen fehlgeschlagen, Datei wiederhergestellt: {exc}")

    print(f"OK: Grenzen eingehaengt ({anzahl} Raeume konfiguriert)")
    print(f"Konfiguration: {zustand / 'gruppen-grenzen.json'}")
    print("Hinweis: Hermes Desktop neu starten, damit die Werte greifen.")


if __name__ == "__main__":
    main()
