/**
 * In-app confirmation dialog for owner dashboard (replaces window.confirm).
 */
(function initOwnerConfirm(global) {
  let resolvePending = null;

  function getEls() {
    return {
      modal: global.document.getElementById("od-confirm-modal"),
      title: global.document.getElementById("od-confirm-title"),
      message: global.document.getElementById("od-confirm-message"),
      okBtn: global.document.getElementById("od-confirm-ok"),
      cancelBtn: global.document.getElementById("od-confirm-cancel"),
    };
  }

  function t(key, fallback) {
    const i18n = global.OD_I18N || {};
    return i18n[key] != null && i18n[key] !== "" ? i18n[key] : fallback;
  }

  function finish(result) {
    const { modal } = getEls();
    if (modal) {
      modal.classList.remove("open");
      modal.setAttribute("hidden", "");
    }
    if (!global.document.querySelector(".od-modal-overlay.open")) {
      global.document.body.classList.remove("od-modal-open");
    }
    const resolve = resolvePending;
    resolvePending = null;
    if (resolve) resolve(result);
  }

  function bind() {
    const { modal, okBtn, cancelBtn } = getEls();
    if (!modal || modal.dataset.odConfirmBound) return;
    modal.dataset.odConfirmBound = "1";

    cancelBtn?.addEventListener("click", () => finish(false));
    okBtn?.addEventListener("click", () => finish(true));
    modal.addEventListener("click", (e) => {
      if (e.target === modal) finish(false);
    });
    global.document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && modal.classList.contains("open")) finish(false);
    });
  }

  function ask(message, options = {}) {
    bind();
    const { modal, title, message: msgEl, okBtn, cancelBtn } = getEls();
    if (!modal || !msgEl) {
      return Promise.resolve(global.confirm(message));
    }

    return new Promise((resolve) => {
      resolvePending = resolve;
      title.textContent = options.title || t("confirmTitle", "Are you sure?");
      msgEl.textContent = message;
      okBtn.textContent = options.confirmLabel || t("confirmDelete", "Delete");
      cancelBtn.textContent = options.cancelLabel || t("confirmCancel", "Cancel");
      okBtn.className = options.danger === false ? "od-btn od-btn-primary" : "od-btn od-btn-danger";
      modal.removeAttribute("hidden");
      modal.classList.add("open");
      global.document.body.classList.add("od-modal-open");
      cancelBtn?.focus();
    });
  }

  global.OwnerConfirm = { ask };

  if (global.document.readyState === "loading") {
    global.document.addEventListener("DOMContentLoaded", bind);
  } else {
    bind();
  }
})(window);
