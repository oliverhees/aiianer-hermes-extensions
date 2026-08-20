#!/usr/bin/env bash
# Installiert die deutsche Sprachdatei fuer Hermes Desktop (Interims-Weg,
# bis Upstream-PR NousResearch/hermes-agent#51762 gemerged ist).
# Nach einem Hermes-Update, das Deutsch wieder entfernt: einfach erneut ausfuehren.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
AGENT_DIR="${HERMES_AGENT_DIR:-$HERMES_HOME_DIR/hermes-agent}"
STORE="$HERMES_HOME_DIR/aiianer-extensions/german-language"

# Remote-Bootstrap (curl | bash): Payload aus dem Repo-Tarball holen
if [ ! -f "$HERE/de.ts" ]; then
  echo "Kein lokaler Clone gefunden - lade AIIANER Hermes Extensions von GitHub ..."
  TMP_DIR="$(mktemp -d)"; trap 'rm -rf "$TMP_DIR"' EXIT
  curl -sL "https://github.com/oliverhees/aiianer-hermes-extensions/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP_DIR"
  INNER="$(find "$TMP_DIR" -path "*extensions/german-language/install.sh" | head -1)"
  [ -n "$INNER" ] || { echo "FEHLER: Download fehlgeschlagen." >&2; exit 1; }
  exec bash "$INNER" "$@"
fi

# Payload dauerhaft ablegen (fuer spaeteres Re-Apply ohne erneuten Download)
mkdir -p "$STORE"
cp "$HERE/de.ts" "$HERE/apply-de.py" "$STORE/"

python3 "$STORE/apply-de.py" "$AGENT_DIR"
echo ""
echo "Fertig. Hermes Desktop komplett neu starten - beim ersten Start baut die App kurz neu."
echo "Sprache umstellen: Settings -> Language -> Deutsch."
echo "Falls Deutsch nach einem Hermes-Update verschwindet: diesen Installer einfach nochmal ausfuehren."
