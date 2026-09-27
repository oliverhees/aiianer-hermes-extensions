#!/usr/bin/env bash
# Installiert den kanonischen Installer von Hermes Backup ohne Shell-Pipeline.
set -euo pipefail
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
INSTALLER="$TMP_DIR/backup-install.sh"
URL="https://raw.githubusercontent.com/oliverhees/hermes-backup-plugin/main/install.sh"

curl --fail --silent --show-error --location "$URL" --output "$INSTALLER"
test -s "$INSTALLER"
exec bash "$INSTALLER" "$@"
