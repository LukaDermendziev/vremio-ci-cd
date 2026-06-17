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
      setTimeout(() => {
        calendar?.updateSize();
        calendar?.refetchEvents();
      }, 100);
    }
  }

  document.querySelectorAll("[data-section]").forEach(el => {
    el.addEventListener("click", e => {
      e.preventDefault();
      showSection(el.dataset.section);
      history.replaceState(null, "", "#" + el.dataset.section);
    });
  });

  document.querySelectorAll("[data-goto]").forEach(el => {
    el.addEventListener("click", () => showSection(el.dataset.goto));
  });

  const hash = location.hash.replace("#", "");
  showSection(hash || "dashboard");

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
    slotsSelect.innerHTML = data.slots.length
      ? data.slots.map(s => `<option value="${s.value}">${s.label}</option>`).join("")
      : '<option value="">No slots available</option>';
    if (startInput?.value && data.slots.some(s => s.value === startInput.value)) {
      slotsSelect.value = startInput.value;
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

  async function openBookingModal(bookingId, preset = {}) {
    bookingForm.reset();
    bookingForm.querySelector('[name="booking_id"]').value = "";
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

  document.querySelectorAll("[data-edit-booking]").forEach(btn => {
    btn.addEventListener("click", () => openBookingModal(btn.dataset.editBooking));
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

  // Calendar
  const calEl = document.getElementById("od-calendar");
  const rangeLabel = document.getElementById("cal-range-label");
  const btnDay = document.getElementById("cal-view-day");
  const btnWeek = document.getElementById("cal-view-week");

  function formatRange(start, end, viewType) {
    const opts = { month: "long", day: "numeric", year: "numeric" };
    const optsShort = { month: "short", day: "numeric" };
    if (viewType === "timeGridDay") {
      return start.toLocaleDateString(undefined, opts);
    }
    const endDisplay = new Date(end);
    endDisplay.setDate(endDisplay.getDate() - 1);
    return `${start.toLocaleDateString(undefined, optsShort)} – ${endDisplay.toLocaleDateString(undefined, opts)}`;
  }

  function isClosedDate(dateStr) {
    const d = new Date(dateStr + "T12:00:00");
    const djangoWeekday = (d.getDay() + 6) % 7;
    return calendarMeta.closedDates.includes(dateStr) || calendarMeta.closedWeekdays.includes(djangoWeekday);
  }

  async function fetchCalendarEvents(info, successCallback, failureCallback) {
    try {
      const res = await fetch(`${config.eventsUrl}?start=${info.startStr}&end=${info.endStr}`);
      const data = await res.json();
      calendarMeta = { closedDates: data.closedDates || [], closedWeekdays: data.closedWeekdays || [] };
      successCallback(data.events || []);
    } catch (err) {
      failureCallback(err);
    }
  }

  if (calEl && window.FullCalendar) {
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

  // ── Calendar per-slot hover (snaps to 30-min rows within the hovered column) ─
  if (calEl) {
    let _hoverEl = null;

    function _clearSlotHover() {
      if (_hoverEl) { _hoverEl.remove(); _hoverEl = null; }
    }

    calEl.addEventListener("mousemove", e => {
      if (e.target.closest(".fc-event")) { _clearSlotHover(); return; }
      const col = e.target.closest(".fc-timegrid-col");
      if (!col) { _clearSlotHover(); return; }

      const frame = col.querySelector(".fc-timegrid-col-frame");
      if (!frame) { _clearSlotHover(); return; }

      const slotEl = calEl.querySelector(".fc-timegrid-slot-lane");
      const slotH = slotEl ? slotEl.offsetHeight : 42;

      const frameRect = frame.getBoundingClientRect();
      const relY = e.clientY - frameRect.top;
      const slotIdx = Math.max(0, Math.floor(relY / slotH));
      const snapY = slotIdx * slotH;

      if (!_hoverEl) {
        _hoverEl = document.createElement("div");
        _hoverEl.style.cssText =
          "position:absolute;left:0;right:0;pointer-events:none;" +
          "background:rgba(0,0,0,0.035);border-radius:2px;z-index:1;" +
          "transition:top 0.06s;";
      }
      if (_hoverEl.parentNode !== frame) {
        _clearSlotHover();
        _hoverEl = document.createElement("div");
        _hoverEl.style.cssText =
          "position:absolute;left:0;right:0;pointer-events:none;" +
          "background:rgba(0,0,0,0.035);border-radius:2px;z-index:1;" +
          "transition:top 0.06s;";
        frame.style.position = "relative";
        frame.appendChild(_hoverEl);
      }
      _hoverEl.style.top = snapY + "px";
      _hoverEl.style.height = slotH + "px";
    });

    calEl.addEventListener("mouseleave", _clearSlotHover);
    // Also clear when hovering an event
    calEl.addEventListener("mouseenter", e => {
      if (e.target.closest(".fc-event")) _clearSlotHover();
    }, true);
  }
}
