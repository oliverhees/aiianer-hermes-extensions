# Entwicklungshandbuch: AIIANER Marktplatz für Hermes

Dieses Dokument ist die Dev-Doku für das Projekt
[aiianer-hermes-extensions](https://github.com/oliverhees/aiianer-hermes-extensions) —
das "AIIANER-Plugin", mit dem wir die deutschen Erweiterungen für Hermes Desktop
ausliefern. Es sorgt dafür, dass Deutsch nach jedem Hermes-Update stabil bleibt
und dass wir neue Erweiterungen einfach nachrüsten können.

> **Wahrheit:** Der maßgebliche Clone liegt jetzt unter
> `/mnt/projekte/aiianer-community-new/aiianer-hermes-plugin-marketplace`.
> Die alte Arbeitskopie unter `eigene_projekte_neu/aiianer-hermes-extensions`
> ist ab sofort ohne Bedeutung. Gearbeitet, committet und gepusht wird nur
> noch hier.

---

## 1. Zielbild: Das Non-Plus-Ultra für den deutschen Markt

Hermes Desktop ist international, aber englisch. Niemand liefert einen
deutschen Marktplatz mit Update-Sicherheit mit. Genau das ist unsere Lücke:
ein **ein-Klick-Marktplatz direkt in Hermes**, der Deutsch und weitere
deutsche Erweiterungen installiert, **nach jedem Hermes-Update von selbst
wiederherstellt** und dabei immer sauber rückbaubar bleibt.

Alle anderen Extensions-Anbieter bauen entweder nur einzelne Dateien ohne
Update-Schutz, oder sie greifen unsauber in den Checkout ein. Wir tun beides
richtig: additiv dort, wo Hermes eine Tür offen lässt (Plugins, Kataloge),
und mit Backup + Wächter dort, wo wir in den Checkout müssen (Sprachdatei).

### Die vier Säulen des Marktplatzes

| Säule | Aufgabe |
| --- | --- |
| **Katalog** | Was gibt es, welche Version, welcher Status je Rechner |
| **Installer** | Komponenten sicher installieren und aktualisieren |
| **Rückbau** | Genau die Sicherung zurückspielen, kein Raten, kein pauschales Löschen |
| **Wächter** | Nach jedem Gateway-Start prüfen, ob ein Update etwas entfernt hat, und es neu einspielen |

---

## 2. Der Kern-Anteil: Was wo lebt

Das Projekt besteht aus einem **Root-Dispatcher** und je **einer Komponente pro
Ordner** unter `extensions/`.

### Verzeichnisstruktur

```
aiianer-hermes-plugin-marketplace/     <- MAßGEBLICHER CLONE (Wahrheit)
├── install.sh                          <- Dispatcher: zeigt/ruft Komponenten-Installer
├── README.md                           <- Öffentliches Readme (Endnutzer-Ansicht)
├── SECURITY.md                         <- Meldeprozess für Sicherheitslücken
├── LICENSING.md / LICENSE / NOTICE     <- Dual-Lizenz: AGPL-3.0 + kommerziell
├── ARCHITEKTUR-MARKTPLATZ.html         <- Visuelle Architekturdarstellung (Stand: frühe Phase)
└── extensions/
    ├── aiianer-hub/                    <- DER Marktplatz selbst (Plugin + Wächter)
    │   ├── plugin.yaml                 <- Plugin-Manifest (Web-Dashboard)
    │   ├── catalog.json                <- Komponentenkatalog (lokal, Fallback)
    │   ├── install.sh / install.ps1    <- Installer: platziert Plugin, Desktop, Wächter, Zustand
    │   ├── guard_check.py              <- gemeinsame Prüf-/Reparaturfunktion
    │   ├── README.md / PROMPT.md       <- Endnutzer-Anleitung + KI-Installationssatz
    │   ├── dashboard/
    │   │   ├── manifest.json           <- Dashboard-Manifest (Tab, Einstieg)
    │   │   ├── plugin_api.py           <- FastAPI-Backend (Routen, Install/Rückbau)
    │   │   └── dist/index.js           <- Web-Dashboard-Bundle (klein, lizenzrein)
    │   ├── desktop/
    │   │   └── plugin.js               <- Desktop-App-Fassung (Electron, ESM, jsx)
    │   └── guard/                      <- Wächter-Snapshot für den Hook
    │       ├── HOOK.yaml
    │       └── handler.py
    ├── german-language/                <- Deutsche Sprachdatei (Patch, in den Checkout)
    ├── bot-mode-german/                <- Deutscher Bot-Modus (additiv in Katalog)
    ├── group-chat-limits/              <- Einstellbare Gruppenchat-Deckel (Patch)
    └── eurouter-provider/              <- EU-Router als Provider (Delegation an eigenes Repo)
```

### Das Schlüssel-Verständnis: Zwei getrennte Plugin-Systeme

Hermes hat **zwei Oberflächen mit zwei getrennten Plugin-Systemen**, und der
Marktplatz muss beide bedienen:

| Oberfläche | Plugin-Ablage | Manifest |
| --- | --- | --- |
| **Web-Dashboard** (`hermes web`, Port 9119) | `~/.hermes/plugins/<name>/dashboard/` | `manifest.json` + `plugin_api.py` (FastAPI-Backend) |
| **Desktop-App** (Electron) | `~/.hermes/desktop-plugins/<name>/plugin.js` | reines ESM, `@hermes/plugin-sdk`, kein Build |

Beide Frontends sprechen **dasselbe Python-Backend** (`plugin_api.py`) an.
Im Desktop über `ctx.rest(...)`, das automatisch auf `/api/plugins/aiianer-hub/`
zeigt. Kein Code-Duplikat für die API-Logik.

### Laufzeit-Ablage (was der Installer auf dem Rechner anlegt)

Alle Pfade liegen **außerhalb** des Hermes-Programm-Checkouts und überleben
jedes Update. `<hermes>` steht für das Hermes-Datenverzeichnis
(`~/.hermes` auf Linux/macOS/WSL, `%LOCALAPPDATA%\hermes` auf Windows nativ,
`HERMES_HOME` falls gesetzt).

| Ort | Was dort liegt |
| --- | --- |
| `<hermes>/plugins/aiianer-hub/` | Web-Dashboard: Reiter + Backend |
| `<hermes>/desktop-plugins/aiianer-hub/` | Desktop-App: Seitenleisten-Eintrag + Seite |
| `<hermes>/hooks/aiianer-guard/` | Der Wächter, lauscht auf `gateway:startup` |
| `<hermes>/aiianer/` | Sprachquelle, Zustand (`installed.json`) und Protokoll (`guard.log`) |
| `<hermes>/aiianer-extensions/<komponente>/` | je Komponente eine Sicherung der Install-Quellen |

---

## 3. Die Komponenten im Katalog

Der Katalog (`catalog.json`) ist die Quelle dessen, was der Marktplatz anbietet.
Jede Komponente hat: `id`, `name`, `version`, `kind` und erklärendes `summary`/
`note`/`coverage`. `kind` steuert die Anzeige (ob es in den Checkout greift oder
eigenständig läuft).

### Aktueller Stand

| id | name | kind | Was es tut |
| --- | --- | --- | --- |
| `german-language` | Deutsche Sprache | `patch` | Hermes-Oberfläche auf Deutsch; wird nach jedem Update automatisch neugespielt |
| `eurouter-provider` | EU-Router | `plugin` | EU-Compliance-Routen im Modell-Picker statt roher Modelle, DSGVO-konform |
| `bot-mode-german` | Bot-Modus auf Deutsch | `plugin` | Deutsche Texte für den Bot-Modus (194 Bausteine), setzt `german-language` voraus |
| `group-chat-limits` | Gruppenchat-Grenzen | `patch` | Runden/Nachrichten pro Chat selbst festlegen statt hartem 3 und 10 |

### Zwei Arten von Komponenten

- **Eigenständig (`plugin`):** lebt vollständig außerhalb des Hermes-Checkouts
  (z. B. `~/.hermes/plugins/model-providers/eurouter`) und kann durch ein
  Update gar nicht kaputtgehen. Kein Wächter nötig.
- **Greift in den Checkout ein (`patch`):** muss in Hermes' eigene Dateien
  schreiben (Sprachdatei, Rundenschleife). Das ist kein Pfusch, sondern die
  einzige Möglichkeit — und es ist so gebaut, dass es sich selbst repariert.

### Abhängigkeiten

- `bot-mode-german` **hängt hart an** `german-language`: ohne `'de'` als
  gültige Locale wäre das Bündel zwar eingetragen, aber nie auswählbar. Das
  Backend prüft das vorher (`_verfuegbar`) und bietet keinen Install-Knopf an,
  solange die Voraussetzung fehlt.

---

## 4. Das einheitliche Install-Muster

Jede Komponente bringt ein `install.sh` mit. Das Muster ist überall dasselbe:

1. **Bootstrap:** Wird das Skript remote via `curl | bash` ausgeführt (kein
   lokaler Clone), lädt es den Repo-Tarball herunter, entpackt ihn und ruft
   den Installer aus dem entpackten Stand erneut auf.
2. **Ort finden:** `HERMES_HOME` / `HERMES_AGENT_DIR` auflösen
   (Linux/macOS/WSL `~/.hermes`, Windows nativ `%LOCALAPPDATA%\hermes`).
3. **Payload sichern:** Die Install-Quellen unter
   `aiianer-extensions/<komponente>/` ablegen, damit Wächter und Rückbau sie
   später ohne erneuten Download haben.
4. **Anwenden:** Entweder nix in den Checkout schreiben (eigenständig), oder
   gezielte, wiederholbare Einfügungen an stabilen Ankern (Patch).
5. **Bestätigen:** "OK" melden und die nächsten Schritte ausgeben
   (meist: Hermes komplett neu starten, Sprache umstellen).

Der Root-`install.sh` ist ein reiner **Dispatcher**: ohne Argument listet er die
Komponenten, mit Argument ruft er `extensions/<komponente>/install.sh` auf.
Remote lädt er sich vorher den Tarball.

### Idempotenz und Update-Sicherheit (die Grundsätze)

1. **Update-sichere Orte** bevorzugen, wo Hermes das offiziell vorsieht
   (`~/.hermes/plugins/...`).
2. **Muss eine Komponente in den Checkout,** arbeitet der Installer mit
   gezielten, wiederholbaren Einfügungen an stabilen Ankern — alles-oder-nichts
   mit Backup, laute Fehlermeldung statt halbem Zustand. Nach einem Update den
   Satz einfach nochmal ausführen.
3. **Offiziellen Weg nehmen, wo es einen gibt.** Bot Mode bringt seit dem Umbau
   einen eigenen Nachrichtenkatalog mit — dort tragen wir nur noch ein deutsches
   Bündel ein, statt Dateien zu ersetzen. Solche Türen halten, weil sie dafür
   gedacht sind.

---

## 5. Das Web-Backend (`plugin_api.py`)

FastAPI-Router unter `/api/plugins/aiianer-hub/`, hinter dem Auth-Gate des
Dashboards. Vollständig dokumentiert mit aussagekräftigen Docstrings.

### Routen

| Route | Zweck |
| --- | --- |
| `GET /catalog` | Katalog (Netz, Fallback lokal) + lokaler Install-Zustand je Komponente |
| `GET /health` | Sitzt nach dem letzten Update noch alles (nutzt `guard_check.check_all`) |
| `POST /install` | Komponente installieren oder aktualisieren |
| `POST /uninstall` | Komponente entfernen, exakt die Sicherung zurückspielen |
| `POST /repair` | Von Hand auslösen, was der Wächter automatisch tut |

### Wichtige Design-Entscheidungen im Backend

- **`NEXT_STEPS` lokal statt im Katalog:** Anweisungs- und Sicherheitslogik
  gehört in den vertrauenswürdigen lokalen Code, nicht in den Katalog, der aus
  dem Netz kommt. Der Katalog darf nur überschreiben, nicht erfinden.
- **`_verfuegbar()` prüft vor dem Anbieten**, nicht erst beim Klick. Ein Knopf,
  der zuverlässig in einen 500er läuft, ist schlimmer als gar kein Knopf.
- **State-Lock (`_state_lock`):** Lesen-Ändern-Schreiben auf `installed.json`
  unter `fcntl`-Sperre, damit zwei parallele Aktionen keinen Zustand verlieren
  (unter Windows ohne Sperre weiter — nicht verweigern).
- **Atomic write:** `installed.json` wird erst als `.tmp` geschrieben, dann
  umbenannt — kein halbes JSON bei Abbruch.
- **Tar-Slip-Schutz:** `tarfile.extractall(..., filter="data")` (Fallback für
  Python < 3.12) — `comp_id` stammt aus dem Netz-Katalog.
- **Der Wächter ist eine Datei, eine Wahrheit:** `guard_check.py` lebt unter
  `~/.hermes/aiianer/` und wird von BEIDEM benutzt — dem Hook-Handler und der
  `/health`-Route.

---

## 6. Die zwei Frontends

Beide frontends sprechen dasselbe Python-Backend. Sie sind bewusst zweimal
gebaut, weil die Plugin-Systeme getrennt sind — aber sie teilen sich Logik und
Design-Entscheidungen.

### Web-Dashboard (`dashboard/dist/index.js`)

- Nutzt ausschließlich das Hermes-Plugin-SDK, bündelt weder React noch fremde
  Komponenten. Das Bundle bleibt klein (ca. 6 KB) und lizenzrein.
- Ohne SDK stiller Ausstieg beim Laden (wie im mitgelieferten
  `hermes-achievements`).
- Rendert Karten je Komponente mit Status, Version, Aktionen
  (Installieren / Neu einspielen / Deinstallieren / Aktualisieren).
- Zeigt **nach** einer Aktion die nächsten Schritte als hervorgehobenen Kasten —
  das ist wichtig, weil nach dem Installieren der deutschen Sprache Hermes noch
  nicht sofort deutsch ist (Neu-Start + Sprache umstellen nötig).

### Desktop-App (`desktop/plugin.js`)

- Reines ESM, wird uncompiliert geladen. Oberfläche über `jsx()`-Aufrufe, keine
  JSX-Syntax (die Datei wird nicht kompiliert).
- **Wichtige Fallen (gut dokumentiert im Code):**
  - `jsx` kommt aus React selbst (`react/jsx-runtime`), NICHT aus dem
    Plugin-SDK — der SDK-Import `jsx` gibt es nicht und lässt das Plugin mit
    "does not provide an export named 'jsx'" scheitern.
  - `ctx.rest()`-Body ist ein Objekt, KEIN `JSON.stringify` — die Brücke
    serialisiert selbst; ein String würde dem Backend ein Objekt-Wrapper
    schicken.
  - Geschachtelte i18n-Keys (z. B. `status.missing`) müssen wirklich
    verschachtelt registriert werden, nicht flach mit Punkt im Key — sonst
    rendert der Badge wörtlich "status.missing".
- Registriert: eigene Route `/aiianer`, Seitenleisten-Eintrag "AIIANER",
  Befehlspaletten-Eintrag.
- Der Refetch nach einer Aktion hängt **bewusst in einer eigenen Kette**, damit
  ein Fehler des Refetch eine geglückte Installation nicht als Fehlschlag
  anzeigt (kann vorkommen, wenn das Gateway gerade neu startet).

---

## 7. Der Installations-Ablauf im Detail

`POST /install` (im Backend) macht:

1. Katalog laden (Netz oder lokal).
2. Komponente im Katalog suchen → 404 wenn unbekannt.
3. `_verfuegbar()` erneut prüfen (auch direkte Aufrufe ohne UI werden
   abgefangen) → 409 wenn nicht installierbar.
4. Repo-Tarball in ein Temp-Verzeichnis laden und sicher entpacken
   (`filter="data"`, Tar-Slip-Schutz).
5. `extensions/<comp_id>/` im heruntergeladenen Repo suchen, `install.sh` darin
   ausführen (Timeout 180s) → 500 mit Fehlertext wenn fehlschlägt.
6. Für Patch-Komponenten (`german-language`, `bot-mode-german`,
   `group-chat-limits`): die Quell-Dateien zusätzlich nach
   `~/.hermes/aiianer/` kopieren — damit der Wächter sie nach einem
   Hermes-Update erneut einspielen kann.
7. Unter dem State-Lock: `installed.json` aktualisieren (Version + Zeitpunkt),
   atomic schreiben.
8. Antwort mit `ok`, `action` (update/install), Version, Log-Zeilen und
   `nextSteps`.

Der **Catalog-Handler** reichert jede Komponente mit lokalem Zustand an:
`installed`, `installedAt`, `nextSteps`, `uninstallSteps`, `available` +
`unavailableReason` (de/en) und `status` (`missing` | `outdated` | `current`).
Damit kann die UI entscheiden, welche Knöpfe sinnvoll sind, ohne selbst zu
raten.

---

## 8. Der Rückbau (Uninstall): nie raten

`POST /uninstall` folgt einer strengen Regel: **es wird nur zurückgespielt,
was gesichert wurde — es wird nie pauschal gelöscht.**

- Der Installer legt für Patch-Komponenten die Sicherungen der angefassten
  Originale ab (`*.orig` in der Sicherungsstruktur
  `aiianer-extensions/<komponente>/`).
- Uninstall liest `installed.json`, prüft `kind` und spielt für jeden Typ seine
  eigene, dokumentierte Rückbau-Logik ab:
  - `bot-mode-german` & `group-chat-limits`: gezielte Regex-Rollbacks in den
    Checkout-Dateien (nur unsere eingefügten Blöcke werden entfernt).
  - `german-language`: unter dem Backup heraus versorgen, ohne die Sprache
    komplett zu deaktivieren — schlimmstenfalls bleibt Englisch der Fallback.
  - `eurouter-provider`: Plugin-Ordner entfernen; echte Liste der angelegten
    Dateien aus der Sicherung, niemals ein wilder `rm -rf`.
- Es wird **nur entfernt, was in `installed.json` als installiert steht.**
  Eine Komponente, die mehrfach gebucht ist, wäre logisch unmöglich — der
  Installer blockt bereits die Zweitinstallation desselben `comp_id`.
- Nach dem Rückbau: `installed.json` aktualisieren, `guard.log` mit
  Uninstall-Protokoll ergänzen.

**Wichtig:** Es gibt keine "Seite, die nie wieder etwas anfasst". Jeder
Uninstall ist ein eigener, dokumentierter Fall pro `kind` — nicht ein
Generik-Dateilöscher.

---

## 9. Der Wächter (Guard): Selbstheilung nach jedem Update

Das Kern-Versprechen: **Hermes-Update fährt drüber → Deutsch ist weg? Der
Wächter legt es beim nächsten Start wieder an.**

### Wie es funktioniert

1. Der Hook `HOOK.yaml` lauscht auf `gateway:startup` — also bei jedem Start
   des Hermes-Gateways, nicht nur beim Install.
2. `handler.py` ruft das gemeinsame `guard_check.py` unter
   `~/.hermes/aiianer/guard_check.py` auf (eine Datei, eine Wahrheit).
3. `guard_check.py` prüft für jede installierte Patch-Komponente, ob ihre
   Anker-Einbauten noch da sind. Fehlt etwas, wird es **aus der lokalen
   Sicherung** (`~/.hermes/aiianer-extensions/…` oder der in
   `~/.hermes/aiianer/` abgelegten Quell-Dateien) neu eingespielt.
4. Ergebnis wird in `~/.hermes/aiianer/guard.log` protokolliert; der Tarball
   wird nach dem Entpacken aufgeräumt.

### Abgrenzung und Sicherheit

- Der Wächter ist **additiv und anker-basiert**: er fügt nur unsere bekannten
  Blöcke wieder ein, er überschreibt nie etwas Fremdes.
- Er wacht **nicht** über eigenständige `plugin`-Komponenten — die brauchen
  keinen Schutz, weil sie außerhalb des Checkouts leben.
- `guard_check.py` ist die **einzige** Instanz der Prüflogik: sowohl der
  Hook als auch die `/health`-Route nutzen sie. Es gibt keine zweite,
  abweichende Kopie.

### Manuelle Trigger

- Die Dashboard-Route `POST /repair` stößt dieselbe Prüfung an — so kann der
  Nutzer "Neu einspielen" drücken, ohne auf einen Gateway-Neustart zu warten.
- Debugging: `python ~/.hermes/aiianer/guard_check.py` von Hand ausführen.

---

## 10. Neue Komponente hinzufügen (das Muster zum Abkupfern)

Eine neue Erweiterung aufnehmen ist ein vollständiger, wiederholbarer Weg:

1. **Ordner anlegen:** `extensions/<komponenten-id>/` mit mindestens
   `install.sh` (nach dem Bootstrap-Muster), `README.md`, `PROMPT.md`,
   optional eigenem Asset-Teil (z. B. `de.ts`, `messages.de.ts`).
2. **Installer schreiben:** idempotent, update-sicher (Sicherungs-Regel),
   Rückbau dokumentieren. Siehe Abschnitt 4.
3. **Katalog erweitern:** `catalog.json` mit `id`, `name`, `version`,
   `kind` (`patch` oder `plugin`), `summary`, `note`, `coverage` eintragen.
   `kind` entscheidet, ob der Rückbau/Installer in den Checkout greift.
4. **Wächter anbinden:** Wenn `kind` = `patch`, muss `guard_check.py` die
   Anker dieser Komponente kennen und aus der lokalen Sicherung neu einspielen
   können. Das ist zwingend, sonst überlebt die Komponente kein Update.
5. **Trennung Checkout vs. Zustand:** die Checkout-Änderung liegt im (rangierten)
   Target; den eigentlichen Eintrag in `installed.json` (Version, Zeitpunkt)
   pflegt nur das Backend unter Lock. Nie beides vermischen.
6. **UI automatisch:** Die Karten im Frontend kommen automatisch, weil sie den
   Katalog rendern. Kein Frontend-Build nötig, nur der Katalog.

---

## 11. Das Zustandsmodell von `installed.json`

Ein JSON-Dokument unter `~/.hermes/aiianer/installed.json`, das niemals kaputt
liegen darf (atomic write, Lock).

Struktur je installierter Komponente (Kurzform):

```json
{
  "<component-id>": {
    "version": "0.x.y",
    "kind": "plugin|patch",
    "installed_at": "ISO-8601-Zeitstempel",
    "artifacts": ["<pfade der angelegten/quell-dateien, für Rückbau>"]
  }
}
```

Regeln:

- **Ein Eintrag pro Komponente.** Eine zweite Installation desselben `comp_id`
  wiederholt den Installationspfad, aktualisiert `version`/`installed_at`.
- **Unbekannte Einträge:** Der Rückbau entfernt nur bekannte Felder —
  eine fremde Datei im Hermes-Verzeichnis ist nicht das Problem des Plugins.
- **Schreibreihenfolge ist geschützt:** Lock, dann `.tmp`-Datei, dann `os.replace`
  — ein Absturz dazwischen lässt das alte, gültige JSON stehen.

---

## 12. Sicherheit (wie hier gedacht)

Die drei Komponenten des Sicherheitsmodells:

1. **Netz-Katalog ist nicht heilig:** Der Katalog kann aus dem Netz kommen,
   aber sein Inhalt wird gegen einen Cursor (fester Eintrag im Katalog) und
   Schemata abgeglichen. Komponenten-Ordner werden nicht direkt aus dem Katalog
   vergeben, sondern über die bekannte Repo-Struktur (Tarball aus der
   festen Quelle, sicher entpackt).
2. **Nur unsere bekannten Anker:** Patches arbeiten an vordefinierten,
   stabilen Code-Stellen im Hermes-Checkout — keine wilden Dateioperationen.
   Ein Hermes-Update, das eine dieser Stellen verschiebt, bricht laut ab und
   meldet sich, statt blind einzufügen.
3. **Keine Credentials im Repo:** Kein Token, kein API-Key in `install.sh`,
   `plugin_api.py` oder im Katalog. Installationen laufen als der lokale
   Benutzer, nutzen das eigene Fernzugriffs-Backend des Betreibers, und rufen
   kein SDK-Tool auf, das blind Credentials auslesen könnte.

Zusätzlich: `SECURITY.md` im Repo beschreibt den Meldeprozess für Lücken
(support@aiianer.de, nicht öffentlich, 72-Stunden-Erstantwort).

---

## 13. Kieler-Regel: Unsere Fehlerkultur im Code

Damit der Marktplatz "das Ding, das man bedingungslos installiert" bleibt:

- **Laut, nicht leise:** Ein `install.sh`, das fehlschlägt, sagt das dem
  Backend — und das Backend dem UI als 500 mit Text. Nie "ok" melden, wenn
  nichts eingebaut wurde.
- **Wiederholbar:** Idempotenz ist Pflicht — ein zweiter Lauf ist eine
  Aktualisierung, kein Fehler.
- **Warum hinter allem:** Der Katalog erklärt `summary`/`note`/`coverage`;
  das Backend dokumentiert `nextSteps`. Kein Knopf ohne erklärten Effekt.
- **Kein eigen-mächtiges Löschen:** Alles Greifende wird gesichert und
  zurückgespielt; Löschen passiert nur über dokumentierte Uninstall-Fälle.

---

## 14. Die Komponenten-Mechanik im Detail

So greift jede Komponente konkret in Hermes ein (oder auch nicht).

### `german-language` — der Patch, der alles trägt

| Aspekt | Wert |
| --- | --- |
| kind | `patch` |
| Was es tut | Übersetzt die Hermes-Oberfläche komplett auf Deutsch |
| Mechanik | `apply-de.py` patcht die Sprachdatei im Hermes-Checkout an stabilen Ankern; die Quell-Dateien liegen zusätzlich unter `~/.hermes/aiianer/` für den Wächter |
| Rückbau | Sicherung zurückspielen; Englisch bleibt der Fallback, die Sprache wird nie hart deaktiviert |
| Wächter | **Pflicht:** spielt die Sprachdatei nach jedem Update neu ein |

Diese Komponente ist die Flaggschiff-Logik: Sie beweist das Versprechen
"Deutsch bleibt, egal was Hermes-Update passiert". Alle anderen Patches
kopieren dieses Muster.

### `bot-mode-german` — der saubere Weg über den offiziellen Katalog

| Aspekt | Wert |
| --- | --- |
| kind | `plugin` |
| Was es tut | Deutsches Bündel (194 Nachrichtenbausteine) für den Bot-Modus |
| Mechanik | Trägt ein Bündel in den offiziellen Bot-Mode-Nachrichtenkatalog ein, statt Dateien zu ersetzen — nutzt die Tür, die Hermes dafür baut |
| Abhängigkeit | Braucht `german-language` (`'de'` als gültige Locale), sonst nicht installierbar |

Lehrstück: Wenn Hermes eine offizielle Erweiterungs-Tür hat, nehmen wir die.
Der Katalog-Ansatz überlebt Updates von selbst, weil er dafür gedacht ist.

### `group-chat-limits` — gezielter Patch in der Rundenschleife

| Aspekt | Wert |
| --- | --- |
| kind | `patch` |
| Was es tut | Runden- und Nachrichten-Grenzen pro Gruppenchat selbst festlegen statt hartem 3 und 10 |
| Mechanik | Gezielte, wiederholbare Einfügungen an den stabilen Ankern der Rundenschleife |
| Rückbau | Regex-Rollback, nur unsere eingefügten Blöcke werden entfernt |

### `eurouter-provider` — eigenständig, kein Eingriff

| Aspekt | Wert |
| --- | --- |
| kind | `plugin` |
| Was es tut | EU-Compliance-Routen im Modell-Picker statt roher Modelle, DSGVO-first |
| Mechanik | Legt einen eigenen Provider-Ordner außerhalb des Checkouts an; delegiert inhaltlich an das EU-Router-Konzept |
| Wächter | **nicht nötig** — liegt außerhalb des Hermes-Checkouts, kein Update kann es entfernen |

Der eurouter zeigt die zweite Säule: **Was außerhalb des Checkouts leben kann,
lebt außerhalb.** Das ist der wartungsärmste Fall überhaupt.

---

## 15. Workflow: Von der Idee zum Push

1. **Ordner/Dateien im Workspace-Clone ändern** (einzige Wahrheit).
2. **Katalog-Version der betroffenen Komponente anheben**, wenn sich etwas
   verändert hat — die UI zeigt sonst "aktuell" obwohl sich der Code geändert
   hat. Version live testen: Install-Status `outdated` erscheint erst, wenn
   lokal eine ältere Version gebucht ist.
3. **Lokal testen** (siehe Abschnitt 16).
4. **Commit** im Workspace-Clone: `git add … && git commit -m "…"`.
5. **Push:** `git push origin main` (Auth ist eingerichtet).
6. **Nicht vergessen:** Der Katalog und der Wächter-Zustand kommen beim
   Install aus dem Netz — ein neuer Push ist erst nach **Cache-Umlauf** live
   (der Katalog-Handler zieht den Tarball aus GitHub, nicht aus dem Repo).

**Wichtig — die Install-Quellen kommen aus dem Netz:** `install.sh`
(Dispatcher) und `install.ps1` ziehen den Tarball von GitHub. Lokale
Änderungen in der Arbeitskopie wirken sich also **nicht** auf fremde
Installationen aus, bis sie gepusht sind.

---

## 16. Testen (bestehendes + nötiges)

### Was heute geprüft wird

- `install_comp` lief bereits für alle vier Komponenten durch (der Marktplatz
  wurde auf der eigenen Maschine installiert; `installed.json` ist befüllt).
- `guard_check.py` ist als eigenständiges Skript lauffähig (manueller Lauf zur
  Diagnose).
- Frontend-Bundles: `dist/index.js` (Web) und `desktop/plugin.js` sind ohne
  Build-Schritt eincheckbar — kein `npm build` nötig, kein Kompilier-Schritt
  im Repo.

### Was fehlt / Sinnvoll als nächster Schritt

- **Automatisierter Test für `guard_check.py`:** Ein Harness, der die
  Hermes-Installation simuliert (Tarball aus einer Staging-Quelle statt GitHub),
  ein Update simuliert (deutschen Patch wegreissen) und verifiziert, dass der
  Wächter ihn wiederherstellt.
- **Idempotenz-Test:** Zweiter Lauf eines jeden `install.sh` sollte identisch
  zum ersten enden (Status "updated", keine Fehler).
- **Rückbau-Test je Komponente:** Install → bewusste Änderung → Uninstall →
  prüfen, dass exakt der Ursprungszustand wieder da ist.
- **Versions-Bump-Test:** `catalog.json`-Version anheben, alte Version in
  `installed.json` — Status muss `outdated` + "Aktualisieren" zeigen.

---

## 17. Release-Praxis

- **`main` ist das Release.** Ältere Versionen werden laut `SECURITY.md` nicht
  mehr unterstützt — d.h. wir halten main grün und aktuell.
- **Kein Feature-Branch-Zwang:** Für ein Zwei-Personen-Team reicht direkt auf
  master zu arbeiten, solange getestet wird. Wenn mehr Leute mitarbeiten:
  themenbezogene Branches + Merge, main bleibt rot-Frei.
- **Ein Release = eine Katalog-Version je geänderter Komponente.** Wer den
  Katalog anfasst, hebt die Version der betroffenen Komponente an — Katalog
  und Komponenten-Versionen bleiben synchron.

---

## 18. Roadmap: Zum Non-Plus-Ultra für den deutschen Markt

Der Vorteil unseres Ansatzes: Der Marktplatz ist bereits die **Vertriebs- und
Update-Infrastruktur**. Jede neue deutsche Erweiterung ist nur noch eine
Komponente im Katalog — kein neues Plugin-System, kein neuer Installer. Das
heißt: Wir können schnell und oft liefern.

### Kriterium für jede neue Komponente

Bevor eine Idee in den Katalog wandert, besteht sie den Test:

1. **Nur wir haben es.** Ist die Funktion für den deutschen Markt gedacht und
   englische Lösungen decken sie nicht ab (Sprach-Integration, DSGVO,
   deutsche Formate, deutsche Community-Workflows)?
2. **Sie hält ein Update aus.** `plugin` (außerhalb Checkout) oder `patch` mit
   Wächter-Anbindung. Keine Komponente, die beim ersten Hermes-Update stirbt.
3. **Ein Klick, klarer Effekt.** Nutzer versteht ohne Handbuch, was sie tut.

### Ideen-Pool (priorisiert)

**Phase A — Komfort (klein, schnell lieferbar):**

- **Deutsche Tastatur-/Prompt-Snippets:** `/de`-Befehle für Alltagsaufgaben
  (formelle E-Mail, Angebot, Rechnung, Entschuldigung) mit deutschem Ton —
  direkt als Komponente im Katalog.
- **Deutsche Format-Werkzeuge:** Datum/Uhrzeit im deutschen Format erzwingen,
  deutsche Zahlen (Komma statt Punkt), Anrede-Korrektur in generierten
  Texten. Als `plugin`, reine Konfiguration.
- **DSGVO-Check-Baustein:** Vor dem Senden prüfen lassen, ob ein Text
  personenbezogene Daten enthält (Name, E-Mail, Adresse) und ob der Empfänger
  sie braucht. Ein Thema, das international kaum jemand als Komponente liefert.

**Phase B — Tiefe (differenzierend):**

- **Deutsche Bot-Stimme als Paket:** Bot-Modus auf Deutsch mit
  Geschäftskorrespondenz-Baustein-Sammlung (Anrede, Höflichkeitsfloskeln,
  Abschlussformeln), nicht nur Übersetzung, sondern deutscher Stil.
- **Deutsches Modell-Bündel:** Im eurouter-Provider die EU-konformen
  Standard-Modelle vorbelegen (z. B. deutsche/europäische Hosts), mit
  verständlicher Erklärung "Daten bleiben in der EU" direkt im Picker.
- **Update-Transparenz:** Nach jedem Hermes-Update im Chat melden
  ("Der deutsche Sprach-Satz wurde automatisch wiederhergestellt") — der
  Wächter kann das als Event liefern. Das ist sichtbarer Mehrwert, den
  sonst niemand hat.

**Phase C — Community (Netzwerk-Effekt):**

- **Deutsche Community-Erweiterungen:** Katalog für Dritte öffnen
  (Komponenten von Community-Mitgliedern), mit Review-Pflicht und
  Aiianer-Siegel ("geprüft von Aiianer"). Das macht den Marktplatz zur
  Plattform, nicht nur zur Sammlung.
- **Deutscher Onboarding-Assistent:** Erste-Schritte-Wizard in deutsch, der
  nach der Installation erklärt, was jetzt deutsch ist und was nicht.

### Was wir NICHT bauen (bewusst)

- **Keine eigene Sprache:** Wir übersetzen Hermes, wir forken nicht.
- **Keine deutschen Modelle erfinden:** Wir bündeln, was es gibt (EU-Hosting,
  Open Source), wir trainieren nichts.
- **Kein Eingriff in fremde Dateien ohne Sicherung:** Der Patch-Weg bleibt
  der dokumentierte Ausnahmefall mit Wächter — nicht der Standard.

---

## 19. Bekannte offene Punkte / Baustellen

- **`ARCHITEKTUR-MARKTPLATZ.html` ist Stand frühe Phase** und zeigt nicht den
  finalen Stand (u. a. eurouter, Wächter-Detail). Sie ist als visueller
  Einstieg ok, aber nicht als Wahrheit für Details — diese Datei hier ist es.
- **`install.ps1`-Windows-Pfad:** Existiert, aber der volle Windows-Test
  (natives PowerShell, `%LOCALAPPDATA%`) steht noch aus.
- **Automatisierte Tests fehlen** (siehe Abschnitt 16) — aktuell ist der
  "Test" die eigene Installation auf Olivers Maschine.
- **Cache-Umlauf nach Push:** Der Netz-Katalog braucht nach einem Push etwas
  Zeit, bis fremde Installationen die neue Version sehen (siehe Abschnitt 15).

---

*Diese Datei ist die Dev-Doku und wird im Workspace-Clone gepflegt. Stand:
September 2026.*