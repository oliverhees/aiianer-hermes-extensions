#!/usr/bin/env bash
# Installiert den kanonischen Installer von Hermes Bot-Mode Advanced ohne Shell-Pipeline.
set -euo pipefail
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
INSTALLER="$TMP_DIR/botmode-advanced-install.sh"
URL="https://raw.githubusercontent.com/oliverhees/hermes-botmode-advanced/main/install.sh"

curl --fail --silent --show-error --location "$URL" --output "$INSTALLER"
test -s "$INSTALLER"
exec bash "$INSTALLER" "$@"
