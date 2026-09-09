/* AIIANER Marktplatz - Oberflaeche.
 * Nutzt ausschliesslich das Hermes-Plugin-SDK, buendelt kein React und keine
 * fremden Komponenten. Damit bleibt das Bundle klein und lizenzrein.
 */
(function () {
  "use strict";

  var SDK = window.__HERMES_PLUGIN_SDK__;
  // Schutz wie im mitgelieferten hermes-achievements: ohne SDK still aussteigen,
  // statt beim Laden der Seite eine Ausnahme zu werfen.
  if (!SDK || !window.__HERMES_PLUGINS__) return;

  var React = SDK.React;
  var h = React.createElement;
  var useState = SDK.hooks.useState;
  var useEffect = SDK.hooks.useEffect;
  var C = SDK.components;

  var API = "/api/plugins/aiianer-hub";

  var LABEL = {
    current: "aktuell",
    outdated: "Update verfügbar",
    missing: "nicht installiert"
  };

  function Row(props) {
    var c = props.item;
    var laufend = props.laufend;      // 'install' | 'uninstall' | null
    var res = props.ergebnis;         // Antwort oder Fehler dieser Karte
    var isPatch = c.kind === "patch";

    return h(
      C.Card,
      { key: c.id, className: "mb-3" },
      h(
        C.CardHeader,
        null,
        h(C.CardTitle, null, c.name),
        h(
          "div",
          { className: "flex flex-wrap items-center gap-2 mt-1" },
          h(C.Badge, null, c.available === false ? "zurzeit nicht möglich" : (LABEL[c.status] || c.status)),
          c.premium
            ? h(C.Badge, { className: "bg-amber-500/20 text-amber-300" }, "Premium")
            : null,
          h(C.Badge, null, "v" + c.version),
          c.installed && c.installed !== c.version
            ? h(C.Badge, null, "installiert: v" + c.installed)
            : null,
          isPatch
            ? h(C.Badge, null, "greift in den Checkout ein")
            : h(C.Badge, null, "eigenständig")
        )
      ),
      h(
        C.CardContent,
        null,
        h("p", { className: "text-sm text-muted-foreground" }, c.summary),
        c.note
          ? h(
              "p",
              { className: "text-xs text-muted-foreground mt-2" },
              c.note
            )
          : null,
        c.coverage
          ? h(
              "p",
              { className: "text-xs text-muted-foreground mt-1" },
              "Abdeckung: " + c.coverage
            )
          : null,
        h(
          "div",
          { className: "mt-3 flex flex-wrap gap-2" },
          c.available === false
            ? h(
                C.Button,
                { key: "unavailable", disabled: true, variant: "outline" },
                "Auf diesem System nicht verfügbar"
              )
            : laufend
            ? h(
                C.Button,
                { disabled: true },
                laufend === "uninstall" ? "wird entfernt ..." : "wird installiert, einen Moment ..."
              )
            : c.status === "missing"
            ? h(
                C.Button,
                { onClick: function () { props.onAktion(c.id, "install"); } },
                "Installieren"
              )
            : [
                c.status === "outdated"
                  ? h(
                      C.Button,
                      { key: "upd", onClick: function () { props.onAktion(c.id, "install"); } },
                      "Auf v" + c.version + " aktualisieren"
                    )
                  : null,
                h(
                  C.Button,
                  { key: "re", variant: "outline", onClick: function () { props.onAktion(c.id, "install"); } },
                  "Neu einspielen"
                ),
                !c.selfManaged
                  ? h(
                      C.Button,
                      { key: "del", variant: "outline", onClick: function () { props.onAktion(c.id, "uninstall"); } },
                      "Deinstallieren"
                    )
                  : null
              ]
        ),

        // Nach der Aktion: was der Nutzer jetzt tun muss. Ohne das erwartet er,
        // dass die Oberflaeche sofort deutsch ist, und das ist sie nicht.
        c.available === false
          ? h(
              "div",
              { className: "mt-3 rounded border border-neutral-600/60 bg-neutral-900/40 p-2" },
              h("p", { className: "text-sm font-medium" }, "Lässt sich gerade nicht installieren:"),
              h("p", { className: "text-sm text-muted-foreground mt-1" }, c.unavailableReason)
            )
          : null,

        res && res.ok && (res.warnings || []).length
          ? h(
              "div",
              { className: "mt-3 rounded border border-amber-600/60 bg-amber-950/20 p-2" },
              h("p", { className: "text-sm font-medium" }, "Diese Reste ließen sich nicht entfernen:"),
              h(
                "ul",
                { className: "text-sm text-muted-foreground list-disc pl-5 mt-1" },
                res.warnings.map(function (z, i) { return h("li", { key: i }, z); })
              )
            )
          : null,

        res && res.ok && !(res.nextSteps || []).length
          ? h(
              "p",
              { className: "mt-3 text-sm text-emerald-400" },
              "Fertig. Hermes neu starten, damit es greift."
            )
          : res && res.ok && (res.nextSteps || []).length
          ? h(
              "div",
              { className: "mt-3 rounded border border-emerald-600/50 bg-emerald-950/20 p-2" },
              h("p", { className: "text-sm font-medium" }, "Fertig. Das ist jetzt zu tun:"),
              h(
                "ol",
                { className: "text-sm text-muted-foreground list-decimal pl-5 mt-1 space-y-0.5" },
                res.nextSteps.map(function (z, i) {
                  return h("li", { key: i }, z);
                })
              )
            )
          : res && !res.ok
          ? h(
              "div",
              { className: "mt-3 rounded border border-red-600/60 bg-red-950/20 p-2" },
              h("p", { className: "text-sm font-medium" }, "Das hat nicht geklappt:"),
              h("p", { className: "text-sm text-muted-foreground mt-1 whitespace-pre-wrap" }, res.message)
            )
          : !laufend && c.available !== false && c.status === "missing" && (c.nextSteps || []).length
          ? h(
              "p",
              { className: "text-xs text-muted-foreground mt-2" },
              "Danach nötig: " + c.nextSteps[0]
            )
          : null
      )
    );
  }

  function Page() {
    var s = useState([]);
    var items = s[0];
    var setItems = s[1];

    var b = useState(null);
    var busy = b[0];
    var setBusy = b[1];

    var lf = useState({});
    var laufend = lf[0];
    var setLaufend = lf[1];

    var eg = useState({});
    var ergebnis = eg[0];
    var setErgebnis = eg[1];

    var e = useState(null);
    var err = e[0];
    var setErr = e[1];

    var hs = useState(null);
    var health = hs[0];
    var setHealth = hs[1];

    var ts = useState("marketplace");
    var aktiverTab = ts[0];
    var setAktiverTab = ts[1];

    // Gibt ein Promise zurueck. Ohne das setzt der Aufrufer den Knopf frei,
    // bevor der neue Katalog da ist: die Karte steht noch auf "missing", der
    // Installieren-Knopf ist wieder aktiv, und ein zweiter Klick startet einen
    // zweiten kompletten Installer-Lauf.
    function load() {
      var a = SDK.fetchJSON(API + "/catalog")
        .then(function (d) {
          setItems(d.components || []);
          setErr(null);
        })
        .catch(function (x) {
          setErr(String(x && x.message ? x.message : x));
        });
      var b = SDK.fetchJSON(API + "/health")
        .then(setHealth)
        .catch(function (x) {
          // Nicht still schlucken: faellt /health aus, fehlt genau der
          // Hinweis samt Reparieren-Knopf, den man dann braeuchte.
          setHealth({ ok: false, broken: [], error: String(x && x.message ? x.message : x) });
        });
      return Promise.all([a, b]);
    }

    useEffect(function () {
      load();
    }, []);

    // Pro Karte merken, was laeuft und was herauskam. Ein globales "busy"
    // reicht nicht: der Nutzer soll sehen, WELCHE Karte gerade arbeitet.
    function aktion(id, welche) {
      setLaufend(function (v) { var n = {}; for (var k in v) n[k] = v[k]; n[id] = welche; return n; });
      setErgebnis(function (v) { var n = {}; for (var k in v) n[k] = v[k]; n[id] = null; return n; });
      SDK.fetchJSON(API + "/" + welche, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: id })
      })
        .then(function (antwort) {
          setErgebnis(function (v) {
            var n = {}; for (var k in v) n[k] = v[k];
            n[id] = { ok: true, nextSteps: (antwort && antwort.nextSteps) || [], warnings: (antwort && antwort.warnings) || [] };
            return n;
          });
          // Auf den frischen Katalog WARTEN, sonst gibt der Knopf zu frueh
          // wieder frei. Ein Fehler hier darf die geglueckte Aktion nicht
          // nachtraeglich zum Fehlschlag machen.
          return load().catch(function () {});
        })
        .catch(function (x) {
          setErgebnis(function (v) {
            var n = {}; for (var k in v) n[k] = v[k];
            n[id] = { ok: false, message: String(x && x.message ? x.message : x) };
            return n;
          });
        })
        .then(function () {
          setLaufend(function (v) { var n = {}; for (var k in v) n[k] = v[k]; n[id] = null; return n; });
        });
    }

    function repair() {
      setBusy("__repair__");
      SDK.fetchJSON(API + "/repair", { method: "POST" })
        .then(function () {
          setBusy(null);
          load();
        })
        .catch(function (x) {
          setBusy(null);
          setErr(String(x && x.message ? x.message : x));
        });
    }

    var installiert = items.filter(function (c) { return c.installed; }).length;
    var updates = items.filter(function (c) { return c.status === "outdated"; }).length;

    return h(
      "div",
      { className: "p-4 max-w-4xl" },
      h(
        "section",
        { className: "mb-5 relative overflow-hidden rounded-xl border border-accent/35 bg-accent/10 px-4 py-3 sm:px-5" },
        h("div", { className: "pointer-events-none absolute inset-y-0 left-0 w-1 bg-accent" }),
        h(
          "div",
          { className: "relative flex flex-wrap items-center justify-between gap-x-5 gap-y-3" },
          h("div", { className: "min-w-0" },
            h("div", { className: "flex flex-wrap items-center gap-x-3 gap-y-1" },
              h("span", { className: "font-mono text-[10px] uppercase tracking-[0.22em] text-accent" }, "AIIANER Community"),
              h("span", { className: "hidden text-[10px] opacity-45 sm:inline" }, "KI zum Anwenden, nicht zum Hypen.")
            ),
            h("p", { className: "mt-1 max-w-2xl text-xs leading-5 text-muted-foreground" }, "Kurse, Vorlagen, Live-Calls und Austausch für Menschen, die KI wirklich einsetzen. AIIANER nutzt Hermes als Basis des KI-Betriebssystems und baut darauf Plugins, MCPs und Werkzeuge für den Alltag.")
          ),
          h("div", { className: "flex flex-col items-stretch gap-1 shrink-0" },
            h("a", { href: "https://aiianer.de", target: "_blank", rel: "noreferrer", className: "rounded-md border border-accent bg-accent px-3 py-2 text-xs font-semibold text-accent-foreground transition hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-accent" }, "Community öffnen ↗"),
            h("span", { className: "max-w-52 text-[10px] leading-4 text-muted-foreground" }, "Falls der Klick nicht öffnet: Rechtsklick auf den Button und „Link im externen Browser öffnen“ wählen.")
          )
        ),
      ),
      h(
        "div",
        { className: "mb-5 flex gap-2 border-b border-border" },
        h("button", { className: aktiverTab === "marketplace" ? "border-b-2 border-accent px-3 py-2 text-xs font-medium text-accent" : "px-3 py-2 text-xs text-muted-foreground hover:text-foreground", onClick: function () { setAktiverTab("marketplace"); } }, "Marktplatz"),
        h("button", { className: aktiverTab === "release-notes" ? "border-b-2 border-accent px-3 py-2 text-xs font-medium text-accent" : "px-3 py-2 text-xs text-muted-foreground hover:text-foreground", onClick: function () { setAktiverTab("release-notes"); } }, "Versionshinweise")
      ),
      h(
        "section",
        { className: aktiverTab === "release-notes" ? "mb-5 rounded-xl border border-border bg-card p-4 sm:p-5" : "hidden" },
        h("p", { className: "text-xs uppercase tracking-widest text-accent" }, "Versionshinweise"),
        h("h2", { className: "mt-1 text-xl font-semibold" }, "AIIANER EXTENSION HUB v1.3.11"),
        h("p", { className: "mt-1 text-sm text-muted-foreground" }, "Die Änderungen dieser Version auf einen Blick."),
        h("div", { className: "mt-5 space-y-4 text-sm" },
          h("div", null, h("p", { className: "font-medium" }, "Community-Link"), h("p", { className: "mt-1 text-muted-foreground" }, "Der Community-Link ist jetzt korrekt mit Hermes verdrahtet. Falls der normale Klick nicht öffnet, erklärt der Hinweis direkt am Button den Weg über das Rechtsklick-Menü.")),
          h("div", null, h("p", { className: "font-medium" }, "Theme-Anpassung"), h("p", { className: "mt-1 text-muted-foreground" }, "Button, Statusanzeigen, Update-Hinweise und Akzentflächen verwenden die aktiven Hermes-Theme-Farben.")),
          h("div", null, h("p", { className: "font-medium" }, "Hermes als Basis"), h("p", { className: "mt-1 text-muted-foreground" }, "Der Header erklärt jetzt, dass AIIANER Hermes als Basis des KI-Betriebssystems nutzt und darauf Plugins, MCPs und Werkzeuge aufbaut."))
        ),
      ),
      h(
        "div",
        { className: aktiverTab === "marketplace" ? "" : "hidden" },
        h(
          "div",
          { className: "mb-5 flex flex-wrap items-end justify-between gap-3" },
          h("div", null,
            h("p", { className: "text-xs uppercase tracking-widest text-accent" }, "Dein Marktplatz"),
            h("h2", { className: "mt-1 text-xl font-semibold" }, "AIIANER EXTENSION HUB"),
            h("p", { className: "text-sm text-muted-foreground mt-1" }, "Installieren, aktuell halten und nach Hermes-Updates entspannt bleiben.")
          ),
          h("div", { className: "flex gap-2 text-xs text-muted-foreground" },
            h(C.Badge, null, items.length + " Komponenten"),
            h(C.Badge, null, installiert + " installiert"),
            updates ? h(C.Badge, { className: "bg-accent/20 text-accent" }, updates + " Update" + (updates === 1 ? "" : "s")) : null
          )
        ),

      updates
        ? h(
            C.Card,
            { className: "mb-5 rounded-2xl border-accent/30 bg-accent/10" },
            h(
              C.CardContent,
              { className: "p-4 sm:p-5" },
              h("p", { className: "text-xs uppercase tracking-widest text-accent" }, "Updates im Außenposten"),
              h("p", { className: "mt-1 text-sm font-medium" }, updates === 1 ? "Eine Erweiterung wartet auf ihr Update." : updates + " Erweiterungen warten auf ihr Update."),
              h("p", { className: "mt-1 text-xs text-muted-foreground" }, "Öffne die jeweilige Karte und aktualisiere sie mit einem Klick. Danach Hermes neu starten, wenn es angezeigt wird.")
            )
          )
        : null,

      health && !health.ok
        ? h(
            C.Card,
            { className: "mb-4" },
            h(
              C.CardContent,
              { className: "pt-4" },
              h(
                "p",
                { className: "text-sm" },
                "Nach einem Hermes-Update fehlt etwas: " +
                  (health.broken || []).join(", ")
              ),
              h(
                "div",
                { className: "mt-2" },
                h(
                  C.Button,
                  { disabled: busy === "__repair__", onClick: repair },
                  busy === "__repair__" ? "repariert ..." : "Jetzt reparieren"
                )
              )
            )
          )
        : null,

      err
        ? h(
            C.Card,
            { className: "mb-4" },
            h(
              C.CardContent,
              { className: "pt-4" },
              h("p", { className: "text-sm" }, err)
            )
          )
        : null,

      items.length === 0 && !err
        ? h(
            "p",
            { className: "text-sm text-muted-foreground" },
            "Katalog wird geladen ..."
          )
        : null,

      items.map(function (c) {
        return h(Row, {
          key: c.id,
          item: c,
          laufend: laufend[c.id] || null,
          ergebnis: ergebnis[c.id] || null,
          onAktion: aktion
        });
      }),

      h(
        "p",
        { className: "text-xs text-muted-foreground mt-6" },
        "Quelle: github.com/oliverhees/aiianer-hermes-extensions"
      )
      )
    );
  }

  window.__HERMES_PLUGINS__.register("aiianer-hub", Page);
})();
