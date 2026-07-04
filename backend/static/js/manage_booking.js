(function () {
  "use strict";

  const I18N = window.MANAGE_I18N || {};

  const form = document.getElementById("bk-manage-cancel-form");
  if (!form) return;

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    const btn = document.getElementById("bk-manage-cancel-btn");
    const csrf = form.querySelector("[name=csrfmiddlewaretoken]")?.value;
    if (btn) {
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
    }
    try {
      const resp = await fetch(form.action, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrf,
          "X-Requested-With": "fetch",
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams(new FormData(form)),
      });
      let data = {};
      try {
        data = await resp.json();
      } catch (_) {
        throw new Error("Invalid response");
      }
      if (!resp.ok || !data.ok) {
        throw new Error(data.error || I18N.cancelError || "Could not cancel appointment.");
      }
      const card = form.closest(".bk-manage-card");
      if (card) {
        card.innerHTML =
          '<div class="bk-manage-success-icon"><i class="bi bi-check-circle-fill"></i></div>' +
          `<h1 class="bk-manage-title">${I18N.cancelledTitle || "Appointment cancelled."}</h1>` +
          `<p class="bk-manage-lead">${I18N.cancelledLead || "Thank you for letting us know. The salon has been notified."}</p>`;
        card.classList.add("bk-manage-success-card");
      }
    } catch (err) {
      const alertBox = document.createElement("div");
      alertBox.className = "bk-manage-alert bk-manage-alert-error";
      alertBox.textContent = err.message || I18N.genericError || "Something went wrong.";
      form.parentElement?.insertBefore(alertBox, form);
      if (btn) {
        btn.disabled = false;
        btn.removeAttribute("aria-busy");
      }
    }
  });
})();
