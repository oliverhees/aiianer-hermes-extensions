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

function makePane(useCatalog, doInstall) {
  return function Pane() {
    // usePluginI18n liefert die Uebersetzerfunktion DIREKT zurueck, kein Objekt.
    const t = usePluginI18n(ID)
    const { data, isLoading, error, refetch } = useCatalog()

    if (isLoading) return jsx(Skeleton, { className: 'h-24 m-3' })
    if (error) {
      return jsx(ErrorState, {
        title: t('errTitle'),
        description: String(error && error.message ? error.message : error)
      })
    }

    const items = (data && data.components) || []
    if (!items.length) return jsx(EmptyState, { title: t('empty') })

    // Kinder gehoeren in props.children, der dritte Parameter ist der key.
    // jsxs statt jsx, sobald children ein Array ist.
    const karten = items.map(c => {
      const kopf = jsxs('div', {
        className: 'flex items-center gap-2',
        children: [
          jsx('span', { className: 'font-medium text-sm', children: c.name }, 'n'),
          jsx(Badge, { children: 'v' + c.version }, 'v'),
          jsx(Badge, { children: t('status.' + c.status) || c.status }, 's')
        ]
      }, 'h')

      const knopfText = c.status === 'missing' ? t('install')
        : c.status === 'outdated' ? t('update')
        : t('installed')

      const zeilen = [
        kopf,
        jsx('p', { className: 'text-xs opacity-70', children: c.summary }, 'd'),
        c.note
          ? jsx('p', { className: 'text-xs opacity-50', children: c.note }, 'note')
          : null,
        jsx('button', {
          className: cn(
            'text-xs rounded px-2 py-1 border',
            c.status === 'current' ? 'opacity-50' : 'hover:bg-accent'
          ),
          disabled: c.status === 'current',
          onClick: () => doInstall(c.id).then(() => refetch()),
          children: knopfText
        }, 'b')
      ]

      return jsxs('div', {
        className: cn('rounded-md border p-3 space-y-2'),
        children: zeilen
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
        update: 'Update',
        installed: 'Installed',
        empty: 'Catalog is empty',
        errTitle: 'Could not load the catalog',
        'status.current': 'current',
        'status.outdated': 'update available',
        'status.missing': 'not installed'
      },
      de: {
        title: 'AIIANER Erweiterungen',
        intro: 'Deutsche Sprache und die AIIANER-Werkzeuge. Was du hier installierst, überlebt Hermes-Updates.',
        install: 'Installieren',
        update: 'Aktualisieren',
        installed: 'Installiert',
        empty: 'Der Katalog ist leer',
        errTitle: 'Katalog konnte nicht geladen werden',
        'status.current': 'aktuell',
        'status.outdated': 'Update verfügbar',
        'status.missing': 'nicht installiert'
      }
    })

    const fetchCatalog = () => ctx.rest('/catalog')
    // PluginRestOptions kennt method/body/upload/timeoutMs. KEIN headers, und
    // body ist ein Objekt - die Bruecke serialisiert selbst. Ein
    // JSON.stringify hier wuerde dem Backend einen String statt eines
    // Objekts schicken.
    const doInstall = id => ctx.rest('/install', { method: 'POST', body: { id } })

    const useCatalog = makeUseCatalog(fetchCatalog)
    const Pane = makePane(useCatalog, doInstall)

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
