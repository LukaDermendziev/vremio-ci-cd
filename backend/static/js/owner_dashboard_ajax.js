/**
 * Async form bindings for owner dashboard (uses OwnerAjax).
 */
(function initOwnerDashboardAjax(global) {
  const OA = global.OwnerAjax;
  if (!OA) return;

  const t = (key, fallback) => {
    const i18n = global.OD_I18N || {};
    return i18n[key] != null && i18n[key] !== "" ? i18n[key] : fallback;
  };

  function syncStats(data) {
    const stats = data.payload?.stats || {};
    if (stats.pending_count !== undefined) {
      global.document.querySelectorAll('[data-stat="pending"]').forEach((el) => {
        el.textContent = String(stats.pending_count);
        if (el.tagName === "EM" && el.closest(".od-quick-action")) {
          el.hidden = stats.pending_count === 0;
        }
      });
    }
    if (stats.today_count !== undefined) {
      global.document.querySelectorAll('[data-stat="today"]').forEach((el) => {
        el.textContent = String(stats.today_count);
      });
    }
  }

  function closeModal(id) {
    global.document.getElementById(id)?.classList.remove("open");
    global.document.body.classList.remove("od-modal-open");
  }

  async function refreshSection(sectionId) {
    await OA.refreshSection(sectionId, () => {
      global.document.dispatchEvent(new CustomEvent("od:rebind"));
    });
  }

  async function calendarRefresh() {
    if (typeof global.odCgFetchAndRender === "function") {
      await global.odCgFetchAndRender();
    }
  }

  function bindAjaxForm(form, options) {
    if (!form) return;
    delete form.dataset.odAjaxBound;
    OA.bindForm(form, options);
  }

  function bindInlineDeleteForms() {
    global.document.querySelectorAll('form input[name="action"]').forEach((input) => {
      const form = input.closest("form");
      if (!form || form.dataset.odInlineDeleteBound) return;
      const action = input.value;
      if (
        ![
          "delete_price_item",
          "delete_blocked_date",
          "delete_service",
        ].includes(action)
      ) {
        return;
      }
      form.dataset.odInlineDeleteBound = "1";
      form.addEventListener("submit", async (e) => {
        e.preventDefault();
        const confirmMsg =
          action === "delete_price_item"
            ? t("confirmDeletePriceItem", "Delete this price item?")
            : action === "delete_blocked_date"
              ? t("confirmRemoveBlockedDate", "Remove this blocked date?")
              : t("confirmDeleteService", "Delete this service?");
        if (!confirm(confirmMsg)) return;
        const submitBtn = form.querySelector('[type="submit"]');
        OA.setButtonLoading(submitBtn, true);
        try {
          const body = new URLSearchParams(new FormData(form));
          const data = await OA.postDashboard(body);
          const msg = OA.firstMessage(data, "success");
          if (msg) OA.showToast(msg, "success");
          syncStats(data);
          if (action === "delete_price_item") {
            form.closest("tr")?.remove();
          } else if (action === "delete_blocked_date") {
            form.closest("li")?.remove();
          } else if (action === "delete_service") {
            const serviceId = form.querySelector('[name="service_id"]')?.value;
            global.document
              .querySelector(`.od-svc-row[data-service-id="${serviceId}"]`)
              ?.remove();
          }
          await calendarRefresh();
        } catch (err) {
          OA.showToast(err.message || t("somethingWentWrong", "Something went wrong."), "error");
        } finally {
          OA.setButtonLoading(submitBtn, false);
        }
      });
    });
  }

  function bindDeleteViaPostForm(formId, buttonId, confirmKey, confirmFallback, onSuccess) {
    const form = global.document.getElementById(formId);
    const btn = global.document.getElementById(buttonId);
    if (!form || !btn || btn.dataset.odDeleteBound) return;
    btn.dataset.odDeleteBound = "1";
    btn.addEventListener("click", async () => {
      if (!confirm(t(confirmKey, confirmFallback))) return;
      OA.setButtonLoading(btn, true);
      try {
        const body = new URLSearchParams(new FormData(form));
        const data = await OA.postDashboard(body);
        const msg = OA.firstMessage(data, "success");
        if (msg) OA.showToast(msg, "success");
        syncStats(data);
        if (onSuccess) await onSuccess(data);
      } catch (err) {
        OA.showToast(err.message || t("somethingWentWrong", "Something went wrong."), "error");
      } finally {
        OA.setButtonLoading(btn, false);
      }
    });
  }

  function initOwnerDashboardAjax() {
    bindAjaxForm(global.document.getElementById("od-booking-form"), {
      closeModal: "od-booking-modal",
      onSuccess: async (data) => {
        syncStats(data);
        closeModal("od-booking-modal");
        await calendarRefresh();
        await refreshSection("od-sec-bookings");
        await refreshSection("od-sec-dashboard");
      },
    });

    bindAjaxForm(global.document.getElementById("od-service-form"), {
      closeModal: "od-service-modal",
      onSuccess: async () => {
        closeModal("od-service-modal");
        await refreshSection("od-sec-services");
      },
    });

    bindAjaxForm(global.document.getElementById("od-customer-form"), {
      closeModal: "od-customer-modal",
      onSuccess: async () => {
        closeModal("od-customer-modal");
        await refreshSection("od-sec-customers");
      },
    });

    bindAjaxForm(global.document.getElementById("od-price-item-form"), {
      closeModal: "od-price-modal",
      onSuccess: async () => {
        closeModal("od-price-modal");
        await refreshSection("od-sec-services");
      },
    });

    bindAjaxForm(global.document.getElementById("od-blocked-date-form"), {
      closeModal: "od-blocked-date-modal",
      onSuccess: async () => {
        closeModal("od-blocked-date-modal");
        await calendarRefresh();
        await refreshSection("od-sec-availability");
      },
    });

    bindAjaxForm(global.document.getElementById("od-block-form"), {
      closeModal: "od-block-modal",
      onSuccess: async () => {
        closeModal("od-block-modal");
        await calendarRefresh();
        await refreshSection("od-sec-availability");
      },
    });

    bindAjaxForm(global.document.querySelector("#od-sec-hours form"), {
      onSuccess: async () => {
        await calendarRefresh();
      },
    });

    bindAjaxForm(global.document.getElementById("od-policy-form"), {
      onSuccess: async () => {},
    });

    bindDeleteViaPostForm(
      "od-booking-delete-form",
      "od-booking-delete",
      "confirmDeleteBooking",
      "Delete this booking permanently?",
      async (data) => {
        const deletedId = data.payload?.deleted_booking_id;
        if (deletedId) {
          global.document
            .querySelectorAll(`.od-bk-card[data-booking-id="${deletedId}"]`)
            .forEach((card) => card.remove());
        }
        closeModal("od-booking-modal");
        syncStats(data);
        await calendarRefresh();
        await refreshSection("od-sec-bookings");
        await refreshSection("od-sec-dashboard");
      },
    );

    bindDeleteViaPostForm(
      "od-service-delete-form",
      "od-service-delete",
      "confirmDeleteService",
      "Delete this service?",
      async () => {
        closeModal("od-service-modal");
        await refreshSection("od-sec-services");
      },
    );

    bindDeleteViaPostForm(
      "od-customer-delete-form",
      "od-customer-delete",
      "confirmDeleteCustomer",
      "Delete this customer?",
      async () => {
        closeModal("od-customer-modal");
        await refreshSection("od-sec-customers");
      },
    );

    bindDeleteViaPostForm(
      "od-block-delete-form",
      "od-block-delete",
      "confirmRemoveTimeBlock",
      "Remove this time block?",
      async () => {
        closeModal("od-block-modal");
        await calendarRefresh();
        await refreshSection("od-sec-availability");
      },
    );

    bindInlineDeleteForms();
  }

  global.initOwnerDashboardAjax = initOwnerDashboardAjax;
  initOwnerDashboardAjax();
})(window);
