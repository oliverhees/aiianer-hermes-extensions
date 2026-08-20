<h1 align="center">AIIANER Hermes Extensions</h1>

<p align="center"><strong>Alle AIIANER-Erweiterungen für Hermes Desktop — installierbar mit je einem Satz an deinen Hermes.</strong></p>

<p align="center">
  <a href="#lizenz"><img src="https://img.shields.io/badge/Lizenz-AGPL--3.0%20%2B%20Kommerziell-red" alt="Lizenz" /></a>
  <img src="https://img.shields.io/badge/Nur%20f%C3%BCr-Hermes%20Desktop-red" alt="Nur für Hermes" />
  <a href="https://aiianer.de"><img src="https://img.shields.io/badge/Community-AIIANER-black" alt="AIIANER Community" /></a>
</p>

---

## Was ist das?

Das zentrale Repo für alle Erweiterungen, die wir bei [AIIANER](https://aiianer.de)
für Hermes Desktop bauen: Provider-Plugins, Sprachdateien, Werkzeuge. Jede
Komponente bringt ihren eigenen Installer mit und — das Besondere — ihren
**Installations-Satz**: eine Nachricht, die du einfach in deinen Hermes-Chat
kopierst. Hermes ist ein Agent mit Terminal-Zugriff und installiert die
Komponente dann selbst, prüft das Ergebnis und sagt dir, was noch zu tun ist.
Kein git, kein Terminal-Wissen nötig.

**Teil des AIIANER-Ökosystems:** Bei [AIIANER](https://aiianer.de) bauen wir
ein KI-Betriebssystem, das [Hermes Desktop](https://github.com/NousResearch/hermes-agent)
als Grundlage nutzt. Hermes selbst ist ein Open-Source-Projekt von
**Nous Research** — die Erweiterungen hier sind unabhängige Community-Projekte
und stehen in keiner offiziellen Verbindung zu Nous Research.

## Komponenten

| Komponente | Was sie tut | Installations-Satz |
| --- | --- | --- |
| **eurouter-provider** | EU Router (eurouter.ai) als Provider: EU-Compliance-Routen statt roher Modelle im Picker, DSGVO-konformes Routing. Eigenes Repo: [hermes-eurouter-plugin](https://github.com/oliverhees/hermes-eurouter-plugin) | [PROMPT.md](extensions/eurouter-provider/PROMPT.md) |
| **german-language** | Deutsche Sprachdatei für Hermes Desktop (Interims-Installer, bis Upstream-PR [#51762](https://github.com/NousResearch/hermes-agent/pull/51762) gemerged ist) | [PROMPT.md](extensions/german-language/PROMPT.md) |

Weitere Komponenten folgen — jede nach demselben Muster: `install.sh` + `PROMPT.md`.

## Installation

**Der einfachste Weg:** Öffne die `PROMPT.md` der Komponente und kopiere den
Satz in deinen Hermes-Chat. Hermes erledigt den Rest.

**Oder im Terminal**, eine Komponente direkt:

```bash
curl -sL https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/install.sh | bash -s german-language
```

Ohne Argument listet der Installer alle verfügbaren Komponenten:

```bash
curl -sL https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/install.sh | bash
```

## Update-Sicherheit — das Designprinzip

Hermes aktualisiert sich täglich und räumt dabei alles weg, was im
Programm-Checkout liegt. Deshalb gilt hier:

1. **Komponenten installieren an update-sichere Orte** (z. B.
   `~/.hermes/plugins/model-providers/`), wo immer Hermes das offiziell vorsieht.
2. **Muss eine Komponente in den Checkout** (wie die Sprachdatei), arbeitet der
   Installer mit gezielten, idempotenten Einfügungen an stabilen Ankern —
   alles-oder-nichts mit Backup, laute Fehlermeldung statt halbem Zustand.
   Nach einem Update, das die Änderung entfernt: denselben Satz einfach nochmal
   an Hermes schicken.
3. **Der Königsweg bleibt Upstream:** Wo es sinnvoll ist, stellen wir PRs an
   Nous Research (die Sprachdatei läuft bereits als
   [#51762](https://github.com/NousResearch/hermes-agent/pull/51762)) — sobald
   gemerged, fliegt der jeweilige Interims-Installer hier raus.

> 🎓 **Tutorials, Setups und Support** gibt es in der
> [AIIANER Community](https://aiianer.de) — inklusive KI-Coach.
> Fragen zu einer Komponente? Log-Zeilen mitschicken, dann schauen wir gemeinsam drauf.

## Lizenz

AIIANER Hermes Extensions ist **dual lizenziert**: **AGPL-3.0** (siehe
[LICENSE](LICENSE)) für private Nutzung, Selbsthoster, Forschung und
Copyleft-Projekte — oder **kommerzielle Lizenz** für den Einsatz in
geschlossenen Produkten, Details in [LICENSING.md](LICENSING.md), Anfragen an
**support@aiianer.de** oder über die [AIIANER Community](https://aiianer.de).

## Sicherheit

Sicherheitslücken bitte **nicht** als öffentliches Issue melden — siehe
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
  Made with 🖤 im AIIANER-Universum
</p>
