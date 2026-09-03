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
          h(C.Badge, null, LABEL[c.status] || c.status),
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
          laufend
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
                h(
                  C.Button,
                  { key: "del", variant: "outline", onClick: function () { props.onAktion(c.id, "uninstall"); } },
                  "Deinstallieren"
                )
              ]
        ),

        // Nach der Aktion: was der Nutzer jetzt tun muss. Ohne das erwartet er,
        // dass die Oberflaeche sofort deutsch ist, und das ist sie nicht.
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
          : !laufend && c.status === "missing" && (c.nextSteps || []).length
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
            n[id] = { ok: true, nextSteps: (antwort && antwort.nextSteps) || [] };
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

    return h(
      "div",
      { className: "p-4 max-w-3xl" },
      h(
        "div",
        { className: "mb-4" },
        h(
          "h2",
          { className: "text-lg font-semibold" },
          "AIIANER Erweiterungen"
        ),
        h(
          "p",
          { className: "text-sm text-muted-foreground mt-1" },
          "Deutsche Sprache und die AIIANER-Werkzeuge fuer Hermes. Was hier " +
            "installiert wird, ueberlebt Hermes-Updates."
        )
      ),

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
