<h1 align="center">🇩🇪 AIIANER Hermes Extensions</h1>

<p align="center"><strong>Der deutsche Marktplatz für Hermes Desktop.</strong><br />
Installierbare Werkzeuge, Sprache und Automationen für deinen KI-Außenposten.</p>

<p align="center">
  <a href="#status"><img src="https://img.shields.io/badge/🚧%20STATUS-BETA-orange" alt="Status: Beta" /></a>
  <a href="#lizenz"><img src="https://img.shields.io/badge/Lizenz-Open--Core%20(MIT%20Basis)-green" alt="Lizenz" /></a>
  <img src="https://img.shields.io/badge/Nur%20f%C3%BCr-Hermes%20Desktop-red" alt="Nur für Hermes" />
  <a href="https://aiianer.de"><img src="https://img.shields.io/badge/Community-AIIANER-black" alt="AIIANER Community" /></a>
</p>

![AIIANER Hermes Marktplatz](docs/assets/aiianer-hermes-marktplatz.png)

> **🚧 BETA:** Der AIIANER Hermes Marktplatz ist aktiv nutzbar, aber noch in Entwicklung. Teste ihn gern — und melde Fehler, Ideen oder UX-Stolpersteine über [Feedback & Issues](https://github.com/oliverhees/aiianer-hermes-extensions/issues/new/choose).

---

## Was ist das?

Der **AIIANER Hermes Marktplatz** ist die deutsche Erweiterungsplattform für
[Hermes Desktop](https://github.com/NousResearch/hermes-agent). Ein Plugin, ein
klarer Ort, ein Klick: deutsche Sprache, nützliche Werkzeuge und update-feste
Automationen direkt in Hermes.

**Tagline:** KI zum Anwenden, nicht zum Hypen.

Der Marktplatz ist ein **Hybrid-Plugin**: Er bringt die Dashboard- und Desktop-
Oberfläche gemeinsam mit seinem Backend in einem Paket mit. Über seine Oberfläche
installierst und aktualisierst du die übrigen AIIANER-Erweiterungen.

## Komponenten

| Komponente | Was sie tut |
| --- | --- |
| **aiianer-hub** | **Der Marktplatz.** Ein Reiter in Hermes zum Installieren und Aktualisieren der AIIANER-Erweiterungen. Enthält außerdem den Wächter, der die Erweiterungen nach Hermes-Updates prüft und bei Bedarf repariert. |
| **eurouter-provider** | EU Router als Provider mit EU-Compliance-Routen im Modell-Picker. |
| **german-language** | Deutsche Oberfläche für Hermes Desktop. Wird nach Hermes-Updates automatisch erneut eingespielt. |
| **bot-mode-german** | Deutsche Texte für Bot Mode: Liste, Gruppenchats, Avatare und Zeitpläne. Setzt `german-language` voraus. |
| **group-chat-limits** | Eigene Runden-, Nachrichten-, Fortsetzungs- und Verlaufsgrenzen pro Gruppenchat. |
| **aiianer-backup** | Lokale vollständige Hermes-Backups in einem externen Ordner. V1 mit Planung, Laufprotokoll, Archivliste und sicherem Restore. GitHub-Backup steht auf der Roadmap. |

## Installation

Der **einzige Installationsweg** führt über Hermes selbst:

1. Öffne in Hermes **Settings → Plugins → Install from Git**.
2. Trage dieses Repository ein:

   ```text
   https://github.com/oliverhees/aiianer-hermes-extensions
   ```

3. Prüfe die angezeigten Plugin-Inhalte und installiere das Plugin.
4. Aktiviere **AIIANER** anschließend, falls Hermes danach fragt, und starte den
   Gateway bzw. Hermes neu.

Das Repo enthält `plugin.yaml` im Root sowie die Dashboard- und Desktop-Hälften.
Hermes erkennt es deshalb direkt als Hybrid-Plugin; kein zusätzlicher Installer,
Terminal-Befehl oder Prompt ist nötig.

Nach dem Neustart erscheint **AIIANER** in der Seitenleiste beziehungsweise als
Dashboard-Reiter. Die weiteren Komponenten installierst du dort mit den jeweiligen
Buttons.

## Update und Entfernen

Git-installierte Plugins verwaltest du in Hermes unter **Settings → Plugins**.
Dort kannst du das Plugin aktualisieren, deaktivieren oder entfernen. Der
Marktplatz kann sich nicht über seine eigene Oberfläche deinstallieren; nutze dafür
den normalen Plugin-Manager von Hermes.

## Update-Sicherheit

Hermes aktualisiert sein eigenes Programmverzeichnis regelmäßig. Der Marktplatz
liegt deshalb vollständig in den vorgesehenen Plugin-Verzeichnissen außerhalb des
Hermes-Checkouts. Die deutsche Sprachdatei und andere notwendige Anpassungen
werden über den Wächter nach einem Hermes-Update erneut eingespielt.

Der Wächter arbeitet mit Sicherungen und wiederholbaren Ankern. Wenn ein Hermes-
Umbau einen Ankerpunkt unbrauchbar macht, meldet der Marktplatz die Ursache,
statt still einen halben Zustand zu hinterlassen.

## Feedback, Hilfe und Probleme

Der Marktplatz ist **Beta**. Genau deshalb ist dein Feedback wichtig:

- 🐛 [Problem melden](https://github.com/oliverhees/aiianer-hermes-extensions/issues/new?template=bug_report.md)
- 💡 [Feature oder Idee vorschlagen](https://github.com/oliverhees/aiianer-hermes-extensions/issues/new?template=feature_request.md)
- 💬 [Allgemeines Feedback geben](https://github.com/oliverhees/aiianer-hermes-extensions/issues/new?template=feedback.md)
- 🔒 Sicherheitslücken bitte ausschließlich an **hi@aiianer.de** melden — siehe [SECURITY.md](SECURITY.md)

Fragen und Support: **[hi@aiianer.de](mailto:hi@aiianer.de)** oder in der [AIIANER Community](https://aiianer.de).

## Lizenz

AIIANER Hermes Extensions folgt einem **Open-Core-Modell**: Die Basis steht unter
**MIT** (siehe [LICENSE](LICENSE)) und ist für private wie kommerzielle Nutzung
frei. Details stehen in [LICENSING.md](LICENSING.md).

## Sicherheit

Sicherheitslücken bitte **nicht** als öffentliches Issue melden, siehe
[SECURITY.md](SECURITY.md).

## Marken

„AIIANER", „Lokyy", „Lokyy Brain", „Datenschleuse" und „Sichtradar" sind
Kennzeichen von Oliver Hees aka Aiianer. Die Lizenz des Quellcodes gewährt keine
Rechte an diesen Namen oder Logos. Forks müssen unter eigenem Namen auftreten.

"Hermes" und "EU Router" sind Produkt- beziehungsweise Angebotsnamen der jeweiligen
Betreiber. Diese Erweiterungen sind unabhängige Community-Projekte.

## Status

**🚧 Beta — live nutzbar, aktiv weiterentwickelt.**

Der lokale Backup-Außenposten ist verfügbar. Die geplante GitHub-Integration für
verschlüsselte, versionierte Backup-Assets folgt als nächste Ausbaustufe und ist
noch nicht Bestandteil der aktuellen V1.

## Roadmap

- [x] Deutscher Hermes-Marktplatz mit Desktop- und Dashboard-Integration
- [x] Externe lokale Backups mit Zeitplan, Laufprotokoll und sicherem Restore
- [x] Feedback- und Issue-Prozess direkt über GitHub
- [ ] GitHub-Integration für verschlüsselte Backup-Assets mit Prüfsumme
- [ ] Weitere deutsche Community-Werkzeuge

---

<p align="center">
  © 2026 <strong>Oliver Hees aka Aiianer</strong> ·
  <a href="https://aiianer.de">aiianer.de</a> ·
  Gebaut im AIIANER-Universum
</p>
