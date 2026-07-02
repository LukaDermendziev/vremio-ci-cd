/**
 * Unified customer blocking UI for owner dashboard and standalone owner pages.
 */
(function initOwnerBlockCustomer(global) {
  const MODAL_ID = "od-block-customer-modal";
  const VIEW_MODAL_ID = "od-block-customer-view-modal";

  function t(key, fallback) {
    const i18n = global.OD_I18N || {};
    return i18n[key] != null && i18n[key] !== "" ? i18n[key] : fallback;
  }

  function tf(key, fallback, params) {
    let text = t(key, fallback);
    if (params) {
      Object.entries(params).forEach(([name, value]) => {
        text = text.replace(new RegExp(`%\\(${name}\\)s`, "g"), value);
      });
    }
    return text;
  }

  function openModal(id) {
    document.getElementById(id)?.classList.add("open");
  }

  function closeModal(id) {
    document.getElementById(id)?.classList.remove("open");
  }

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

  function getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  }

  let config = {};
  let viewEntryId = null;

  function setSummaryField(id, value, rowId) {
    const el = document.getElementById(id);
    const row = rowId ? document.getElementById(rowId) : null;
    if (!el) return;
    if (value) {
      el.textContent = value;
      if (row) row.hidden = false;
    } else {
      el.textContent = "—";
      if (row) row.hidden = true;
    }
  }

  function populateBlockForm(data, mode = "block") {
    const form = document.getElementById("od-block-customer-form");
    if (!form) return;

    document.getElementById("od-block-customer-id").value = data.customer_id || "";
    document.getElementById("od-block-booking-id").value = data.booking_id || "";
    document.getElementById("od-block-entry-id").value = data.block_entry_id || data.entry_id || "";

    setSummaryField("od-block-customer-name", data.customer_name);
    setSummaryField("od-block-customer-phone", data.phone_number);
    setSummaryField("od-block-customer-email", data.email, "od-block-customer-email-row");
    setSummaryField("od-block-booking-ref", data.booking_reference, "od-block-booking-ref-row");

    const reasonField = document.getElementById("od-block-reason-field");
    const confirmText = document.getElementById("od-block-confirm-text");
    const submitBtn = document.getElementById("od-block-customer-submit");
    const title = document.getElementById("od-block-customer-modal-title");
    const reasonSelect = document.getElementById("od-block-reason-code");
    const notesInput = document.getElementById("od-block-notes");

    if (mode === "edit") {
      title.textContent = t("editBlockReason", "Edit block reason");
      submitBtn.textContent = t("saveChanges", "Save changes");
      confirmText.hidden = true;
      reasonSelect.value = data.reason_code || "";
      notesInput.value = data.notes || "";
      document.getElementById("od-block-entry-id").value = data.entry_id || data.block_entry_id || "";
    } else {
      title.textContent = t("blockCustomer", "Block customer");
      submitBtn.textContent = t("blockCustomer", "Block customer");
      confirmText.hidden = false;
      reasonSelect.value = "";
      notesInput.value = "";
      document.getElementById("od-block-entry-id").value = "";
      if (form) {
        delete form.dataset.editMode;
      }
      if (submitBtn) {
        delete submitBtn.dataset.mode;
      }
    }

    if (data.is_blocked && mode !== "edit") {
      submitBtn.disabled = true;
      submitBtn.textContent = t("alreadyBlocked", "Already blocked");
    } else {
      submitBtn.disabled = false;
    }
  }

  async function fetchBlockContext({ customerId, bookingId }) {
    const params = new URLSearchParams();
    if (customerId) params.set("customer_id", customerId);
    if (bookingId) params.set("booking_id", bookingId);
    const resp = await fetch(`${config.contextUrl}?${params.toString()}`);
    if (!resp.ok) throw new Error("Failed to load customer");
    return resp.json();
  }

  async function openBlockCustomerModal(preset = {}) {
    const modal = document.getElementById(MODAL_ID);
    if (!modal) return;

    let data = { ...preset };
    if (!data.customer_name && (preset.customerId || preset.bookingId || preset.customer_id || preset.booking_id)) {
      try {
        data = await fetchBlockContext({
          customerId: preset.customerId || preset.customer_id,
          bookingId: preset.bookingId || preset.booking_id,
        });
      } catch (err) {
        showToast(t("somethingWentWrong", "Something went wrong. Please try again."), "error");
        console.error(err);
        return;
      }
    }

    populateBlockForm(data, preset.mode || "block");
    openModal(MODAL_ID);
  }

  function renderViewModal(data) {
    const body = document.getElementById("od-block-customer-view-body");
    if (!body) return;

    const eventsHtml = (data.events || [])
      .map(
        (event) => `
          <div class="od-block-event">
            <strong>${event.event_label}</strong>
            <span>${event.performed_by || ""}</span>
            <time>${new Date(event.created_at).toLocaleString()}</time>
            ${event.notes ? `<p>${event.notes}</p>` : ""}
          </div>
        `,
      )
      .join("");

    body.innerHTML = `
      <div class="od-block-customer-summary">
        <div class="od-block-customer-row"><span class="od-block-label">${t("customer", "Customer")}</span><strong>${data.customer_name || "—"}</strong></div>
        <div class="od-block-customer-row"><span class="od-block-label">${t("phone", "Phone")}</span><span>${data.phone_number || "—"}</span></div>
        ${data.email ? `<div class="od-block-customer-row"><span class="od-block-label">${t("email", "Email")}</span><span>${data.email}</span></div>` : ""}
        <div class="od-block-customer-row"><span class="od-block-label">${t("dateBlocked", "Date blocked")}</span><span>${data.blocked_at ? new Date(data.blocked_at).toLocaleString() : "—"}</span></div>
        <div class="od-block-customer-row"><span class="od-block-label">${t("reason", "Reason")}</span><span>${data.reason_label || "—"}</span></div>
        <div class="od-block-customer-row"><span class="od-block-label">${t("status", "Status")}</span><span>${data.is_active ? t("blocked", "Blocked") : t("unblocked", "Unblocked")}</span></div>
        ${data.notes ? `<div class="od-block-customer-row"><span class="od-block-label">${t("notes", "Notes")}</span><span>${data.notes}</span></div>` : ""}
      </div>
      ${eventsHtml ? `<div class="od-block-events"><div class="od-field-label">${t("auditLog", "Audit log")}</div>${eventsHtml}</div>` : ""}
    `;

    viewEntryId = data.id;
    const unblockBtn = document.getElementById("od-block-customer-unblock-btn");
    const editBtn = document.getElementById("od-block-customer-edit-btn");
    if (unblockBtn) unblockBtn.hidden = !data.is_active;
    if (editBtn) editBtn.hidden = !data.is_active;
  }

  async function openBlockCustomerView(entryId) {
    const resp = await fetch(`${config.detailUrlBase}${entryId}/`);
    if (!resp.ok) {
      showToast(t("somethingWentWrong", "Something went wrong. Please try again."), "error");
      return;
    }
    renderViewModal(await resp.json());
    openModal(VIEW_MODAL_ID);
  }

  async function submitBlockForm(event) {
    event.preventDefault();
    const form = event.target;
    const submitBtn = document.getElementById("od-block-customer-submit");
    const entryId = document.getElementById("od-block-entry-id").value;
    const mode = submitBtn?.dataset.mode || (entryId && form.dataset.editMode === "1" ? "edit" : "block");

    const body = new URLSearchParams(new FormData(form));
    let url = config.blockUrl;
    if (mode === "edit" && entryId) {
      url = `${config.updateUrlBase}${entryId}/update/`;
    }

    submitBtn.disabled = true;
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "fetch",
          "Content-Type": "application/x-www-form-urlencoded",
        },
        body,
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) {
        throw new Error(data.error || "Request failed");
      }
      closeModal(MODAL_ID);
      showToast(
        mode === "edit"
          ? t("blockReasonUpdated", "Block reason updated.")
          : t("customerBlocked", "Customer blocked."),
      );
      const formEl = document.getElementById("od-block-customer-form");
      if (formEl) delete formEl.dataset.editMode;
      if (submitBtn) delete submitBtn.dataset.mode;
      document.dispatchEvent(new CustomEvent("od:customer-blocked", { detail: data.entry }));
    } catch (err) {
      showToast(err.message || t("somethingWentWrong", "Something went wrong. Please try again."), "error");
    } finally {
      submitBtn.disabled = false;
    }
  }

  async function unblockCurrentEntry() {
    if (!viewEntryId) return;
    if (!confirm(t("confirmUnblockCustomer", "Unblock this customer? They will be able to book again."))) return;

    try {
      const resp = await fetch(`${config.unblockUrlBase}${viewEntryId}/unblock/`, {
        method: "POST",
        headers: {
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "fetch",
        },
      });
      const data = await resp.json();
      if (!resp.ok || !data.ok) throw new Error(data.error || "Request failed");
      closeModal(VIEW_MODAL_ID);
      showToast(t("customerUnblocked", "Customer unblocked."));
      document.dispatchEvent(new CustomEvent("od:customer-unblocked", { detail: data.entry }));
    } catch (err) {
      showToast(err.message || t("somethingWentWrong", "Something went wrong. Please try again."), "error");
    }
  }

  function bindTriggers(root = document) {
    root.querySelectorAll("[data-open-block-customer]").forEach((btn) => {
      if (btn.dataset.odBlockBound) return;
      btn.dataset.odBlockBound = "1";
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        openBlockCustomerModal({
          customerId: btn.dataset.customerId,
          bookingId: btn.dataset.bookingId,
          customer_id: btn.dataset.customerId,
          booking_id: btn.dataset.bookingId,
          customer_name: btn.dataset.customerName,
          phone_number: btn.dataset.phone,
          email: btn.dataset.email,
          booking_reference: btn.dataset.bookingReference,
        });
      });
    });

    root.querySelectorAll("[data-view-block-entry]").forEach((btn) => {
      if (btn.dataset.odBlockViewBound) return;
      btn.dataset.odBlockViewBound = "1";
      btn.addEventListener("click", () => openBlockCustomerView(btn.dataset.viewBlockEntry));
    });

    root.querySelectorAll("[data-open-block-customer-edit]").forEach((btn) => {
      if (btn.dataset.odBlockEditBound) return;
      btn.dataset.odBlockEditBound = "1";
      btn.addEventListener("click", () => {
        populateBlockForm(
          {
            entry_id: btn.dataset.entryId,
            customer_name: btn.dataset.customerName,
            phone_number: btn.dataset.phone,
            email: btn.dataset.email,
            reason_code: btn.dataset.reasonCode,
            notes: btn.dataset.notes,
          },
          "edit",
        );
        const formEl = document.getElementById("od-block-customer-form");
        if (formEl) formEl.dataset.editMode = "1";
        const submitBtn = document.getElementById("od-block-customer-submit");
        if (submitBtn) submitBtn.dataset.mode = "edit";
        openModal(MODAL_ID);
      });
    });
  }

  function initBlockCustomerModule(options = {}) {
    config = { ...options };
    const form = document.getElementById("od-block-customer-form");
    form?.addEventListener("submit", submitBlockForm);

    document.getElementById("od-block-customer-unblock-btn")?.addEventListener("click", unblockCurrentEntry);
    document.getElementById("od-block-customer-edit-btn")?.addEventListener("click", async () => {
      if (!viewEntryId) return;
      const resp = await fetch(`${config.detailUrlBase}${viewEntryId}/`);
      if (!resp.ok) return;
      const data = await resp.json();
      closeModal(VIEW_MODAL_ID);
      populateBlockForm({ ...data, entry_id: viewEntryId }, "edit");
      const formEl = document.getElementById("od-block-customer-form");
      if (formEl) formEl.dataset.editMode = "1";
      const submitBtn = document.getElementById("od-block-customer-submit");
      if (submitBtn) submitBtn.dataset.mode = "edit";
      openModal(MODAL_ID);
    });

    bindTriggers();
    document.addEventListener("click", (e) => {
      const trigger = e.target.closest("[data-open-block-customer]");
      if (trigger && !trigger.dataset.odBlockBound) bindTriggers(trigger.parentElement || document);
    });
  }

  global.initOwnerBlockCustomer = initBlockCustomerModule;
  global.odOpenBlockCustomerModal = openBlockCustomerModal;
  global.odOpenBlockCustomerView = openBlockCustomerView;
})(window);
