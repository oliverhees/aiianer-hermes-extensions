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

# Wo Hermes seine Daten haelt. Reihenfolge wie in Hermes' eigenem install.ps1:
#   1. HERMES_HOME, wenn gesetzt
#   2. natives Windows (Git Bash, MSYS, Cygwin): %LOCALAPPDATA%\hermes
#   3. sonst (Linux, macOS, WSL): ~/.hermes
resolve_hermes_home() {
  if [ -n "${HERMES_HOME:-}" ]; then
    printf '%s' "$HERMES_HOME"; return
  fi
  case "$(uname -s 2>/dev/null || echo unknown)" in
    MINGW*|MSYS*|CYGWIN*)
      if [ -n "${LOCALAPPDATA:-}" ]; then
        if command -v cygpath >/dev/null 2>&1; then
          printf '%s' "$(cygpath -u "$LOCALAPPDATA")/hermes"
        else
          printf '%s' "${LOCALAPPDATA//\\//}/hermes"
        fi
        return
      fi
      ;;
  esac
  printf '%s' "$HOME/.hermes"
}

HERMES_HOME_DIR="$(resolve_hermes_home)"

PLUGIN_DIR="$HERMES_HOME_DIR/plugins/aiianer-hub"
HOOK_DIR="$HERMES_HOME_DIR/hooks/aiianer-guard"
STATE_DIR="$HERMES_HOME_DIR/aiianer"

if [ ! -d "$HERMES_HOME_DIR" ]; then
  echo "FEHLER: $HERMES_HOME_DIR existiert nicht." >&2
  echo "" >&2
  echo "Gesucht wurde dort, weil:" >&2
  if [ -n "${HERMES_HOME:-}" ]; then
    echo "  HERMES_HOME ist auf diesen Pfad gesetzt." >&2
  else
    case "$(uname -s 2>/dev/null || echo unknown)" in
      MINGW*|MSYS*|CYGWIN*) echo "  Du bist auf nativem Windows, dort liegt Hermes unter %LOCALAPPDATA%\\hermes." >&2 ;;
      *) echo "  Auf Linux, macOS und WSL liegt Hermes unter ~/.hermes." >&2 ;;
    esac
  fi
  echo "" >&2
  echo "Ist Hermes installiert? Falls es woanders liegt, setze HERMES_HOME." >&2
  exit 1
fi

echo "Hermes-Verzeichnis: $HERMES_HOME_DIR"

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
