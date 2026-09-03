# AIIANER Marktplatz

Ein Reiter in Hermes, aus dem du die deutschen AIIANER-Erweiterungen
installierst und aktuell hältst. Und ein Wächter, der nach jedem
Hermes-Update prüft, ob noch alles sitzt, und Fehlendes selbst nachlegt.

---

## Warum es das gibt

Hermes aktualisiert sich fast täglich und ersetzt dabei sein eigenes
Verzeichnis komplett. Alles, was dort hineingeschrieben wurde, ist danach weg.
Genau das passiert der deutschen Sprachdatei, weil Hermes keine Möglichkeit
anbietet, eine Sprache zur Laufzeit anzumelden.

Der Marktplatz löst das, indem er selbst außerhalb dieses Verzeichnisses wohnt
und die Sprachdatei nach jedem Update erneut einspielt. Du merkst davon nichts.

## Installation

**Der einfache Weg.** Kopiere den Satz aus [PROMPT.md](PROMPT.md) in deinen
Hermes-Chat. Hermes hat Terminal-Zugriff und installiert sich das selbst.

**Oder im Terminal.** Welcher Befehl gilt, hängt vom System ab.

Linux, macOS und Windows mit WSL:

```bash
curl -sL https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/install.sh | bash -s aiianer-hub
```

Windows nativ, also in PowerShell ohne WSL:

```powershell
irm https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/extensions/aiianer-hub/install.ps1 | iex
```

Danach **Hermes komplett neu starten**.

## Wo du es findest

Hermes hat zwei Oberflächen mit zwei getrennten Plugin-Systemen. Der Marktplatz
bedient beide, du findest ihn also überall.

| Oberfläche | Wo | Wie du sie öffnest |
| --- | --- | --- |
| **Desktop-App** | Eintrag „AIIANER" in der Seitenleiste | Hermes normal starten |
| **Web-Dashboard** | Reiter „AIIANER" neben Skills | `hermes web`, dann `http://127.0.0.1:9119` |

Wenn du in der Desktop-App suchst und nichts findest, hast du Hermes nach der
Installation vermutlich nicht neu gestartet. Plugins werden nur beim Start
geladen.

## Was wohin installiert wird

Hermes legt seine Daten je nach System woanders ab. Der Installer findet den
richtigen Ort selbst, du musst nichts einstellen.

| System | Hermes-Verzeichnis |
| --- | --- |
| Linux, macOS, WSL | `~/.hermes` |
| Windows nativ | `%LOCALAPPDATA%\hermes`, also `C:\Users\DeinName\AppData\Local\hermes` |
| Beliebig | Was in `HERMES_HOME` steht, falls du das gesetzt hast |

Darin landen drei Ordner. Im Folgenden steht `<hermes>` für den Pfad aus der
Tabelle oben.

| Ort | Was dort liegt |
| --- | --- |
| `<hermes>/plugins/aiianer-hub/` | Web-Dashboard: Reiter und das Backend |
| `<hermes>/desktop-plugins/aiianer-hub/` | Desktop-App: Seitenleisten-Eintrag und Seite |
| `<hermes>/hooks/aiianer-guard/` | Der Wächter, lauscht auf den Gateway-Start |
| `<hermes>/aiianer/` | Sprachquelle, Zustand und Protokoll |

Alle drei liegen **außerhalb** des Hermes-Programmverzeichnisses und überleben
deshalb jedes Update.

## Der Wächter

Bei jedem Start des Gateways prüft er, ob deine Erweiterungen ein Update
überstanden haben. Fehlt etwas, spielt er es aus `~/.hermes/aiianer/` neu ein.

Sein Protokoll liegt unter:

```
<hermes>/aiianer/guard.log
```

Auf Linux und macOS also `~/.hermes/aiianer/guard.log`, auf nativem Windows
`%LOCALAPPDATA%\hermes\aiianer\guard.log`.

Dort steht pro Start eine Zeile. Entweder „Pruefung ok, nichts zu tun" oder
„german-language nach Update erneut eingespielt".

Der Wächter kann den Gateway-Start nicht kaputt machen. Fehler werden gefangen
und protokolliert, nie weitergereicht.

## Zwei Arten von Komponenten

Im Marktplatz steht bei jeder Komponente, welcher Art sie ist. Der Unterschied
ist wichtig genug, um ihn zu kennen.

**Eigenständig.** Das Plugin lebt vollständig außerhalb des Hermes-Verzeichnisses
und kann durch ein Update gar nicht kaputtgehen. Der EU-Router und der deutsche
Bot-Modus sind so gebaut.

**Greift in den Checkout ein.** Die Sprachdatei muss in Hermes' eigene Dateien
geschrieben werden, weil es keinen anderen Weg gibt. Sie ist deshalb auf den
Wächter angewiesen. Das ist kein Pfusch, sondern die einzige Möglichkeit, und
sie ist so gebaut, dass sie sich selbst repariert.

## Wenn es doch mal klemmt

Hermes baut manchmal größer um. Passt danach ein Ankerpunkt nicht mehr, kann
der Wächter die Sprachdatei nicht mehr einsetzen. **Er versagt dann nicht
still.** Im Marktplatz erscheint ein Hinweis mit einem Knopf „Jetzt reparieren",
und im Protokoll steht die genaue Ursache.

Wenn auch das nicht hilft, ist der Patcher an den neuen Hermes-Stand anzupassen.
Melde dich in dem Fall in der [AIIANER Community](https://aiianer.de) und schick
die letzten Zeilen aus `guard.log` mit. Das ist genau die Rückmeldung, mit der
wir es reparieren.

## Was der Marktplatz technisch tut

Vier Routen, alle hinter der normalen Anmeldung des Dashboards:

| Route | Wofür |
| --- | --- |
| `GET /api/plugins/aiianer-hub/catalog` | Was gibt es, was ist installiert, was ist veraltet |
| `GET /api/plugins/aiianer-hub/health` | Sitzt nach dem letzten Update noch alles |
| `POST /api/plugins/aiianer-hub/install` | Eine Komponente installieren oder aktualisieren |
| `POST /api/plugins/aiianer-hub/repair` | Von Hand auslösen, was der Wächter automatisch tut |

Die Oberfläche nutzt ausschließlich das Plugin-SDK von Hermes und bringt weder
React noch fremde Komponenten mit. Das Bundle ist knapp sechs Kilobyte groß.

Der Katalog wird beim Öffnen aus dem öffentlichen Repo geladen. Ist gerade kein
Netz da, greift die mitgelieferte Fassung. Ein eigener Server ist nicht nötig.

## Entfernen

Linux, macOS, WSL:

```bash
rm -rf ~/.hermes/plugins/aiianer-hub ~/.hermes/hooks/aiianer-guard ~/.hermes/aiianer
```

Windows nativ, in PowerShell:

```powershell
Remove-Item -Recurse -Force "$env:LOCALAPPDATA\hermes\plugins\aiianer-hub", "$env:LOCALAPPDATA\hermes\hooks\aiianer-guard", "$env:LOCALAPPDATA\hermes\aiianer"
```

Danach Hermes neu starten. Bereits installierte Komponenten bleiben, die
entfernst du einzeln aus dem Ordner `plugins`.
