/* Lightweight photo preview + owner booking photo actions for standalone owner pages. */

(function initOwnerPhotoTools() {
  const photoModal = document.getElementById("od-photo-modal");
  if (!photoModal || photoModal.dataset.odPhotoToolsInit) return;
  photoModal.dataset.odPhotoToolsInit = "1";

  const I18N = window.OD_I18N || {};
  const t = (key, fallback) => (I18N[key] != null && I18N[key] !== "") ? I18N[key] : fallback;

  function openModal(id) {
    document.getElementById(id)?.classList.add("open");
  }

  function closeModal(id) {
    document.getElementById(id)?.classList.remove("open");
  }

  function openPhotoPreview(url, trigger) {
    if (!url) return;
    const img = document.getElementById("od-photo-modal-img");
    const link = document.getElementById("od-photo-modal-open");
    const blockBtn = document.getElementById("od-photo-modal-block");
    const blockSource = trigger?.closest(".od-photo-actions")?.querySelector("[data-open-block-customer]") || trigger;
    if (img) img.src = url;
    if (link) link.href = url;
    if (blockBtn && blockSource?.dataset?.customerId) {
      blockBtn.hidden = false;
      blockBtn.dataset.customerId = blockSource.dataset.customerId || "";
      blockBtn.dataset.bookingId = blockSource.dataset.bookingId || trigger?.closest(".od-photo-controls")?.dataset.bookingId || "";
      blockBtn.dataset.customerName = blockSource.dataset.customerName || "";
      blockBtn.dataset.phone = blockSource.dataset.phone || "";
      blockBtn.dataset.email = blockSource.dataset.email || "";
      blockBtn.dataset.bookingReference = blockSource.dataset.bookingReference || "";
    } else if (blockBtn) {
      blockBtn.hidden = true;
    }
    openModal("od-photo-modal");
  }

  document.addEventListener("click", (e) => {
    const trigger = e.target.closest("[data-photo-preview]");
    if (!trigger) return;
    e.preventDefault();
    openPhotoPreview(trigger.dataset.photoPreview, trigger);
  });

  document.querySelectorAll("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", () => closeModal(btn.dataset.closeModal));
  });

  photoModal.addEventListener("click", (e) => {
    if (e.target === photoModal) closeModal("od-photo-modal");
  });

  const CONFIRM_ACTIONS = {
    delete_reference_photo: t("confirmDeletePhoto", "Delete this reference photo?"),
  };

  function showToast(msg, type = "success") {
    let toast = document.getElementById("od-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "od-toast";
      toast.className = "od-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.className = `od-toast od-toast-${type} od-toast-show`;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => toast.classList.remove("od-toast-show"), 3200);
  }

  async function sendBookingAction(action, bookingId, card) {
    const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
    const body = new URLSearchParams({
      action,
      booking_id: bookingId,
      return_section: "customers",
    });
    try {
      const resp = await fetch("/owner/dashboard/", {
        method: "POST",
        headers: {
          "X-CSRFToken": csrf,
          "X-Requested-With": "fetch",
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body,
      });
      if (!resp.ok) throw new Error("Server error");
      const data = await resp.json();
      if (!data.ok) throw new Error("Action failed");

      const msg = (data.messages || []).find((m) => m[0] === "success");

      if (action === "delete_reference_photo") {
        if (card) {
          const photoControls = card.querySelector(".od-photo-controls");
          if (photoControls) {
            photoControls.outerHTML = `<p class="od-photo-none">${t("noPhotoAttached", "No photo attached.")}</p>`;
          }
        }
        showToast(msg ? msg[1] : t("photoRemoved", "Photo removed."));
      }
    } catch (err) {
      showToast(t("somethingWentWrong", "Something went wrong. Please try again."), "error");
      console.error(err);
    }
  }

  function bindBkAction(btn) {
    if (btn.dataset.odBkBound) return;
    btn.dataset.odBkBound = "1";
    btn.addEventListener("click", async () => {
      const action = btn.dataset.bkAction;
      const bookingId = btn.dataset.bkId;
      const card = btn.closest(".od-bk-card");
      if (CONFIRM_ACTIONS[action] && !confirm(CONFIRM_ACTIONS[action])) return;
      btn.disabled = true;
      await sendBookingAction(action, bookingId, card);
      btn.disabled = false;
    });
  }

  document.querySelectorAll("[data-bk-action]").forEach(bindBkAction);
})();
