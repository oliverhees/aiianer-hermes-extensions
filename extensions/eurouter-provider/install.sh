#!/usr/bin/env bash
# Delegiert an den kanonischen Installer des eigenstaendigen Plugin-Repos —
# eine Quelle der Wahrheit, keine dritte Kopie des Plugin-Codes.
set -euo pipefail
curl -sL https://raw.githubusercontent.com/oliverhees/hermes-eurouter-plugin/main/install.sh | bash -s -- "$@"
