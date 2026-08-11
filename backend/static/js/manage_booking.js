(function () {
  "use strict";

  const I18N = window.MANAGE_I18N || {};

  const form = document.getElementById("bk-manage-cancel-form");
  if (!form) return;

  function cancelMessage() {
    const root = document.getElementById("vm-page-loader");
    return (
      (root && root.dataset.cancelMessage) ||
      I18N.cancelling ||
      "Cancelling your booking…"
    );
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    const btn = document.getElementById("bk-manage-cancel-btn");
    const csrf = form.querySelector("[name=csrfmiddlewaretoken]")?.value;
    if (btn) {
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
    }

    // Same intentional hold as booking "Send request": show overlay first,
    // then run the cancel after the minimum hold so it is always visible.
    const cancel = async function () {
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
        if (window.PageLoader) window.PageLoader.hide();
        const card = form.closest(".bk-manage-card");
        if (card) {
          card.innerHTML =
            '<div class="bk-manage-success-icon" aria-hidden="true">' +
              '<svg class="bk-check-svg bk-manage-check-svg" viewBox="0 0 60 60" fill="none" xmlns="http://www.w3.org/2000/svg">' +
                '<circle class="bk-check-circle bk-manage-check-circle" cx="30" cy="30" r="26" stroke-width="2.5" stroke-linecap="round"/>' +
                '<polyline class="bk-check-mark bk-manage-check-mark" points="16,31 25,40 44,20" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>' +
              "</svg>" +
            "</div>" +
            `<h1 class="bk-manage-title">${I18N.cancelledTitle || "Appointment cancelled."}</h1>` +
            `<p class="bk-manage-lead">${I18N.cancelledLead || "Thank you for letting us know. The salon has been notified."}</p>`;
          card.classList.add("bk-manage-success-card");
        }
      } catch (err) {
        if (window.PageLoader) window.PageLoader.hide();
        const alertBox = document.createElement("div");
        alertBox.className = "bk-manage-alert bk-manage-alert-error";
        alertBox.textContent = err.message || I18N.genericError || "Something went wrong.";
        form.parentElement?.insertBefore(alertBox, form);
        if (btn) {
          btn.disabled = false;
          btn.removeAttribute("aria-busy");
        }
      }
    };

    if (window.PageLoader && typeof window.PageLoader.holdThen === "function") {
      window.PageLoader.holdThen(cancel, cancelMessage());
    } else {
      cancel();
    }
  });
})();
