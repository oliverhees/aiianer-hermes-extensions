#!/usr/bin/env bash
# Installiert den kanonischen EU-Router-Installer ohne Shell-Pipeline.
set -euo pipefail
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
INSTALLER="$TMP_DIR/eurouter-install.sh"
URL="https://raw.githubusercontent.com/oliverhees/hermes-eurouter-plugin/main/install.sh"

curl --fail --silent --show-error --location "$URL" --output "$INSTALLER"
test -s "$INSTALLER"
exec bash "$INSTALLER" "$@"
