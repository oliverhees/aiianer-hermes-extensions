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
    outdated: "Update verfuegbar",
    missing: "nicht installiert"
  };

  function Row(props) {
    var c = props.item;
    var busy = props.busy === c.id;
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
          isPatch
            ? h(C.Badge, null, "greift in den Checkout ein")
            : h(C.Badge, null, "eigenstaendig")
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
          { className: "mt-3 flex gap-2" },
          h(
            C.Button,
            {
              disabled: busy || c.status === "current",
              onClick: function () {
                props.onInstall(c.id);
              }
            },
            busy
              ? "laeuft ..."
              : c.status === "missing"
              ? "Installieren"
              : c.status === "outdated"
              ? "Aktualisieren"
              : "Installiert"
          )
        )
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

    var e = useState(null);
    var err = e[0];
    var setErr = e[1];

    var hs = useState(null);
    var health = hs[0];
    var setHealth = hs[1];

    function load() {
      SDK.fetchJSON(API + "/catalog")
        .then(function (d) {
          setItems(d.components || []);
          setErr(null);
        })
        .catch(function (x) {
          setErr(String(x && x.message ? x.message : x));
        });
      SDK.fetchJSON(API + "/health")
        .then(setHealth)
        .catch(function () {
          setHealth(null);
        });
    }

    useEffect(function () {
      load();
    }, []);

    function install(id) {
      setBusy(id);
      setErr(null);
      SDK.fetchJSON(API + "/install", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: id })
      })
        .then(function () {
          setBusy(null);
          load();
        })
        .catch(function (x) {
          setBusy(null);
          setErr(String(x && x.message ? x.message : x));
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
          busy: busy,
          onInstall: install
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
