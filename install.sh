#!/usr/bin/env bash
# AIIANER Hermes Extensions - Dispatcher.
#   ./install.sh                   verfuegbare Komponenten anzeigen
#   ./install.sh <komponente>      eine Komponente installieren
# Remote:
#   curl -sL https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/install.sh | bash -s <komponente>
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd)"

if [ ! -d "$HERE/extensions" ]; then
  TMP_DIR="$(mktemp -d)"; trap 'rm -rf "$TMP_DIR"' EXIT
  curl -sL "https://github.com/oliverhees/aiianer-hermes-extensions/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP_DIR"
  INNER="$(find "$TMP_DIR" -maxdepth 2 -name install.sh | head -1)"
  [ -n "$INNER" ] || { echo "FEHLER: Download fehlgeschlagen." >&2; exit 1; }
  exec bash "$INNER" "$@"
fi

if [ $# -eq 0 ]; then
  echo "Verfuegbare Komponenten:"
  for d in "$HERE"/extensions/*/; do
    echo "  - $(basename "$d")"
  done
  echo ""
  echo "Installation: ./install.sh <komponente>"
  exit 0
fi

COMP="$1"; shift || true
TARGET="$HERE/extensions/$COMP/install.sh"
if [ ! -f "$TARGET" ]; then
  echo "FEHLER: Komponente '$COMP' nicht gefunden. Verfuegbar:" >&2
  for d in "$HERE"/extensions/*/; do echo "  - $(basename "$d")" >&2; done
  exit 1
fi
exec bash "$TARGET" "$@"
