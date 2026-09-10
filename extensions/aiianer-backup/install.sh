#!/usr/bin/env bash
set -euo pipefail
home="${HERMES_HOME:-$HOME/.hermes}"
mkdir -p "$home/scripts" "$home/aiianer"
install -m 0755 "$(dirname "$0")/backup_runner.py" "$home/scripts/aiianer-backup-runner.py"
if [[ ! -e "$home/aiianer/backup-state.json" ]]; then
  umask 077
  printf '%s\n' '{"schemaVersion":1,"enabled":false,"target_dir":"","schedule":"manual","retention":{"enabled":false,"keep":5},"state":"never_run","lastRun":null,"lastArchive":null,"lastErrorCode":null}' > "$home/aiianer/backup-state.json"
fi
printf '%s\n' "AIIANER Backup installiert. Zielordner im Backups-Tab festlegen; keine Uploads in V1."
