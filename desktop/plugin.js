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

import * as ReactModule from 'react'
import * as HermesSdk from '@hermes/plugin-sdk'

const React = ReactModule.default ?? ReactModule
const { useEffect, useState } = ReactModule

const jsx = (type, props = {}, key) => React.createElement(type, { ...props, key })
const jsxs = jsx

const { host } = HermesSdk
const cn = (...values) => values.filter(Boolean).join(' ')

const ID = 'aiianer-hub'

// -- Daten --------------------------------------------------------------------

function useHubData(fetchCatalog, fetchReleases, fetchRoadmap) {
  const [state, setState] = useState({
    catalog: null,
    releases: null,
    roadmap: null,
    isLoading: true,
    isFetching: false,
    error: null
  })
  const load = () => {
    setState(previous => ({ ...previous, isFetching: true, error: null }))
    return Promise.all([fetchCatalog(), fetchReleases(), fetchRoadmap()])
      .then(([catalog, releases, roadmap]) => {
        setState({ catalog, releases, roadmap, isLoading: false, isFetching: false, error: null })
        return { data: catalog, releases, roadmap }
      })
      .catch(error => {
        setState(previous => ({ ...previous, isLoading: false, isFetching: false, error }))
        throw error
      })
  }
  useEffect(() => { void load() }, [])
  return {
    data: state.catalog,
    releaseDaten: state.releases,
    roadmapDaten: state.roadmap,
    isLoading: state.isLoading,
    isFetching: state.isFetching,
    error: state.error,
    releasesLaden: state.isLoading,
    roadmapLaden: state.isLoading,
    releasesFehler: state.error,
    roadmapFehler: state.error,
    refetch: load
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
          jsxs('div', { className: 'flex items-center gap-2', children: [
            jsx('h1', { className: 'text-xl font-bold tracking-tight text-foreground sm:text-2xl', children: 'AIIANER COMMUNITY' }, 'brand'),
            jsx('span', { className: 'rounded border border-amber-300/70 bg-amber-400/15 px-2 py-0.5 text-[10px] font-bold tracking-wider text-amber-200', children: '🚧 BETA' }, 'beta')
          ] }, 'brand-row'),
          jsxs('div', { className: 'mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1', children: [
            jsx('span', { className: 'font-mono text-[10px] uppercase tracking-[0.22em] text-accent', children: 'KI zum Anwenden, nicht zum Hypen.' }, 'tagline'),
            jsx('span', { className: 'hidden text-[10px] opacity-45 sm:inline', children: 'Dein Außenposten für KI, die arbeitet.' }, 'subline')
          ] }),
          jsxs('p', { className: 'mt-2 max-w-2xl text-xs leading-5 opacity-70', children: [
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
            jsx('span', { className: 'max-w-44 text-[10px] leading-4 opacity-60', children: 'Rechtsklick auf den Button und „Link im externen Browser öffnen“ wählen.' }, 'open-help'),
            jsx('span', { className: 'max-w-44 text-[10px] leading-4 opacity-60', children: 'EUrouter.ai · Affiliate-Link' }, 'affiliate'),
            jsx('a', { href: 'https://www.eurouter.ai?ref=06ZUHPBK', target: '_blank', rel: 'noreferrer', className: 'text-[10px] text-accent hover:underline', children: 'EUrouter.ai ansehen ↗' }, 'affiliate-link'),
          ] }, 'cta-wrap')
        ] })
      ] }, 'content')
    ]
  })
}

// -- Versionshinweise ---------------------------------------------------------
function Versionshinweise({ daten, laedt, fehler }) {
  const releases = (daten && daten.releases) || []
  const quelle = daten && daten.source === 'github' ? 'GitHub-Releases' : 'lokaler Rückfall'
  const datum = wert => {
    if (!wert) return ''
    const parsed = new Date(wert)
    return Number.isNaN(parsed.getTime()) ? '' : new Intl.DateTimeFormat('de-DE', { dateStyle: 'medium' }).format(parsed)
  }

  return jsxs('section', {
    className: 'rounded-xl border border-white/10 bg-black/10 p-4 sm:p-5 space-y-5',
    children: [
      jsxs('div', {
        children: [
          jsx('p', { className: 'text-xs uppercase tracking-widest text-accent', children: 'Versionshinweise' }, 'eyebrow'),
          jsx('h2', { className: 'mt-1 text-xl font-semibold', children: 'Was sich im Außenposten geändert hat' }, 'title'),
          jsx('p', { className: 'mt-1 text-sm opacity-65', children: `Versionierte Hinweise aus ${quelle}.` }, 'intro')
        ]
      }, 'heading'),
      laedt ? jsx('div', { className: 'h-24 animate-pulse rounded-lg bg-white/10' }, 'loading') : null,
      !laedt && fehler ? jsx('p', { className: 'text-sm text-red-300', children: 'Versionshinweise konnten nicht geladen werden.' }, 'error') : null,
      !laedt && !fehler && !releases.length ? jsx('p', { className: 'text-sm opacity-65', children: 'Noch keine veröffentlichten Versionshinweise vorhanden.' }, 'empty') : null,
      !laedt && !fehler && releases.map(release => jsxs('article', {
        className: 'border-t border-white/10 pt-4 first:border-t-0 first:pt-0',
        children: [
          jsxs('div', { className: 'flex flex-wrap items-center gap-2', children: [
            jsx('span', { className: 'rounded border border-accent/40 px-2 py-0.5 text-xs', children: release.tagName }, 'tag'),
            datum(release.publishedAt) ? jsx('span', { className: 'text-xs opacity-50', children: datum(release.publishedAt) }, 'date') : null
          ] }, 'meta'),
          jsx('h3', { className: 'mt-2 text-base font-semibold', children: release.name || release.tagName }, 'name'),
          jsx('p', { className: 'mt-2 whitespace-pre-wrap text-sm leading-6 opacity-75', children: release.body || 'Keine zusätzlichen Hinweise zu dieser Version.' }, 'body'),
          release.url ? jsx('a', { href: release.url, target: '_blank', rel: 'noreferrer', className: 'mt-3 inline-block text-xs font-medium text-accent hover:underline', children: 'Auf GitHub ansehen ↗' }, 'link') : null
        ]
      }, release.tagName))
    ]
  })
}

function Roadmap({ daten, laedt, fehler }) {
  const items = (daten && daten.items) || []
  const quelle = daten && daten.source === 'github' ? 'GitHub' : 'lokalen Rückfall'
  return jsxs('section', { className: 'rounded-xl border border-white/10 bg-black/10 p-4 sm:p-5 space-y-4', children: [
    jsxs('div', { children: [
      jsx('p', { className: 'text-xs uppercase tracking-widest text-accent', children: 'Roadmap' }, 'eyebrow'),
      jsx('h2', { className: 'mt-1 text-xl font-semibold', children: 'Was als Nächstes andockt' }, 'title'),
      jsx('p', { className: 'mt-1 text-sm opacity-65', children: `Geplante Erweiterungen aus ${quelle}.` }, 'intro')
    ] }, 'heading'),
    laedt ? jsx('div', { className: 'h-24 animate-pulse rounded-lg bg-white/10' }, 'loading') : null,
    !laedt && fehler ? jsx('p', { className: 'text-sm text-red-300', children: 'Roadmap konnte nicht geladen werden.' }, 'error') : null,
    !laedt && !fehler && items.map(item => jsxs('article', { className: 'rounded-lg border border-white/10 p-3', children: [
      jsxs('div', { className: 'flex flex-wrap items-center justify-between gap-2', children: [jsx('h3', { className: 'font-semibold', children: item.name }, 'name'), jsx('span', { className: 'rounded border border-accent/40 px-2 py-0.5 text-xs', children: item.status }, 'status')] }, 'meta'),
      jsx('p', { className: 'mt-2 text-sm leading-6 opacity-75', children: item.summary }, 'summary'),
      item.value ? jsx('p', { className: 'mt-1 text-xs leading-5 opacity-60', children: item.value }, 'value') : null,
      item.link ? jsx('a', { href: item.link, target: '_blank', rel: 'noreferrer', className: 'mt-2 inline-block text-xs text-accent hover:underline', children: 'Mehr dazu auf GitHub ↗' }, 'link') : null
    ] }, item.id)),
    !laedt && !fehler && !items.length ? jsx('p', { className: 'text-sm opacity-65', children: 'Noch keine Roadmap-Einträge vorhanden.' }, 'empty') : null
  ] })
}

// -- Oberflaeche --------------------------------------------------------------
function makePane(fetchCatalog, fetchReleases, fetchRoadmap, aktionen, onCommunity, translate) {
  return function Pane() {
    const t = translate
    const {
      data,
      releaseDaten,
      roadmapDaten,
      isLoading,
      releasesLaden,
      roadmapLaden,
      isFetching,
      error,
      releasesFehler,
      roadmapFehler,
      refetch
    } = useHubData(fetchCatalog, fetchReleases, fetchRoadmap)

    // laufend[id] = 'install' | 'uninstall'; ergebnis[id] = Antwort oder Fehler.
    // Ohne den laufend-Zustand wirkt der Klick stumm, bis der Refetch kommt -
    // genau das war die Beschwerde.
    const [laufend, setLaufend] = useState({})
    const [ergebnis, setErgebnis] = useState({})
    const [aktiverTab, setAktiverTab] = useState('marketplace')
    const [backup, setBackup] = useState(null)
    const [backupArchives, setBackupArchives] = useState([])
    const [restorePlan, setRestorePlan] = useState(null)
    const [restoreText, setRestoreText] = useState('')
    const [restoreAcknowledged, setRestoreAcknowledged] = useState(false)
    const [backupTarget, setBackupTarget] = useState('')
    const [backupSchedule, setBackupSchedule] = useState('manual')
    const [backupTime, setBackupTime] = useState('02:00')
    const [backupWeekday, setBackupWeekday] = useState(0)
    const [backupBrowser, setBackupBrowser] = useState(null)
    const [backupBusy, setBackupBusy] = useState(false)
    const refreshBackup = () => Promise.all([aktionen.backupStatus(), aktionen.backupArchives()]).then(([result, archives]) => {
      setBackup(result)
      setBackupArchives(archives.archives || [])
      if (!backupTarget && result.targetDir) setBackupTarget(result.targetDir)
      setBackupSchedule(result.schedule || 'manual')
      setBackupTime(result.scheduleTime || '02:00')
      setBackupWeekday(Number.isInteger(result.scheduleWeekday) ? result.scheduleWeekday : 0)
      return result
    })
    useEffect(() => {
      if (aktiverTab === 'backups') refreshBackup().catch(() => setBackup({ state: 'failed', lastErrorCode: 'STATUS_UNAVAILABLE' }))
    }, [aktiverTab])
    const browseBackup = path => {
      setBackupBusy(true)
      aktionen.backupBrowse({ path }).then(setBackupBrowser).catch(() => setBackupBrowser({ error: 'Ordner konnte nicht geöffnet werden.' })).finally(() => setBackupBusy(false))
    }
    const prepareRestore = name => {
      setBackupBusy(true)
      aktionen.backupRestorePrepare({ name }).then(plan => { setRestorePlan(plan); setRestoreText(''); setRestoreAcknowledged(false) }).finally(() => setBackupBusy(false))
    }
    const confirmRestore = () => {
      if (!restorePlan || restoreText !== restorePlan.confirmationText || !restoreAcknowledged) return
      setBackupBusy(true)
      aktionen.backupRestoreConfirm({ name: restorePlan.name, confirmationToken: restorePlan.confirmationToken, confirmationText: restoreText, acknowledged: true }).then(() => { setRestorePlan(null); return refreshBackup() }).finally(() => setBackupBusy(false))
    }
    const saveBackup = () => {
      setBackupBusy(true)
      aktionen.backupSettings({ enabled: backupSchedule !== 'manual', target_dir: backupTarget, schedule: backupSchedule, scheduleTime: backupTime, scheduleWeekday: backupWeekday, retention: { enabled: false, keep: 5 } })
        .then(result => { setBackup(result); setBackupBrowser(null) }).finally(() => setBackupBusy(false))
    }
    const runBackup = () => {
      setBackupBusy(true); aktionen.backupRun().then(setBackup).finally(() => setBackupBusy(false))
    }

    const updateNotification = anzahl => {
      if (!anzahl) {
        host.notify({
          id: 'aiianer-updates',
          kind: 'success',
          title: 'AIIANER EXTENSION HUB',
          message: 'Alles aktuell. Es gibt keine verfügbaren Updates.',
          durationMs: 5000,
          placement: 'default'
        })
        return
      }

      host.notify({
        id: 'aiianer-updates',
        kind: 'warning',
        title: 'Updates verfügbar',
        message: `${anzahl} ${anzahl === 1 ? 'Erweiterung wartet' : 'Erweiterungen warten'} auf ein Update.`,
        detail: 'Öffne den AIIANER EXTENSION HUB und aktualisiere die rot markierten Buttons.',
        durationMs: 0,
        placement: 'default',
        action: { label: 'Hub öffnen', onClick: () => host.navigate('/aiianer') }
      })
    }

    useEffect(() => {
      if (data) updateNotification((data.components || []).filter(c => c.status === 'outdated').length)
    }, [data])

    const updatesPruefen = () => {
      void refetch().then(result => {
        updateNotification((result.data?.components || []).filter(c => c.status === 'outdated').length)
      }).catch(error => {
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
            const gatewayNeustart = aktion === 'install' && antwort.requiresGatewayRestart === true
            if (gatewayNeustart) {
              host.notify({
                kind: 'warning',
                title: 'Hub wird neu geladen',
                message: 'Der neue Hub-Stand ist installiert. Das Hermes-Backend wird jetzt neu gestartet.'
              })
              if (typeof host.restartGateway === 'function') {
                return host.restartGateway()
                  .then(() => {
                    host.notify({
                      kind: 'success',
                      title: 'Hub aktualisiert',
                      message: 'Backend und Katalog laufen jetzt mit dem neuen Stand. Bitte Hermes komplett beenden und neu starten, damit die Desktop-Oberfläche den neuen Plugin-Code lädt.'
                    })
                    return refetch().catch(() => {})
                  })
                  .catch(error => {
                    const text = error && error.message ? error.message : String(error)
                    setErgebnis(v => ({ ...v, [id]: {
                      ok: true,
                      ...antwort,
                      warnings: ['Der Hub ist installiert, aber der automatische Backend-Neustart ist fehlgeschlagen: ' + text]
                    } }))
                  })
              }
            }
            if (aktion === 'install' && (antwort.nextSteps || []).some(step => /neu starten|restart/i.test(step))) {
              host.notify({
                kind: 'warning',
                title: 'Hermes-Neustart erforderlich',
                message: 'Das Update ist installiert. Bitte Hermes komplett beenden und neu starten.'
              })
            }
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

    const backupInstalled = Boolean(data && (data.components || []).some(c => c.id === 'aiianer-backup' && c.installed))
    useEffect(() => {
      if (!backupInstalled && aktiverTab === 'backups') setAktiverTab('marketplace')
    }, [backupInstalled, aktiverTab])

    if (isLoading) return jsx('div', { className: 'h-24 m-3 animate-pulse rounded-lg bg-white/10' })
    if (error) {
      return jsxs('div', { className: 'm-3 rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm', children: [
        jsx('strong', { children: t('errTitle') }),
        jsx('p', { className: 'mt-2 opacity-75', children: String(error && error.message ? error.message : error) })
      ] })
    }

    const items = (data && data.components) || []
    if (!items.length) return jsx('p', { className: 'm-3 p-4 text-sm opacity-70', children: t('empty') })

    const knopf = (schluessel, beschriftung, opts) =>
      jsx('button', {
        className: cn(
          'min-h-9 rounded-lg px-3 py-2 text-xs font-medium border transition-all',
          opts.aus ? 'opacity-50 cursor-not-allowed' : 'hover:bg-accent hover:-translate-y-px',
          opts.update
            ? 'border-red-500/80 bg-red-500/15 text-red-300 shadow-sm shadow-red-500/20 hover:bg-red-500/25'
            : opts.betont
              ? 'border-accent/70 bg-accent/15 text-accent shadow-sm shadow-accent/20'
              : 'border-white/15 bg-white/5'
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
          jsx('span', { className: 'rounded border border-accent/40 px-2 py-0.5 text-xs', children: 'v' + c.version }, 'v'),
          jsx('span', { className: 'rounded border border-accent/40 px-2 py-0.5 text-xs', children: c.available === false ? t('status.unavailable') : t('status.' + c.status) }, 's'),
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
            aus: gesperrt, betont: true, update: true, onClick: () => ausfuehren(c.id, 'install')
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
    // Dieser Marker darf keine eigene Versionskonstante haben. Er zeigt exakt
    // dieselbe Katalogantwort wie die Hub-Karte und aktualisiert sich nach dem
    // Refetch deshalb gemeinsam mit ihr.
    const hub = items.find(c => c.id === ID)
    const hubVersion = (hub && (hub.installed || hub.version)) || '—'

    return jsxs('div', {
      className: 'min-w-0 w-full max-w-6xl overflow-x-hidden p-4 sm:p-6 lg:p-8 space-y-6',
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
              children: 'Versionshinweise'
            }, 'release-tab'),
            jsx('button', {
              className: aktiverTab === 'roadmap' ? 'border-b-2 border-accent px-3 py-2 text-xs font-medium text-accent' : 'px-3 py-2 text-xs opacity-60 hover:opacity-100',
              onClick: () => setAktiverTab('roadmap'),
              children: 'Roadmap'
            }, 'roadmap-tab'),
            backupInstalled ? jsx('button', {
              className: aktiverTab === 'backups' ? 'border-b-2 border-accent px-3 py-2 text-xs font-medium text-accent' : 'px-3 py-2 text-xs opacity-60 hover:opacity-100',
              onClick: () => setAktiverTab('backups'),
              children: 'Backups'
            }, 'backups-tab') : null,
            jsx('span', {
              className: 'ml-auto self-center pb-2 text-[10px] font-mono tracking-wider opacity-50',
              children: 'v' + hubVersion
            }, 'version')
          ]
        }, 'tabs'),
        aktiverTab === 'backups' && backupInstalled
          ? jsxs('section', { className: 'rounded-xl border border-white/10 bg-black/10 p-4 sm:p-5 space-y-5', children: [
              jsx('p', { className: 'text-xs uppercase tracking-widest text-accent', children: 'AIIANER BACKUP-AUSSENPOSTEN' }),
              jsx('h2', { className: 'text-xl font-semibold', children: 'Backups · lokal und außerhalb von Hermes' }),
              jsx('p', { className: 'break-words whitespace-normal text-sm leading-5 opacity-70', children: 'Deine Daten verlassen diesen Rechner nicht. Wähle den Zielordner einfach aus — innerhalb von HERMES_HOME ist absichtlich gesperrt.' }),
              jsxs('div', { className: 'space-y-2', children: [
                jsx('label', { className: 'text-xs font-medium opacity-75', children: 'Speicherort' }),
                jsxs('div', { className: 'flex gap-2', children: [
                  jsx('input', { className: 'min-w-0 flex-1 rounded-md border border-white/15 bg-white/5 px-3 py-2 text-sm', value: backupTarget, placeholder: '/home/deinname/Backups', onChange: event => setBackupTarget(event.target.value) }),
                  jsx('button', { className: 'shrink-0 rounded-md border border-white/15 px-3 py-2 text-xs', disabled: backupBusy, onClick: () => browseBackup(backupTarget || undefined), children: 'Ordner auswählen' })
                ] })
              ] }),
              backupBrowser ? jsxs('div', { className: 'rounded-md border border-white/15 bg-white/[0.03] p-3 space-y-2', children: [
                backupBrowser.error ? jsx('p', { className: 'text-xs text-red-300', children: backupBrowser.error }) : jsxs(React.Fragment, { children: [
                  jsxs('div', { className: 'flex flex-wrap items-center gap-2', children: [
                    jsx('button', { className: 'rounded border border-white/15 px-2 py-1 text-xs', disabled: !backupBrowser.parent || backupBusy, onClick: () => browseBackup(backupBrowser.parent), children: '← Hoch' }),
                    jsx('button', { className: 'rounded border border-accent/60 px-2 py-1 text-xs text-accent', disabled: backupBusy, onClick: () => { setBackupTarget(backupBrowser.path); setBackupBrowser(null) }, children: 'Diesen Ordner wählen' }),
                    jsx('span', { className: 'min-w-0 break-all text-[11px] opacity-60', children: backupBrowser.path })
                  ] }),
                  backupBrowser.directories && backupBrowser.directories.length ? jsx('div', { className: 'grid max-h-52 grid-cols-1 gap-1 overflow-auto sm:grid-cols-2', children: backupBrowser.directories.map(folder => jsx('button', { className: 'truncate rounded px-2 py-1 text-left text-xs hover:bg-white/10', onClick: () => browseBackup(folder.path), children: `📁 ${folder.name}` }, folder.path)) }) : jsx('p', { className: 'text-xs opacity-60', children: 'Keine Unterordner. Du kannst diesen Ordner direkt wählen.' })
                ] })
              ] }) : null,
              jsx('p', { className: 'break-words whitespace-normal text-xs leading-5 opacity-70', children: 'Hier stellst du die automatische Backup-Routine ein. Nach dem Speichern legt Hermes einen eigenen Zeitplan an. Ohne Zielordner wird nichts ausgeführt.' }),
              jsx('p', { className: 'break-words whitespace-normal text-xs leading-5 text-amber-200/75', children: 'Backup beim Schließen von Hermes ist in V1 noch nicht verfügbar. Diese Option folgt erst mit einem verlässlichen App-Shutdown-Hook.' }),
              jsxs('div', { className: 'grid gap-3 rounded-md border border-white/10 p-3 sm:grid-cols-3', children: [
                jsxs('label', { className: 'min-w-0 space-y-1 text-xs', children: [jsx('span', { className: 'font-medium opacity-75', children: 'Automatisches Backup' }), jsx('select', { className: 'w-full min-w-0 rounded border border-white/15 bg-background px-2 py-2 text-foreground', style: { colorScheme: 'dark' }, value: backupSchedule, onChange: event => setBackupSchedule(event.target.value), children: [jsx('option', { className: 'bg-background text-foreground', value: 'manual', children: 'Aus · nur manuell' }), jsx('option', { className: 'bg-background text-foreground', value: 'daily', children: 'Täglich' }), jsx('option', { className: 'bg-background text-foreground', value: 'weekly', children: 'Wöchentlich' })] })] }),
                jsxs('label', { className: 'space-y-1 text-xs', children: [jsx('span', { className: 'font-medium opacity-75', children: 'Uhrzeit' }), jsx('input', { className: 'w-full rounded border border-white/15 bg-black/20 px-2 py-2', type: 'time', value: backupTime, disabled: backupSchedule === 'manual', onChange: event => setBackupTime(event.target.value) })] }),
                backupSchedule === 'weekly' ? jsxs('label', { className: 'space-y-1 text-xs', children: [jsx('span', { className: 'font-medium opacity-75', children: 'Wochentag' }), jsx('select', { className: 'w-full rounded border border-white/15 bg-black/20 px-2 py-2', value: backupWeekday, onChange: event => setBackupWeekday(Number(event.target.value)), children: ['Sonntag', 'Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag'].map((name, day) => jsx('option', { value: day, children: name }, day)) })] }) : jsx('div', { className: 'text-xs self-end opacity-55', children: backupSchedule === 'daily' ? 'Läuft jeden Tag zur gewählten Uhrzeit.' : 'Manuelle Sicherungen bleiben jederzeit möglich.' })
              ] }),
              jsxs('div', { className: 'flex gap-2 flex-wrap', children: [
                jsx('button', { className: 'rounded-md border border-accent px-3 py-2 text-xs', disabled: backupBusy || !backupTarget, onClick: saveBackup, children: backupBusy ? 'Arbeite ...' : 'Speicherort & Plan sichern' }),
                jsx('button', { className: 'rounded-md border border-white/15 px-3 py-2 text-xs', disabled: backupBusy || !(backup && backup.configured), onClick: runBackup, children: 'Jetzt sichern' }),
                jsx('button', { className: 'rounded-md border border-white/15 px-3 py-2 text-xs', disabled: backupBusy, onClick: () => refreshBackup(), children: 'Status aktualisieren' })
              ] }),
              backup ? jsxs('div', { className: 'space-y-1 text-xs opacity-75', children: [
                jsx('p', { children: `Status: ${backup.state}${backup.lastErrorCode ? ` · Backup: ${backup.lastErrorCode}` : ''}${backup.scheduleErrorCode ? ` · Zeitplan: ${backup.scheduleErrorCode}` : ''}` }),
                backup.lastArchive ? jsx('p', { children: `Letztes Archiv: ${backup.lastArchive.name} · ${backup.lastArchive.fileCount || '?'} Dateien` }) : null,
                jsx('p', { children: `${backup.archiveCount || 0} veröffentlichte Archive im Zielordner.` })
              ] }) : jsx('div', { className: 'h-12 animate-pulse rounded-lg bg-white/10' }),
              jsxs('div', { className: 'rounded-md border border-white/10 p-3', children: [
                jsx('h3', { className: 'text-sm font-medium', children: 'Laufprotokoll' }),
                backup && backup.history && backup.history.length ? jsx('div', { className: 'mt-2 space-y-1 text-xs', children: backup.history.map((entry, index) => jsx('p', { className: entry.state === 'success' ? 'text-emerald-300' : 'text-red-300', children: `${entry.state === 'success' ? '✓' : '✕'} ${new Date(entry.at).toLocaleString('de-DE')} · ${entry.state === 'success' ? (entry.archive && entry.archive.name ? entry.archive.name : 'Sicherung erfolgreich') : (entry.errorCode || 'Fehler')}` }, `${entry.at}-${index}`)) }) : jsx('p', { className: 'mt-2 text-xs opacity-60', children: 'Noch kein Backup-Lauf protokolliert.' })
              ] }),
              jsxs('div', { className: 'rounded-md border border-white/10 p-3 space-y-2', children: [
                jsx('h3', { className: 'text-sm font-medium', children: 'Verfügbare Backups' }),
                backupArchives.length ? jsx('div', { className: 'space-y-2', children: backupArchives.map(archive => jsxs('div', { className: 'flex flex-wrap items-center justify-between gap-2 border-t border-white/10 pt-2 first:border-t-0 first:pt-0', children: [
                  jsxs('div', { className: 'min-w-0', children: [jsx('p', { className: 'truncate text-xs font-medium', children: archive.name }), jsx('p', { className: 'text-[11px] opacity-60', children: `${new Date(archive.modified).toLocaleString('de-DE')} · ${(archive.bytes / 1024 / 1024).toFixed(1)} MB` })] }),
                  jsx('button', { className: 'rounded border border-amber-300/60 px-2 py-1 text-xs text-amber-200', disabled: backupBusy || archive.valid === false, onClick: () => prepareRestore(archive.name), children: archive.valid === false ? 'Ungültig' : 'Wiederherstellen' })
                ] }, archive.name)) }) : jsx('p', { className: 'text-xs opacity-60', children: 'Noch keine fertigen Backups im Zielordner.' })
              ] }),
              restorePlan ? jsxs('div', { className: 'rounded-md border border-red-400/50 bg-red-950/20 p-3 space-y-2', children: [
                jsx('h3', { className: 'text-sm font-medium text-red-200', children: 'Wiederherstellung bestätigen' }),
                jsx('p', { className: 'text-xs text-red-100/80', children: restorePlan.warning }),
                jsx('p', { className: 'break-all rounded bg-black/20 p-2 font-mono text-xs', children: restorePlan.confirmationText }),
                jsx('input', { className: 'w-full rounded border border-red-300/40 bg-black/20 px-2 py-2 text-xs', value: restoreText, placeholder: 'Bestätigung exakt eintippen', onChange: event => setRestoreText(event.target.value) }),
                jsx('label', { className: 'flex items-start gap-2 text-xs', children: [jsx('input', { type: 'checkbox', checked: restoreAcknowledged, onChange: event => setRestoreAcknowledged(event.target.checked) }), jsx('span', { children: 'Ich weiß, dass bestehende Hermes-Daten überschrieben werden können.' })] }),
                jsxs('div', { className: 'flex gap-2', children: [jsx('button', { className: 'rounded border border-red-300 bg-red-500/20 px-3 py-2 text-xs text-red-100', disabled: backupBusy || restoreText !== restorePlan.confirmationText || !restoreAcknowledged, onClick: confirmRestore, children: 'Import mit Überschreiben ausführen' }), jsx('button', { className: 'rounded border border-white/15 px-3 py-2 text-xs', disabled: backupBusy, onClick: () => setRestorePlan(null), children: 'Abbrechen' })] })
              ] }) : null,
              jsxs('div', { className: 'rounded-md border border-white/10 p-3 space-y-2', children: [
                jsx('h3', { className: 'text-sm font-medium', children: 'Restore-Anleitung' }),
                jsx('p', { className: 'text-xs opacity-75', children: '1. Wähle oben ein gültiges Archiv. 2. Lies die Warnung und tippe den exakten Bestätigungssatz ein. 3. Setze die Checkbox und starte den Import. Hermes muss danach gegebenenfalls neu gestartet werden.' }),
                jsx('p', { className: 'text-xs opacity-60', children: 'Alternativ im Terminal: hermes import /vollständiger/pfad/zu/deinem-backup.zip. Für das Überschreiben bestehender Daten verwendet der Assistent den offiziellen Importpfad mit --force.' })
              ] }),
              jsx('p', { className: 'text-xs text-amber-300/80', children: 'Wiederherstellung überschreibt möglicherweise bestehende Hermes-Daten. Sie wird niemals automatisch ausgeführt.' })
            ] }, 'backups-content')
          : aktiverTab === 'release-notes'
          ? jsx(Versionshinweise, { daten: releaseDaten, laedt: releasesLaden, fehler: releasesFehler }, 'release-notes')
          : aktiverTab === 'roadmap'
          ? jsx(Roadmap, { daten: roadmapDaten, laedt: roadmapLaden, fehler: roadmapFehler }, 'roadmap')
          : jsxs('div', {
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
                jsx('span', { className: 'rounded border border-accent/40 px-2 py-0.5 text-xs', children: `${items.length} Komponenten` }, 'count'),
                jsx('span', { className: 'rounded border border-accent/40 px-2 py-0.5 text-xs', children: `${installiert} installiert` }, 'installed'),
                updates ? jsx('span', { className: 'rounded border border-accent/40 px-2 py-0.5 text-xs', children: `${updates} Update${updates === 1 ? '' : 's'}` }, 'updates') : null
              ]
            }, 'stats'),
            jsx('p', { className: 'text-sm opacity-70', children: 'Deutsche Sprache und die AIIANER-Werkzeuge. Was du hier installierst, überlebt Hermes-Updates.' }, 'intro'),
            ...karten
          ]
        }, 'marketplace-content'),
        jsx('footer', {
          className: 'border-t border-white/10 pt-4 text-center text-[10px] opacity-45',
          children: 'Mit Liebe und Leidenschaft erstellt von Oliver Hees aka Aiianer · 2026'
        }, 'footer')
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
        // Der Hub ist bewusst deutschsprachig. Dieser Fallback greift, wenn
        // Hermes selbst englisch läuft, und verhindert eine Mischoberfläche.
        title: 'AIIANER EXTENSION HUB',
        intro: 'Deutsche Sprache und die AIIANER-Werkzeuge. Was du hier installierst, überlebt Hermes-Updates.',
        install: 'Installieren',
        reinstall: 'Neu einspielen',
        uninstall: 'Deinstallieren',
        updateTo: v => `Auf v${v} aktualisieren`,
        installedIs: v => `installiert: v${v}`,
        installing: 'Wird installiert, einen Moment ...',
        uninstalling: 'Wird entfernt ...',
        doneTitle: 'Fertig. Das ist jetzt zu tun:',
        doneBare: 'Fertig. Hermes komplett beenden und neu starten, damit es greift.',
        warnTitle: 'Diese Reste ließen sich nicht entfernen:',
        failTitle: 'Das hat nicht geklappt:',
        afterwards: 'Danach nötig:',
        empty: 'Der Katalog ist leer',
        errTitle: 'Katalog konnte nicht geladen werden',
        status: { current: 'aktuell', outdated: 'Update verfügbar', missing: 'nicht installiert', unavailable: 'zurzeit nicht möglich' },
        unavailTitle: 'Lässt sich gerade nicht installieren:',
        unavailableAction: 'Auf diesem System nicht verfügbar',
        lang: 'de'
      },
      de: {
        title: 'AIIANER EXTENSION HUB',
        intro: 'Deutsche Sprache und die AIIANER-Werkzeuge. Was du hier installierst, überlebt Hermes-Updates.',
        install: 'Installieren',
        reinstall: 'Neu einspielen',
        uninstall: 'Deinstallieren',
        updateTo: v => `Auf v${v} aktualisieren`,
        installedIs: v => `installiert: v${v}`,
        installing: 'Wird installiert, einen Moment ...',
        uninstalling: 'Wird entfernt ...',
        doneTitle: 'Fertig. Das ist jetzt zu tun:',
        doneBare: 'Fertig. Hermes komplett beenden und neu starten, damit es greift.',
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
    const fetchReleases = () => ctx.rest('/releases')
    const fetchRoadmap = () => ctx.rest('/roadmap')
    // PluginRestOptions kennt method/body/upload/timeoutMs. KEIN headers, und
    // body ist ein Objekt - die Bruecke serialisiert selbst. Ein
    // JSON.stringify hier wuerde dem Backend einen String statt eines
    // Objekts schicken.
    const aktionen = {
      install: id => ctx.rest('/install', { method: 'POST', body: { id } }),
      uninstall: id => ctx.rest('/uninstall', { method: 'POST', body: { id } }),
      backupStatus: () => ctx.rest('/backup/status'),
      backupSettings: body => ctx.rest('/backup/settings', { method: 'PUT', body }),
      backupBrowse: body => ctx.rest('/backup/browse', { method: 'POST', body }),
      backupArchives: () => ctx.rest('/backup/archives'),
      backupRestorePrepare: body => ctx.rest('/backup/restore/prepare', { method: 'POST', body }),
      backupRestoreConfirm: body => ctx.rest('/backup/restore/confirm', { method: 'POST', body }),
      backupRun: () => ctx.rest('/backup/run', { method: 'POST', body: {} })    }

    const onCommunity = event => {
      event.preventDefault()
      void ctx.os.openExternal('https://aiianer.de')
    }
    const translate = ctx.i18n.t.bind(ctx.i18n)
    const Pane = makePane(fetchCatalog, fetchReleases, fetchRoadmap, aktionen, onCommunity, translate)

    // Eigene Seite
    ctx.register({
      id: 'aiianer-route',
      title: 'AIIANER EXTENSION HUB',
      area: 'routes',
      data: { path: '/aiianer' },
      render: Pane
    })

    // Eintrag in der Seitenleiste, der die Seite oeffnet
    ctx.register({
      id: 'aiianer-nav',
      area: 'sidebar.nav',
      order: 60,
      data: { codicon: 'package', label: 'AIIANER EXTENSION HUB', path: '/aiianer' }
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
