#!/usr/bin/env bash
# Einstellbare Limits fuer Hermes Gruppenchats (Plugin hermes-bots).
#
# Bot Mode deckelt jeden Gruppenchat hart: 3 Runden und 10 Bot-Nachrichten
# pro Nachricht, die du schickst, dazu 6 Mitglieder und 24 Verlaufszeilen.
# Die Zehn bindet dabei fast immer zuerst - bei 6 Bots ist eine Runde schon
# 6 Nachrichten, das Rundenlimit wird also nie erreicht.
#
# Diese Komponente macht alle vier Werte pro Raum einstellbar: als Zahl, aus,
# oder unveraendert. "Aus" uebergibt an eine Notbremse (Standard 50 Runden /
# 200 Nachrichten), die sich ebenfalls abschalten laesst - dann laeuft der
# Raum, bis alle Bots passen oder du erneut schreibst.
#
# ANDERS ALS DIE UEBRIGEN AIIANER-KOMPONENTEN wird hier nicht die ganze
# Plugin-Datei ersetzt, sondern ein Patch angewendet. Das ueberlebt kleine
# Hermes-Updates: der Patch findet seine Stellen auch, wenn sie ein paar
# Zeilen verrutscht sind. Passt er gar nicht mehr, bricht der Installer ab,
# statt irgendetwas kaputt zu schreiben.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]:-.}")" 2>/dev/null && pwd)"
HERMES_HOME_DIR="${HERMES_HOME:-$HOME/.hermes}"
AGENT_DIR="${HERMES_AGENT_DIR:-$HERMES_HOME_DIR/hermes-agent}"
REL="apps/desktop/src/plugins/hermes-bots/plugin.js"
TARGET="$AGENT_DIR/$REL"
STORE="$HERMES_HOME_DIR/aiianer-extensions/group-chat-limits"

# Remote-Bootstrap (curl | bash)
if [ ! -f "$HERE/limits.patch" ]; then
  echo "Kein lokaler Clone gefunden - lade AIIANER Hermes Extensions von GitHub ..."
  TMP_DIR="$(mktemp -d)"; trap 'rm -rf "$TMP_DIR"' EXIT
  curl -sL "https://github.com/oliverhees/aiianer-hermes-extensions/archive/refs/heads/main.tar.gz" | tar -xz -C "$TMP_DIR"
  INNER="$(find "$TMP_DIR" -path "*extensions/group-chat-limits/install.sh" | head -1)"
  [ -n "$INNER" ] || { echo "FEHLER: Download fehlgeschlagen." >&2; exit 1; }
  exec bash "$INNER" "$@"
fi

if [ ! -f "$TARGET" ]; then
  echo "FEHLER: Bot-Mode-Plugin nicht gefunden unter $TARGET" >&2
  echo "Ist Hermes Desktop installiert? (Bot Mode gehoert zum Lieferumfang.)" >&2
  exit 1
fi

if grep -q "resolveGroupChatLimits" "$TARGET"; then
  echo "Die einstellbaren Gruppenchat-Limits sind bereits installiert - nichts zu tun."
  exit 0
fi

if grep -q "DE_MESSAGES" "$TARGET"; then
  echo "ABBRUCH: Auf diesem Hermes laeuft die deutsche Bot-Mode-Uebersetzung." >&2
  echo "" >&2
  echo "Beide Komponenten aendern dieselbe Datei, und der Patch findet seine" >&2
  echo "Stellen in der uebersetzten Fassung nicht wieder. Wir liefern eine" >&2
  echo "kombinierte Variante nach - Bescheid gibt es in der AIIANER Community:" >&2
  echo "https://aiianer.de" >&2
  exit 2
fi

# Trockenlauf zuerst: erst wenn der Patch sicher passt, wird geschrieben.
apply_patch() {
  local mode="$1"
  if command -v git >/dev/null 2>&1; then
    if [ "$mode" = "check" ]; then
      git -C "$AGENT_DIR" apply --check "$HERE/limits.patch" 2>/dev/null
    else
      git -C "$AGENT_DIR" apply "$HERE/limits.patch"
    fi
  elif command -v patch >/dev/null 2>&1; then
    if [ "$mode" = "check" ]; then
      patch -p1 -d "$AGENT_DIR" --dry-run --silent < "$HERE/limits.patch" >/dev/null 2>&1
    else
      patch -p1 -d "$AGENT_DIR" --silent < "$HERE/limits.patch"
    fi
  else
    echo "FEHLER: Weder git noch patch gefunden - eines von beiden wird gebraucht." >&2
    return 3
  fi
}

if ! apply_patch check; then
  echo "ABBRUCH: Der Patch passt nicht auf dieses Bot-Mode-Plugin." >&2
  echo "" >&2
  echo "Das heisst in aller Regel: Hermes hat Bot Mode weiterentwickelt und" >&2
  echo "genau die Stellen umgebaut, die wir aendern. Wuerden wir jetzt mit" >&2
  echo "Gewalt patchen, waere das Plugin hinterher kaputt. Deshalb passiert" >&2
  echo "hier absichtlich nichts." >&2
  echo "" >&2
  echo "Wir ziehen die Komponente nach - Bescheid gibt es in der AIIANER" >&2
  echo "Community: https://aiianer.de" >&2
  exit 2
fi

mkdir -p "$STORE"
cp "$TARGET" "$STORE/plugin.js.backup"
apply_patch apply
cp "$HERE/limits.patch" "$STORE/" 2>/dev/null || true

if ! grep -q "resolveGroupChatLimits" "$TARGET"; then
  echo "FEHLER: Patch lief durch, die Aenderung ist aber nicht in der Datei." >&2
  cp "$STORE/plugin.js.backup" "$TARGET"
  echo "Originalzustand wiederhergestellt." >&2
  exit 1
fi

if command -v node >/dev/null 2>&1 && ! node --check "$TARGET" >/dev/null 2>&1; then
  echo "FEHLER: Die gepatchte Datei ist syntaktisch nicht in Ordnung." >&2
  cp "$STORE/plugin.js.backup" "$TARGET"
  echo "Originalzustand wiederhergestellt." >&2
  exit 1
fi

echo "Einstellbare Gruppenchat-Limits installiert."
echo "Original gesichert unter: $STORE/plugin.js.backup"
echo ""
echo "WICHTIG - wo das NICHT auftaucht:"
echo "  Diese Komponente ist KEIN eigenes Plugin. Sie aendert das mitgelieferte"
echo "  Bots-Plugin, das fest zur App gehoert. Unter Settings -> Plugins und in"
echo "  den Ordnern .hermes/plugins bzw. .hermes/desktop-plugins erscheint also"
echo "  KEIN neuer Eintrag. Dort steht weiterhin nur \"Bots (bundled)\"."
echo ""
echo "Naechste Schritte:"
echo "  1. Hermes Desktop komplett neu starten (die App baut beim ersten Start kurz neu)"
echo "  2. Einen GRUPPENCHAT oeffnen (nicht den normalen Chat eines einzelnen Bots)."
echo "     Rechts neben \"N bots\" in der Kopfzeile steht jetzt das Budget,"
echo "     z.B. \"3 rounds - 10 msgs\". Ein Klick darauf oeffnet die Einstellungen."
echo "  3. Noch kein Gruppenchat da? Beim Anlegen gibt es unten \"Room budget\""
echo "     zum Aufklappen."
echo ""
echo "Pruefen, ob es wirklich drin ist:"
echo "  grep -c \"Room budget\" \"$AGENT_DIR/$REL\"    # muss > 0 sein"
echo ""
echo "Rueckgaengig machen: cp \"$STORE/plugin.js.backup\" \"$TARGET\""
echo "Nach einem Hermes-Update, das die Datei zuruecksetzt: diesen Installer erneut ausfuehren."
