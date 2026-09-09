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
        { className: "mb-5 relative overflow-hidden rounded-xl border border-orange-500/35 bg-gradient-to-r from-orange-950/50 via-neutral-900 to-neutral-950 px-4 py-3 sm:px-5" },
        h("div", { className: "pointer-events-none absolute inset-y-0 left-0 w-1 bg-orange-500" }),
        h(
          "div",
          { className: "relative flex flex-wrap items-center justify-between gap-x-5 gap-y-3" },
          h("div", { className: "min-w-0" },
            h("div", { className: "flex flex-wrap items-center gap-x-3 gap-y-1" },
              h("span", { className: "font-mono text-[10px] uppercase tracking-[0.22em] text-orange-300" }, "AIIANER Community"),
              h("span", { className: "hidden text-[10px] opacity-45 sm:inline" }, "KI zum Anwenden, nicht zum Hypen.")
            ),
            h("p", { className: "mt-1 max-w-2xl text-xs leading-5 opacity-70" }, "Kurse, Vorlagen, Live-Calls und Austausch für Menschen, die KI wirklich einsetzen.")
          ),
          h("a", { href: "https://aiianer.de", target: "_blank", rel: "noreferrer", className: "shrink-0 rounded-md bg-orange-500 px-3 py-2 text-xs font-semibold text-white transition hover:bg-orange-400 focus:outline-none focus:ring-2 focus:ring-orange-300" }, "Community öffnen ↗")
        )
      ),
      h(
        "div",
        { className: "mb-5 flex flex-wrap items-end justify-between gap-3" },
        h("div", null,
          h("p", { className: "text-xs uppercase tracking-widest text-orange-300" }, "Dein Marktplatz"),
          h("h2", { className: "mt-1 text-xl font-semibold" }, "AIIANER Erweiterungen"),
          h("p", { className: "text-sm text-muted-foreground mt-1" }, "Installieren, aktuell halten und nach Hermes-Updates entspannt bleiben.")
        ),
        h("div", { className: "flex gap-2 text-xs text-muted-foreground" },
          h(C.Badge, null, items.length + " Komponenten"),
          h(C.Badge, null, installiert + " installiert"),
          updates ? h(C.Badge, { className: "bg-orange-500/20 text-orange-200" }, updates + " Update" + (updates === 1 ? "" : "s")) : null
        )
      ),

      updates
        ? h(
            C.Card,
            { className: "mb-5 rounded-2xl border-orange-500/30 bg-orange-500/10" },
            h(
              C.CardContent,
              { className: "p-4 sm:p-5" },
              h("p", { className: "text-xs uppercase tracking-widest text-orange-300" }, "Updates im Außenposten"),
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
    );
  }

  window.__HERMES_PLUGINS__.register("aiianer-hub", Page);
})();
