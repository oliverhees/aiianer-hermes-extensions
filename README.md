<h1 align="center">AIIANER Hermes Extensions</h1>

<p align="center"><strong>Alle AIIANER-Erweiterungen für Hermes Desktop. Eine installierst du mit einem Satz an deinen Hermes.</strong></p>

<p align="center">
  <a href="#lizenz"><img src="https://img.shields.io/badge/Lizenz-AGPL--3.0%20%2B%20Kommerziell-red" alt="Lizenz" /></a>
  <img src="https://img.shields.io/badge/Nur%20f%C3%BCr-Hermes%20Desktop-red" alt="Nur für Hermes" />
  <a href="https://aiianer.de"><img src="https://img.shields.io/badge/Community-AIIANER-black" alt="AIIANER Community" /></a>
</p>

---

## Was ist das?

Das zentrale Repo für alle Erweiterungen, die wir bei [AIIANER](https://aiianer.de)
für Hermes Desktop bauen: Provider-Plugins, Sprachdateien, Werkzeuge. Jede
Komponente bringt ihren eigenen Installer mit, und dazu ihren
**Installations-Satz**: eine Nachricht, die du einfach in deinen Hermes-Chat
kopierst. Hermes ist ein Agent mit Terminal-Zugriff und installiert die
Komponente dann selbst, prüft das Ergebnis und sagt dir, was noch zu tun ist.
Kein git, kein Terminal-Wissen nötig.

**Teil des AIIANER-Ökosystems:** Bei [AIIANER](https://aiianer.de) bauen wir
ein KI-Betriebssystem, das [Hermes Desktop](https://github.com/NousResearch/hermes-agent)
als Grundlage nutzt. Hermes selbst ist ein Open-Source-Projekt von
**Nous Research**. Die Erweiterungen hier sind unabhängige Community-Projekte
und stehen in keiner offiziellen Verbindung zu Nous Research.

## Komponenten

| Komponente | Was sie tut | Installations-Satz |
| --- | --- | --- |
| **aiianer-hub** | **Der Marktplatz.** Ein Reiter in Hermes, aus dem du alle Komponenten unten installierst und aktuell hältst. Bringt einen Wächter mit, der nach jedem Hermes-Update prüft, ob noch alles sitzt, und Fehlendes selbst nachlegt. [Anleitung](extensions/aiianer-hub/README.md) | [PROMPT.md](extensions/aiianer-hub/PROMPT.md) |
| **eurouter-provider** | EU Router (eurouter.ai) als Provider: EU-Compliance-Routen statt roher Modelle im Picker, DSGVO-konformes Routing. Eigenes Repo: [hermes-eurouter-plugin](https://github.com/oliverhees/hermes-eurouter-plugin) | [PROMPT.md](extensions/eurouter-provider/PROMPT.md) |
| **german-language** | Deutsche Sprachdatei für Hermes Desktop (eigenständiger Installer, trägt Deutsch als Sprache in Hermes ein) | [PROMPT.md](extensions/german-language/PROMPT.md) |
| **bot-mode-german** | Deutsche Texte für **Bot Mode**: Liste, Gruppenchats, Avatare, Zeitpläne. 194 Bausteine, eingetragen in den plugin-eigenen Nachrichtenkatalog von Bot Mode. Setzt `german-language` voraus | [PROMPT.md](extensions/bot-mode-german/PROMPT.md) |

| **group-chat-limits** | Runden, Nachrichten, Fortsetzungen und Verlauf pro Gruppenchat selbst festlegen, inklusive „aus“ mit abschaltbarer Bremse. Hermes deckelt hart bei 3 Runden und 10 Nachrichten, wobei die Zehn bei 6 Bots immer zuerst greift | [PROMPT.md](extensions/group-chat-limits/PROMPT.md) |

Weitere Komponenten folgen, jede nach demselben Muster: `install.sh` plus `PROMPT.md`.

## Installation

**Empfohlen: erst den Marktplatz.** Installierst du `aiianer-hub`, brauchst du
danach kein Terminal mehr. Alles Weitere wählst du im Reiter „AIIANER" direkt in
Hermes aus, inklusive Updates.

Linux, macOS, WSL:

```bash
curl -sL https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/install.sh | bash -s aiianer-hub
```

Windows nativ, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/extensions/aiianer-hub/install.ps1 | iex
```

Danach Hermes neu starten. Die [Anleitung](extensions/aiianer-hub/README.md)
erklärt den Rest.

**Einzelne Komponente ohne Marktplatz:** Öffne die `PROMPT.md` der Komponente und
kopiere den Satz in deinen Hermes-Chat. Hermes erledigt den Rest.

**Oder im Terminal**, eine Komponente direkt:

```bash
curl -sL https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/install.sh | bash -s german-language
```

Ohne Argument listet der Installer alle verfügbaren Komponenten:

```bash
curl -sL https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/install.sh | bash
```

## Update-Sicherheit, das Designprinzip

Hermes aktualisiert sich täglich und räumt dabei alles weg, was im
Programm-Checkout liegt. Deshalb gilt hier:

1. **Komponenten installieren an update-sichere Orte** (z. B.
   `~/.hermes/plugins/model-providers/`), wo immer Hermes das offiziell vorsieht.
2. **Muss eine Komponente in den Checkout** (wie die Sprachdatei), arbeitet der
   Installer mit gezielten, wiederholbaren Einfügungen an stabilen Ankern:
   alles-oder-nichts mit Backup, laute Fehlermeldung statt halbem Zustand.
   Nach einem Update, das die Änderung entfernt: denselben Satz einfach nochmal
   an Hermes schicken.
3. **Nimm den offiziellen Weg, wo es einen gibt.** Bot Mode zum Beispiel
   bringt seit dem Umbau einen eigenen Nachrichtenkatalog mit. Da tragen wir
   nur noch ein deutsches Bündel ein, statt Dateien zu ersetzen. Solche Türen
   halten, weil sie dafür gedacht sind.

> Tutorials, Setups und Support gibt es in der
> [AIIANER Community](https://aiianer.de), inklusive KI-Coach.
> Fragen zu einer Komponente? Log-Zeilen mitschicken, dann schauen wir gemeinsam drauf.

## Lizenz

AIIANER Hermes Extensions ist **dual lizenziert**: **AGPL-3.0** (siehe
[LICENSE](LICENSE)) für private Nutzung, Selbsthoster, Forschung und
Copyleft-Projekte. Alternativ eine **kommerzielle Lizenz** für den Einsatz in
geschlossenen Produkten, Details in [LICENSING.md](LICENSING.md), Anfragen an
**support@aiianer.de** oder über die [AIIANER Community](https://aiianer.de).

## Sicherheit

Sicherheitslücken bitte **nicht** als öffentliches Issue melden, siehe
[SECURITY.md](SECURITY.md).

## Marken

„AIIANER", „Lokyy", „Lokyy Brain", „Datenschleuse" und „Sichtradar" sind
Kennzeichen von Oliver Hees aka Aiianer. Die Lizenz des Quellcodes gewährt
**keine** Rechte an diesen Namen oder Logos. Forks müssen unter eigenem Namen
auftreten.

„Hermes" ist ein Open-Source-Projekt von **Nous Research**
([github.com/NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)).
„EU Router" / eurouter.ai ist ein Angebot des jeweiligen Betreibers.
Die Erweiterungen hier sind unabhängige Community-Projekte ohne offizielle
Verbindung zu Nous Research oder eurouter.ai.

---

<p align="center">
  © 2026 <strong>Oliver Hees aka Aiianer</strong> ·
  <a href="https://aiianer.de">aiianer.de</a> ·
  Gebaut im AIIANER-Universum
</p>
