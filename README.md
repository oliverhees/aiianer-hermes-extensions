<h1 align="center">AIIANER Hermes Extensions</h1>

<p align="center"><strong>Erweiterungen für Hermes Desktop — direkt aus GitHub installierbar.</strong></p>

<p align="center">
  <a href="#lizenz"><img src="https://img.shields.io/badge/Lizenz-Open--Core%20(MIT%20Basis)-green" alt="Lizenz" /></a>
  <img src="https://img.shields.io/badge/Nur%20f%C3%BCr-Hermes%20Desktop-red" alt="Nur für Hermes" />
  <a href="https://aiianer.de"><img src="https://img.shields.io/badge/Community-AIIANER-black" alt="AIIANER Community" /></a>
</p>

---

## Was ist das?

Das zentrale Repo für die AIIANER-Erweiterungen von Hermes: der AIIANER-Marktplatz,
deutsche Sprachpakete, Bot-Mode-Texte, Gruppenchat-Grenzen und weitere Werkzeuge.

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
| **aiianer-backup** | Lokale vollständige Hermes-Backups in einem externen Ordner. V1 ohne Upload/GitHub; Wiederherstellung nur nach expliziter Bestätigung. |

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

## Lizenz

AIIANER Hermes Extensions folgt einem **Open-Core-Modell**: Die Basis steht unter
**MIT** (siehe [LICENSE](LICENSE)) und ist für private wie kommerzielle Nutzung
frei. Details stehen in [LICENSING.md](LICENSING.md). Support gibt es unter
**support@aiianer.de** oder in der [AIIANER Community](https://aiianer.de).

## Sicherheit

Sicherheitslücken bitte **nicht** als öffentliches Issue melden, siehe
[SECURITY.md](SECURITY.md).

## Marken

„AIIANER", „Lokyy", „Lokyy Brain", „Datenschleuse" und „Sichtradar" sind
Kennzeichen von Oliver Hees aka Aiianer. Die Lizenz des Quellcodes gewährt keine
Rechte an diesen Namen oder Logos. Forks müssen unter eigenem Namen auftreten.

„Hermes" und „EU Router" sind Produkt- beziehungsweise Angebotsnamen der jeweiligen
Betreiber. Diese Erweiterungen sind unabhängige Community-Projekte.

---

<p align="center">
  © 2026 <strong>Oliver Hees aka Aiianer</strong> ·
  <a href="https://aiianer.de">aiianer.de</a> ·
  Gebaut im AIIANER-Universum
</p>
