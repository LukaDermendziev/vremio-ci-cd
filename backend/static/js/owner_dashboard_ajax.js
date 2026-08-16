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

  async function confirmAsk(message, options = {}) {
    if (global.OwnerConfirm?.ask) {
      return global.OwnerConfirm.ask(message, options);
    }
    return global.confirm(message);
  }

  function serviceCard(serviceId) {
    return global.document.querySelector(`.od-svc-card[data-service-id="${serviceId}"]`);
  }

  function serviceDeleteMessage(serviceId) {
    const card = serviceId ? serviceCard(serviceId) : null;
    const serviceName = card?.dataset.name?.trim();
    if (serviceName) {
      return t(
        "confirmDeleteServiceNamed",
        `Delete service "${serviceName}"? This cannot be undone.`,
      ).replace("%(name)s", serviceName);
    }
    return t("confirmDeleteService", "Delete this service? This cannot be undone.");
  }

  function removeServiceCard(serviceId) {
    const card = serviceId ? serviceCard(serviceId) : null;
    if (!card) return;
    card.classList.add("od-removing");
    global.setTimeout(() => card.remove(), 200);
  }

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
    if (!global.document.querySelector(".od-modal-overlay.open")) {
      global.document.body.classList.remove("od-modal-open");
    }
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
    OA.bindForm(form, options);
  }

  function bindBookingForm() {
    const form = global.document.getElementById("od-booking-form");
    if (!form || form.dataset.odBookingSameClientBound) return;
    form.dataset.odBookingSameClientBound = "1";

    let submitting = false;

    async function submitBooking(extra = {}) {
      const body = new URLSearchParams(new FormData(form));
      Object.entries(extra).forEach(([key, value]) => {
        body.set(key, value);
      });
      // Only coerce boolean policy-style checkboxes. Never send services=false —
      // ModelMultipleChoiceField treats that as an invalid choice.
      form.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
        if (!cb.name || cb.disabled || cb.name === "services") return;
        if (!body.has(cb.name)) body.append(cb.name, "false");
      });
      return OA.postDashboard(body);
    }

    async function handleSuccess(data) {
      const msg =
        OA.firstMessage(data, "success") ||
        OA.firstMessage(data, "warning") ||
        OA.firstMessage(data, "info") ||
        "";
      if (msg) OA.showToast(msg, "success");
      syncStats(data);
      closeModal("od-booking-modal");
      await calendarRefresh();
      await refreshSection("od-sec-bookings");
      await refreshSection("od-sec-dashboard");
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (submitting) return;

      const hasService = !!form.querySelector('input[name="services"]:checked');
      if (!hasService) {
        OA.showToast(
          t("chooseAtLeastOneService", "Please choose at least one service."),
          "error",
        );
        return;
      }
      const startTime = form.querySelector("#od-booking-start-time")?.value?.trim();
      const slotsSelect = form.querySelector("#od-owner-slots");
      if (slotsSelect?.value) {
        const hiddenStart = form.querySelector("#od-booking-start-time");
        if (hiddenStart) hiddenStart.value = slotsSelect.value;
      }
      if (!(startTime || slotsSelect?.value)) {
        OA.showToast(
          t("chooseStartTime", "Please choose a start time."),
          "error",
        );
        return;
      }

      submitting = true;
      const submitBtn = form.querySelector('[type="submit"]');
      const confirmedInput = form.querySelector("#od-same-client-confirmed");
      if (confirmedInput) confirmedInput.value = "";
      OA.setButtonLoading(submitBtn, true);
      try {
        const data = await submitBooking();
        await handleSuccess(data);
      } catch (err) {
        if (err.data?.code === "phone_match") {
          const existing = err.data.phone_match?.existing_name || "";
          const typed = err.data.phone_match?.typed_name || "";
          const message = t(
            "sameClientConfirm",
            "This phone belongs to %(existing)s. You entered %(typed)s. Is this the same client?",
          )
            .replace("%(existing)s", existing)
            .replace("%(typed)s", typed);
          const same = await confirmAsk(message, {
            title: t("sameClientTitle", "Same client?"),
            confirmLabel: t("sameClientYes", "Yes, same client"),
            cancelLabel: t("sameClientNo", "Different person"),
            danger: false,
          });
          if (same) {
            if (confirmedInput) confirmedInput.value = "1";
            try {
              const data = await submitBooking({ same_client_confirmed: "1" });
              await handleSuccess(data);
            } catch (retryErr) {
              OA.showToast(
                retryErr.message || t("somethingWentWrong", "Something went wrong."),
                "error",
              );
            }
          } else {
            OA.showToast(
              t(
                "sameClientUseDifferentPhone",
                "Use a different phone number for a different person.",
              ),
              "error",
            );
            form.querySelector('[name="phone_number"]')?.focus();
          }
        } else {
          OA.showToast(
            err.message || t("somethingWentWrong", "Something went wrong."),
            "error",
          );
        }
      } finally {
        submitting = false;
        OA.setButtonLoading(submitBtn, false);
      }
    });
  }

  function bindPolicyForm() {
    bindAjaxForm(global.document.getElementById("od-policy-form"), {
      onSuccess: async () => {
        await refreshSection("od-sec-policy");
      },
    });
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
        let confirmMsg;
        if (action === "delete_price_item") {
          confirmMsg = t("confirmDeletePriceItem", "Delete this price item?");
        } else if (action === "delete_blocked_date") {
          const ids = (form.querySelector('[name="override_ids"]')?.value || "")
            .split(",")
            .map((part) => part.trim())
            .filter(Boolean);
          confirmMsg =
            ids.length > 1
              ? t("confirmRemoveBlockedDates", "Remove these blocked dates?")
              : t("confirmRemoveBlockedDate", "Remove this blocked date?");
        } else {
          const serviceId = form.querySelector('[name="service_id"]')?.value;
          confirmMsg = serviceDeleteMessage(serviceId);
        }
        if (!(await confirmAsk(confirmMsg))) return;
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
            const serviceId =
              data.payload?.deleted_service_id ||
              form.querySelector('[name="service_id"]')?.value;
            removeServiceCard(serviceId);
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
      let confirmMsg = t(confirmKey, confirmFallback);
      if (formId === "od-service-delete-form") {
        const serviceId = form.querySelector('[name="service_id"]')?.value;
        confirmMsg = serviceDeleteMessage(serviceId);
      }
      if (!(await confirmAsk(confirmMsg))) return;
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
    bindBookingForm();

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
        await refreshSection("od-sec-customers", window.odRebindDashboard);
      },
    });

    bindAjaxForm(global.document.getElementById("od-price-item-form"), {
      closeModal: "od-price-modal",
      onSuccess: async (_data, form) => {
        form.querySelector('[name="item_id"]')?.setAttribute("value", "");
        form.reset();
        const sortInput = form.querySelector('[name="item_sort"]');
        if (sortInput) sortInput.value = "0";
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

    bindAjaxForm(global.document.getElementById("od-working-hours-form"), {
      onSuccess: async () => {
        await calendarRefresh();
      },
    });

    bindAjaxForm(global.document.getElementById("od-public-hours-form"), {
      onSuccess: async () => {},
    });

    bindPolicyForm();

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
      "Delete this service? This cannot be undone.",
      async (data) => {
        const deletedId =
          data.payload?.deleted_service_id ||
          global.document
            .getElementById("od-service-delete-form")
            ?.querySelector('[name="service_id"]')
            ?.value;
        removeServiceCard(deletedId);
        closeModal("od-service-modal");
      },
    );

    bindDeleteViaPostForm(
      "od-customer-delete-form",
      "od-customer-delete",
      "confirmDeleteCustomer",
      "Delete this customer?",
      async () => {
        closeModal("od-customer-modal");
        await refreshSection("od-sec-customers", window.odRebindDashboard);
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
  global.odBindInlineDeleteForms = bindInlineDeleteForms;
  global.odBindPolicyForm = bindPolicyForm;
  initOwnerDashboardAjax();
  global.document.addEventListener("od:rebind", bindPolicyForm);
})(window);
