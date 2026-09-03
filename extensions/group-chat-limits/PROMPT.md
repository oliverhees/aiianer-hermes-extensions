# Installations-Satz für den Hermes-Chat

> Installiere bitte die einstellbaren Gruppenchat-Grenzen. Führe dazu diesen Befehl aus:
> `curl -sL https://raw.githubusercontent.com/oliverhees/aiianer-hermes-extensions/main/extensions/group-chat-limits/install.sh | bash`
> Sag mir, was das Skript gemeldet hat. Falls es mit "FEHLER" endet, erkläre mir kurz warum
> und ändere nichts weiter. Bei Erfolg erinnere mich daran, Hermes komplett neu zu starten.

## Was das bringt

Hermes deckelt einen Gruppenchat hart: 3 Runden und 10 Nachrichten. Bei sechs
Bots greift die Zehn praktisch immer zuerst, der Raum ist also nach knapp zwei
Runden still, egal wie interessant es gerade wird.

Nach der Installation legst du das pro Raum selbst fest. Voreingestellt sind
8 Runden und 40 Nachrichten für alle Räume.

## Grenzen ändern

1. `~/.hermes/aiianer/gruppen-grenzen.json` bearbeiten
2. Im AIIANER-Marktplatz auf "Neu einspielen"
3. Hermes neu starten

Der Umweg über den Marktplatz ist nötig, weil die Oberfläche im Browser läuft
und keine Dateien lesen kann. Beim Einspielen wird deine Konfiguration zu Code,
den Hermes beim nächsten Start mitbaut.

## Aufbau der Datei

```json
{
  "*": { "rounds": 8, "messages": 40 },
  "Redaktion": { "rounds": null, "safetyRounds": 30 },
  "Duo": { "rounds": 2, "history": 60 }
}
```

Der Schlüssel ist der Gruppenname, `*` gilt für alle Räume ohne eigenen
Eintrag. Ein eigener Eintrag erbt **nicht** vom Stern: was dort nicht steht,
kommt von Hermes.

| Achse | Voreinstellung | Bedeutung |
| --- | --- | --- |
| `rounds` | 3 | Runden pro Absenden |
| `messages` | 10 | Bot-Nachrichten pro Absenden |
| `continuations` | 2 | Fortsetzungen durch Erwähnungen |
| `history` | 24 | Verlaufszeilen, die ins Modell gehen |
| `safetyRounds` | 50 | Bremse, greift nur wenn `rounds` auf `null` steht |
| `safetyMessages` | 200 | Bremse, greift nur wenn `messages` auf `null` steht |

Eine Zahl setzt die Grenze. `null` schaltet die Achse ab, dann übernimmt die
Bremse. Steht auch die Bremse auf `null`, läuft der Raum, bis jeder Bot passt
oder du erneut sendest. Das ist Absicht, aber du solltest wissen, was du tust.

Gegen Tippfehler gibt es Deckel: höchstens 100 Runden, 500 Nachrichten,
200 Verlaufszeilen. Eine 5000 im Rundenfeld ist kein Wunsch, sondern ein
verrutschter Finger.
