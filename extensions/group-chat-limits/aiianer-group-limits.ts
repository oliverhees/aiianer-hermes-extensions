/**
 * Einstellbare Grenzen pro Gruppenchat.
 *
 * Hermes deckelt einen Gruppenchat hart: 3 Runden, 10 Nachrichten, 2
 * Fortsetzungen, 24 Verlaufszeilen. Die Zehn greift bei sechs Bots praktisch
 * immer zuerst, der Raum ist also nach knapp zwei Runden still.
 *
 * Upstream hat diese Deckel bewusst in EINEN Block gelegt (group-chat.ts:
 * "making them configurable ... is live contributor work ... both need exactly
 * one seam to hook"). Genau da haengt sich diese Datei ein. Sie ersetzt die
 * Konstanten nicht, sie loest sie pro Raum auf.
 *
 * Woher die Werte kommen: aus aiianer-group-limits.data.ts, die der Installer
 * aus ~/.hermes/aiianer/gruppen-grenzen.json erzeugt. Der Renderer kann keine
 * Dateien lesen, deshalb wird die Konfiguration beim Einspielen zu Code und
 * beim naechsten Start mitgebaut. Aenderungen brauchen also einmal
 * "Neu einspielen" und einen Neustart.
 *
 * Drei Zustaende je Achse:
 *
 *    Zahl     die Grenze, wird durchgesetzt wie vorher
 *    null     aus, diese Achse stoppt den Lauf nicht mehr
 *    fehlt    erbt die Voreinstellung von Hermes
 *
 * Steht Runden oder Nachrichten auf "aus", uebernimmt die Sicherheitsbremse.
 * Auch die laesst sich abschalten, dann laeuft der Raum, bis jeder Bot passt
 * oder du erneut sendest.
 */

import { AIIANER_GROUP_LIMITS } from './aiianer-group-limits.data'
import {
  GROUP_CHAT_HISTORY_LIMIT,
  GROUP_CHAT_MAX_CONTINUATIONS,
  GROUP_CHAT_MAX_MESSAGES,
  GROUP_CHAT_MAX_ROUNDS
} from './group-chat'

/** Obergrenzen. Kein Schutz vor dir, sondern vor Tippfehlern: eine 5000 im
 *  Rundenfeld waere kein Wunsch, sondern ein verrutschter Finger. */
export const GROUP_CHAT_LIMIT_CEILINGS = {
  rounds: 100,
  messages: 500,
  continuations: 100,
  history: 200
} as const

/** Wo die Sicherheitsbremse einsetzt, wenn ein Raum eine Achse abschaltet. */
export const GROUP_CHAT_SAFETY_DEFAULTS = { rounds: 50, messages: 200 } as const

export interface GroupChatLimitOverrides {
  rounds?: null | number
  messages?: null | number
  continuations?: null | number
  history?: number
  safetyRounds?: null | number
  safetyMessages?: null | number
}

export interface GroupChatCaps {
  /** Infinity heisst unbegrenzt. Die Schleife muss so keinen Sonderfall kennen. */
  rounds: number
  messages: number
  continuations: number
  /** Immer endlich: ein Raum ohne Verlaufsgrenze schickt irgendwann den
   *  ganzen Chat ins Modell. */
  history: number
}

/** Eine Achse aufloesen. Bewusst streng: Number(true) ist 1 und Number([]) ist
 *  0, ein verirrter Boolean oder ein Array laese sich sonst als echte Grenze. */
function achse(
  roh: Record<string, unknown>,
  key: string,
  fallback: number,
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
 * Die wirksamen Deckel fuer einen Raum. Fasst Grenze und Bremse zu je einer
 * Zahl zusammen, damit die Schleife nur einen Wert kennen muss.
 *
 * Faellt bei jedem Zweifel auf Hermes' Voreinstellungen zurueck. Eine kaputte
 * Konfiguration darf einen Gruppenchat nicht endlos laufen lassen.
 */
export function aiianerCaps(group: string): GroupChatCaps {
  const alle = AIIANER_GROUP_LIMITS as Record<string, unknown>
  const roheingabe =
    (alle && typeof alle === 'object' ? alle[group] ?? alle['*'] : null) ?? {}
  const roh = typeof roheingabe === 'object' && roheingabe ? (roheingabe as Record<string, unknown>) : {}

  const C = GROUP_CHAT_LIMIT_CEILINGS
  const rounds = achse(roh, 'rounds', GROUP_CHAT_MAX_ROUNDS, C.rounds)
  const messages = achse(roh, 'messages', GROUP_CHAT_MAX_MESSAGES, C.messages)

  // Bremsen zaehlen nur, wenn die zugehoerige Achse aus ist. Steht auch die
  // Bremse auf null, ist der Raum wirklich unbegrenzt.
  const bremseRunden =
    rounds === null ? achse(roh, 'safetyRounds', GROUP_CHAT_SAFETY_DEFAULTS.rounds, C.rounds) : null
  const bremseNachrichten =
    messages === null
      ? achse(roh, 'safetyMessages', GROUP_CHAT_SAFETY_DEFAULTS.messages, C.messages)
      : null

  const zahl = (grenze: null | number, bremse: null | number) => {
    if (grenze !== null) {
      return grenze
    }

    return bremse === null ? Number.POSITIVE_INFINITY : bremse
  }

  return {
    rounds: zahl(rounds, bremseRunden),
    messages: zahl(messages, bremseNachrichten),
    continuations: zahl(
      achse(roh, 'continuations', GROUP_CHAT_MAX_CONTINUATIONS, C.continuations),
      null
    ),
    history: achse(roh, 'history', GROUP_CHAT_HISTORY_LIMIT, C.history) ?? GROUP_CHAT_HISTORY_LIMIT
  }
}
