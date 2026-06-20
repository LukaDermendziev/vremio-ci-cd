/* Owner dashboard: navigation, modals, calendar */

function initOwnerDashboard(config) {
  let calendar = null;
  let calendarMeta = { closedDates: [], closedWeekdays: [] };
  let lastDateClick = { time: 0, dateStr: "" };

  function openModal(id) {
    document.getElementById(id)?.classList.add("open");
  }

  function closeModal(id) {
    document.getElementById(id)?.classList.remove("open");
  }

  function showToast(msg, isError = false) {
    let toast = document.getElementById("od-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "od-toast";
      toast.className = "od-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.toggle("error", isError);
    toast.classList.add("show");
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove("show"), 3500);
  }

  function closeAllModals() {
    document.querySelectorAll(".od-modal-overlay.open").forEach(m => m.classList.remove("open"));
  }

  document.querySelectorAll("[data-close-modal]").forEach(btn => {
    btn.addEventListener("click", () => closeModal(btn.dataset.closeModal));
  });

  document.querySelectorAll(".od-modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", e => {
      if (e.target === overlay) closeModal(overlay.id);
    });
  });

  function showSection(id) {
    document.querySelectorAll(".od-section").forEach(s => s.classList.remove("active"));
    document.querySelectorAll(".od-nav a").forEach(a => a.classList.remove("is-active"));
    document.getElementById("od-sec-" + id)?.classList.add("active");
    document.querySelector(`.od-nav a[data-section="${id}"]`)?.classList.add("is-active");
    if (id === "calendar") {
      setTimeout(() => cgFetchAndRender(), 100);
    }
  }

  // ── Mobile sidebar + bottom nav ──────────────────────────────────────────
  const sidebar    = document.querySelector(".od-sidebar");
  const backdrop   = document.getElementById("od-backdrop");
  const hamClose   = document.getElementById("od-ham-close");
  const bnMoreBtn  = document.getElementById("od-bn-more");

  function openSidebar() {
    sidebar?.classList.add("is-open");
    backdrop?.classList.add("is-visible");
    document.body.style.overflow = "hidden";
  }
  function closeSidebar() {
    sidebar?.classList.remove("is-open");
    backdrop?.classList.remove("is-visible");
    document.body.style.overflow = "";
  }

  hamClose?.addEventListener("click", closeSidebar);
  document.getElementById("od-ham-close-bottom")?.addEventListener("click", closeSidebar);
  backdrop?.addEventListener("click", closeSidebar);
  bnMoreBtn?.addEventListener("click", openSidebar);

  // Close sidebar overlay when window widens past mobile breakpoint
  window.addEventListener("resize", () => {
    if (window.innerWidth > 600) closeSidebar();
  });

  // ── Bottom nav clicks ─────────────────────────────────────────────────────
  function syncBottomNav(sectionId) {
    document.querySelectorAll(".od-bn-item[data-bn-section]").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.bnSection === sectionId);
    });
  }

  document.querySelectorAll(".od-bn-item[data-bn-section]").forEach(btn => {
    btn.addEventListener("click", () => {
      showSection(btn.dataset.bnSection);
      history.replaceState(null, "", "#" + btn.dataset.bnSection);
      syncBottomNav(btn.dataset.bnSection);
      closeSidebar();
    });
  });

  document.querySelectorAll("[data-section]").forEach(el => {
    el.addEventListener("click", e => {
      e.preventDefault();
      showSection(el.dataset.section);
      history.replaceState(null, "", "#" + el.dataset.section);
      syncBottomNav(el.dataset.section);
      if (window.innerWidth <= 600 && sidebar?.classList.contains("is-open")) closeSidebar();
    });
  });

  document.querySelectorAll("[data-goto]").forEach(el => {
    el.addEventListener("click", () => showSection(el.dataset.goto));
  });

  const hash = location.hash.replace("#", "");
  const initSection = hash || "dashboard";
  showSection(initSection);
  syncBottomNav(initSection);

  // Status tabs
  const tabs = document.querySelectorAll(".od-tab");
  const bkCards = document.querySelectorAll("#bk-list .od-bk-card");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      const status = tab.dataset.tab;
      let shown = 0;
      bkCards.forEach(card => {
        const visible = card.dataset.status === status;
        card.style.display = visible ? "" : "none";
        if (visible) shown++;
      });
      let empty = document.getElementById("bk-empty");
      if (!empty) {
        empty = document.createElement("div");
        empty.id = "bk-empty";
        empty.className = "od-empty";
        empty.textContent = "No bookings in this category.";
        document.getElementById("bk-list")?.appendChild(empty);
      }
      if (empty) empty.style.display = shown === 0 ? "block" : "none";
    });
  });
  tabs[0]?.click();

  // Booking modal
  const bookingModal = "od-booking-modal";
  const bookingForm = document.getElementById("od-booking-form");
  const serviceSelect = document.getElementById("od-booking-service");
  const dateInput = document.getElementById("od-booking-date");
  const startInput = document.getElementById("od-booking-start-time");
  const slotsSelect = document.getElementById("od-owner-slots");
  const bookingDeleteBtn = document.getElementById("od-booking-delete");
  const bookingDeleteForm = document.getElementById("od-booking-delete-form");

  async function loadOwnerSlots() {
    if (!serviceSelect?.value || !dateInput?.value) return;
    const exclude = bookingForm.querySelector('[name="booking_id"]')?.value || "";
    const url = `${config.slotsUrl}?service=${serviceSelect.value}&date=${dateInput.value}&exclude=${exclude}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!slotsSelect) return;

    const prevTime = startInput?.value || "";
    const slotsAvailable = data.slots || [];

    slotsSelect.innerHTML = slotsAvailable.length
      ? slotsAvailable.map(s => `<option value="${s.value}">${s.label}</option>`).join("")
      : '<option value="">No slots available</option>';

    const warning = document.getElementById("od-slots-warning");
    if (prevTime && slotsAvailable.length && slotsAvailable.some(s => s.value === prevTime)) {
      slotsSelect.value = prevTime;
      if (warning) warning.style.display = "none";
    } else if (prevTime && slotsAvailable.length && !slotsAvailable.some(s => s.value === prevTime)) {
      // Previously selected time is no longer available
      if (warning) {
        warning.textContent = `The time ${prevTime} is no longer available. Please select another slot.`;
        warning.style.display = "block";
      }
    } else {
      if (warning) warning.style.display = "none";
    }

    startInput.value = slotsSelect.value || "";
  }

  [serviceSelect, dateInput].forEach(el => el?.addEventListener("change", loadOwnerSlots));
  slotsSelect?.addEventListener("change", () => { startInput.value = slotsSelect.value; });

  function fillBookingForm(data) {
    bookingForm.querySelector('[name="booking_id"]').value = data.id || "";
    bookingForm.querySelector('[name="full_name"]').value = data.full_name || "";
    bookingForm.querySelector('[name="phone_number"]').value = data.phone_number || "";
    bookingForm.querySelector('[name="instagram_username"]').value = data.instagram_username || "";
    bookingForm.querySelector('[name="email"]').value = data.email || "";
    bookingForm.querySelector('[name="preferred_contact_method"]').value = data.preferred_contact_method || "viber";
    if (data.service_id) serviceSelect.value = data.service_id;
    dateInput.value = data.date || "";
    startInput.value = data.start_time || "";
    bookingForm.querySelector('[name="status"]').value = data.status || "approved";
    bookingForm.querySelector('[name="source"]').value = data.source || "owner_manual";
    bookingForm.querySelector('[name="owner_note"]').value = data.owner_note || "";
  }

  function getCurrentSection() {
    return document.querySelector(".od-section.active")?.id?.replace("od-sec-", "") || "dashboard";
  }

  async function openBookingModal(bookingId, preset = {}) {
    bookingForm.reset();
    bookingForm.querySelector('[name="booking_id"]').value = "";
    // Set return_section dynamically so Save/Delete lands back where the owner is
    const returnSec = getCurrentSection();
    bookingForm.querySelector('[name="return_section"]').value = returnSec;
    bookingDeleteForm.querySelector('[name="return_section"]').value = returnSec;
    document.getElementById("od-booking-modal-title").textContent = bookingId ? "Edit booking" : "Add booking";
    bookingDeleteBtn.style.display = bookingId ? "" : "none";

    if (bookingId) {
      const card = document.querySelector(`.od-bk-card[data-booking-id="${bookingId}"]`);
      if (card) {
        fillBookingForm({
          id: bookingId,
          full_name: card.dataset.fullName,
          phone_number: card.dataset.phone,
          instagram_username: card.dataset.instagram,
          email: card.dataset.email,
          preferred_contact_method: card.dataset.contact,
          service_id: card.dataset.serviceId,
          date: card.dataset.date,
          start_time: card.dataset.startTime,
          status: card.dataset.status,
          source: card.dataset.source,
          owner_note: card.dataset.ownerNote,
        });
      } else {
        const res = await fetch(`${config.bookingDetailUrl}${bookingId}/detail/`);
        if (res.ok) fillBookingForm(await res.json());
      }
      bookingDeleteForm.querySelector('[name="booking_id"]').value = bookingId;
    } else if (preset.date) {
      dateInput.value = preset.date;
      if (preset.time) startInput.value = preset.time;
      bookingForm.querySelector('[name="status"]').value = "approved";
      bookingForm.querySelector('[name="source"]').value = "owner_manual";
    }

    await loadOwnerSlots();
    openModal(bookingModal);
  }

  bookingForm?.addEventListener("submit", () => {
    if (slotsSelect?.value) startInput.value = slotsSelect.value;
  });

  bookingDeleteBtn?.addEventListener("click", () => {
    if (confirm("Delete this booking permanently?")) bookingDeleteForm.submit();
  });

  document.querySelectorAll("[data-add-booking]").forEach(btn => {
    btn.addEventListener("click", () => openBookingModal(null));
  });

  // Service modal
  const serviceForm = document.getElementById("od-service-form");
  const serviceDeleteBtn = document.getElementById("od-service-delete");
  const serviceDeleteForm = document.getElementById("od-service-delete-form");

  function openServiceModal(serviceId) {
    serviceForm.reset();
    serviceForm.querySelector('[name="service_id"]').value = "";
    serviceForm.querySelector('[name="is_active"]').checked = true;
    document.getElementById("od-service-modal-title").textContent = serviceId ? "Edit service" : "Add service";
    serviceDeleteBtn.style.display = serviceId ? "" : "none";

    if (serviceId) {
      const row = document.querySelector(`.od-svc-row[data-service-id="${serviceId}"]`);
      if (row) {
        serviceForm.querySelector('[name="service_id"]').value = serviceId;
        serviceForm.querySelector('[name="name"]').value = row.dataset.name || "";
        serviceForm.querySelector('[name="description"]').value = row.dataset.description || "";
        serviceForm.querySelector('[name="duration_minutes"]').value = row.dataset.duration || 120;
        serviceForm.querySelector('[name="base_price"]').value = row.dataset.price || 0;
        serviceForm.querySelector('[name="sort_order"]').value = row.dataset.sortOrder || 0;
        serviceForm.querySelector('[name="extra_duration_note"]').value = row.dataset.extraNote || "";
        serviceForm.querySelector('[name="is_active"]').checked = row.dataset.active === "true";
        serviceForm.querySelector('[name="requires_photo"]').checked = row.dataset.requiresPhoto === "true";
        serviceForm.querySelector('[name="photo_recommended"]').checked = row.dataset.photoRecommended === "true";
      }
      serviceDeleteForm.querySelector('[name="service_id"]').value = serviceId;
    }
    openModal("od-service-modal");
  }

  document.querySelectorAll("[data-add-service]").forEach(btn => btn.addEventListener("click", () => openServiceModal(null)));
  document.querySelectorAll("[data-edit-service]").forEach(btn => btn.addEventListener("click", () => openServiceModal(btn.dataset.editService)));
  serviceDeleteBtn?.addEventListener("click", () => {
    if (confirm("Delete this service?")) serviceDeleteForm.submit();
  });

  // ── AJAX booking status actions (no page reload) ─────────────────────────────
  const STATUS_LABELS = {
    pending: "Pending", approved: "Approved", rejected: "Rejected",
    cancelled: "Cancelled", completed: "Completed", no_show: "No Show"
  };
  const CONFIRM_ACTIONS = {
    reject: "Reject this booking?",
    cancel: "Cancel this booking?",
    mark_no_show: "Mark as no-show?",
  };

  function bkActionButtons(status, bookingId) {
    const b = id => `data-bk-id="${id}"`;
    const btn = (action, label, cls) =>
      `<button class="od-btn ${cls} od-btn-sm" type="button" data-bk-action="${action}" ${b(bookingId)}>${label}</button>`;
    let html = "";
    if (status === "pending") {
      html += btn("approve", "Approve", "od-btn-success");
      html += btn("reject",  "Reject",  "od-btn-danger");
    }
    if (status === "approved") {
      html += btn("mark_completed", "Mark completed", "od-btn-ghost");
      html += btn("mark_no_show",   "No-show",        "od-btn-ghost");
      html += btn("cancel",         "Cancel",         "od-btn-ghost");
    }
    return html;
  }

  async function sendBookingAction(action, bookingId, card) {
    const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
    const body = new URLSearchParams({ action, booking_id: bookingId, return_section: "bookings" });
    try {
      const resp = await fetch(window.location.pathname, {
        method: "POST",
        headers: { "X-CSRFToken": csrf, "X-Requested-With": "fetch",
                   "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!resp.ok) throw new Error("Server error");
      const data = await resp.json();
      if (!data.ok) throw new Error("Action failed");

      // Infer the new status from the action name — don't depend solely on server response
      // so the UI always updates correctly even if new_status is missing from JSON
      const ACTION_TO_STATUS = {
        approve:         "approved",
        reject:          "rejected",
        mark_completed:  "completed",
        mark_no_show:    "no_show",
        cancel:          "cancelled",
        cancel_booking:  "cancelled",
      };
      const newStatus = data.new_status || ACTION_TO_STATUS[action] || "pending";
      const newStatusDisplay = data.new_status_display || STATUS_LABELS[newStatus] || newStatus;

      // ── 1. Decrement pending badge BEFORE touching card.dataset.status ────────
      const wasPending = card.dataset.status === "pending";
      if (wasPending && newStatus !== "pending") {
        const pendingBadge = document.querySelector('.od-tab[data-tab="pending"] .od-tab-n');
        if (pendingBadge) {
          const cur = parseInt(pendingBadge.textContent, 10);
          if (!isNaN(cur) && cur > 0) pendingBadge.textContent = String(cur - 1);
        }
      }

      // ── 2. Update card's data-status ─────────────────────────────────────────
      card.dataset.status = newStatus;

      // ── 3. Update the visible status badge ───────────────────────────────────
      const badge = card.querySelector(".od-bk-status-badge");
      if (badge) {
        badge.textContent = newStatusDisplay;
        badge.className = `od-badge od-badge-${newStatus} od-bk-status-badge`;
      }

      // ── 4. Swap action buttons to match new status ───────────────────────────
      const actionsEl = card.querySelector(".od-bk-actions-live");
      if (actionsEl) {
        const staticBtns = [...actionsEl.querySelectorAll(
          "[data-edit-booking],[href^='tel:'],[data-message-booking]"
        )].map(el => el.outerHTML).join("");
        actionsEl.innerHTML = bkActionButtons(newStatus, bookingId) + staticBtns;
        actionsEl.querySelectorAll("[data-bk-action]").forEach(b => bindBkAction(b));
        actionsEl.querySelectorAll("[data-edit-booking]").forEach(btn =>
          btn.addEventListener("click", () => openBookingModal(btn.dataset.editBooking)));
        actionsEl.querySelectorAll("[data-message-booking]").forEach(btn =>
          bindMessageBtn(btn));
      }

      // ── 5. Toast ──────────────────────────────────────────────────────────────
      if (data.messages?.length) {
        showToast(data.messages[0][1], data.messages[0][0] === "success" ? "success" : "error");
      }

      // ── 6. Sync overview stat counters without a full reload ─────────────────
      if (data.pending_count !== undefined) {
        document.querySelectorAll('[data-stat="pending"]').forEach(el => {
          el.textContent = data.pending_count;
        });
      }
      if (data.today_count !== undefined) {
        document.querySelectorAll('[data-stat="today"]').forEach(el => {
          el.textContent = data.today_count;
        });
      }

      // ── 7. Fade out of current tab — card stays in DOM for other tabs ─────────
      const activeTab = document.querySelector(".od-tab.active")?.dataset.tab;
      if (activeTab && activeTab !== "all" && activeTab !== newStatus) {
        card.style.transition = "opacity .3s";
        card.style.opacity = "0";
        setTimeout(() => {
          card.style.display = "none";
          card.style.opacity = "";
          card.style.transition = "";
          const shownNow = [...document.querySelectorAll("#bk-list .od-bk-card")]
            .filter(c => c.style.display !== "none" && c.dataset.status === activeTab).length;
          const empty = document.getElementById("bk-empty");
          if (empty) empty.style.display = shownNow === 0 ? "block" : "none";
        }, 320);
      }

      // ── 8. Update / remove duplicate copies of this card in OTHER sections ────
      // (e.g. the overview panel "Pending booking requests" card)
      document.querySelectorAll(`.od-bk-card[data-booking-id="${bookingId}"]`).forEach(otherCard => {
        if (otherCard === card) return; // already handled above
        // Update status badge
        const otherBadge = otherCard.querySelector(".od-bk-status-badge");
        if (otherBadge) {
          otherBadge.textContent = newStatusDisplay;
          otherBadge.className = `od-badge od-badge-${newStatus} od-bk-status-badge`;
        }
        otherCard.dataset.status = newStatus;
        // Fade out from sections that only show pending (the overview card)
        otherCard.style.transition = "opacity .3s";
        otherCard.style.opacity = "0";
        setTimeout(() => {
          otherCard.style.display = "none";
          otherCard.style.opacity = "";
          otherCard.style.transition = "";
          // Show "all caught up" message if overview list is now empty
          const list = otherCard.closest(".od-bk-list");
          if (list) {
            const remaining = list.querySelectorAll(".od-bk-card:not([style*='display: none'])");
            if (remaining.length === 0) {
              const emptyEl = list.nextElementSibling;
              if (emptyEl?.classList.contains("od-empty")) emptyEl.style.display = "block";
              list.style.display = "none";
            }
          }
        }, 320);
      });
    } catch (err) {
      showToast("Something went wrong. Please try again.", "error");
      console.error(err);
    }
  }

  function showToast(msg, type = "success") {
    let toast = document.getElementById("od-toast");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "od-toast";
      document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.className = `od-toast od-toast-${type} od-toast-show`;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => toast.classList.remove("od-toast-show"), 3200);
  }

  function bindBkAction(btn) {
    btn.addEventListener("click", async () => {
      const action = btn.dataset.bkAction;
      const bookingId = btn.dataset.bkId;
      const card = btn.closest(".od-bk-card");
      if (!card) return;
      if (CONFIRM_ACTIONS[action]) {
        if (!confirm(CONFIRM_ACTIONS[action])) return;
      }
      btn.disabled = true;
      btn.style.opacity = ".5";
      await sendBookingAction(action, bookingId, card);
      btn.disabled = false;
      btn.style.opacity = "";
    });
  }

  // Bind all status-action buttons on load (covers server-rendered cards)
  document.querySelectorAll("[data-bk-action]").forEach(bindBkAction);

  // Also bind edit buttons on load
  document.querySelectorAll("[data-edit-booking]").forEach(btn => {
    btn.addEventListener("click", () => openBookingModal(btn.dataset.editBooking));
  });

  function bindMessageBtn(btn) {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.messageBooking;
      const type = btn.dataset.messageType || "approved";
      // Delegate to the message modal handler if it exists
      const existing = document.querySelector(`[data-message-booking="${id}"]`);
      if (existing && existing !== btn) { existing.click(); return; }
      // Fallback: just open the modal directly
      const msgModal = document.getElementById("od-message-modal");
      if (msgModal) {
        msgModal.querySelector?.('[name="booking_id"]') && (msgModal.querySelector('[name="booking_id"]').value = id);
        openModal("od-message-modal");
      }
    });
  }

  // ── Price list modal ────────────────────────────────────────────────────────
  const priceServiceId   = document.getElementById("od-price-service-id");
  const priceItemId      = document.getElementById("od-price-item-id");
  const priceItemGroup   = document.getElementById("od-price-item-group");
  const priceItemName    = document.getElementById("od-price-item-name");
  const priceItemPrice   = document.getElementById("od-price-item-price");
  const priceItemSort    = document.getElementById("od-price-item-sort");
  const priceItemPhoto   = document.getElementById("od-price-item-photo");
  const priceItemSubmit  = document.getElementById("od-price-item-submit");
  const priceItemClear   = document.getElementById("od-price-item-clear");
  const priceSvcName     = document.getElementById("od-price-modal-svc-name");

  function resetPriceForm() {
    if (priceItemId)    priceItemId.value = "";
    if (priceItemGroup) priceItemGroup.value = "";
    if (priceItemName)  priceItemName.value = "";
    if (priceItemPrice) priceItemPrice.value = "";
    if (priceItemSort)  priceItemSort.value = "0";
    if (priceItemPhoto) priceItemPhoto.checked = false;
    if (priceItemSubmit) {
      priceItemSubmit.innerHTML = '<i class="bi bi-plus-lg"></i> Add item';
    }
  }

  function openPriceModal(serviceId, serviceName) {
    const card = document.querySelector(`[data-service-id="${serviceId}"]`);
    if (priceServiceId) priceServiceId.value = serviceId;
    if (priceSvcName)   priceSvcName.textContent = serviceName || (card ? card.dataset.name : "");
    resetPriceForm();
    openModal("od-price-modal");
    setTimeout(() => priceItemName?.focus(), 120);
  }

  // "Add price item" buttons on service cards
  document.querySelectorAll("[data-manage-prices]").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      openPriceModal(btn.dataset.managePrices, btn.dataset.serviceName);
    });
  });

  // Inline "Edit" buttons inside the price table — data comes directly from button attributes
  document.querySelectorAll("[data-inline-edit-item]").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      const svcId   = btn.dataset.svcId;
      const svcName = btn.dataset.svcName;
      // Fill modal from button data-* attributes (no JSON parsing needed)
      if (priceServiceId) priceServiceId.value = svcId;
      if (priceSvcName)   priceSvcName.textContent = svcName;
      resetPriceForm();
      if (priceItemId)    priceItemId.value    = btn.dataset.inlineEditItem;
      if (priceItemGroup) priceItemGroup.value  = btn.dataset.itemGroup  || "";
      if (priceItemName)  priceItemName.value   = btn.dataset.itemName   || "";
      if (priceItemPrice) priceItemPrice.value  = btn.dataset.itemPrice  || "";
      if (priceItemSort)  priceItemSort.value   = btn.dataset.itemSort   || "0";
      if (priceItemPhoto) priceItemPhoto.checked = btn.dataset.itemPhoto === "true";
      if (priceItemSubmit) priceItemSubmit.innerHTML = '<i class="bi bi-check-lg"></i> Save changes';
      openModal("od-price-modal");
      setTimeout(() => priceItemName?.focus(), 80);
    });
  });

  // ── Drag-to-reorder price list rows ──────────────────────────────────────────
  document.querySelectorAll(".od-svc-price-body").forEach(body => {
    const tbody = body.querySelector("tbody");
    if (!tbody) return;
    let dragSrc = null;

    tbody.addEventListener("dragstart", e => {
      const row = e.target.closest(".od-price-drag-row");
      if (!row) return;
      dragSrc = row;
      row.classList.add("od-drag-active");
      e.dataTransfer.effectAllowed = "move";
    });

    tbody.addEventListener("dragend", e => {
      const row = e.target.closest(".od-price-drag-row");
      if (row) row.classList.remove("od-drag-active");
      tbody.querySelectorAll(".od-drag-over").forEach(r => r.classList.remove("od-drag-over"));
      dragSrc = null;
    });

    tbody.addEventListener("dragover", e => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      const row = e.target.closest(".od-price-drag-row");
      tbody.querySelectorAll(".od-drag-over").forEach(r => r.classList.remove("od-drag-over"));
      if (row && row !== dragSrc) row.classList.add("od-drag-over");
    });

    tbody.addEventListener("drop", e => {
      e.preventDefault();
      const target = e.target.closest(".od-price-drag-row");
      if (!target || target === dragSrc || !dragSrc) return;
      // Re-insert dragged row before or after target
      const allRows = [...tbody.querySelectorAll(".od-price-drag-row")];
      const srcIdx = allRows.indexOf(dragSrc);
      const tgtIdx = allRows.indexOf(target);
      if (srcIdx < tgtIdx) {
        target.after(dragSrc);
      } else {
        target.before(dragSrc);
      }
      target.classList.remove("od-drag-over");
      // Persist new order via AJAX
      const orderedIds = [...tbody.querySelectorAll(".od-price-drag-row")]
        .map(r => r.dataset.itemId).join(",");
      const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
      fetch(window.location.pathname, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": csrf },
        body: `action=reorder_price_items&item_ids=${encodeURIComponent(orderedIds)}&return_section=services`
      });
    });
  });

  priceItemClear?.addEventListener("click", resetPriceForm);

  // ── Touch long-press drag-to-reorder (mobile) ────────────────────────────────
  document.querySelectorAll(".od-svc-price-body").forEach(body => {
    const tbody = body.querySelector("tbody");
    if (!tbody) return;

    let touchDragEl  = null;
    let lpTimer      = null;
    let touchActive  = false;
    let startTouchY  = 0;
    let startTouchX  = 0;

    function saveTouchOrder() {
      const orderedIds = [...tbody.querySelectorAll(".od-price-drag-row")]
        .map(r => r.dataset.itemId).join(",");
      const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
      fetch(window.location.pathname, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded", "X-CSRFToken": csrf },
        body: `action=reorder_price_items&item_ids=${encodeURIComponent(orderedIds)}&return_section=services`
      });
    }

    tbody.addEventListener("touchstart", e => {
      const handle = e.target.closest(".od-drag-handle");
      if (!handle) return;
      const row = handle.closest(".od-price-drag-row");
      if (!row) return;

      startTouchY = e.touches[0].clientY;
      startTouchX = e.touches[0].clientX;

      lpTimer = setTimeout(() => {
        touchActive = true;
        touchDragEl = row;
        row.classList.add("od-drag-active");
        try { navigator.vibrate?.(40); } catch (_) {}
      }, 420);
    }, { passive: true });

    tbody.addEventListener("touchmove", e => {
      const t = e.touches[0];
      // Cancel long-press if user scrolled before it fired
      if (!touchActive) {
        if (Math.abs(t.clientY - startTouchY) > 8 || Math.abs(t.clientX - startTouchX) > 8) {
          clearTimeout(lpTimer);
          lpTimer = null;
        }
        return;
      }
      e.preventDefault(); // stop page scroll while dragging

      const rows = [...tbody.querySelectorAll(".od-price-drag-row")];
      let over = null;
      for (const r of rows) {
        if (r === touchDragEl) continue;
        const rect = r.getBoundingClientRect();
        if (t.clientY >= rect.top && t.clientY <= rect.bottom) { over = r; break; }
      }
      rows.forEach(r => r.classList.remove("od-drag-over"));
      if (over) over.classList.add("od-drag-over");
    }, { passive: false });

    function endTouchDrag() {
      clearTimeout(lpTimer);
      if (!touchActive || !touchDragEl) { touchActive = false; touchDragEl = null; return; }

      const target = tbody.querySelector(".od-drag-over");
      if (target && target !== touchDragEl) {
        const rows = [...tbody.querySelectorAll(".od-price-drag-row")];
        const si = rows.indexOf(touchDragEl);
        const ti = rows.indexOf(target);
        if (si < ti) target.after(touchDragEl);
        else target.before(touchDragEl);
        saveTouchOrder();
      }
      tbody.querySelectorAll(".od-drag-active,.od-drag-over").forEach(r =>
        r.classList.remove("od-drag-active","od-drag-over"));
      touchActive  = false;
      touchDragEl  = null;
    }

    tbody.addEventListener("touchend",    endTouchDrag);
    tbody.addEventListener("touchcancel", endTouchDrag);
  });

  // ── Collapsible group header rows in price tables ────────────────────────────
  document.querySelectorAll(".od-price-group-toggle").forEach(btn => {
    btn.addEventListener("click", () => {
      const groupId = btn.dataset.toggleGroup;
      const collapsed = btn.classList.toggle("od-group-collapsed");
      // Hide/show all item rows that belong to this group
      // They are the sibling <tr> rows after this header row until the next group row
      let row = btn.closest("tr").nextElementSibling;
      while (row && !row.classList.contains("od-price-group-row")) {
        row.classList.toggle("od-group-hidden", collapsed);
        row = row.nextElementSibling;
      }
    });
  });

  // ── Expand/collapse price list panels ────────────────────────────────────────
  document.querySelectorAll("[data-price-toggle]").forEach(btn => {
    btn.addEventListener("click", () => {
      const svcId  = btn.dataset.priceToggle;
      const body   = document.getElementById(`od-price-body-${svcId}`);
      const chev   = document.getElementById(`od-price-chevron-${svcId}`);
      if (!body) return;
      const open = !body.hidden;
      body.hidden = open;
      btn.setAttribute("aria-expanded", String(!open));
      chev?.classList.toggle("od-price-toggle-chevron--open", !open);
    });
  });

  // Customer modal
  const customerForm = document.getElementById("od-customer-form");
  const customerDeleteBtn = document.getElementById("od-customer-delete");
  const customerDeleteForm = document.getElementById("od-customer-delete-form");

  function openCustomerModal(customerId) {
    customerForm.reset();
    customerForm.querySelector('[name="customer_id"]').value = "";
    document.getElementById("od-customer-modal-title").textContent = customerId ? "Edit customer" : "Add customer";
    customerDeleteBtn.style.display = customerId ? "" : "none";

    if (customerId) {
      const row = document.querySelector(`tr[data-customer-id="${customerId}"]`);
      if (row) {
        customerForm.querySelector('[name="customer_id"]').value = customerId;
        customerForm.querySelector('[name="full_name"]').value = row.dataset.fullName || "";
        customerForm.querySelector('[name="phone_number"]').value = row.dataset.phone || "";
        customerForm.querySelector('[name="instagram_username"]').value = row.dataset.instagram || "";
        customerForm.querySelector('[name="email"]').value = row.dataset.email || "";
        customerForm.querySelector('[name="preferred_contact_method"]').value = row.dataset.contact || "viber";
      }
      customerDeleteForm.querySelector('[name="customer_id"]').value = customerId;
    }
    openModal("od-customer-modal");
  }

  document.querySelectorAll("[data-add-customer]").forEach(btn => btn.addEventListener("click", () => openCustomerModal(null)));
  document.querySelectorAll("[data-edit-customer]").forEach(btn => btn.addEventListener("click", () => openCustomerModal(btn.dataset.editCustomer)));
  customerDeleteBtn?.addEventListener("click", () => {
    if (confirm("Delete this customer?")) customerDeleteForm.submit();
  });

  // Block modal
  const blockForm = document.getElementById("od-block-form");
  const blockDeleteBtn = document.getElementById("od-block-delete");
  const blockDeleteForm = document.getElementById("od-block-delete-form");

  function openBlockModal(blockId, preset = {}) {
    blockForm.reset();
    blockForm.querySelector('[name="block_id"]').value = "";
    document.getElementById("od-block-modal-title").textContent = blockId ? "Edit blocked time" : "Block time";
    blockDeleteBtn.style.display = blockId ? "" : "none";

    if (blockId) {
      blockForm.querySelector('[name="block_id"]').value = blockId;
      blockDeleteForm.querySelector('[name="block_id"]').value = blockId;
    }

    if (blockId && blockForm.dataset.fromEvent) {
      const p = JSON.parse(blockForm.dataset.fromEvent);
      blockForm.querySelector('[name="block_id"]').value = blockId;
      blockForm.querySelector('[name="date"]').value = p.date || "";
      blockForm.querySelector('[name="start_time"]').value = p.startTime || "";
      blockForm.querySelector('[name="end_time"]').value = p.endTime || "";
      blockForm.querySelector('[name="reason"]').value = p.reason || "";
      delete blockForm.dataset.fromEvent;
    } else if (preset.date) {
      blockForm.querySelector('[name="date"]').value = preset.date;
      if (preset.startTime) blockForm.querySelector('[name="start_time"]').value = preset.startTime;
      if (preset.endTime) blockForm.querySelector('[name="end_time"]').value = preset.endTime;
    }

    if (blockId) blockDeleteForm.querySelector('[name="block_id"]').value = blockId;
    openModal("od-block-modal");
  }

  document.querySelectorAll("[data-add-block]").forEach(btn => btn.addEventListener("click", () => openBlockModal(null)));
  document.querySelectorAll("[data-add-blocked-date]").forEach(btn => btn.addEventListener("click", () => openModal("od-blocked-date-modal")));
  document.querySelectorAll("[data-edit-block]").forEach(btn => btn.addEventListener("click", () => {
    const blockId = btn.dataset.editBlock;
    openBlockModal(blockId, {
      date: btn.dataset.blockDate,
      startTime: btn.dataset.blockStart,
      endTime: btn.dataset.blockEnd,
    });
    blockForm.querySelector('[name="reason"]').value = btn.dataset.blockReason || "";
    blockForm.querySelector('[name="block_id"]').value = blockId;
    blockDeleteForm.querySelector('[name="block_id"]').value = blockId;
    blockDeleteBtn.style.display = "";
  }));
  blockDeleteBtn?.addEventListener("click", () => {
    if (confirm("Remove this time block?")) blockDeleteForm.submit();
  });

  document.querySelectorAll("[data-delete-blocked-date]").forEach(btn => {
    btn.addEventListener("click", () => {
      if (confirm("Remove this blocked date?")) btn.closest("form")?.submit();
    });
  });

  // ── Utility: register both dblclick (desktop) and double-tap (mobile) ───────
  function onDoubleTap(el, handler) {
    el.addEventListener("dblclick", handler);
    let _last = 0;
    el.addEventListener("touchend", (e) => {
      const now = Date.now();
      if (now - _last < 320 && now - _last > 30) {
        e.preventDefault(); // suppress the ghost click that follows
        handler(e);
      }
      _last = now;
    }, { passive: false });
  }

  // ── Custom calendar grid (cgrid) ─────────────────────────────────────────────
  const cgridEl = document.getElementById("od-calendar-grid");
  const cgRangeLabel = document.getElementById("cal-range-label");

  const CG_HOURS = ["08:00","09:00","10:00","11:00","12:00","13:00","14:00","15:00","16:00","17:00","18:00"];
  const CG_STATUS = {
    pending:   { cls: "cgrid-chip-pending",   label: "Pending" },
    approved:  { cls: "cgrid-chip-approved",  label: "Approved" },
    completed: { cls: "cgrid-chip-completed", label: "Completed" },
    rejected:  { cls: "cgrid-chip-rejected",  label: "Rejected" },
    cancelled: { cls: "cgrid-chip-cancelled", label: "Cancelled" },
    no_show:   { cls: "cgrid-chip-no_show",   label: "No Show" },
    block:     { cls: "cgrid-chip-block",     label: "Block" },
  };

  let cgView = "week";
  let cgWeekStart = cgMonday(new Date());
  let cgDayDate  = new Date();
  let cgEvents   = [];
  let cgMeta     = { closedDates: [], closedWeekdays: [] };

  function cgMonday(d) {
    const r = new Date(d); r.setHours(0,0,0,0);
    const day = r.getDay(); r.setDate(r.getDate() - (day === 0 ? 6 : day - 1));
    return r;
  }
  function cgIso(d) {
    return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  }
  function cgIsClosedDay(d) {
    const ds = cgIso(d);
    const dw = (d.getDay() + 6) % 7;
    return cgMeta.closedDates.includes(ds) || cgMeta.closedWeekdays.includes(dw);
  }
  function cgIsPast(ds, time) {
    const dt = new Date(ds + "T" + time + ":00");
    return dt < new Date();
  }
  function cgFmtWeekRange(mon) {
    const sun = new Date(mon); sun.setDate(mon.getDate() + 6);
    const fmtS = mon.toLocaleDateString("en-GB", { day:"numeric", month:"short" });
    const fmtE = sun.toLocaleDateString("en-GB", { day:"numeric", month:"short", year:"numeric" });
    return `${fmtS} – ${fmtE}`;
  }
  function cgEventsAt(ds, hour) {
    return cgEvents.filter(ev => {
      if (ev.date !== ds) return false;
      const h = parseInt((ev.time || ev.start_time || "").split(":")[0]);
      return h === hour;
    });
  }

  function cgChipHtml(ev) {
    if (ev.type === "block") {
      return `<div class="cgrid-chip cgrid-chip-block" data-block-id="${ev.blockId||ev.id||''}">
        <div class="cgrid-chip-block">Blocked ${ev.start_time||ev.time||''}${ev.end_time ? '–'+ev.end_time : ''}</div>
      </div>`;
    }
    const sc = CG_STATUS[ev.status] || CG_STATUS.pending;
    return `<div class="cgrid-chip ${sc.cls}" data-booking-id="${ev.bookingId||ev.id||''}">
      <div class="cgrid-chip-name">${ev.customerName||ev.title||''}</div>
      <div class="cgrid-chip-meta">${ev.time||''} · ${ev.duration||''}min</div>
    </div>`;
  }

  function cgRenderWeek() {
    const days = Array.from({length:7}, (_,i) => { const d=new Date(cgWeekStart); d.setDate(d.getDate()+i); return d; });
    const today = cgIso(new Date());
    const cols = `68px repeat(7, 1fr)`;

    let html = `<div class="cgrid-head" style="grid-template-columns:${cols}">`;
    html += `<div class="cgrid-head-time"></div>`;
    days.forEach(d => {
      const ds = cgIso(d);
      const isToday = ds === today;
      const isClosed = cgIsClosedDay(d);
      const dow = d.toLocaleDateString("en-GB",{weekday:"short"}).toUpperCase();
      html += `<div class="cgrid-head-day${isToday?' cgrid-head-today':''}${isClosed?' cgrid-head-closed':''}">
        <div class="cgrid-head-dow">${dow}</div>
        <div class="cgrid-head-num">${d.getDate()}</div>
        ${isClosed ? '<div class="cgrid-closed-tag">Closed</div>' : ''}
      </div>`;
    });
    html += `</div>`;

    CG_HOURS.forEach(time => {
      const hour = parseInt(time);
      html += `<div class="cgrid-row" style="grid-template-columns:${cols}">`;
      html += `<div class="cgrid-time-label">${time}</div>`;
      days.forEach(d => {
        const ds = cgIso(d);
        const isClosed = cgIsClosedDay(d);
        const isPast = cgIsPast(ds, time);
        let cls = "cgrid-cell";
        if (isClosed) cls += " cgrid-cell-closed";
        else if (isPast) cls += " cgrid-cell-past";
        const evs = cgEventsAt(ds, hour);
        html += `<div class="${cls}" data-date="${ds}" data-time="${time}">`;
        evs.forEach(ev => { html += cgChipHtml(ev); });
        html += `</div>`;
      });
      html += `</div>`;
    });

    cgridEl.innerHTML = html;

    // Click handlers
    cgridEl.querySelectorAll(".cgrid-chip[data-booking-id]").forEach(chip => {
      chip.addEventListener("click", e => { e.stopPropagation(); openBookingModal(chip.dataset.bookingId); });
    });
    cgridEl.querySelectorAll(".cgrid-chip[data-block-id]").forEach(chip => {
      chip.addEventListener("click", e => { e.stopPropagation(); openBlockModal(chip.dataset.blockId); });
    });
    cgridEl.querySelectorAll(".cgrid-cell:not(.cgrid-cell-closed):not(.cgrid-cell-past)").forEach(cell => {
      onDoubleTap(cell, () => {
        openBookingModal(null, { date: cell.dataset.date, time: cell.dataset.time });
      });
    });
  }

  function cgRenderDay() {
    const ds = cgIso(cgDayDate);
    const dayStr = cgDayDate.toLocaleDateString("en-GB",{weekday:"long",day:"numeric",month:"long",year:"numeric"});
    const count = cgEvents.filter(ev => ev.date === ds).length;
    let html = `<div class="cgrid-day-header" style="padding:14px 16px;border-bottom:1px solid #E5E7EB;background:#F9FAFB;">
      <p style="font-size:14px;font-weight:600;color:#111827;margin:0">${dayStr}</p>
      <p style="font-size:12px;color:#6B7280;margin:4px 0 0">${count} appointment${count!==1?'s':''}</p>
    </div>`;

    CG_HOURS.forEach(time => {
      const hour = parseInt(time);
      const isPast = cgIsPast(ds, time);
      const evs = cgEventsAt(ds, hour);
      html += `<div class="cgrid-day-row${isPast?' cgrid-cell-past':''}" data-date="${ds}" data-time="${time}">
        <div class="cgrid-day-time">${time}</div>
        <div class="cgrid-day-content">`;
      if (evs.length) {
        evs.forEach(ev => {
          if (ev.type === "block") {
            html += `<div class="cgrid-day-chip cgrid-chip-block" data-block-id="${ev.blockId||''}"
              style="border-left-color:#7C3AED;background:#EDE9FE;">
              <div><div class="cgrid-day-chip-name" style="color:#7C3AED">Blocked</div>
              <div class="cgrid-day-chip-meta">${ev.start_time||ev.time||''}${ev.end_time?'–'+ev.end_time:''}</div></div>
            </div>`;
          } else {
            const sc = CG_STATUS[ev.status] || CG_STATUS.pending;
            const dotColor = {"pending":"#D97706","approved":"#059669","completed":"#2563EB","rejected":"#DB2777","cancelled":"#6B7280","no_show":"#C2410C"}[ev.status]||"#D97706";
            html += `<div class="cgrid-day-chip ${sc.cls}" data-booking-id="${ev.bookingId||ev.id||''}"
              style="cursor:pointer;">
              <div>
                <div class="cgrid-day-chip-name">${ev.customerName||ev.title||''}</div>
                <div class="cgrid-day-chip-svc">${ev.services||ev.service||''}</div>
                <div class="cgrid-day-chip-meta">${ev.time||''} · ${ev.duration||''}min</div>
              </div>
              <span style="font-size:11px;padding:2px 8px;border-radius:99px;background:${dotColor}22;color:${dotColor};font-weight:600">${sc.label}</span>
            </div>`;
          }
        });
      } else {
        html += `<div class="cgrid-day-empty">— Available</div>`;
      }
      html += `</div></div>`;
    });

    cgridEl.innerHTML = html;

    cgridEl.querySelectorAll(".cgrid-day-chip[data-booking-id]").forEach(c => {
      c.addEventListener("click", () => openBookingModal(c.dataset.bookingId));
    });
    cgridEl.querySelectorAll(".cgrid-day-chip[data-block-id]").forEach(c => {
      c.addEventListener("click", () => openBlockModal(c.dataset.blockId));
    });
    cgridEl.querySelectorAll(".cgrid-day-row:not(.cgrid-cell-past)").forEach(row => {
      onDoubleTap(row, () => {
        openBookingModal(null, { date: row.dataset.date, time: row.dataset.time });
      });
    });
  }

  function cgRender() {
    if (!cgridEl) return;
    if (cgView === "week") {
      cgRangeLabel && (cgRangeLabel.textContent = cgFmtWeekRange(cgWeekStart));
      cgRenderWeek();
    } else {
      cgRangeLabel && (cgRangeLabel.textContent = cgDayDate.toLocaleDateString("en-GB",{weekday:"long",day:"numeric",month:"long",year:"numeric"}));
      cgRenderDay();
    }
    document.querySelectorAll(".cgrid-view-btn").forEach(b => b.classList.remove("active"));
    document.getElementById(cgView === "week" ? "cal-view-week" : "cal-view-day")?.classList.add("active");
  }

  async function cgFetchAndRender() {
    if (!cgridEl) return;
    let start, end;
    if (cgView === "week") {
      start = cgIso(cgWeekStart);
      const endD = new Date(cgWeekStart); endD.setDate(endD.getDate()+7);
      end = cgIso(endD);
    } else {
      start = cgIso(cgDayDate);
      const endD = new Date(cgDayDate); endD.setDate(endD.getDate()+1);
      end = cgIso(endD);
    }
    try {
      const res = await fetch(`${config.eventsUrl}?start=${start}&end=${end}`);
      const data = await res.json();
      cgMeta = { closedDates: data.closedDates||[], closedWeekdays: data.closedWeekdays||[] };
      cgEvents = (data.events||[]).map(ev => {
        const s = ev.start || "";
        const ds = s.split("T")[0] || "";
        const tm = s.split("T")[1]?.slice(0,5) || ev.time || "";
        const endS = ev.end || "";
        const endTm = endS.split("T")[1]?.slice(0,5) || "";
        const ep = ev.extendedProps || {};
        return {
          ...ep, date: ds, time: tm, end_time: endTm,
          title: ev.title||"",
          bookingId: ep.bookingId, blockId: ep.blockId,
          type: ep.type||"booking",
        };
      });
    } catch(e) { console.error("cgrid fetch error", e); }
    cgRender();
  }

  document.getElementById("cal-prev")?.addEventListener("click", () => {
    if (cgView === "week") { cgWeekStart.setDate(cgWeekStart.getDate()-7); }
    else { cgDayDate.setDate(cgDayDate.getDate()-1); }
    cgFetchAndRender();
  });
  document.getElementById("cal-next")?.addEventListener("click", () => {
    if (cgView === "week") { cgWeekStart.setDate(cgWeekStart.getDate()+7); }
    else { cgDayDate.setDate(cgDayDate.getDate()+1); }
    cgFetchAndRender();
  });
  document.getElementById("cal-today")?.addEventListener("click", () => {
    cgWeekStart = cgMonday(new Date()); cgDayDate = new Date();
    cgFetchAndRender();
  });
  document.getElementById("cal-view-week")?.addEventListener("click", () => { cgView="week"; cgFetchAndRender(); });
  document.getElementById("cal-view-day")?.addEventListener("click",  () => { cgView="day";  cgFetchAndRender(); });

  // End of cgrid — remove old FullCalendar placeholder
  if (cgridEl) cgFetchAndRender();

  if (false && window.FullCalendar) {
    calendar = new FullCalendar.Calendar(calEl, {
      initialView: "timeGridWeek",
      headerToolbar: false,
      height: "auto",
      timeZone: "local",
      slotMinTime: "07:00:00",
      slotMaxTime: "20:00:00",
      slotDuration: "00:30:00",
      allDaySlot: false,
      nowIndicator: true,
      firstDay: 1,
      weekends: true,
      events: fetchCalendarEvents,
      eventClick(info) {
        info.jsEvent.preventDefault();
        const props = info.event.extendedProps;
        if (props.type === "booking") openBookingModal(props.bookingId);
        if (props.type === "block") {
          blockForm.dataset.fromEvent = JSON.stringify(props);
          openBlockModal(props.blockId);
        }
      },
      eventContent(arg) {
        const p = arg.event.extendedProps;
        if (p.type === "block") {
          return { html: `<div class="fc-custom-block"><span>${arg.event.title}</span></div>` };
        }
        if (p.type !== "booking") return undefined;
        const name = p.customerName || arg.event.title;
        const svc = p.services || "";
        const dur = p.duration ? `${p.duration} min` : "";
        return {
          html: `<div class="fc-custom-event fc-status-${p.status}">
            <div class="fc-ev-name">${name}</div>
            <div class="fc-ev-svc">${svc}</div>
            <div class="fc-ev-dur">${dur}</div>
          </div>`,
        };
      },
      dayHeaderContent(arg) {
        const pad = (n) => String(n).padStart(2, "0");
        const d = arg.date;
        const dateStr = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        const closed = isClosedDate(dateStr);
        const day = arg.date.toLocaleDateString(undefined, { weekday: "short" });
        const num = arg.date.getDate();
        return {
          html: `<div class="fc-day-head${closed ? " is-closed" : ""}">
            <span class="fc-day-name">${day}</span>
            <span class="fc-day-num">${num}</span>
            ${closed ? '<span class="fc-day-closed">Closed</span>' : ""}
          </div>`,
        };
      },
      dayCellClassNames(arg) {
        const pad = (n) => String(n).padStart(2, "0");
        const d = arg.date;
        const dateStr = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        return isClosedDate(dateStr) ? ["fc-day-closed-cell"] : [];
      },
      datesSet(info) {
        if (rangeLabel) rangeLabel.textContent = formatRange(info.start, info.end, info.view.type);
      },
      dateClick(info) {
        const d = info.date;
        const pad = (n) => String(n).padStart(2, "0");
        const dateStr = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
        const timeStr = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
        const now = Date.now();
        if (now - lastDateClick.time < 400 && lastDateClick.dateStr === dateStr + timeStr) {
          if (info.date < new Date()) {
            showToast("Cannot add bookings in the past.", true);
            lastDateClick = { time: 0, dateStr: "" };
            return;
          }
          if (!isClosedDate(dateStr)) openBookingModal(null, { date: dateStr, time: timeStr });
          lastDateClick = { time: 0, dateStr: "" };
          return;
        }
        lastDateClick = { time: now, dateStr: dateStr + timeStr };
      },
    });
    calendar.render();

    document.getElementById("cal-prev")?.addEventListener("click", () => calendar.prev());
    document.getElementById("cal-next")?.addEventListener("click", () => calendar.next());
    document.getElementById("cal-today")?.addEventListener("click", () => calendar.today());

    btnDay?.addEventListener("click", () => {
      calendar.changeView("timeGridDay");
      btnDay.classList.add("active");
      btnWeek?.classList.remove("active");
    });
    btnWeek?.addEventListener("click", () => {
      calendar.changeView("timeGridWeek");
      btnWeek.classList.add("active");
      btnDay?.classList.remove("active");
    });
    btnWeek?.classList.add("active");
  }

  // Messages
  const msgModal = document.getElementById("od-msg-modal");
  const msgText = document.getElementById("od-modal-text");
  const msgLinks = document.getElementById("od-modal-links");

  document.querySelectorAll("[data-message-booking]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.messageBooking;
      const type = btn.dataset.messageType || "approved";
      const res = await fetch(`${config.messageUrlBase}${id}/message/?type=${type}`);
      const data = await res.json();
      msgText.textContent = data.message;
      msgLinks.innerHTML = `
        <a class="od-btn od-btn-primary" href="${data.links.viber}" target="_blank" rel="noopener">Viber</a>
        <a class="od-btn od-btn-primary" href="${data.links.whatsapp}" target="_blank" rel="noopener">WhatsApp</a>
        <a class="od-btn od-btn-ghost" href="${data.links.sms}">SMS</a>
        <a class="od-btn od-btn-ghost" href="${data.links.tel}">Call</a>
        <button type="button" class="od-btn od-btn-ghost" id="od-copy-msg">Copy message</button>`;
      document.getElementById("od-copy-msg")?.addEventListener("click", () => navigator.clipboard.writeText(data.message));
      openModal("od-msg-modal");
    });
  });

  document.getElementById("od-modal-close")?.addEventListener("click", () => closeModal("od-msg-modal"));

  window.odOpenBookingModal = openBookingModal;
  window.odOpenBlockModal = openBlockModal;

  // ── Toggle checkboxes (working hours + policy) ──────────────────────────────
  function initToggles() {
    document.querySelectorAll(
      ".od-hours-edit-row input[type='checkbox'], " +
      ".od-section#od-sec-policy input[type='checkbox']"
    ).forEach(cb => cb.classList.add("od-toggle-cb"));
  }
  initToggles();
}
