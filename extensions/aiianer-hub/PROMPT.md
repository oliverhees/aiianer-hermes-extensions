# AIIANER Marktplatz installieren

Kopiere diese Nachricht in deinen Hermes-Chat. Sie funktioniert auf jedem
System, weil Hermes selbst herausfindet, wo er läuft.

> Installiere bitte den AIIANER Marktplatz für mich.
>
> Finde zuerst heraus, auf welchem System du läufst, und nimm dann den
> passenden Befehl:
>
> Auf Linux, macOS oder Windows mit WSL:
> `curl -sL https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/install.sh | bash -s aiianer-hub`
>
> Auf nativem Windows in PowerShell:
> `irm https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/extensions/aiianer-hub/install.ps1 | iex`
>
> Prüfe danach, ob in deinem Hermes-Verzeichnis diese drei Ordner liegen:
> `plugins/aiianer-hub`, `hooks/aiianer-guard` und `aiianer`. Dein
> Hermes-Verzeichnis ist `~/.hermes` auf Linux, macOS und WSL, und
> `%LOCALAPPDATA%\hermes` auf nativem Windows. Falls `HERMES_HOME` gesetzt ist,
> gilt das stattdessen.
>
> Sag mir, ob alles geklappt hat, und erinnere mich daran, Hermes komplett neu
> zu starten. Danach finde ich den Reiter „AIIANER" neben Skills.
