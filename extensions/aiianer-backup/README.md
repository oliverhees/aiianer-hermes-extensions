# AIIANER Backup-Außenposten (V1)

Lokale, vollständige Hermes-Backups in einem externen Ordner. Der Runner ruft ausschließlich `hermes backup` per argv auf, veröffentlicht ZIPs atomar und kann optional eigene Archive im Ziel-Root begrenzt aufbewahren.

Installation erfolgt aus dem AIIANER Extension Hub. Danach in Hermes Desktop → AIIANER Extension Hub → Tab „Backups“ einen absoluten lokalen Zielordner außerhalb von `HERMES_HOME` eintragen. V1 lädt nichts hoch, verändert keine globalen Hermes-Einstellungen und spielt Backups nicht automatisch zurück.

Die Automatisierung nutzt den Hermes-Cron-no-agent-Pfad und läuft nur, wenn der Gateway aktiv ist. Wiederherstellung bleibt ein expliziter, serverseitig bestätigter Vorgang.
