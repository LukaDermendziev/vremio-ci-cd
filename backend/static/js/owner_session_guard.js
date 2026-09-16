/**
 * If the owner dashboard is restored from the browser back-forward cache,
 * force a fresh server request so logged-out users cannot view stale pages.
 */
(function () {
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) {
      window.location.reload();
    }
  });
})();
