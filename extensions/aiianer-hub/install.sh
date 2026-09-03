#!/usr/bin/env bash
# AIIANER Marktplatz installieren.
#
# Legt drei Dinge an, alle AUSSERHALB des Hermes-Checkouts:
#   ~/.hermes/plugins/aiianer-hub/   das Plugin mit Reiter und Backend
#   ~/.hermes/hooks/aiianer-guard/   der Waechter auf gateway:startup
#   ~/.hermes/aiianer/               gemeinsame Pruefjunktion und Zustand
#
# Idempotent. Mehrfaches Ausfuehren aktualisiert nur.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"

PLUGIN_DIR="$HERMES_HOME_DIR/plugins/aiianer-hub"
HOOK_DIR="$HERMES_HOME_DIR/hooks/aiianer-guard"
STATE_DIR="$HERMES_HOME_DIR/aiianer"

if [ ! -d "$HERMES_HOME_DIR" ]; then
  echo "FEHLER: $HERMES_HOME_DIR existiert nicht. Ist Hermes installiert?" >&2
  exit 1
fi

echo "Installiere AIIANER Marktplatz ..."

# 1) Plugin
mkdir -p "$PLUGIN_DIR/dashboard/dist"
cp "$HERE/plugin.yaml"                     "$PLUGIN_DIR/plugin.yaml"
cp "$HERE/catalog.json"                    "$PLUGIN_DIR/catalog.json"
cp "$HERE/dashboard/manifest.json"         "$PLUGIN_DIR/dashboard/manifest.json"
cp "$HERE/dashboard/plugin_api.py"         "$PLUGIN_DIR/dashboard/plugin_api.py"
cp "$HERE/dashboard/dist/index.js"         "$PLUGIN_DIR/dashboard/dist/index.js"
rm -rf "$PLUGIN_DIR/dashboard/__pycache__"
echo "  Plugin      -> $PLUGIN_DIR"

# 2) Gemeinsame Pruefjunktion
mkdir -p "$STATE_DIR"
cp "$HERE/guard_check.py" "$STATE_DIR/guard_check.py"
echo "  Pruefung    -> $STATE_DIR/guard_check.py"

# 3) Waechter
mkdir -p "$HOOK_DIR"
cp "$HERE/guard/HOOK.yaml"  "$HOOK_DIR/HOOK.yaml"
cp "$HERE/guard/handler.py" "$HOOK_DIR/handler.py"
rm -rf "$HOOK_DIR/__pycache__"
echo "  Waechter    -> $HOOK_DIR"

echo ""
echo "Fertig. Naechste Schritte:"
echo "  1. Hermes komplett neu starten"
echo "  2. Der Reiter 'AIIANER' erscheint neben Skills"
echo "  3. Dort auswaehlen, was du installieren willst"
echo ""
echo "Der Waechter prueft ab jetzt bei jedem Gateway-Start, ob ein"
echo "Hermes-Update etwas entfernt hat, und spielt es erneut ein."
