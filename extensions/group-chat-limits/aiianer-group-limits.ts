/**
 * Einstellbare Grenzen pro Gruppenchat.
 *
 * Hermes deckelt einen Gruppenchat hart: 3 Runden, 10 Nachrichten, 2
 * Fortsetzungen, 24 Verlaufszeilen, 6 Mitglieder. Die Zehn greift bei sechs
 * Bots praktisch immer zuerst, der Raum ist also nach knapp zwei Runden still.
 *
 * Upstream hat diese Deckel bewusst in EINEN Block gelegt (group-chat.ts,
 * "making them configurable ... is live contributor work ... both need exactly
 * one seam to hook"). Genau da hängt sich diese Datei ein: sie ersetzt die
 * Konstanten nicht, sie löst sie pro Raum auf.
 *
 * Drei Zustände je Achse:
 *
 *    Zahl     die Grenze, wird durchgesetzt wie vorher
 *    null     aus, diese Achse stoppt den Lauf nicht mehr
 *    fehlt    erbt die Voreinstellung von Hermes
 *
 * Steht Runden oder Nachrichten auf "aus", übernimmt die Sicherheitsbremse.
 * Auch die lässt sich abschalten, dann läuft der Raum, bis jeder Bot passt
 * oder du erneut sendest. Das ist Absicht und wird in der Oberfläche als
 * solche benannt.
 */

import {
  GROUP_CHAT_HISTORY_LIMIT,
  GROUP_CHAT_MAX_CONTINUATIONS,
  GROUP_CHAT_MAX_MEMBERS,
  GROUP_CHAT_MAX_MESSAGES,
  GROUP_CHAT_MAX_ROUNDS
} from './group-chat'

/** Obergrenzen. Kein Schutz vor dir, sondern vor Tippfehlern: eine 5000 im
 *  Rundenfeld wäre kein Wunsch, sondern ein verrutschter Finger. */
export const GROUP_CHAT_LIMIT_CEILINGS = {
  rounds: 100,
  messages: 500,
  members: 24,
  history: 200
} as const

/** Wo die Sicherheitsbremse einsetzt, wenn ein Raum eine Achse abschaltet. */
export const GROUP_CHAT_SAFETY_DEFAULTS = { rounds: 50, messages: 200 } as const

export interface GroupChatLimitOverrides {
  rounds?: null | number
  messages?: null | number
  continuations?: null | number
  history?: null | number
  members?: null | number
  safetyRounds?: null | number
  safetyMessages?: null | number
}

export interface ResolvedGroupChatLimits {
  rounds: null | number
  messages: null | number
  continuations: null | number
  history: number
  members: number
  /** Greift nur, wenn rounds auf null steht. */
  safetyRounds: null | number
  /** Greift nur, wenn messages auf null steht. */
  safetyMessages: null | number
}

type MitLimits = { limits?: unknown } | null | undefined

/** Eine Achse auflösen. Bewusst streng: Number(true) ist 1 und Number([]) ist
 *  0, ein verirrter Boolean oder ein Array läse sich sonst als echte Grenze. */
function achse(
  roh: Record<string, unknown>,
  key: string,
  fallback: null | number,
  deckel: number
): null | number {
  if (!Object.prototype.hasOwnProperty.call(roh, key)) {
    return fallback
  }
  const wert = roh[key]
  if (wert === null) {
    return null
  }
  if (typeof wert !== 'number' && typeof wert !== 'string') {
    return fallback
  }
  const n = Math.floor(Number(wert))

  return Number.isFinite(n) && n > 0 ? Math.min(n, deckel) : fallback
}

/**
 * Grenzen für einen Raum auflösen. Nimmt den Raum-Datensatz, nicht den Namen,
 * damit die Funktion rein bleibt und sich ohne Store testen lässt.
 */
export function resolveGroupChatLimits(room: MitLimits): ResolvedGroupChatLimits {
  const roh =
    room && typeof room === 'object' && room.limits && typeof room.limits === 'object'
      ? (room.limits as Record<string, unknown>)
      : {}

  const C = GROUP_CHAT_LIMIT_CEILINGS
  const rounds = achse(roh, 'rounds', GROUP_CHAT_MAX_ROUNDS, C.rounds)
  const messages = achse(roh, 'messages', GROUP_CHAT_MAX_MESSAGES, C.messages)

  return {
    rounds,
    messages,
    continuations: achse(roh, 'continuations', GROUP_CHAT_MAX_CONTINUATIONS, C.rounds),
    // Verlauf und Mitglieder kennen kein "aus": ein Raum ohne Verlaufsgrenze
    // schickt irgendwann den ganzen Chat ins Modell, und ohne Mitgliedergrenze
    // bricht die Synchronisierung.
    history: achse(roh, 'history', GROUP_CHAT_HISTORY_LIMIT, C.history) ?? GROUP_CHAT_HISTORY_LIMIT,
    members: achse(roh, 'members', GROUP_CHAT_MAX_MEMBERS, C.members) ?? GROUP_CHAT_MAX_MEMBERS,
    // Bremsen zählen nur, wenn die zugehörige Achse aus ist.
    safetyRounds:
      rounds === null ? achse(roh, 'safetyRounds', GROUP_CHAT_SAFETY_DEFAULTS.rounds, C.rounds) : null,
    safetyMessages:
      messages === null
        ? achse(roh, 'safetyMessages', GROUP_CHAT_SAFETY_DEFAULTS.messages, C.messages)
        : null
  }
}

/**
 * Die tatsächlich wirksamen Deckel für die Schleife. Fasst Grenze und Bremse
 * zu je einer Zahl zusammen, damit die Schleife nur einen Wert kennen muss.
 * `null` heißt hier wirklich unbegrenzt.
 */
export function groupChatDriveCaps(room: MitLimits) {
  const l = resolveGroupChatLimits(room)

  return {
    rounds: l.rounds === null ? l.safetyRounds : l.rounds,
    messages: l.messages === null ? l.safetyMessages : l.messages,
    continuations: l.continuations,
    history: l.history,
    members: l.members
  }
}

/** Kurzform für die Oberfläche: "3 Runden · 10 Nachrichten" bzw. "unbegrenzt". */
export function groupChatBudgetLabel(room: MitLimits, texte: { runden: string; nachrichten: string; unbegrenzt: string }) {
  const c = groupChatDriveCaps(room)
  const teil = (wert: null | number, wort: string) =>
    wert === null ? `${wort}: ${texte.unbegrenzt}` : `${wert} ${wort}`

  return `${teil(c.rounds, texte.runden)} · ${teil(c.messages, texte.nachrichten)}`
}

/** Eine Achse für die Speicherung normalisieren. Gibt `undefined` zurück,
 *  wenn der Wert die Voreinstellung ist, damit ein Raum ohne Abweichung auch
 *  keinen Eintrag bekommt. */
export function normalizeGroupChatLimit(
  wert: null | number | string,
  standard: number,
  deckel: number
): null | number | undefined {
  if (wert === null) {
    return null
  }
  const n = Math.floor(Number(wert))
  if (!Number.isFinite(n) || n <= 0) {
    return undefined
  }
  const begrenzt = Math.min(n, deckel)

  return begrenzt === standard ? undefined : begrenzt
}
