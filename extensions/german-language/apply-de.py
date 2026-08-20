#!/usr/bin/env python3
"""Verdrahtet die deutsche Sprachdatei drift-tolerant in den Hermes-Checkout.

Statt Upstream-Dateien zu ueberschreiben (bricht bei jedem Upstream-Drift),
werden NUR gezielte 'de'-Eintraege an stabilen Ankern eingefuegt:
  - types.ts:     | 'de' an die Locale-Union
  - catalog.ts:   import { de } + de-Eintrag im TRANSLATIONS-Record
  - languages.ts: LOCALE_OPTIONS-Eintrag + LOCALE_ALIASES
  - de.ts:        Kopie der Sprachdatei

Idempotent (erneuter Lauf aktualisiert nur de.ts), alles-oder-nichts mit
.bak-Restore bei jedem Fehler. Quelle: PR #51762 (NousResearch/hermes-agent).
Sobald der PR gemerged ist, wird dieser Installer ueberfluessig.
"""
import re, shutil, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / ".hermes" / "hermes-agent"
I18N = AGENT / "apps" / "desktop" / "src" / "i18n"

def fail(msg):
    print(f"FEHLER: {msg}", file=sys.stderr)
    sys.exit(1)

if not (I18N / "types.ts").exists():
    fail(f"i18n-Verzeichnis nicht gefunden: {I18N} - ist Hermes Desktop installiert?")

types_s = (I18N / "types.ts").read_text()
catalog_s = (I18N / "catalog.ts").read_text()
langs_s = (I18N / "languages.ts").read_text()

already = ("'de'" in types_s.split("\n", 40)[0:40] and False) or False
# Idempotenz-Check auf allen drei Dateien
m_union = re.search(r"^export type Locale = (.+)$", types_s, re.M)
if not m_union:
    fail("Anker 'export type Locale =' in types.ts nicht gefunden (Upstream-Drift) - bitte in der AIIANER Community melden")
wired = "'de'" in m_union.group(1) and "./de'" in catalog_s and "id: 'de'" in langs_s

if not wired:
    # types.ts: Union erweitern
    types_n = types_s.replace(m_union.group(0), m_union.group(0) + " | 'de'", 1) \
        if "'de'" not in m_union.group(1) else types_s

    # catalog.ts: Import + Record-Eintrag
    catalog_n = catalog_s
    if "./de'" not in catalog_n:
        m_imp = re.search(r"^import \{ \w+ \} from '\./\w[\w-]*'$", catalog_n, re.M)
        if not m_imp:
            fail("Import-Anker in catalog.ts nicht gefunden (Upstream-Drift)")
        catalog_n = catalog_n.replace(m_imp.group(0), m_imp.group(0) + "\nimport { de } from './de'", 1)
        m_rec = re.search(r"(export const TRANSLATIONS[^=]*=\s*\{)(.*?)(\n\})", catalog_n, re.S)
        if not m_rec:
            fail("TRANSLATIONS-Anker in catalog.ts nicht gefunden (Upstream-Drift)")
        body = m_rec.group(2).rstrip()
        if not body.endswith(","):
            body += ","
        catalog_n = catalog_n.replace(m_rec.group(0), m_rec.group(1) + body + "\n  de" + m_rec.group(3), 1)

    # languages.ts: LOCALE_OPTIONS + Aliases
    langs_n = langs_s
    if "id: 'de'" not in langs_n:
        m_opt = re.search(r"(export const LOCALE_OPTIONS = \[)(.*?)(\n\] as const)", langs_n, re.S)
        if not m_opt:
            fail("LOCALE_OPTIONS-Anker in languages.ts nicht gefunden (Upstream-Drift)")
        body = m_opt.group(2).rstrip()
        entry = "\n  {\n    id: 'de',\n    name: 'Deutsch',\n    englishName: 'German',\n    configValue: 'de'\n  }"
        if not body.endswith(","):
            body += ","
        langs_n = langs_n.replace(m_opt.group(0), m_opt.group(1) + body + entry + m_opt.group(3), 1)
        m_al = re.search(r"(const LOCALE_ALIASES: Record<string, Locale> = \{)(.*?)(\n\})", langs_n, re.S)
        if m_al:  # Aliases sind nice-to-have, kein Blocker
            abody = m_al.group(2).rstrip()
            if not abody.endswith(","):
                abody += ","
            aliases = "\n  de: 'de',\n  'de-de': 'de',\n  de_de: 'de',\n  'de-at': 'de',\n  'de-ch': 'de',\n  german: 'de',\n  deutsch: 'de'"
            langs_n = langs_n.replace(m_al.group(0), m_al.group(1) + abody + aliases + m_al.group(3), 1)

    # Alles-oder-nichts: Backups, schreiben, verifizieren, sonst Restore
    targets = [("types.ts", types_n), ("catalog.ts", catalog_n), ("languages.ts", langs_n)]
    for name, _ in targets:
        shutil.copy2(I18N / name, I18N / (name + ".aiianer-bak"))
    try:
        for name, content in targets:
            (I18N / name).write_text(content)
        ok = ("'de'" in re.search(r"^export type Locale = (.+)$", (I18N / "types.ts").read_text(), re.M).group(1)
              and "./de'" in (I18N / "catalog.ts").read_text()
              and "id: 'de'" in (I18N / "languages.ts").read_text())
        if not ok:
            raise RuntimeError("Verifikation nach dem Schreiben fehlgeschlagen")
    except Exception as exc:
        for name, _ in targets:
            shutil.copy2(I18N / (name + ".aiianer-bak"), I18N / name)
        fail(f"Wiring fehlgeschlagen, alle Dateien wiederhergestellt: {exc}")

# de.ts immer (neu) kopieren - so bringt ein erneuter Lauf Uebersetzungs-Updates
shutil.copy2(HERE / "de.ts", I18N / "de.ts")
state = "bereits verdrahtet, de.ts aktualisiert" if wired else "neu verdrahtet"
print(f"OK: Deutsche Sprachdatei {state} ({I18N})")
print("Hinweis: Beim naechsten Start von 'hermes desktop' baut die App sich automatisch neu (Content-Stamp).")
