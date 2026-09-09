# Premium-Gating: So testest du es

Das Open-Core-Modell (Ebene 2, siehe [LICENSING.md](LICENSING.md)) sperrt
Premium-Komponenten hinter eine Community-Mitgliedschaft. Dieses Dokument
zeigt Schritt für Schritt, wie du das Gating auf einem Test-System durchspielst.

## Wann ein Test fällig ist

- Nach jeder Änderung an `plugin_api.py`, `dist/index.js` oder `catalog.json`
- Vor dem ersten Live-Einsatz einer echten Premium-Komponente

## Das Prinzip in Kürze

1. Der Katalog markiert eine Komponente mit `"premium": true`.
2. Das Backend prüft vor Installation (`/api/plugins/aiianer-hub/install`) und
   bei der Katalog-Anzeige (`/catalog`) die
   Mitgliedschaftsdatei `~/.hermes/aiianer/mitgliedschaft.json`.
3. Ohne gültige Mitgliedschaft: kein Install-Knopf, Status 403 bei direktem
   API-Aufruf, Sperr-Grund als Hinweis.

## Unterschiedliche Berechtigungen, die die Prüfung versteht

Die Datei `~/.hermes/aiianer/mitgliedschaft.json` wird gelesen als:

```json
{ "level": "mitglied", "gueltigBis": "2027-12-31" }
```

- `level` muss `"mitglied"` oder `"wartung"` sein. Alles andere (z. B. `"gast"`)
  ist nicht berechtigt.
- `gueltigBis` muss ein Datum `JJJJ-MM-TT` sein, das heute oder später liegt.
- Fehlt die Datei, ist sie kaputtes JSON oder abgelaufen: gesperrt.

## Test 1: Premium-Komponente ohne Mitgliedschaft

1. Markiere im Katalog eine Komponente temporär mit `"premium": true`
   (z. B. `group-chat-limits`), lade `catalog.json` neu.
2. Stelle sicher, dass **keine** `mitgliedschaft.json` unter `~/.hermes/aiianer/`
   liegt.
3. Öffne das Dashboard: Die Karte zeigt das Badge `Premium`, der Install-Knopf
   fehlt, stattdessen steht der Sperr-Grund
   „Diese Komponente ist exklusiv fuer AIIANER-Community-Mitglieder."
4. Direkter API-Aufruf:
   `curl -X POST http://localhost:PORT/api/plugins/aiianer-hub/install -H 'Content-Type: application/json' -d '{"id":"group-chat-limits"}'`
   → Erwartet: Status 403 mit dem Sperr-Grund.

## Test 2: Mitgliedschaft aktivieren

1. Lege an: `~/.hermes/aiianer/mitgliedschaft.json`
   ```json
   { "level": "mitglied", "gueltigBis": "2099-01-01" }
   ```
2. Dashboards neu laden: Der Install-Knopf ist jetzt da, kein Sperr-Grund.
   Der API-Aufruf aus Test 1 erlaubt die Installation.

## Test 3: Abgelaufene Mitgliedschaft

1. Setze `gueltigBis` auf ein Datum in der Vergangenheit, z. B. `2020-01-01`.
2. Neu laden: wieder gesperrt, genau wie in Test 1.

## Test 4: Installierte Premium-Komponente, Mitgliedschaft abgelaufen

1. Aktiviere die Mitgliedschaft und installiere eine Premium-Komponente.
2. Setze danach `gueltigBis` in die Vergangenheit.
3. Neu laden: Updates und Neues-Einspielen sind gesperrt, aber der
   Deinstallieren-Knopf bleibt sichtbar, damit sich niemand einsperrt.

## Automatisierter Logik-Test

Die Kernlogik liegt in `_premium_berechtigt()` in `plugin_api.py`. Sie lässt
sich isoliert prüfen (kein Server nötig):

```bash
HERMES_HOME=/tmp/test-hermes python3 - <<'PY'
import json, pathlib
from importlib import util
spec = util.spec_from_file_location("api", "extensions/aiianer-hub/dashboard/plugin_api.py")
m = util.module_from_spec(spec); spec.loader.exec_module(m)
premium = {"id":"x","premium":True}
print(m._premium_berechtigt(premium))   # fehlt Datei -> gesperrt
PY
```

Nach jedem Test die temporär gesetzte `mitgliedschaft.json` wieder entfernen,
damit keine Testrechte auf dem echten System liegen bleiben.

## Achtung

- Der Test-Key ist **kein** echtes Lizenzsystem, sondern ein schlanker Zaun.
  Echte Premium-Komponenten liegen nicht in diesem Repo und werden separat
  verteilt. Das Gating hier verhindert nur, dass Nicht-Mitglieder den
  Install-Weg im Katalog nutzen.
- Keine echten Zugangsdaten oder Tokens in die Mitgliedschaftsdatei stecken.
  Sie ist kein Sicherheitsanker, sondern eine Berechtigungsprüfung für die
  Install-Schiene.
