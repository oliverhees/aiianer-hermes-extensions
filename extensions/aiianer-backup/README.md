# AIIANER Backup-Außenposten (V1)

Lokale, vollständige Hermes-Backups in einem externen Ordner. Der Runner ruft ausschließlich `hermes backup` per argv auf, veröffentlicht ZIPs atomar und kann optional eigene Archive im Ziel-Root begrenzt aufbewahren.

Installation erfolgt aus dem AIIANER Extension Hub. Danach in Hermes Desktop → AIIANER Extension Hub → Tab „Backups“ den Zielordner im integrierten Ordner-Browser auswählen (oder für NAS/USB einen absoluten Pfad eingeben). Ziele innerhalb von `HERMES_HOME` werden gesperrt. V1 lädt nichts hoch, verändert keine globalen Hermes-Einstellungen und spielt Backups nicht automatisch zurück.

Die Automatisierung nutzt den Hermes-Cron-no-agent-Pfad und kann täglich oder wöchentlich zu einer gewählten Uhrzeit laufen, wenn der Gateway aktiv ist. Der Tab zeigt die letzten 20 Läufe mit Erfolg bzw. Fehlercode. Wiederherstellung bleibt ein expliziter, serverseitig bestätigter Vorgang.
