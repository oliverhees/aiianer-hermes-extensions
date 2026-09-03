#!/usr/bin/env bash
# Einstellbare Grenzen fuer Hermes-Gruppenchats.
#
# Hermes deckelt hart: 3 Runden, 10 Nachrichten. Bei sechs Bots greift die Zehn
# praktisch immer zuerst, der Raum ist nach knapp zwei Runden still. Diese
# Komponente macht die Deckel pro Raum einstellbar.
#
# Ein einziger Eingriff in Hermes' Code: die Rundenschleife holt ihre Deckel
# aus einer Funktion statt aus vier Konstanten. Upstream hat diese Naht selbst
# vorbereitet.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
AGENT_DIR="${HERMES_AGENT_DIR:-$HERMES_HOME_DIR/hermes-agent}"
STATE_DIR="$HERMES_HOME_DIR/aiianer"
STORE="$HERMES_HOME_DIR/aiianer-extensions/group-chat-limits"

if [ ! -f "$HERE/aiianer-group-limits.ts" ]; then
  echo "Kein lokaler Clone gefunden - lade AIIANER Hermes Extensions von GitHub ..."
  TMP_DIR="$(mktemp -d)"; trap 'rm -rf "$TMP_DIR"' EXIT
  curl -sL "https://github.com/oliverhees/aiianer-hermes-extensions/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP_DIR"
  INNER="$(find "$TMP_DIR" -path "*extensions/group-chat-limits/install.sh" | head -1)"
  [ -n "$INNER" ] || { echo "FEHLER: Download fehlgeschlagen." >&2; exit 1; }
  exec bash "$INNER" "$@"
fi

TARGET="$AGENT_DIR/apps/desktop/src/plugins/hermes-bots/group-rounds.ts"
if [ ! -f "$TARGET" ]; then
  echo "FEHLER: Rundenschleife des Gruppenchats nicht gefunden unter" >&2
  echo "  $TARGET" >&2
  echo "Ist Hermes Desktop installiert und aktuell?" >&2
  exit 1
fi

mkdir -p "$STATE_DIR" "$STORE"

# Beispiel-Konfiguration anlegen, aber niemals eine vorhandene ueberschreiben.
if [ ! -f "$STATE_DIR/gruppen-grenzen.json" ]; then
  cp "$HERE/gruppen-grenzen.beispiel.json" "$STATE_DIR/gruppen-grenzen.json"
  echo "Beispiel-Konfiguration angelegt: $STATE_DIR/gruppen-grenzen.json"
fi

cp "$HERE/aiianer-group-limits.ts" "$HERE/apply-limits.py" \
   "$HERE/gruppen-grenzen.beispiel.json" "$STORE/"
cp "$HERE/aiianer-group-limits.ts" "$HERE/apply-limits.py" "$STATE_DIR/"

python3 "$STORE/apply-limits.py" "$AGENT_DIR" "$STATE_DIR"

echo ""
echo "Fertig. Hermes Desktop komplett neu starten - beim ersten Start baut die App kurz neu."
echo ""
echo "Grenzen aendern:"
echo "  1. $STATE_DIR/gruppen-grenzen.json bearbeiten"
echo "  2. Im AIIANER-Marktplatz auf 'Neu einspielen'"
echo "  3. Hermes neu starten"
