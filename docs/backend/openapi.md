# OSSS API (OpenAPI)

> If the panel below stays blank, click this link to verify the JSON exists:
> **[OpenAPI JSON](../openapi.json)**

<div id="redoc-container"></div>

<script>
  (function () {
    function init() {
      var el = document.getElementById('redoc-container');
      if (window.Redoc && el) {
        // From /OSSS/backend/openapi/ → /OSSS/backend/openapi.json
        window.Redoc.init('../openapi.json', {}, el);
      } else {
        setTimeout(init, 50);
      }
    }
    init();
  })();
</script>

<noscript>
  JavaScript is required to render the ReDoc UI. You can still download the
  <a href="../openapi.json">OpenAPI JSON</a>.
</noscript>
