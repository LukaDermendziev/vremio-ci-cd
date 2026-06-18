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
      cell.addEventListener("dblclick", () => {
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
      row.addEventListener("dblclick", () => {
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
