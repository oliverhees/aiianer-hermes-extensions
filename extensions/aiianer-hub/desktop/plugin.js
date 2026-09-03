/**
 * AIIANER Marktplatz - Desktop-Fassung.
 *
 * Gleiche Aufgabe wie die Web-Fassung unter dashboard/dist/index.js, nur fuer
 * die Electron-App. Beide sprechen dasselbe Python-Backend an:
 *   ~/.hermes/plugins/aiianer-hub/dashboard/plugin_api.py
 * Im Desktop laeuft das ueber ctx.rest(), das automatisch auf
 * /api/plugins/aiianer-hub/ zeigt.
 *
 * Reines ESM, wird uncompiliert geladen. Oberflaeche ueber jsx()-Aufrufe,
 * keine JSX-Syntax. Vorbild: das mitgelieferte cron-costs.
 */

// jsx kommt aus React selbst, NICHT aus dem Plugin-SDK. Das mitgelieferte
// cron-costs macht es genauso. Ein Import von 'jsx' aus @hermes/plugin-sdk
// laesst das Plugin beim Laden mit "does not provide an export named 'jsx'"
// scheitern.
import { useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

import {
  Badge,
  cn,
  EmptyState,
  ErrorState,
  host,
  Skeleton,
  useQuery,
  usePluginI18n
} from '@hermes/plugin-sdk'

const ID = 'aiianer-hub'

// -- Daten --------------------------------------------------------------------

function makeUseCatalog(fetchCatalog) {
  return function useCatalog() {
    return useQuery({
      queryKey: [ID, 'catalog'],
      queryFn: fetchCatalog,
      staleTime: 30000
    })
  }
}

// -- Oberflaeche --------------------------------------------------------------

function makePane(useCatalog, aktionen) {
  return function Pane() {
    const t = usePluginI18n(ID)
    const { data, isLoading, error, refetch } = useCatalog()

    // laufend[id] = 'install' | 'uninstall'; ergebnis[id] = Antwort oder Fehler.
    // Ohne den laufend-Zustand wirkt der Klick stumm, bis der Refetch kommt -
    // genau das war die Beschwerde.
    const [laufend, setLaufend] = useState({})
    const [ergebnis, setErgebnis] = useState({})

    const ausfuehren = (id, aktion) => {
      setLaufend(v => ({ ...v, [id]: aktion }))
      setErgebnis(v => ({ ...v, [id]: null }))
      aktionen[aktion](id)
        .then(
          antwort => {
            setErgebnis(v => ({ ...v, [id]: { ok: true, ...antwort } }))
            // Der Refetch haengt BEWUSST in einer eigenen Kette. Steckte er im
            // selben .then, landete sein Fehler im .catch unten und wuerde eine
            // geglueckte Installation als Fehlschlag anzeigen - samt Verlust
            // der Schritte, die der Nutzer danach braucht. Genau dann ist das
            // wahrscheinlich, wenn das Gateway gerade neu startet.
            return refetch().catch(() => {})
          },
          err => {
            const text = err && err.message ? err.message : String(err)
            setErgebnis(v => ({ ...v, [id]: { ok: false, message: text } }))
          }
        )
        .finally(() => setLaufend(v => ({ ...v, [id]: null })))
    }

    if (isLoading) return jsx(Skeleton, { className: 'h-24 m-3' })
    if (error) {
      return jsx(ErrorState, {
        title: t('errTitle'),
        description: String(error && error.message ? error.message : error)
      })
    }

    const items = (data && data.components) || []
    if (!items.length) return jsx(EmptyState, { title: t('empty') })

    const knopf = (schluessel, beschriftung, opts) =>
      jsx('button', {
        className: cn(
          'text-xs rounded px-2 py-1 border transition-opacity',
          opts.aus ? 'opacity-50 cursor-not-allowed' : 'hover:bg-accent',
          opts.betont ? 'border-red-500/60' : ''
        ),
        disabled: opts.aus,
        onClick: opts.onClick,
        children: beschriftung
      }, schluessel)

    const karten = items.map(c => {
      const aktiv = laufend[c.id]
      const res = ergebnis[c.id]
      const gesperrt = Boolean(aktiv)

      const kopf = jsxs('div', {
        className: 'flex items-center gap-2 flex-wrap',
        children: [
          jsx('span', { className: 'font-medium text-sm', children: c.name }, 'n'),
          jsx(Badge, { children: 'v' + c.version }, 'v'),
          jsx(Badge, { children: c.available === false ? t('status.unavailable') : t('status.' + c.status) }, 's'),
          c.installed && c.installed !== c.version
            ? jsx('span', {
                className: 'text-xs opacity-60',
                children: t('installedIs', c.installed)
              }, 'iv')
            : null
        ]
      }, 'h')

      // Knopfreihe: was moeglich ist, haengt am Status - und zuerst daran,
      // ob die Komponente auf diesem Rechner ueberhaupt installierbar ist.
      // Ein Knopf, der zuverlaessig in einen Fehler laeuft, ist schlimmer als
      // gar kein Knopf.
      const reihe = []
      if (c.available === false) {
        // kein Knopf, die Begruendung steht unten
      } else if (aktiv) {
        reihe.push(knopf('busy', aktiv === 'uninstall' ? t('uninstalling') : t('installing'), { aus: true }))
      } else if (c.status === 'missing') {
        reihe.push(knopf('inst', t('install'), { aus: gesperrt, onClick: () => ausfuehren(c.id, 'install') }))
      } else {
        if (c.status === 'outdated') {
          reihe.push(knopf('upd', t('updateTo', c.version), {
            aus: gesperrt, betont: true, onClick: () => ausfuehren(c.id, 'install')
          }))
        }
        reihe.push(knopf('rein', t('reinstall'), { aus: gesperrt, onClick: () => ausfuehren(c.id, 'install') }))
        reihe.push(knopf('deinst', t('uninstall'), { aus: gesperrt, onClick: () => ausfuehren(c.id, 'uninstall') }))
      }

      // Was jetzt zu tun ist. Vor dem Klick als leiser Hinweis, nach dem
      // Klick als hervorgehobener Kasten - der Nutzer erwartet sonst, dass
      // Deutsch sofort da ist.
      // Bei einer Komponente, die sich nicht installieren laesst, gibt es kein
      // "Danach" - der Vorab-Hinweis waere dort schlicht falsch.
      const schritte = res && res.ok
        ? (res.nextSteps || [])
        : (aktiv || c.available === false
            ? []
            : (c.status === 'missing' ? (c.nextSteps || []) : []))

      const hinweis = []
      if (c.available === false) {
        hinweis.push(jsxs('div', {
          className: 'rounded border border-neutral-600/60 bg-neutral-900/40 p-2 space-y-1',
          children: [
            jsx('p', { className: 'text-xs font-medium', children: t('unavailTitle') }, 'ut'),
            jsx('p', {
              className: 'text-xs opacity-70',
              // Das Backend liefert beide Sprachen. t('lang') sagt, welche die
              // App gerade spricht - sonst stuende ein deutscher Absatz unter
              // einer englischen Ueberschrift.
              children: (t('lang') === 'en' && c.unavailableReasonEn) || c.unavailableReason
            }, 'ur')
          ]
        }, 'unavail'))
      }
      // Liegengebliebene Reste zuerst, und in Gelb: sie sind weder Erfolg
      // noch Fehlschlag, aber der Nutzer muss sie sehen. Ohne diesen Zweig
      // waere das Feld warnings totes Gewicht in der Antwort.
      if (res && res.ok && (res.warnings || []).length) {
        hinweis.push(jsxs('div', {
          className: 'rounded border border-amber-600/60 bg-amber-950/20 p-2 space-y-1',
          children: [
            jsx('p', { className: 'text-xs font-medium', children: t('warnTitle') }, 'wt'),
            jsxs('ul', {
              className: 'text-xs opacity-80 list-disc pl-4 space-y-0.5',
              children: res.warnings.map((z, i) => jsx('li', { children: z }, 'w' + i))
            }, 'ul')
          ]
        }, 'warn'))
      }
      if (res && res.ok && !schritte.length) {
        // Ohne diesen Zweig faellt eine erfolgreiche Aktion ohne hinterlegte
        // Schritte durch alle Faelle: der Knopf wird wieder normal und
        // sichtbar passiert gar nichts.
        hinweis.push(jsx('p', {
          className: 'text-xs text-emerald-400',
          children: t('doneBare')
        }, 'okbare'))
      } else if (res && res.ok && schritte.length) {
        hinweis.push(jsxs('div', {
          className: 'rounded border border-emerald-600/50 bg-emerald-950/20 p-2 space-y-1',
          children: [
            jsx('p', { className: 'text-xs font-medium', children: t('doneTitle') }, 'dt'),
            jsxs('ol', {
              className: 'text-xs opacity-80 list-decimal pl-4 space-y-0.5',
              children: schritte.map((z, i) => jsx('li', { children: z }, 'z' + i))
            }, 'ol')
          ]
        }, 'ok'))
      } else if (res && !res.ok) {
        hinweis.push(jsxs('div', {
          className: 'rounded border border-red-600/60 bg-red-950/20 p-2 space-y-1',
          children: [
            jsx('p', { className: 'text-xs font-medium', children: t('failTitle') }, 'ft'),
            jsx('p', { className: 'text-xs opacity-80 whitespace-pre-wrap', children: res.message }, 'fm')
          ]
        }, 'err'))
      } else if (schritte.length) {
        hinweis.push(jsx('p', {
          className: 'text-xs opacity-50',
          children: t('afterwards') + ' ' + schritte[0]
        }, 'vor'))
      }

      return jsxs('div', {
        className: cn('rounded-md border p-3 space-y-2'),
        children: [
          kopf,
          jsx('p', { className: 'text-xs opacity-70', children: c.summary }, 'd'),
          c.note ? jsx('p', { className: 'text-xs opacity-50', children: c.note }, 'note') : null,
          jsxs('div', { className: 'flex items-center gap-2 flex-wrap', children: reihe }, 'row'),
          ...hinweis
        ]
      }, c.id)
    })

    return jsxs('div', {
      className: 'p-3 space-y-3',
      children: [
        jsx('p', { className: 'text-xs opacity-70', children: t('intro') }, 'intro'),
        ...karten
      ]
    })
  }
}

// -- Plugin -------------------------------------------------------------------

export default {
  id: ID,
  name: 'AIIANER',
  register(ctx) {
    ctx.i18n.register({
      en: {
        title: 'AIIANER Extensions',
        intro: 'German language and the AIIANER tools. What you install here survives Hermes updates.',
        install: 'Install',
        reinstall: 'Reinstall',
        uninstall: 'Uninstall',
        updateTo: v => `Update to v${v}`,
        installedIs: v => `installed: v${v}`,
        installing: 'Installing, please wait...',
        uninstalling: 'Removing...',
        doneTitle: 'Done. What to do next:',
        doneBare: 'Done. Restart Hermes to apply it.',
        warnTitle: 'Some leftovers could not be removed:',
        failTitle: 'That did not work:',
        afterwards: 'Afterwards:',
        empty: 'Catalog is empty',
        errTitle: 'Could not load the catalog',
        // Geschachtelt, NICHT flach mit Punkt im Schluessel: resolvePath in
        // i18n/runtime.ts laeuft den Punktpfad durch einen verschachtelten
        // Baum. Ein flacher Schluessel 'status.missing' wird nie gefunden und
        // translateFrom gibt dann den Schluessel selbst zurueck - im Badge
        // stand woertlich "status.missing".
        status: { current: 'current', outdated: 'update available', missing: 'not installed', unavailable: 'not available' },
        unavailTitle: 'Cannot be installed right now:',
        lang: 'en'
      },
      de: {
        title: 'AIIANER Erweiterungen',
        intro: 'Deutsche Sprache und die AIIANER-Werkzeuge. Was du hier installierst, überlebt Hermes-Updates.',
        install: 'Installieren',
        reinstall: 'Neu einspielen',
        uninstall: 'Deinstallieren',
        updateTo: v => `Auf v${v} aktualisieren`,
        installedIs: v => `installiert: v${v}`,
        installing: 'Wird installiert, einen Moment ...',
        uninstalling: 'Wird entfernt ...',
        doneTitle: 'Fertig. Das ist jetzt zu tun:',
        doneBare: 'Fertig. Hermes neu starten, damit es greift.',
        warnTitle: 'Diese Reste liessen sich nicht entfernen:',
        failTitle: 'Das hat nicht geklappt:',
        afterwards: 'Danach nötig:',
        empty: 'Der Katalog ist leer',
        errTitle: 'Katalog konnte nicht geladen werden',
        status: { current: 'aktuell', outdated: 'Update verfügbar', missing: 'nicht installiert', unavailable: 'zurzeit nicht möglich' },
        unavailTitle: 'Lässt sich gerade nicht installieren:',
        lang: 'de'
      }
    })

    const fetchCatalog = () => ctx.rest('/catalog')
    // PluginRestOptions kennt method/body/upload/timeoutMs. KEIN headers, und
    // body ist ein Objekt - die Bruecke serialisiert selbst. Ein
    // JSON.stringify hier wuerde dem Backend einen String statt eines
    // Objekts schicken.
    const aktionen = {
      install: id => ctx.rest('/install', { method: 'POST', body: { id } }),
      uninstall: id => ctx.rest('/uninstall', { method: 'POST', body: { id } })
    }

    const useCatalog = makeUseCatalog(fetchCatalog)
    const Pane = makePane(useCatalog, aktionen)

    // Eigene Seite
    ctx.register({
      id: 'aiianer-route',
      title: 'AIIANER Erweiterungen',
      area: 'routes',
      data: { path: '/aiianer' },
      render: () => jsx(Pane, {})
    })

    // Eintrag in der Seitenleiste, der die Seite oeffnet
    ctx.register({
      id: 'aiianer-nav',
      area: 'sidebar.nav',
      order: 60,
      data: { codicon: 'package', label: 'AIIANER', path: '/aiianer' }
    })

    // Ueber die Befehlspalette erreichbar
    ctx.register({
      id: 'aiianer-open',
      area: 'palette',
      data: {
        id: 'aiianer.open',
        label: 'AIIANER: Erweiterungen oeffnen',
        keywords: ['aiianer', 'marktplatz', 'deutsch', 'erweiterungen'],
        run: () => host.navigate('/aiianer')
      }
    })
  }
}
