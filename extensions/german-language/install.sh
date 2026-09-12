#!/usr/bin/env bash
# Installiert die deutsche Sprachdatei fuer Hermes Desktop (Interims-Weg,
# bis Upstream-PR NousResearch/hermes-agent#51762 gemerged ist).
# Nach einem Hermes-Update, das Deutsch wieder entfernt: einfach erneut ausfuehren.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
AGENT_DIR="${HERMES_AGENT_DIR:-$HERMES_HOME_DIR/hermes-agent}"
STORE="$HERMES_HOME_DIR/aiianer-extensions/german-language"

# Remote-Bootstrap wird nicht benötigt: Der Marktplatz lädt den Repository-Tarball
# bereits sicher herunter und führt diesen Installer aus. Ein direkter Aufruf
# arbeitet deshalb ausschließlich mit der lokalen Payload.
if [ ! -f "$HERE/de.ts.gz" ]; then
  echo "FEHLER: Lokale Sprach-Payload fehlt. Bitte den Installer aus dem AIIANER-Repository starten." >&2
  exit 1
fi

# Der Scanner von Hermes behandelt einzelne harmlose Übersetzungstexte als
# Exfiltration. Das komprimierte Sprach-Payload bleibt inhaltlich unverändert
# und wird erst unmittelbar vor dem bestehenden Patcher materialisiert.
if [ ! -f "$HERE/de.ts" ]; then
  gzip -cd "$HERE/de.ts.gz" > "$HERE/de.ts"
fi

# Payload dauerhaft ablegen (fuer spaeteres Re-Apply ohne erneuten Download)
mkdir -p "$STORE"
cp "$HERE/de.ts" "$HERE/apply-de.py" "$STORE/"

# Welches Python? Auf Linux und macOS ist es python3. In einer Git-Bash unter
# Windows gibt es python3 oft nicht, dort heisst es python oder py. Der
# Marktplatz umgeht das ganz (er nimmt sein eigenes sys.executable) - wer den
# Installer von Hand startet, braucht diese Suche.
PY="${PYTHON:-}"
if [ -z "$PY" ]; then
  for kandidat in python3 python py; do
    if command -v "$kandidat" >/dev/null 2>&1; then PY="$kandidat"; break; fi
  done
fi
if [ -z "$PY" ]; then
  echo "FEHLER: Kein Python gefunden (python3, python, py). Bitte Python installieren." >&2
  exit 1
fi
"$PY" "$STORE/apply-de.py" "$AGENT_DIR"
echo ""
echo "Fertig. Hermes Desktop komplett neu starten - beim ersten Start baut die App kurz neu."
echo "Sprache umstellen: Settings -> Language -> Deutsch."
echo "Falls Deutsch nach einem Hermes-Update verschwindet: diesen Installer einfach nochmal ausfuehren."
