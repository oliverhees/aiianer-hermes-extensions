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

// Keine ESM-Imports: Hermes setzt diese Namespaces vor dem Plugin-Import als
// Runtime-Globals. So muss der Loader weder React noch das SDK in Blob-Shims
// umschreiben — genau dort entstand der Fehler "Unexpected token ']'".
const ReactModule = globalThis.__HERMES_REACT__
const React = ReactModule.default ?? ReactModule
const { useEffect, useState } = ReactModule

const jsx = (type, props = {}, key) => React.createElement(type, { ...props, key })
const jsxs = jsx

const {
  Badge,
  cn,
  EmptyState,
  ErrorState,
  host,
  Skeleton,
  useQuery,
  usePluginI18n
} = globalThis.__HERMES_PLUGIN_SDK__

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

// -- AIIANER-Community-Banner -------------------------------------------------
function MarketplaceHero({ updates, installiert, total, onCommunity }) {
  return jsxs('section', {
    className: 'relative overflow-hidden rounded-xl border border-accent/35 bg-gradient-to-r from-accent/20 via-background to-background px-4 py-3 sm:px-5',
    children: [
      jsx('div', { className: 'pointer-events-none absolute inset-y-0 left-0 w-1 bg-accent' }, 'accent'),
      jsxs('div', { className: 'relative flex flex-wrap items-center justify-between gap-x-5 gap-y-3', children: [
        jsxs('div', { className: 'min-w-0', children: [
          jsxs('div', { className: 'flex flex-wrap items-center gap-x-3 gap-y-1', children: [
            jsx('span', { className: 'font-mono text-[10px] uppercase tracking-[0.22em] text-accent', children: 'AIIANER COMMUNITY' }, 'brand'),
            jsx('span', { className: 'hidden text-[10px] opacity-45 sm:inline', children: 'KI zum Anwenden, nicht zum Hypen.' }, 'tagline')
          ] }),
          jsxs('p', { className: 'mt-1 max-w-2xl text-xs leading-5 opacity-70', children: [
            'Kurse, Vorlagen, Live-Calls und Austausch für Menschen, die KI wirklich einsetzen. ',
            'AIIANER nutzt Hermes als Basis des KI-Betriebssystems und baut darauf Plugins, MCPs und Werkzeuge für den Alltag.'
          ] }, 'copy')
        ] }),
        jsxs('div', { className: 'flex shrink-0 items-center gap-3', children: [
          jsxs('span', { className: 'hidden font-mono text-[9px] uppercase tracking-[0.12em] opacity-55 lg:inline', children: [
            `${total} Komponenten`, ' · ', `${installiert} aktiv`, updates ? ` · ${updates} Update${updates === 1 ? '' : 's'}` : ''
          ] }, 'stats'),
          jsxs('div', { className: 'flex flex-col items-stretch gap-1', children: [
            jsx('a', { href: 'https://aiianer.de', target: '_blank', rel: 'noreferrer', onClick: onCommunity, className: 'rounded-md border border-accent bg-accent px-3 py-2 text-xs font-semibold text-accent-foreground transition hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-accent', children: 'Community öffnen ↗' }, 'cta'),
            jsx('span', { className: 'max-w-44 text-[10px] leading-4 opacity-60', children: 'Rechtsklick auf den Button und „Link im externen Browser öffnen“ wählen.' }, 'open-help')
          ] }, 'cta-wrap')
        ] })
      ] }, 'content')
    ]
  })
}

// -- Release Notes ------------------------------------------------------------
function ReleaseNotes() {
  return jsxs('section', {
    className: 'rounded-xl border border-white/10 bg-black/10 p-4 sm:p-5 space-y-5',
    children: [
      jsxs('div', {
        children: [
          jsx('p', { className: 'text-xs uppercase tracking-widest text-accent', children: 'Release Notes' }, 'eyebrow'),
          jsx('h2', { className: 'mt-1 text-xl font-semibold', children: 'AIIANER Hub v1.3.3' }, 'title'),
          jsx('p', { className: 'mt-1 text-sm opacity-65', children: 'Die Änderungen dieser Version auf einen Blick.' }, 'intro')
        ]
      }, 'heading'),
      jsxs('div', {
        className: 'space-y-4 text-sm',
        children: [
          jsxs('div', { children: [
            jsx('p', { className: 'font-medium', children: 'Community-Link' }, 'title'),
            jsx('p', { className: 'mt-1 opacity-70', children: 'Der Community-Link ist jetzt korrekt mit Hermes verdrahtet. Falls der normale Klick nicht öffnet, erklärt der Hinweis direkt am Button den Weg über das Rechtsklick-Menü.' }, 'copy')
          ] }, 'community'),
          jsxs('div', { children: [
            jsx('p', { className: 'font-medium', children: 'Theme-Anpassung' }, 'title'),
            jsx('p', { className: 'mt-1 opacity-70', children: 'Button, Statusanzeigen, Update-Hinweise und Akzentflächen verwenden die aktiven Hermes-Theme-Farben.' }, 'copy')
          ] }, 'theme'),
          jsxs('div', { children: [
            jsx('p', { className: 'font-medium', children: 'Hermes als Basis' }, 'title'),
            jsx('p', { className: 'mt-1 opacity-70', children: 'Der Header erklärt jetzt, dass AIIANER Hermes als Basis des KI-Betriebssystems nutzt und darauf Plugins, MCPs und Werkzeuge aufbaut.' }, 'copy')
          ] }, 'hermes')
        ]
      }, 'notes')
    ]
  })
}

// -- Oberflaeche --------------------------------------------------------------
function makePane(useCatalog, aktionen, onCommunity) {
  return function Pane() {
    const t = usePluginI18n(ID)
    const { data, isLoading, isFetching, error, refetch } = useCatalog()

    // laufend[id] = 'install' | 'uninstall'; ergebnis[id] = Antwort oder Fehler.
    // Ohne den laufend-Zustand wirkt der Klick stumm, bis der Refetch kommt -
    // genau das war die Beschwerde.
    const [laufend, setLaufend] = useState({})
    const [ergebnis, setErgebnis] = useState({})
    const [aktiverTab, setAktiverTab] = useState('marketplace')

    useEffect(() => {
      const anzahl = (data?.components || []).filter(c => c.status === 'outdated').length

      if (anzahl) {
        host.notify({
          kind: 'warning',
          title: 'Updates verfügbar',
          message: `${anzahl} ${anzahl === 1 ? 'Erweiterung wartet' : 'Erweiterungen warten'} auf ein Update.`
        })
      }
    }, [data])

    const updatesPruefen = () => {
      void refetch().catch(error => {
        host.notifyError(error)
      })
    }

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
          'min-h-9 rounded-lg px-3 py-2 text-xs font-medium border transition-all',
          opts.aus ? 'opacity-50 cursor-not-allowed' : 'hover:bg-accent hover:-translate-y-px',
          opts.betont ? 'border-accent/70 bg-accent/15 text-accent shadow-sm shadow-accent/20' : 'border-white/15 bg-white/5'
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
        reihe.push(knopf('unavailable', t('unavailableAction'), { aus: true }))
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
        if (!c.selfManaged) {
          reihe.push(knopf('deinst', t('uninstall'), { aus: gesperrt, onClick: () => ausfuehren(c.id, 'uninstall') }))
        }
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
        className: cn(
          'group rounded-xl border border-white/10 bg-black/10 p-4 sm:p-5 space-y-3 shadow-sm transition-colors',
          'hover:border-accent/35 hover:bg-accent/10'
        ),
        children: [
          kopf,
          jsx('p', { className: 'text-xs opacity-70', children: c.summary }, 'd'),
          c.note ? jsx('p', { className: 'text-xs opacity-50', children: c.note }, 'note') : null,
          jsxs('div', { className: 'flex items-center gap-2 flex-wrap border-t border-white/10 pt-3 mt-3', children: reihe }, 'row'),
          ...hinweis
        ]
      }, c.id)
    })

    const installiert = items.filter(c => c.installed).length
    const updates = items.filter(c => c.status === 'outdated').length

    return jsxs('div', {
      className: 'p-4 sm:p-6 lg:p-8 space-y-6 max-w-6xl',
      children: [
        jsx(MarketplaceHero, {
          updates,
          installiert,
          total: items.length,
          onCommunity,
        }, 'community-hero'),
        jsxs('div', {
          className: 'flex gap-2 border-b border-white/10',
          children: [
            jsx('button', {
              className: aktiverTab === 'marketplace' ? 'border-b-2 border-accent px-3 py-2 text-xs font-medium text-accent' : 'px-3 py-2 text-xs opacity-60 hover:opacity-100',
              onClick: () => setAktiverTab('marketplace'),
              children: 'Marktplatz'
            }, 'marketplace-tab'),
            jsx('button', {
              className: aktiverTab === 'release-notes' ? 'border-b-2 border-accent px-3 py-2 text-xs font-medium text-accent' : 'px-3 py-2 text-xs opacity-60 hover:opacity-100',
              onClick: () => setAktiverTab('release-notes'),
              children: 'Release Notes'
            }, 'release-tab')
          ]
        }, 'tabs'),
        aktiverTab === 'release-notes' ? jsx(ReleaseNotes, {}, 'release-notes') : jsxs('div', {
          className: 'space-y-4',
          children: [
            jsx('button', {
              className: 'justify-self-start rounded-md border border-accent/60 bg-accent/10 px-3 py-2 text-xs font-medium text-accent transition hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50',
              disabled: isFetching,
              onClick: updatesPruefen,
              children: isFetching ? 'Prüfe Updates ...' : 'Updates prüfen'
            }, 'check-updates'),
            jsxs('div', {
              children: [
                jsx('p', { className: 'text-xs uppercase tracking-widest text-accent', children: 'Dein Marktplatz' }, 'eyebrow'),
                jsx('h2', { className: 'mt-1 text-xl font-semibold', children: t('title') }, 'title'),
                jsx('p', { className: 'text-sm opacity-65 mt-1', children: 'Installieren, aktuell halten und nach Hermes-Updates entspannt bleiben.' }, 'copy')
              ]
            }, 'heading'),
            jsxs('div', {
              className: 'flex gap-2 text-xs opacity-70',
              children: [
                jsx(Badge, { children: `${items.length} Komponenten` }, 'count'),
                jsx(Badge, { children: `${installiert} installiert` }, 'installed'),
                updates ? jsx(Badge, { children: `${updates} Update${updates === 1 ? '' : 's'}` }, 'updates') : null
              ]
            }, 'stats'),
            updates ? jsxs('section', {
              className: 'rounded-2xl border border-accent/30 bg-accent/10 p-4 sm:p-5',
              children: [
                jsx('p', { className: 'text-xs uppercase tracking-widest text-accent', children: 'Updates im Außenposten' }, 'eyebrow'),
                jsx('p', { className: 'mt-1 text-sm font-medium', children: updates === 1 ? 'Eine Erweiterung wartet auf ihr Update.' : `${updates} Erweiterungen warten auf ihr Update.` }, 'title'),
                jsx('p', { className: 'mt-1 text-xs opacity-70', children: 'Öffne die jeweilige Karte und aktualisiere sie mit einem Klick. Danach Hermes neu starten, wenn es angezeigt wird.' }, 'copy')
              ]
            }, 'updates-panel') : null,
            jsx('p', { className: 'text-sm opacity-70', children: t('intro') }, 'intro'),
            ...karten
          ]
        }, 'marketplace-content')
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
        unavailableAction: 'Not available on this system',
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
        warnTitle: 'Diese Reste ließen sich nicht entfernen:',
        failTitle: 'Das hat nicht geklappt:',
        afterwards: 'Danach nötig:',
        empty: 'Der Katalog ist leer',
        errTitle: 'Katalog konnte nicht geladen werden',
        status: { current: 'aktuell', outdated: 'Update verfügbar', missing: 'nicht installiert', unavailable: 'zurzeit nicht möglich' },
        unavailTitle: 'Lässt sich gerade nicht installieren:',
        unavailableAction: 'Auf diesem System nicht verfügbar',
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
    const onCommunity = event => {
      event.preventDefault()
      void ctx.os.openExternal('https://aiianer.de')
    }
    const Pane = makePane(useCatalog, aktionen, onCommunity)

    // Eigene Seite
    ctx.register({
      id: 'aiianer-route',
      title: 'AIIANER Erweiterungen',
      area: 'routes',
      data: { path: '/aiianer' },
      render: Pane
    })

    // Eintrag in der Seitenleiste, der die Seite oeffnet
    ctx.register({
      id: 'aiianer-nav',
      area: 'sidebar.nav',
      order: 60,
      data: { codicon: 'package', label: 'AIIANER Hub', path: '/aiianer' }
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
