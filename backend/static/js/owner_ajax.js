/**
 * Shared Fetch helpers for owner dashboard async form actions.
 */
(function initOwnerAjax(global) {
  const DASHBOARD_URL = "/owner/dashboard/";

  function getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  }

  function showToast(msg, type = "success") {
    let toast = document.getElementById("od-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "od-toast";
      toast.className = "od-toast";
      toast.setAttribute("role", "status");
      toast.setAttribute("aria-live", "polite");
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.className = `od-toast od-toast-${type} od-toast-show`;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove("od-toast-show"), 3500);
  }

  function setButtonLoading(btn, loading) {
    if (!btn) return;
    if (loading) {
      btn.dataset.odPrevDisabled = btn.disabled ? "1" : "";
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
      btn.classList.add("is-loading");
    } else {
      btn.disabled = btn.dataset.odPrevDisabled === "1";
      btn.removeAttribute("aria-busy");
      btn.classList.remove("is-loading");
    }
  }

  function firstMessage(data, level = "success") {
    const msg = (data.messages || []).find((m) => m[0] === level);
    return msg ? msg[1] : "";
  }

  async function postDashboard(body) {
    const resp = await fetch(DASHBOARD_URL, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCsrfToken(),
        "X-Requested-With": "fetch",
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
    });
    let data = {};
    try {
      data = await resp.json();
    } catch (_) {
      throw new Error("Invalid server response");
    }
    if (!resp.ok || data.ok === false) {
      const errMsg =
        data.error ||
        firstMessage(data, "error") ||
        firstMessage(data, "danger") ||
        "Something went wrong.";
      const err = new Error(errMsg);
      err.data = data;
      throw err;
    }
    return data;
  }

  async function refreshSection(sectionId, rebind) {
    const scrollY = window.scrollY;
    const hash = window.location.hash || "";
    const resp = await fetch(`${DASHBOARD_URL}${hash}`, {
      headers: { "X-Requested-With": "fetch" },
    });
    if (!resp.ok) return;
    const html = await resp.text();
    const doc = new DOMParser().parseFromString(html, "text/html");
    const fresh = doc.getElementById(sectionId);
    const current = document.getElementById(sectionId);
    if (!fresh || !current) return;
    current.innerHTML = fresh.innerHTML;
    window.scrollTo(0, scrollY);
    if (typeof rebind === "function") rebind();
  }

  function bindForm(form, options = {}) {
    if (!form) return;
    if (form._odSubmitHandler) {
      form.removeEventListener("submit", form._odSubmitHandler);
      form._odSubmitHandler = null;
    }
    form.dataset.odAjaxBound = "1";
    let submitting = false;
    form._odSubmitHandler = async (e) => {
      e.preventDefault();
      if (submitting) return;
      submitting = true;
      const submitBtn = form.querySelector('[type="submit"]') || options.loadingBtn;
      setButtonLoading(submitBtn, true);
      try {
        const body = new URLSearchParams(new FormData(form));
        const data = await postDashboard(body);
        const msg =
          firstMessage(data, "success") ||
          firstMessage(data, "warning") ||
          firstMessage(data, "info") ||
          options.successMessage ||
          "";
        if (msg) showToast(msg, "success");
        if (options.closeModal) {
          const modalId = typeof options.closeModal === "string" ? options.closeModal : null;
          if (modalId) {
            document.getElementById(modalId)?.classList.remove("open");
            document.body.classList.remove("od-modal-open");
          }
        }
        if (options.onSuccess) await options.onSuccess(data, form);
      } catch (err) {
        showToast(err.message || "Something went wrong.", "error");
        if (options.onError) options.onError(err, form);
      } finally {
        submitting = false;
        setButtonLoading(submitBtn, false);
      }
    };
    form.addEventListener("submit", form._odSubmitHandler);
  }

  async function postAction(params, options = {}) {
    const submitBtn = options.loadingBtn;
    setButtonLoading(submitBtn, true);
    try {
      const body =
        params instanceof URLSearchParams ? params : new URLSearchParams(params);
      const data = await postDashboard(body);
      const msg = firstMessage(data, "success") || options.successMessage || "";
      if (msg) showToast(msg, "success");
      if (options.onSuccess) await options.onSuccess(data);
      return data;
    } catch (err) {
      showToast(err.message || "Something went wrong.", "error");
      if (options.onError) options.onError(err);
      throw err;
    } finally {
      setButtonLoading(submitBtn, false);
    }
  }

  global.OwnerAjax = {
    postDashboard,
    bindForm,
    postAction,
    refreshSection,
    showToast,
    setButtonLoading,
    getCsrfToken,
    firstMessage,
  };
})(window);
