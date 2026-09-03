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

import {
  Badge,
  cn,
  EmptyState,
  ErrorState,
  host,
  jsx,
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
    const { t } = usePluginI18n(ID)
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

    return jsx('div', { className: 'p-3 space-y-3' }, [
      jsx('p', { key: 'intro', className: 'text-xs opacity-70' }, t('intro')),
      ...items.map(c =>
        jsx('div', {
          key: c.id,
          className: cn('rounded-md border p-3 space-y-2')
        }, [
          jsx('div', { key: 'h', className: 'flex items-center gap-2' }, [
            jsx('span', { key: 'n', className: 'font-medium text-sm' }, c.name),
            jsx(Badge, { key: 'v' }, 'v' + c.version),
            jsx(Badge, { key: 's' }, t('status.' + c.status) || c.status)
          ]),
          jsx('p', { key: 'd', className: 'text-xs opacity-70' }, c.summary),
          c.note ? jsx('p', { key: 'note', className: 'text-xs opacity-50' }, c.note) : null,
          jsx('button', {
            key: 'b',
            className: cn(
              'text-xs rounded px-2 py-1 border',
              c.status === 'current' ? 'opacity-50' : 'hover:bg-accent'
            ),
            disabled: c.status === 'current',
            onClick: () => doInstall(c.id).then(() => refetch())
          }, c.status === 'missing' ? t('install')
            : c.status === 'outdated' ? t('update')
            : t('installed'))
        ])
      )
    ])
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
    const doInstall = id =>
      ctx.rest('/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id })
      })

    const useCatalog = makeUseCatalog(fetchCatalog)
    const Pane = makePane(useCatalog, doInstall)

    // Eigene Seite
    ctx.register({
      id: 'aiianer-route',
      name: 'AIIANER',
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
      data: { path: '/aiianer', label: 'AIIANER', codicon: 'package' },
      render: () => null
    })

    // Ueber die Befehlspalette erreichbar
    ctx.register({
      id: 'aiianer-open',
      area: 'palette',
      data: {
        id: 'aiianer.open',
        label: 'AIIANER Erweiterungen',
        run: () => host.navigate && host.navigate('/aiianer')
      },
      render: () => null
    })
  }
}
