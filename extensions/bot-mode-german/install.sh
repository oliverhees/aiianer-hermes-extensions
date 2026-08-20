#!/usr/bin/env bash
# Deutsche Uebersetzung fuer Hermes "Bot Mode" (Plugin hermes-bots).
#
# Interims-Weg, bis der Upstream-PR gemerged ist: Bot Mode liegt als
# gebuendeltes Plugin IM Hermes-Checkout und hat upstream noch gar keine
# i18n-Anbindung - alle Texte sind dort hart englisch. Diese Komponente
# ersetzt die Plugin-Datei durch die uebersetzte Fassung (identischer Code,
# nur alle Texte ueber ctx.i18n mit EN- und DE-Bundle).
#
# SICHERHEITSNETZ: Ersetzt wird NUR, wenn die vorhandene Datei exakt der
# Upstream-Fassung entspricht, von der wir portiert haben. Hat Hermes Bot
# Mode inzwischen weiterentwickelt, bricht der Installer bewusst ab, statt
# neue Funktionen still gegen eine aeltere Uebersetzung zu tauschen.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
AGENT_DIR="${HERMES_AGENT_DIR:-$HERMES_HOME_DIR/hermes-agent}"
TARGET="$AGENT_DIR/apps/desktop/src/plugins/hermes-bots/plugin.js"
STORE="$HERMES_HOME_DIR/aiianer-extensions/bot-mode-german"

# Remote-Bootstrap (curl | bash)
if [ ! -f "$HERE/plugin.js" ]; then
  echo "Kein lokaler Clone gefunden - lade AIIANER Hermes Extensions von GitHub ..."
  TMP_DIR="$(mktemp -d)"; trap 'rm -rf "$TMP_DIR"' EXIT
  curl -sL "https://github.com/oliverhees/aiianer-hermes-extensions/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP_DIR"
  INNER="$(find "$TMP_DIR" -path "*extensions/bot-mode-german/install.sh" | head -1)"
  [ -n "$INNER" ] || { echo "FEHLER: Download fehlgeschlagen." >&2; exit 1; }
  exec bash "$INNER" "$@"
fi

# shellcheck source=/dev/null
. "$HERE/base.sha256"

if [ ! -f "$TARGET" ]; then
  echo "FEHLER: Bot-Mode-Plugin nicht gefunden unter $TARGET" >&2
  echo "Ist Hermes Desktop installiert? (Bot Mode gehoert zum Lieferumfang.)" >&2
  exit 1
fi

CURRENT="$(sha256sum "$TARGET" | cut -d' ' -f1)"

if [ "$CURRENT" = "$TRANSLATED_SHA256" ]; then
  echo "Bot Mode ist bereits auf Deutsch umgestellt - nichts zu tun."
  exit 0
fi

if [ "$CURRENT" != "$UPSTREAM_BASE_SHA256" ]; then
  echo "ABBRUCH: Bot Mode hat sich seit unserer Uebersetzung geaendert." >&2
  echo "" >&2
  echo "Das heisst: Hermes hat neue Funktionen in Bot Mode gebracht. Wuerden wir" >&2
  echo "die Datei jetzt ersetzen, waeren diese Funktionen wieder weg. Deshalb" >&2
  echo "passiert hier absichtlich nichts." >&2
  echo "" >&2
  echo "Wir ziehen die Uebersetzung nach - Bescheid gibt es in der AIIANER" >&2
  echo "Community: https://aiianer.de" >&2
  exit 2
fi

mkdir -p "$STORE"
cp "$TARGET" "$STORE/plugin.js.upstream-backup"
cp "$HERE/plugin.js" "$TARGET"
cp "$HERE/plugin.js" "$HERE/base.sha256" "$STORE/" 2>/dev/null || true

echo "Bot Mode auf Deutsch umgestellt."
echo "Original gesichert unter: $STORE/plugin.js.upstream-backup"
echo ""
echo "Naechste Schritte:"
echo "  1. Hermes Desktop komplett neu starten (die App baut beim ersten Start kurz neu)"
echo "  2. Sprache unter Settings -> Language auf Deutsch stellen"
echo ""
echo "Nach einem Hermes-Update, das die Datei zuruecksetzt: diesen Installer erneut ausfuehren."
