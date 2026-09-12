#!/usr/bin/env bash
# Deutsches Buendel fuer den Hermes-Bot-Modus.
#
# Frueher ersetzte diese Komponente eine einzelne, komplett uebersetzte Datei.
# Hermes hat den Bot-Modus seither auf viele Module aufgeteilt und dabei einen
# plugin-eigenen Nachrichtenkatalog eingefuehrt. Damit ist die Uebersetzung
# wieder additiv: ein 'de'-Buendel dazu, fertig. Das ist stabiler, weil ein
# Upstream-Umbau am Code die Texte nicht mehr mitreisst.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
AGENT_DIR="${HERMES_AGENT_DIR:-$HERMES_HOME_DIR/hermes-agent}"
STORE="$HERMES_HOME_DIR/aiianer-extensions/bot-mode-german"

# Ohne lokalen Clone: aus dem Netz holen und dort weitermachen.
if [ ! -f "$HERE/de-bots.ts" ]; then
  echo "Kein lokaler Clone gefunden - lade AIIANER Hermes Extensions von GitHub ..."
  TMP_DIR="$(mktemp -d)"; trap 'rm -rf "$TMP_DIR"' EXIT
  curl -sL "https://github.com/oliverhees/aiianer-hermes-extensions/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP_DIR"
  INNER="$(find "$TMP_DIR" -path "*extensions/bot-mode-german/install.sh" | head -1)"
  [ -n "$INNER" ] || { echo "FEHLER: Download fehlgeschlagen." >&2; exit 1; }
  exec bash "$INNER" "$@"
fi

CATALOG="$AGENT_DIR/apps/desktop/src/plugins/hermes-bots/i18n.ts"
if [ ! -f "$CATALOG" ]; then
  echo "FEHLER: Nachrichtenkatalog des Bot-Modus nicht gefunden unter" >&2
  echo "  $CATALOG" >&2
  echo "Ist Hermes Desktop installiert und aktuell?" >&2
  exit 1
fi

# Abhaengigkeit: 'de' muss eine gueltige Locale sein, sonst ist das Buendel
# zwar registriert, aber nie erreichbar. Das erledigt german-language.
TYPES="$AGENT_DIR/apps/desktop/src/i18n/types.ts"
if [ -f "$TYPES" ] && ! grep -qE "^export type Locale = .*'de'" "$TYPES"; then
  echo "FEHLER: Die deutsche Sprache ist nicht eingerichtet." >&2
  echo "" >&2
  echo "Der Bot-Modus haengt daran: ohne 'de' als gueltige Sprache waere das" >&2
  echo "Buendel zwar eingetragen, aber Hermes koennte es nie auswaehlen." >&2
  echo "" >&2
  echo "Installiere zuerst 'Deutsche Sprache' im AIIANER-Marktplatz." >&2
  exit 2
fi

mkdir -p "$STORE"
cp "$HERE/de-bots.ts" "$HERE/apply-bots-de.py" "$STORE/"
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
"$PY" "$STORE/apply-bots-de.py" "$AGENT_DIR"

echo ""
echo "Fertig. Hermes Desktop komplett neu starten - beim ersten Start baut die App kurz neu."
echo "Falls der Bot-Modus nach einem Hermes-Update wieder englisch ist:"
echo "im AIIANER-Marktplatz auf 'Neu einspielen', oder der Waechter holt es beim"
echo "naechsten Gateway-Start selbst nach."
