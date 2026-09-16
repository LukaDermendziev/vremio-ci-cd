/**
 * Full-screen page loader for intentional waits (booking submit).
 * Show immediately; optional minimum hold before a callback runs.
 */
(function () {
  const DEFAULT_SUBMIT_HOLD_MS = 900;
  let showTimer = null;
  let active = false;

  function el() {
    return document.getElementById("vm-page-loader");
  }

  function msgEl() {
    return document.getElementById("vm-page-loader-msg");
  }

  function defaultMessage() {
    const root = el();
    return (root && root.dataset.defaultMessage) || "Loading…";
  }

  function submitMessage() {
    const root = el();
    return (root && root.dataset.submitMessage) || defaultMessage();
  }

  function submitHoldMs() {
    const root = el();
    const raw = root && root.dataset.submitHoldMs;
    const n = raw ? parseInt(raw, 10) : DEFAULT_SUBMIT_HOLD_MS;
    return Number.isFinite(n) && n >= 0 ? n : DEFAULT_SUBMIT_HOLD_MS;
  }

  function reveal(root) {
    active = true;
    root.hidden = false;
    root.setAttribute("aria-hidden", "false");
    root.classList.add("is-visible");
    document.documentElement.classList.add("vm-page-loader-open");
  }

  function show(message, options) {
    const root = el();
    if (!root) return;
    const opts = options || {};
    const text = (message && String(message).trim()) || defaultMessage();
    const label = msgEl();
    if (label) label.textContent = text;

    if (showTimer) {
      clearTimeout(showTimer);
      showTimer = null;
    }

    if (opts.immediate) {
      reveal(root);
      return;
    }

    const delay = typeof opts.delayMs === "number" ? opts.delayMs : 0;
    if (delay <= 0) {
      reveal(root);
      return;
    }
    showTimer = setTimeout(() => {
      showTimer = null;
      reveal(root);
    }, delay);
  }

  function hide() {
    const root = el();
    if (showTimer) {
      clearTimeout(showTimer);
      showTimer = null;
    }
    if (!root) return;
    active = false;
    root.classList.remove("is-visible");
    root.setAttribute("aria-hidden", "true");
    root.hidden = true;
    document.documentElement.classList.remove("vm-page-loader-open");
  }

  /**
   * Show submit loader immediately, hold for a minimum duration, then run fn.
   * Used so fast local posts still feel intentional.
   */
  function holdThen(fn, message, holdMs) {
    show(message || submitMessage(), { immediate: true });
    const ms = typeof holdMs === "number" ? holdMs : submitHoldMs();
    window.setTimeout(() => {
      if (typeof fn === "function") fn();
    }, ms);
  }

  window.addEventListener("pageshow", (event) => {
    if (event.persisted || active) hide();
  });

  window.PageLoader = { show, hide, holdThen, submitMessage, submitHoldMs };
})();
