(function () {
  "use strict";

  var form = document.getElementById("bk-manage-cancel-form");
  if (!form) return;

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    var btn = document.getElementById("bk-manage-cancel-btn");
    var csrf = form.querySelector("[name=csrfmiddlewaretoken]")?.value;
    if (btn) {
      btn.disabled = true;
      btn.setAttribute("aria-busy", "true");
    }
    try {
      var resp = await fetch(form.action, {
        method: "POST",
        headers: {
          "X-CSRFToken": csrf,
          "X-Requested-With": "fetch",
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body: new URLSearchParams(new FormData(form)),
      });
      var data = {};
      try {
        data = await resp.json();
      } catch (_) {
        throw new Error("Invalid response");
      }
      if (!resp.ok || !data.ok) {
        throw new Error(data.error || "Could not cancel appointment.");
      }
      var card = form.closest(".bk-manage-card");
      if (card) {
        card.innerHTML =
          '<div class="bk-manage-success-icon"><i class="bi bi-check-circle-fill"></i></div>' +
          '<h1 class="bk-manage-title">Appointment cancelled.</h1>' +
          '<p class="bk-manage-lead">Thank you for letting us know. The salon has been notified.</p>';
        card.classList.add("bk-manage-success-card");
      }
    } catch (err) {
      var alertBox = document.createElement("div");
      alertBox.className = "bk-manage-alert bk-manage-alert-error";
      alertBox.textContent = err.message || "Something went wrong.";
      form.parentElement?.insertBefore(alertBox, form);
      if (btn) {
        btn.disabled = false;
        btn.removeAttribute("aria-busy");
      }
    }
  });
})();
