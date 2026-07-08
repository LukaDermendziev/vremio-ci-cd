/* Owner dashboard: navigation, modals, calendar */

function initOwnerDashboard(config) {
  const I18N = window.OD_I18N || {};
  const CG_LOCALE = config.locale || document.documentElement.lang || "mk";

  const CG_IS_MK = String(CG_LOCALE || "").toLowerCase().startsWith("mk");
  const CG_MONTHS_MK_SHORT = ["јан", "фев", "мар", "апр", "мај", "јун", "јул", "авг", "сеп", "окт", "ное", "дек"];
  const CG_MONTHS_MK_LONG = ["јануари", "февруари", "март", "април", "мај", "јуни", "јули", "август", "септември", "октомври", "ноември", "декември"];
  const CG_WEEKDAYS_MK_LONG = ["недела", "понеделник", "вторник", "среда", "четврток", "петок", "сабота"];
  const t = (key, fallback) => (I18N[key] != null && I18N[key] !== "") ? I18N[key] : fallback;
  const tf = (key, fallback, vars) => {
    let s = t(key, fallback);
    if (vars) {
      Object.entries(vars).forEach(([k, v]) => {
        s = s.replace(new RegExp(`%\\(${k}\\)s`, "g"), v);
      });
    }
    return s;
  };

  function formatDateDigitsInput(value) {
    const digits = value.replace(/\D/g, "").slice(0, 8);
    if (digits.length <= 2) return digits;
    if (digits.length <= 4) return `${digits.slice(0, 2)}/${digits.slice(2)}`;
    return `${digits.slice(0, 2)}/${digits.slice(2, 4)}/${digits.slice(4)}`;
  }

  function formatDateDisplayInput(value) {
    if (!value) return "";
    const sanitized = value.replace(/[^\d/]/g, "");
    const parts = sanitized.split("/").slice(0, 3);
    const digits = sanitized.replace(/\D/g, "").slice(0, 8);

    // Single-digit day/month or trailing slash — keep manual dd/m/yyyy entry.
    const manualEntry =
      sanitized.endsWith("/") ||
      (parts[0]?.length === 1 && parts.length > 1) ||
      (parts[1]?.length === 1 && parts.length > 2);

    if (manualEntry) {
      const limits = [2, 2, 4];
      return parts.map((part, index) => part.slice(0, limits[index])).join("/");
    }

    // Otherwise rebuild from digits so year digits are not trapped in the month segment.
    return formatDateDigitsInput(digits);
  }

  function applyDateDisplayMask(input) {
    const selStart = input.selectionStart ?? input.value.length;
    const digitsBeforeCaret = input.value.slice(0, selStart).replace(/\D/g, "").length;
    const formatted = formatDateDisplayInput(input.value);
    if (formatted === input.value) return;

    input.value = formatted;

    let digitsSeen = 0;
    let newCaret = formatted.length;
    for (let i = 0; i < formatted.length; i++) {
      if (/\d/.test(formatted[i])) {
        digitsSeen++;
        if (digitsSeen >= digitsBeforeCaret) {
          newCaret = i + 1;
          break;
        }
      }
    }
    try {
      input.setSelectionRange(newCaret, newCaret);
    } catch (_) {
      /* ignore */
    }
  }

  function isoToDisplay(iso) {
    if (!iso || !/^\d{4}-\d{2}-\d{2}$/.test(iso)) return "";
    const [y, m, d] = iso.split("-");
    return `${d}/${m}/${y}`;
  }

  function displayToIso(display) {
    if (!display) return "";
    const match = display.trim().match(/^(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})$/);
    if (!match) return "";
    const day = match[1].padStart(2, "0");
    const month = match[2].padStart(2, "0");
    const year = match[3];
    const dt = new Date(`${year}-${month}-${day}T12:00:00`);
    if (Number.isNaN(dt.getTime())) return "";
    if (dt.getFullYear() !== Number(year) || dt.getMonth() + 1 !== Number(month) || dt.getDate() !== Number(day)) {
      return "";
    }
    return `${year}-${month}-${day}`;
  }

  function todayIsoLocal() {
    const now = new Date();
    const y = now.getFullYear();
    const m = String(now.getMonth() + 1).padStart(2, "0");
    const d = String(now.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  }

  function isBeforeToday(iso) {
    return !!iso && iso < todayIsoLocal();
  }

  function validateOwnerDateField(wrap, { report = false } = {}) {
    const display = wrap?.querySelector(".od-date-display");
    const hidden = wrap?.querySelector(".od-date-value");
    if (!display || !hidden) return true;

    const iso = hidden.value || displayToIso(display.value);
    if (!iso) {
      display.setCustomValidity("");
      return true;
    }

    if (isBeforeToday(iso) && iso !== (wrap.dataset.initialDateIso || "")) {
      display.setCustomValidity(t("dateInPast", "Choose today or a future date."));
      if (report) display.reportValidity();
      return false;
    }

    display.setCustomValidity("");
    return true;
  }

  function refreshNativeDateMins(root = document) {
    const min = todayIsoLocal();
    root.querySelectorAll(".od-date-native").forEach(el => {
      el.min = min;
    });
  }

  function setDateFieldInitialIso(wrap, iso) {
    if (wrap) wrap.dataset.initialDateIso = iso || "";
  }

  function setDateFieldValue(wrap, iso) {
    if (!wrap) return;
    const display = wrap.querySelector(".od-date-display");
    const hidden = wrap.querySelector(".od-date-value");
    const native = wrap.querySelector(".od-date-native");
    const cleanIso = iso || "";
    if (hidden) hidden.value = cleanIso;
    if (display) {
      display.value = cleanIso ? isoToDisplay(cleanIso) : "";
      display.setCustomValidity("");
    }
    if (native) native.value = cleanIso;
  }

  function initDateField(wrap) {
    if (!wrap || wrap.dataset.odDateInit) return;
    wrap.dataset.odDateInit = "1";
    const display = wrap.querySelector(".od-date-display");
    const hidden = wrap.querySelector(".od-date-value");
    const native = wrap.querySelector(".od-date-native");
    const btn = wrap.querySelector(".od-date-picker-btn");
    if (!display || !hidden) return;

    if (hidden.value) setDateFieldValue(wrap, hidden.value);
    if (native) native.min = todayIsoLocal();

    display.addEventListener("blur", () => {
      if (!display.value.trim()) {
        display.setCustomValidity("");
        setDateFieldValue(wrap, "");
        hidden.dispatchEvent(new Event("change", { bubbles: true }));
        return;
      }
      const iso = displayToIso(display.value);
      if (!iso) {
        display.setCustomValidity(t("dateFormatInvalid", "Use dd/mm/yyyy"));
        display.reportValidity();
        return;
      }
      if (isBeforeToday(iso) && iso !== (wrap.dataset.initialDateIso || "")) {
        display.setCustomValidity(t("dateInPast", "Choose today or a future date."));
        display.reportValidity();
        return;
      }
      display.setCustomValidity("");
      setDateFieldValue(wrap, iso);
      hidden.dispatchEvent(new Event("change", { bubbles: true }));
    });

    display.addEventListener("input", () => {
      display.setCustomValidity("");
      applyDateDisplayMask(display);
    });

    native?.addEventListener("change", () => {
      if (native.value && isBeforeToday(native.value) && native.value !== (wrap.dataset.initialDateIso || "")) {
        display.setCustomValidity(t("dateInPast", "Choose today or a future date."));
        display.reportValidity();
        setDateFieldValue(wrap, "");
        return;
      }
      setDateFieldValue(wrap, native.value);
      validateOwnerDateField(wrap);
      hidden.dispatchEvent(new Event("change", { bubbles: true }));
    });

    btn?.addEventListener("click", () => {
      if (native?.showPicker) native.showPicker();
      else native?.focus();
    });
  }

  function initDateFields(root = document) {
    root.querySelectorAll("[data-od-date-field]").forEach(initDateField);
  }

  function syncAllDateFields(form) {
    form?.querySelectorAll("[data-od-date-field]").forEach(wrap => {
      const display = wrap.querySelector(".od-date-display");
      const iso = display?.value.trim() ? displayToIso(display.value) : "";
      if (display?.value.trim() && !iso) return;
      setDateFieldValue(wrap, iso);
    });
  }

  initDateFields();
  refreshNativeDateMins();

  document.querySelectorAll(".od-form").forEach(form => {
    form.addEventListener("submit", e => {
      syncAllDateFields(form);
      let valid = true;
      let firstInvalidWrap = null;
      form.querySelectorAll("[data-od-date-field]").forEach(wrap => {
        if (!validateOwnerDateField(wrap)) {
          valid = false;
          if (!firstInvalidWrap) firstInvalidWrap = wrap;
        }
      });
      if (!valid) {
        firstInvalidWrap?.querySelector(".od-date-display")?.reportValidity();
        e.preventDefault();
      }
    });
  });

  let calendar = null;
  let calendarMeta = { closedDates: [], closedWeekdays: [] };
  let lastDateClick = { time: 0, dateStr: "" };

  function openModal(id) {
    document.getElementById(id)?.classList.add("open");
    document.body.classList.add("od-modal-open");
  }

  function closeModal(id) {
    document.getElementById(id)?.classList.remove("open");
    if (!document.querySelector(".od-modal-overlay.open")) {
      document.body.classList.remove("od-modal-open");
    }
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
    document.body.classList.remove("od-modal-open");
  }

  document.querySelectorAll("[data-close-modal]").forEach(btn => {
    btn.addEventListener("click", () => closeModal(btn.dataset.closeModal));
  });

  document.querySelectorAll(".od-modal-overlay").forEach(overlay => {
    overlay.addEventListener("click", e => {
      if (e.target === overlay) closeModal(overlay.id);
    });
  });

  function showSection(id, options = {}) {
    document.querySelectorAll(".od-section").forEach(s => s.classList.remove("active"));
    document.querySelectorAll(".od-nav a").forEach(a => a.classList.remove("is-active"));
    document.getElementById("od-sec-" + id)?.classList.add("active");
    document.querySelector(`.od-nav a[data-section="${id}"]`)?.classList.add("is-active");
    if (id === "calendar") {
      setTimeout(() => {
        if (options.calendarToday && typeof window.odGoToCalendarToday === "function") {
          window.odGoToCalendarToday();
        } else if (typeof window.odCgFetchAndRender === "function") {
          window.odCgFetchAndRender();
        }
      }, 100);
    }
  }

  // ── Mobile sidebar + bottom nav ──────────────────────────────────────────
  let savedScrollY = 0;

  const sidebar    = document.querySelector(".od-sidebar");
  const backdrop   = document.getElementById("od-backdrop");
  const hamClose   = document.getElementById("od-ham-close");
  const bnMoreBtn  = document.getElementById("od-bn-more");

  function lockPageScroll() {
    savedScrollY = window.scrollY || document.documentElement.scrollTop || 0;
    document.body.style.top = `-${savedScrollY}px`;
    document.body.style.position = "fixed";
    document.body.style.width = "100%";
  }

  function unlockPageScroll() {
    document.body.style.position = "";
    document.body.style.top = "";
    document.body.style.width = "";
    window.scrollTo(0, savedScrollY);
  }

  function openSidebar() {
    if (sidebar?.classList.contains("is-open")) return;
    lockPageScroll();
    sidebar?.classList.add("is-open");
    backdrop?.classList.add("is-visible");
    document.body.classList.add("od-sidebar-open");
  }

  function closeSidebar() {
    if (!sidebar?.classList.contains("is-open")) return;
    sidebar?.classList.remove("is-open");
    backdrop?.classList.remove("is-visible");
    document.body.classList.remove("od-sidebar-open");
    unlockPageScroll();
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
      closeAllModals();
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

  function activateBookingTab(status) {
    const tab = document.querySelector(`.od-tab[data-tab="${status}"]`);
    if (tab) tab.click();
  }

  document.querySelectorAll("[data-goto]").forEach(el => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      const section = el.dataset.goto;
      showSection(section, {
        calendarToday: section === "calendar" && el.hasAttribute("data-calendar-today"),
      });
      history.replaceState(null, "", "#" + section);
      syncBottomNav(section);
      if (el.dataset.bookingTab && section === "bookings") {
        activateBookingTab(el.dataset.bookingTab);
      }
    });
  });

  window.addEventListener("popstate", () => {
    const section = location.hash.replace("#", "") || "dashboard";
    showSection(section);
    syncBottomNav(section);
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
        empty.textContent = t("noBookingsInCategory", "No bookings in this category.");
        document.getElementById("bk-list")?.appendChild(empty);
      }
      if (empty) empty.style.display = shown === 0 ? "block" : "none";
    });
  });
  tabs[0]?.click();

  // Booking modal
  const bookingModal = "od-booking-modal";
  const bookingForm = document.getElementById("od-booking-form");
  const servicesContainer = document.getElementById("od-booking-services");
  const servicesSummary = document.getElementById("od-owner-services-summary");
  const scheduleSection = document.getElementById("od-booking-schedule");
  const scheduleBody = document.getElementById("od-booking-schedule-body");
  const dateInput = document.getElementById("od-booking-date");
  const startInput = document.getElementById("od-booking-start-time");
  const slotsSelect = document.getElementById("od-owner-slots");
  const bookingDeleteBtn = document.getElementById("od-booking-delete");
  const bookingDeleteForm = document.getElementById("od-booking-delete-form");

  function getSelectedServiceIds() {
    return [...(servicesContainer?.querySelectorAll('input[name="services"]:checked') || [])]
      .map(el => el.value);
  }

  function setSelectedServices(serviceIds) {
    if (!servicesContainer) return;
    const idSet = new Set((serviceIds || []).map(String));
    servicesContainer.querySelectorAll('input[name="services"]').forEach(cb => {
      cb.checked = idSet.has(cb.value);
    });
    updateOwnerServicesSummary();
  }

  function updateOwnerServicesSummary() {
    const checked = [...(servicesContainer?.querySelectorAll('input[name="services"]:checked') || [])];
    if (!servicesSummary) return;
    if (!checked.length) {
      servicesSummary.textContent = "";
      return;
    }
    const gap = parseInt(config.serviceGapMinutes || 30, 10);
    let total = checked.reduce((sum, el) => sum + parseInt(el.dataset.duration || "0", 10), 0);
    if (checked.length > 1) total += gap * (checked.length - 1);
    const names = checked.map(el => {
      const label = el.closest("label");
      return label ? label.textContent.trim() : "";
    }).filter(Boolean);
    servicesSummary.textContent = `${names.join(" + ")} · ${total} ${t("minSuffix", "min")}`;
  }

  function renderBookingSchedule(data) {
    if (!scheduleSection || !scheduleBody) return;
    const rows = data?.service_schedule || [];
    if (!rows.length) {
      scheduleSection.hidden = true;
      scheduleBody.innerHTML = "";
      return;
    }
    scheduleSection.hidden = false;
    scheduleBody.innerHTML = rows.map(row => `
      <tr>
        <td>${row.name || ""}</td>
        <td>${row.start_time || ""}</td>
        <td>${row.end_time || ""}</td>
        <td>${row.duration_minutes || ""} ${t("minSuffix", "min")}</td>
      </tr>
    `).join("");
  }

  async function loadOwnerSlots() {
    const warning = document.getElementById("od-slots-warning");
    const serviceIds = getSelectedServiceIds();
    if (!serviceIds.length || !dateInput?.value) {
      if (warning) warning.style.display = "none";
      return;
    }
    const exclude = bookingForm.querySelector('[name="booking_id"]')?.value || "";
    const isEdit = Boolean(exclude);
    const url = `${config.slotsUrl}?services=${serviceIds.join(",")}&date=${dateInput.value}&exclude=${exclude}`;
    const res = await fetch(url);
    const data = await res.json();
    if (!slotsSelect) return;

    const prevTime = startInput?.value || "";
    const slotsAvailable = data.slots || [];

    slotsSelect.innerHTML = slotsAvailable.length
      ? slotsAvailable.map(s => `<option value="${s.value}">${s.label}</option>`).join("")
      : `<option value="">${t("noSlotsAvailable", "No slots available")}</option>`;

    if (prevTime && slotsAvailable.length && slotsAvailable.some(s => s.value === prevTime)) {
      slotsSelect.value = prevTime;
      if (warning) warning.style.display = "none";
    } else if (isEdit && prevTime && slotsAvailable.length && !slotsAvailable.some(s => s.value === prevTime)) {
      if (warning) {
        warning.textContent = tf("timeNoLongerAvailable", "The time %(time)s is no longer available. Please select another slot.", { time: prevTime });
        warning.style.display = "block";
      }
    } else {
      if (warning) warning.style.display = "none";
      if (slotsAvailable.length) {
        slotsSelect.value = slotsAvailable[0].value;
      }
    }

    startInput.value = slotsSelect.value || "";
  }

  servicesContainer?.addEventListener("change", () => {
    updateOwnerServicesSummary();
    loadOwnerSlots();
  });
  dateInput?.addEventListener("change", loadOwnerSlots);
  slotsSelect?.addEventListener("change", () => { startInput.value = slotsSelect.value; });

  function fillBookingForm(data) {
    bookingForm.querySelector('[name="booking_id"]').value = data.id || "";
    bookingForm.querySelector('[name="full_name"]').value = data.full_name || "";
    bookingForm.querySelector('[name="phone_number"]').value = data.phone_number || "";
    bookingForm.querySelector('[name="instagram_username"]').value = data.instagram_username || "";
    bookingForm.querySelector('[name="email"]').value = data.email || "";
    bookingForm.querySelector('[name="preferred_contact_method"]').value = data.preferred_contact_method || "viber";
    if (data.service_ids?.length) setSelectedServices(data.service_ids);
    else if (data.service_id) setSelectedServices([data.service_id]);
    else setSelectedServices([]);
    const dateWrap = dateInput?.closest("[data-od-date-field]");
    setDateFieldValue(dateWrap, data.date || "");
    setDateFieldInitialIso(dateWrap, data.date || "");
    startInput.value = data.start_time || "";
    bookingForm.querySelector('[name="status"]').value = data.status || "approved";
    bookingForm.querySelector('[name="source"]').value = data.source || "owner_manual";
    bookingForm.querySelector('[name="owner_note"]').value = data.owner_note || "";
    const customerNoteWrap = document.getElementById("od-booking-customer-note-wrap");
    const customerNoteEl = document.getElementById("od-booking-customer-note");
    if (customerNoteWrap && customerNoteEl) {
      const note = (data.customer_note || "").trim();
      if (note) {
        customerNoteEl.textContent = note;
        customerNoteWrap.hidden = false;
      } else {
        customerNoteEl.textContent = "";
        customerNoteWrap.hidden = true;
      }
    }
    updateReferencePhotoSection(data);
    updateBookingCustomerActions(data);
    renderBookingSchedule(data);
  }

  function updateBookingCustomerActions(data) {
    const section = document.getElementById("od-booking-customer-actions");
    const callLink = document.getElementById("od-booking-call");
    const emailLink = document.getElementById("od-booking-email");
    const blockBtn = document.getElementById("od-booking-block-customer");
    if (!section) return;

    if (!data?.id) {
      section.hidden = true;
      return;
    }

    section.hidden = false;
    if (callLink && data.phone_number) {
      callLink.href = `tel:${data.phone_number}`;
      callLink.hidden = false;
    } else if (callLink) {
      callLink.hidden = true;
    }

    if (emailLink) {
      if (data.email) {
        emailLink.href = `mailto:${data.email}`;
        emailLink.hidden = false;
      } else {
        emailLink.hidden = true;
      }
    }

    if (blockBtn) {
      blockBtn.dataset.customerId = data.customer_id || "";
      blockBtn.dataset.bookingId = data.id || "";
      blockBtn.dataset.customerName = data.full_name || "";
      blockBtn.dataset.phone = data.phone_number || "";
      blockBtn.dataset.email = data.email || "";
      blockBtn.dataset.bookingReference = data.booking_reference || "";
      blockBtn.disabled = Boolean(data.is_customer_blocked);
      blockBtn.textContent = data.is_customer_blocked
        ? t("alreadyBlocked", "Already blocked")
        : t("blockCustomer", "Block customer");
      if (!blockBtn.dataset.odBlockBound) {
        blockBtn.dataset.odBlockBound = "1";
        blockBtn.addEventListener("click", (e) => {
          e.preventDefault();
          window.odOpenBlockCustomerModal({
            customerId: blockBtn.dataset.customerId,
            bookingId: blockBtn.dataset.bookingId,
            customer_name: blockBtn.dataset.customerName,
            phone_number: blockBtn.dataset.phone,
            email: blockBtn.dataset.email,
            booking_reference: blockBtn.dataset.bookingReference,
            is_blocked: blockBtn.disabled,
          });
        });
      }
    }
  }

  function updateReferencePhotoSection(data) {
    const section = document.getElementById("od-booking-photo-section");
    const emptyEl = document.getElementById("od-booking-photo-empty");
    const previewEl = document.getElementById("od-booking-photo-preview");
    const imgEl = document.getElementById("od-booking-photo-img");
    const showBtn = document.getElementById("od-booking-photo-show");
    const deleteBtn = document.getElementById("od-booking-photo-delete");
    if (!section) return;
    const hasPhoto = data.has_reference_photo && data.reference_photo_url;
    section.hidden = !data.id;
    if (!data.id) return;
    if (hasPhoto) {
      emptyEl.hidden = true;
      previewEl.hidden = false;
      imgEl.src = data.reference_photo_url;
      if (showBtn) {
        showBtn.onclick = () => openPhotoPreview(data.reference_photo_url, data);
      }
      if (deleteBtn) {
        deleteBtn.dataset.bkId = String(data.id);
        if (!deleteBtn._photoActionBound) {
          deleteBtn._photoActionBound = true;
          bindBkAction(deleteBtn);
        }
      }
    } else {
      emptyEl.hidden = false;
      previewEl.hidden = true;
      imgEl.removeAttribute("src");
    }
  }

  function openPhotoPreview(url, bookingData = null) {
    if (!url) return;
    const img = document.getElementById("od-photo-modal-img");
    const link = document.getElementById("od-photo-modal-open");
    const blockBtn = document.getElementById("od-photo-modal-block");
    if (img) img.src = url;
    if (link) link.href = url;
    if (blockBtn) {
      const card = bookingData || {};
      const hasContext = card.id || card.customer_id;
      blockBtn.hidden = !hasContext;
      if (hasContext) {
        blockBtn.dataset.customerId = card.customer_id || "";
        blockBtn.dataset.bookingId = card.id || "";
        blockBtn.dataset.customerName = card.full_name || "";
        blockBtn.dataset.phone = card.phone_number || "";
        blockBtn.dataset.email = card.email || "";
        blockBtn.dataset.bookingReference = card.booking_reference || "";
      }
    }
    openModal("od-photo-modal");
  }

  document.addEventListener("click", (e) => {
    const trigger = e.target.closest("[data-photo-preview]");
    if (trigger) {
      e.preventDefault();
      const card = trigger.closest(".od-bk-card");
      const bookingData = card ? {
        id: card.dataset.bookingId,
        customer_id: card.dataset.customerId,
        full_name: card.dataset.fullName,
        phone_number: card.dataset.phone,
        email: card.dataset.email,
        booking_reference: card.dataset.bookingId
          ? `#${card.dataset.bookingId} · ${card.dataset.date || ""} ${card.dataset.startTime || ""}`.trim()
          : "",
      } : null;
      openPhotoPreview(trigger.dataset.photoPreview, bookingData);
    }
  });

  function getCurrentSection() {
    return document.querySelector(".od-section.active")?.id?.replace("od-sec-", "") || "dashboard";
  }

  async function openBookingModal(bookingId, preset = {}) {
    bookingForm.reset();
    const warning = document.getElementById("od-slots-warning");
    if (warning) {
      warning.style.display = "none";
      warning.textContent = "";
    }
    const dateWrap = dateInput?.closest("[data-od-date-field]");
    setDateFieldValue(dateWrap, "");
    setDateFieldInitialIso(dateWrap, "");
    bookingForm.querySelector('[name="booking_id"]').value = "";
    // Set return_section dynamically so Save/Delete lands back where the owner is
    const returnSec = getCurrentSection();
    bookingForm.querySelector('[name="return_section"]').value = returnSec;
    bookingDeleteForm.querySelector('[name="return_section"]').value = returnSec;
    document.getElementById("od-booking-modal-title").textContent = bookingId ? t("editBooking", "Edit booking") : t("addBooking", "Add booking");
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
          service_ids: (card.dataset.serviceIds || "").split(",").filter(Boolean).map(Number),
          date: card.dataset.date,
          start_time: card.dataset.startTime,
          status: card.dataset.status,
          source: card.dataset.source,
          owner_note: card.dataset.ownerNote,
          customer_note: card.dataset.customerNote,
          has_reference_photo: card.dataset.hasPhoto === "true",
          reference_photo_url: card.dataset.photoUrl || null,
        });
      }
      try {
        const res = await fetch(`${config.bookingDetailUrl}${bookingId}/detail/`);
        if (res.ok) fillBookingForm(await res.json());
      } catch (_) { /* card fallback above */ }
      bookingDeleteForm.querySelector('[name="booking_id"]').value = bookingId;
    } else if (preset.date) {
      setDateFieldValue(dateInput?.closest("[data-od-date-field]"), preset.date);
      if (preset.time) startInput.value = preset.time;
      bookingForm.querySelector('[name="status"]').value = "approved";
      bookingForm.querySelector('[name="source"]').value = "owner_manual";
      updateReferencePhotoSection({});
      updateBookingCustomerActions({});
      renderBookingSchedule({});
    } else {
      updateReferencePhotoSection({});
      updateBookingCustomerActions({});
      renderBookingSchedule({});
    }

    await loadOwnerSlots();
    openModal(bookingModal);
  }

  bookingForm?.addEventListener("submit", () => {
    if (slotsSelect?.value) startInput.value = slotsSelect.value;
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
    document.getElementById("od-service-modal-title").textContent = serviceId ? t("editService", "Edit service") : t("addService", "Add service");
    serviceDeleteBtn.style.display = serviceId ? "" : "none";

    if (serviceId) {
      const row = document.querySelector(`.od-svc-card[data-service-id="${serviceId}"]`);
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

  // ── AJAX booking status actions (no page reload) ─────────────────────────────
  const STATUS_LABELS = {
    pending: t("statusPending", "Pending"),
    approved: t("statusApproved", "Approved"),
    rejected: t("statusRejected", "Rejected"),
    cancelled: t("statusCancelled", "Cancelled"),
    completed: t("statusCompleted", "Completed"),
    no_show: t("statusNoShow", "No Show"),
  };
  const CONFIRM_ACTIONS = {
    reject: t("confirmRejectBooking", "Reject this booking?"),
    cancel: t("confirmCancelBooking", "Cancel this booking?"),
    mark_no_show: t("confirmMarkNoShow", "Mark as no-show?"),
    delete_reference_photo: t("confirmDeletePhoto", "Delete this reference photo?"),
  };

  function bkActionButtons(status, bookingId) {
    const b = id => `data-bk-id="${id}"`;
    const btn = (action, label, cls) =>
      `<button class="od-btn ${cls} od-btn-sm" type="button" data-bk-action="${action}" ${b(bookingId)}>${label}</button>`;
    let html = "";
    if (status === "pending") {
      html += btn("approve", t("approve", "Approve"), "od-btn-success");
      html += btn("reject",  t("reject", "Reject"),  "od-btn-danger");
    }
    if (status === "approved") {
      html += btn("mark_completed", t("markCompleted", "Mark completed"), "od-btn-ghost");
      html += btn("mark_no_show",   t("noShow", "No-show"),        "od-btn-ghost");
      html += btn("cancel",         t("cancel", "Cancel"),         "od-btn-ghost");
    }
    return html;
  }

  function syncPendingCount(count) {
    const n = Number(count);
    if (Number.isNaN(n)) return;
    document.querySelectorAll('[data-stat="pending"]').forEach(el => {
      el.textContent = String(n);
      if (el.tagName === "EM" && el.closest(".od-quick-action")) {
        el.hidden = n === 0;
      }
    });
  }

  async function sendBookingAction(action, bookingId, card) {
    const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
    const body = new URLSearchParams({ action, booking_id: bookingId, return_section: "bookings" });
    try {
      const resp = await fetch("/owner/dashboard/", {
        method: "POST",
        headers: { "X-CSRFToken": csrf, "X-Requested-With": "fetch",
                   "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
      if (!resp.ok) throw new Error("Server error");
      const data = await resp.json();
      if (!data.ok) {
        const errMsg = (data.messages || []).find(m => m[0] === "error" || m[0] === "danger");
        throw new Error(errMsg ? errMsg[1] : "Action failed");
      }

      if (action === "delete_reference_photo") {
        if (card) {
          const photoControls = card.querySelector(".od-photo-controls");
          if (photoControls) {
            photoControls.outerHTML = `<p class="od-photo-none">${t("noPhotoAttached", "No photo attached.")}</p>`;
          }
          card.dataset.hasPhoto = "false";
          delete card.dataset.photoUrl;
        }
        updateReferencePhotoSection({
          id: bookingId,
          has_reference_photo: false,
          reference_photo_url: null,
        });
        const msg = (data.messages || []).find(m => m[0] === "success");
        showToast(msg ? msg[1] : t("photoRemoved", "Photo removed."));
        return;
      }

      // Infer the new status from the action name
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

      // ── 1. Update card's data-status ─────────────────────────────────────────
      card.dataset.status = newStatus;

      // ── 2. Update the visible status badge ───────────────────────────────────
      const badge = card.querySelector(".od-bk-status-badge");
      if (badge) {
        badge.textContent = newStatusDisplay;
        badge.className = `od-badge od-badge-${newStatus} od-bk-status-badge`;
      }

      // ── 3. Swap action buttons to match new status ───────────────────────────
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

      // ── 4. Toast ──────────────────────────────────────────────────────────────
      if (data.messages?.length) {
        showToast(data.messages[0][1], data.messages[0][0] === "success" ? "success" : "error");
      }

      // ── 5. Sync overview stat counters without a full reload ─────────────────
      if (data.pending_count !== undefined) {
        syncPendingCount(data.pending_count);
      }
      if (data.today_count !== undefined) {
        document.querySelectorAll('[data-stat="today"]').forEach(el => {
          el.textContent = data.today_count;
        });
      }

      // ── 6. Fade out of current tab — card stays in DOM for other tabs ─────────
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

      // ── 7. Update / remove duplicate copies of this card in OTHER sections ────
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
      showToast(t("somethingWentWrong", "Something went wrong. Please try again."), "error");
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

  async function copyToClipboard(text) {
    if (!text) return false;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
        return true;
      }
    } catch (_) {
      /* fall through to execCommand */
    }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "0";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, text.length);
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch (_) {
      ok = false;
    }
    document.body.removeChild(ta);
    return ok;
  }

  function appendMessageLink(container, href, label, className) {
    if (!href) return;
    const a = document.createElement("a");
    a.className = `od-btn ${className}`;
    a.href = href;
    a.textContent = label;
    container.appendChild(a);
  }

  function renderMessageLinks(data) {
    msgLinks.innerHTML = "";
    appendMessageLink(msgLinks, data.links.viber, t("viber", "Viber"), "od-btn-primary");
    appendMessageLink(msgLinks, data.links.whatsapp, t("whatsapp", "WhatsApp"), "od-btn-primary");
    appendMessageLink(msgLinks, data.links.sms, t("sms", "SMS"), "od-btn-ghost");
    appendMessageLink(msgLinks, data.links.tel, t("call", "Call"), "od-btn-ghost");
    const copyBtn = document.createElement("button");
    copyBtn.type = "button";
    copyBtn.className = "od-btn od-btn-ghost";
    copyBtn.textContent = t("copyMessage", "Copy message");
    copyBtn.addEventListener("click", async () => {
      const ok = await copyToClipboard(data.message);
      showToast(
        ok ? t("messageCopied", "Message copied.") : t("copyFailed", "Could not copy. Long-press the message to copy."),
        ok ? "success" : "error",
      );
    });
    msgLinks.appendChild(copyBtn);
  }

  function bindBkAction(btn) {
    if (btn.dataset.odBkBound) return;
    btn.dataset.odBkBound = "1";
    btn.addEventListener("click", async () => {
      const action = btn.dataset.bkAction;
      const bookingId = btn.dataset.bkId;
      const card = btn.closest(".od-bk-card");
      if (!card && action !== "delete_reference_photo") return;
      if (CONFIRM_ACTIONS[action]) {
        const ok = window.OwnerConfirm?.ask
          ? await window.OwnerConfirm.ask(CONFIRM_ACTIONS[action])
          : confirm(CONFIRM_ACTIONS[action]);
        if (!ok) return;
      }
      if (window.OwnerAjax) {
        window.OwnerAjax.setButtonLoading(btn, true);
      } else {
        btn.disabled = true;
      }
      await sendBookingAction(action, bookingId, card);
      if (window.OwnerAjax) {
        window.OwnerAjax.setButtonLoading(btn, false);
      } else {
        btn.disabled = false;
      }
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
      const msgModal = document.getElementById("od-msg-modal");
      if (msgModal) openModal("od-msg-modal");
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
      priceItemSubmit.innerHTML = `<i class="bi bi-plus-lg"></i> ${t("addItem", "Add item")}`;
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

  function bindPriceListInteractions() {
    document.querySelectorAll("[data-manage-prices]").forEach(btn => {
      if (btn.dataset.odManagePricesBound) return;
      btn.dataset.odManagePricesBound = "1";
      btn.addEventListener("click", e => {
        e.stopPropagation();
        openPriceModal(btn.dataset.managePrices, btn.dataset.serviceName);
      });
    });

    document.querySelectorAll("[data-inline-edit-item]").forEach(btn => {
      if (btn.dataset.odInlineEditBound) return;
      btn.dataset.odInlineEditBound = "1";
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
      if (priceItemSubmit) priceItemSubmit.innerHTML = `<i class="bi bi-check-lg"></i> ${t("saveChanges", "Save changes")}`;
      openModal("od-price-modal");
      setTimeout(() => priceItemName?.focus(), 80);
    });
    });

    document.querySelectorAll(".od-svc-price-body").forEach(body => {
      const tbody = body.querySelector("tbody");
      if (!tbody || tbody.dataset.odPriceDragBound) return;
      tbody.dataset.odPriceDragBound = "1";
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
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
          "X-CSRFToken": csrf,
          "X-Requested-With": "fetch",
        },
        body: `action=reorder_price_items&item_ids=${encodeURIComponent(orderedIds)}&return_section=services`,
      }).then(async (resp) => {
        if (!resp.ok && window.OwnerAjax) {
          try {
            const data = await resp.json();
            const errMsg = (data.messages || []).find(m => m[0] === "error");
            window.OwnerAjax.showToast(errMsg ? errMsg[1] : t("somethingWentWrong", "Something went wrong."), "error");
          } catch (_) {
            window.OwnerAjax.showToast(t("somethingWentWrong", "Something went wrong."), "error");
          }
        }
      });
    });

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
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRFToken": csrf,
            "X-Requested-With": "fetch",
          },
          body: `action=reorder_price_items&item_ids=${encodeURIComponent(orderedIds)}&return_section=services`,
        }).then(async (resp) => {
          if (!resp.ok && window.OwnerAjax) {
            try {
              const data = await resp.json();
              const errMsg = (data.messages || []).find(m => m[0] === "error");
              window.OwnerAjax.showToast(errMsg ? errMsg[1] : t("somethingWentWrong", "Something went wrong."), "error");
            } catch (_) {
              window.OwnerAjax.showToast(t("somethingWentWrong", "Something went wrong."), "error");
            }
          }
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
        const touch = e.touches[0];
        if (!touchActive) {
          if (Math.abs(touch.clientY - startTouchY) > 8 || Math.abs(touch.clientX - startTouchX) > 8) {
            clearTimeout(lpTimer);
            lpTimer = null;
          }
          return;
        }
        e.preventDefault();

        const rows = [...tbody.querySelectorAll(".od-price-drag-row")];
        let over = null;
        for (const r of rows) {
          if (r === touchDragEl) continue;
          const rect = r.getBoundingClientRect();
          if (touch.clientY >= rect.top && touch.clientY <= rect.bottom) { over = r; break; }
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

      tbody.addEventListener("touchend", endTouchDrag);
      tbody.addEventListener("touchcancel", endTouchDrag);
    });

    document.querySelectorAll(".od-price-group-toggle").forEach(btn => {
      if (btn.dataset.odPriceGroupBound) return;
      btn.dataset.odPriceGroupBound = "1";
      btn.addEventListener("click", () => {
        const collapsed = btn.classList.toggle("od-group-collapsed");
        let row = btn.closest("tr").nextElementSibling;
        while (row && !row.classList.contains("od-price-group-row")) {
          row.classList.toggle("od-group-hidden", collapsed);
          row = row.nextElementSibling;
        }
      });
    });

    document.querySelectorAll("[data-price-toggle]").forEach(btn => {
      if (btn.dataset.odPriceToggleBound) return;
      btn.dataset.odPriceToggleBound = "1";
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
  }

  bindPriceListInteractions();

  priceItemClear?.addEventListener("click", resetPriceForm);

  // Customer modal
  const customerForm = document.getElementById("od-customer-form");
  const customerDeleteBtn = document.getElementById("od-customer-delete");
  const customerDeleteForm = document.getElementById("od-customer-delete-form");
  const customerBlockBtn = document.getElementById("od-customer-block");

  function openCustomerModal(customerId) {
    customerForm.reset();
    customerForm.querySelector('[name="customer_id"]').value = "";
    document.getElementById("od-customer-modal-title").textContent = customerId ? t("editCustomer", "Edit customer") : t("addCustomer", "Add customer");
    customerDeleteBtn.style.display = customerId ? "" : "none";
    if (customerBlockBtn) customerBlockBtn.style.display = customerId ? "" : "none";

    if (customerId) {
      const row = document.querySelector(`tr[data-customer-id="${customerId}"]`);
      if (row) {
        customerForm.querySelector('[name="customer_id"]').value = customerId;
        customerForm.querySelector('[name="full_name"]').value = row.dataset.fullName || "";
        customerForm.querySelector('[name="phone_number"]').value = row.dataset.phone || "";
        customerForm.querySelector('[name="instagram_username"]').value = row.dataset.instagram || "";
        customerForm.querySelector('[name="email"]').value = row.dataset.email || "";
        customerForm.querySelector('[name="preferred_contact_method"]').value = row.dataset.contact || "viber";
        if (customerBlockBtn) {
          customerBlockBtn.dataset.customerId = customerId;
          customerBlockBtn.dataset.customerName = row.dataset.fullName || "";
          customerBlockBtn.dataset.phone = row.dataset.phone || "";
          customerBlockBtn.dataset.email = row.dataset.email || "";
          delete customerBlockBtn.dataset.bookingId;
          delete customerBlockBtn.dataset.bookingReference;
        }
      }
      customerDeleteForm.querySelector('[name="customer_id"]').value = customerId;
    }
    openModal("od-customer-modal");
  }

  document.querySelectorAll("[data-add-customer]").forEach(btn => btn.addEventListener("click", () => openCustomerModal(null)));
  document.querySelectorAll("[data-edit-customer]").forEach(btn => btn.addEventListener("click", () => openCustomerModal(btn.dataset.editCustomer)));

  // Block modal
  const blockForm = document.getElementById("od-block-form");
  const blockDeleteBtn = document.getElementById("od-block-delete");
  const blockDeleteForm = document.getElementById("od-block-delete-form");

  function openBlockModal(blockId, preset = {}) {
    blockForm.reset();
    setDateFieldValue(blockForm.querySelector('[name="date"]')?.closest("[data-od-date-field]"), "");
    blockForm.querySelector('[name="block_id"]').value = "";
    document.getElementById("od-block-modal-title").textContent = blockId ? t("editBlockedTime", "Edit blocked time") : t("blockTime", "Block time");
    blockDeleteBtn.style.display = blockId ? "" : "none";

    if (blockId) {
      blockForm.querySelector('[name="block_id"]').value = blockId;
      blockDeleteForm.querySelector('[name="block_id"]').value = blockId;
    }

    if (blockId && blockForm.dataset.fromEvent) {
      const p = JSON.parse(blockForm.dataset.fromEvent);
      blockForm.querySelector('[name="block_id"]').value = blockId;
      setDateFieldValue(blockForm.querySelector('[name="date"]')?.closest("[data-od-date-field]"), p.date || "");
      blockForm.querySelector('[name="start_time"]').value = p.startTime || "";
      blockForm.querySelector('[name="end_time"]').value = p.endTime || "";
      blockForm.querySelector('[name="reason"]').value = p.reason || "";
      delete blockForm.dataset.fromEvent;
    } else if (preset.date) {
      setDateFieldValue(blockForm.querySelector('[name="date"]')?.closest("[data-od-date-field]"), preset.date);
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
  // Blocked date inline deletes handled by owner_dashboard_ajax.js

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
  const CG_ROW_H = 68;
  const CG_STATUS = {
    pending:   { cls: "cgrid-chip-pending",   label: t("statusPending", "Pending") },
    approved:  { cls: "cgrid-chip-approved",  label: t("statusApproved", "Approved") },
    completed: { cls: "cgrid-chip-completed", label: t("statusCompleted", "Completed") },
    rejected:  { cls: "cgrid-chip-rejected",  label: t("statusRejected", "Rejected") },
    cancelled: { cls: "cgrid-chip-cancelled", label: t("statusCancelled", "Cancelled") },
    no_show:   { cls: "cgrid-chip-no_show",   label: t("statusNoShow", "No Show") },
    block:     { cls: "cgrid-chip-block",     label: t("block", "Block") },
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
    if (CG_IS_MK) {
      const startMonth = CG_MONTHS_MK_SHORT[mon.getMonth()];
      const endMonth = CG_MONTHS_MK_SHORT[sun.getMonth()];
      const fmtS = `${mon.getDate()} ${startMonth}`;
      const fmtE = `${sun.getDate()} ${endMonth} ${sun.getFullYear()}`;
      return `${fmtS} – ${fmtE}`;
    }
    const fmtS = mon.toLocaleDateString(CG_LOCALE, { day:"numeric", month:"short" });
    const fmtE = sun.toLocaleDateString(CG_LOCALE, { day:"numeric", month:"short", year:"numeric" });
    return `${fmtS} – ${fmtE}`;
  }
  function cgFormatDayLong(d) {
    if (CG_IS_MK) {
      const weekday = CG_WEEKDAYS_MK_LONG[d.getDay()];
      const month = CG_MONTHS_MK_LONG[d.getMonth()];
      return `${weekday}, ${d.getDate()} ${month} ${d.getFullYear()}`;
    }
    return d.toLocaleDateString(CG_LOCALE, { weekday:"long", day:"numeric", month:"long", year:"numeric" });
  }
  function cgFormatWeekdayShort(d) {
    return d.toLocaleDateString(CG_LOCALE, { weekday:"short" }).toUpperCase();
  }
  function cgParseTimeMinutes(t) {
    if (!t) return null;
    const parts = String(t).split(":");
    const h = parseInt(parts[0], 10);
    const m = parseInt(parts[1] || "0", 10);
    if (Number.isNaN(h)) return null;
    return h * 60 + m;
  }
  function cgEventSpan(ev) {
    const startMin = cgParseTimeMinutes(ev.time || ev.start_time);
    if (startMin == null) return null;
    let endMin = cgParseTimeMinutes(ev.end_time);
    if (endMin == null && ev.duration) {
      endMin = startMin + parseInt(ev.duration, 10);
    }
    if (endMin == null) endMin = startMin + 60;
    return { startMin, endMin };
  }
  function cgHourOverlapsEvent(ev, hour) {
    const span = cgEventSpan(ev);
    if (!span) return false;
    const hourStart = hour * 60;
    const hourEnd = hourStart + 60;
    return span.startMin < hourEnd && span.endMin > hourStart;
  }

  function cgEventsForDate(ds) {
    return cgEvents.filter(ev => ev.date === ds);
  }
  function cgSpanStyle(ev, rowH = CG_ROW_H) {
    const span = cgEventSpan(ev);
    const gridStart = cgParseTimeMinutes(CG_HOURS[0]) || 480;
    if (!span) return { top: 0, height: rowH };
    const top = ((span.startMin - gridStart) / 60) * rowH;
    const height = ((span.endMin - span.startMin) / 60) * rowH;
    return { top: Math.max(top, 0), height: Math.max(height, 24) };
  }
  function cgSlotIsBusy(ds, time) {
    const hour = parseInt(time, 10);
    return cgEvents.some(ev => ev.date === ds && cgHourOverlapsEvent(ev, hour));
  }
  function cgCountBookingsOnDate(ds) {
    return cgEvents.filter(ev => ev.date === ds && ev.type === "booking").length;
  }

  function escapeHtml(value) {
    if (value == null) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function cgChipContent(ev) {
    if (ev.type === "block") {
      return `<div class="cgrid-chip-block">${escapeHtml(tf("blockedRange", "Blocked %(start)s%(end)s", { start: ev.start_time || ev.time || "", end: ev.end_time ? "–" + ev.end_time : "" }))}</div>`;
    }
    const photoIcon = ev.hasReferencePhoto ? `<span class="cgrid-chip-photo" title="${escapeHtml(t("photoUploaded", "Photo uploaded"))}"><i class="bi bi-camera-fill"></i></span>` : "";
    const svcLabel = escapeHtml(ev.servicesLabel || ev.services || "");
    const customerName = escapeHtml(ev.customerName || ev.title || "");
    const timeRange = escapeHtml(ev.end_time ? `${ev.time || ""} – ${ev.end_time}` : (ev.time || ""));
    const meta = `${timeRange} · ${escapeHtml(ev.duration || "")}${t("minSuffix", "min")}`;
    return `
      <div class="cgrid-chip-name">${customerName}${photoIcon}</div>
      ${svcLabel ? `<div class="cgrid-chip-svc">${svcLabel}</div>` : ""}
      <div class="cgrid-chip-meta">${meta}</div>
    `;
  }

  function cgSpanEventHtml(ev, rowH, variant = "week") {
    const { top, height } = cgSpanStyle(ev, rowH);
    if (ev.type === "block") {
      return `<div class="cgrid-span-event cgrid-span-block" data-block-id="${ev.blockId || ev.id || ""}" style="top:${top}px;height:${height}px">
        <div class="cgrid-chip cgrid-chip-block">${cgChipContent(ev)}</div>
      </div>`;
    }
    const sc = CG_STATUS[ev.status] || CG_STATUS.pending;
    const dotColor = {"pending":"#D97706","approved":"#059669","completed":"#2563EB","rejected":"#DB2777","cancelled":"#6B7280","no_show":"#C2410C"}[ev.status] || "#D97706";
    const svcLabel = escapeHtml(ev.servicesLabel || ev.services || "");
    const customerName = escapeHtml(ev.customerName || ev.title || "");
    const timeRange = escapeHtml(ev.end_time ? `${ev.time || ""} – ${ev.end_time}` : (ev.time || ""));
    if (variant === "day") {
      return `<div class="cgrid-span-event" data-booking-id="${ev.bookingId || ev.id || ""}" style="top:${top}px;height:${height}px">
        <div class="cgrid-day-chip ${sc.cls}">
          <div class="cgrid-day-chip-body">
            <div class="cgrid-day-chip-name">${customerName}</div>
            ${svcLabel ? `<div class="cgrid-day-chip-svc">${svcLabel}</div>` : ""}
            <div class="cgrid-day-chip-meta">${timeRange} · ${escapeHtml(ev.duration || "")}${t("minSuffix", "min")}</div>
          </div>
          <span class="cgrid-day-chip-status" style="background:${dotColor}22;color:${dotColor}">${escapeHtml(sc.label)}</span>
        </div>
      </div>`;
    }
    return `<div class="cgrid-span-event" data-booking-id="${ev.bookingId || ev.id || ""}" style="top:${top}px;height:${height}px">
      <div class="cgrid-chip ${sc.cls}">${cgChipContent(ev)}</div>
    </div>`;
  }

  function cgBindCalendarInteractions(slotSelector) {
    cgridEl.querySelectorAll(".cgrid-span-event[data-booking-id]").forEach(chip => {
      chip.addEventListener("click", e => { e.stopPropagation(); openBookingModal(chip.dataset.bookingId); });
    });
    cgridEl.querySelectorAll(".cgrid-span-event[data-block-id]").forEach(chip => {
      chip.addEventListener("click", e => { e.stopPropagation(); openBlockModal(chip.dataset.blockId); });
    });
    cgridEl.querySelectorAll(slotSelector).forEach(slot => {
      onDoubleTap(slot, () => {
        if (slot.classList.contains("cgrid-slot-closed") || slot.classList.contains("cgrid-slot-past")) return;
        openBookingModal(null, { date: slot.dataset.date, time: slot.dataset.time });
      });
    });
  }

  function cgChipHtml(ev) {
    if (ev.type === "block") {
      return `<div class="cgrid-chip cgrid-chip-block" data-block-id="${ev.blockId||ev.id||''}">${cgChipContent(ev)}</div>`;
    }
    const sc = CG_STATUS[ev.status] || CG_STATUS.pending;
    return `<div class="cgrid-chip ${sc.cls}" data-booking-id="${ev.bookingId||ev.id||''}">${cgChipContent(ev)}</div>`;
  }

  function cgRenderWeek() {
    const days = Array.from({length:7}, (_,i) => { const d=new Date(cgWeekStart); d.setDate(d.getDate()+i); return d; });
    const today = cgIso(new Date());
    const cols = `68px repeat(7, 1fr)`;
    const totalH = CG_HOURS.length * CG_ROW_H;

    let html = `<div class="cgrid-head" style="grid-template-columns:${cols}">`;
    html += `<div class="cgrid-head-time"></div>`;
    days.forEach(d => {
      const ds = cgIso(d);
      const isToday = ds === today;
      const isClosed = cgIsClosedDay(d);
      const dow = cgFormatWeekdayShort(d);
      html += `<div class="cgrid-head-day${isToday?' cgrid-head-today':''}${isClosed?' cgrid-head-closed':''}">
        <div class="cgrid-head-dow">${dow}</div>
        <div class="cgrid-head-num">${d.getDate()}</div>
        ${isClosed ? `<div class="cgrid-closed-tag">${t("closed", "Closed")}</div>` : ""}
      </div>`;
    });
    html += `</div>`;

    html += `<div class="cgrid-body" style="grid-template-columns:${cols}">`;
    html += `<div class="cgrid-times">`;
    CG_HOURS.forEach(time => {
      html += `<div class="cgrid-time-label" style="height:${CG_ROW_H}px">${time}</div>`;
    });
    html += `</div>`;

    days.forEach(d => {
      const ds = cgIso(d);
      const isClosed = cgIsClosedDay(d);
      html += `<div class="cgrid-col${isClosed ? " cgrid-col-closed" : ""}" data-date="${ds}">`;
      html += `<div class="cgrid-col-slots" style="height:${totalH}px">`;
      CG_HOURS.forEach(time => {
        const isPast = cgIsPast(ds, time);
        let slotCls = "cgrid-slot";
        if (isClosed) slotCls += " cgrid-slot-closed";
        else if (isPast) slotCls += " cgrid-slot-past";
        else if (cgSlotIsBusy(ds, time)) slotCls += " cgrid-slot-busy";
        html += `<div class="${slotCls}" data-date="${ds}" data-time="${time}" style="height:${CG_ROW_H}px"></div>`;
      });
      html += `</div>`;
      html += `<div class="cgrid-col-events" style="height:${totalH}px">`;
      if (!isClosed) cgEventsForDate(ds).forEach(ev => { html += cgSpanEventHtml(ev, CG_ROW_H, "week"); });
      html += `</div></div>`;
    });
    html += `</div>`;

    cgridEl.innerHTML = html;
    cgBindCalendarInteractions(".cgrid-slot:not(.cgrid-slot-closed):not(.cgrid-slot-past):not(.cgrid-slot-busy)");
  }

  function cgRenderDay() {
    const ds = cgIso(cgDayDate);
    const dayStr = cgFormatDayLong(cgDayDate);
    const count = cgCountBookingsOnDate(ds);
    const totalH = CG_HOURS.length * CG_ROW_H;

    let html = `<div class="cgrid-day-header" style="padding:14px 16px;border-bottom:1px solid #E5E7EB;background:#F9FAFB;">
      <p style="font-size:14px;font-weight:600;color:#111827;margin:0">${dayStr}</p>
      <p style="font-size:12px;color:#6B7280;margin:4px 0 0">${count === 1 ? tf("appointmentCountSingular", "%(count)s appointment", { count }) : tf("appointmentCountPlural", "%(count)s appointments", { count })}</p>
    </div>`;

    html += `<div class="cgrid-day-timeline">`;
    html += `<div class="cgrid-day-times">`;
    CG_HOURS.forEach(time => {
      html += `<div class="cgrid-day-time" style="height:${CG_ROW_H}px">${time}</div>`;
    });
    html += `</div>`;
    html += `<div class="cgrid-day-track" style="height:${totalH}px">`;
    html += `<div class="cgrid-day-slots">`;
    CG_HOURS.forEach(time => {
      const isPast = cgIsPast(ds, time);
      let slotCls = "cgrid-slot cgrid-day-slot";
      if (isPast) slotCls += " cgrid-slot-past";
      else if (cgSlotIsBusy(ds, time)) slotCls += " cgrid-slot-busy";
      html += `<div class="${slotCls}" data-date="${ds}" data-time="${time}" style="height:${CG_ROW_H}px"></div>`;
    });
    html += `</div>`;
    html += `<div class="cgrid-col-events cgrid-day-events">`;
    cgEventsForDate(ds).forEach(ev => { html += cgSpanEventHtml(ev, CG_ROW_H, "day"); });
    html += `</div></div></div>`;

    cgridEl.innerHTML = html;
    cgBindCalendarInteractions(".cgrid-day-slot:not(.cgrid-slot-past):not(.cgrid-slot-busy)");
  }

  function cgRender() {
    if (!cgridEl) return;
    if (cgView === "week") {
      cgRangeLabel && (cgRangeLabel.textContent = cgFmtWeekRange(cgWeekStart));
      cgRenderWeek();
    } else {
      cgRangeLabel && (cgRangeLabel.textContent = cgFormatDayLong(cgDayDate));
      cgRenderDay();
    }
    document.querySelectorAll(".cgrid-view-btn").forEach(b => b.classList.remove("active"));
    document.getElementById(cgView === "week" ? "cal-view-week" : "cal-view-day")?.classList.add("active");
  }

  async function cgFetchAndRender() {
    if (!cgridEl) return;
    if (window.odMcIsMobileCalendar?.()) {
      return window.odMcFetchMonth?.(true);
    }
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
          hasReferencePhoto: ep.hasReferencePhoto,
          services: ep.services || "",
          servicesLabel: ep.servicesLabel || "",
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
  if (window.initOwnerCalendarMobile) {
    window.initOwnerCalendarMobile({
      eventsUrl: config.eventsUrl,
      locale: CG_LOCALE,
      openBookingModal,
      openBlockModal,
    });
  }
  if (cgridEl) cgFetchAndRender();
  window.odCgFetchAndRender = cgFetchAndRender;
  window.odGoToCalendarToday = function odGoToCalendarToday() {
    if (window.odMcIsMobileCalendar?.()) {
      window.odMcGoToday?.();
      return;
    }
    cgView = "day";
    cgDayDate = new Date();
    cgWeekStart = cgMonday(new Date());
    cgFetchAndRender();
  };

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
            ${closed ? `<span class="fc-day-closed">${t("closed", "Closed")}</span>` : ""}
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
            showToast(t("cannotAddPastBooking", "Cannot add bookings in the past."), true);
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
      renderMessageLinks(data);
      openModal("od-msg-modal");
    });
  });

  document.getElementById("od-modal-close")?.addEventListener("click", () => closeModal("od-msg-modal"));

  // Blocked customers list
  const blockedSearch = document.getElementById("od-blocked-search");
  blockedSearch?.addEventListener("input", () => {
    const query = blockedSearch.value.trim().toLowerCase();
    const rows = document.querySelectorAll("#od-blocked-table tbody tr");
    let visible = 0;
    rows.forEach((row) => {
      const text = row.dataset.searchText || row.textContent.toLowerCase();
      const show = !query || text.includes(query);
      row.hidden = !show;
      if (show) visible += 1;
    });
    let empty = document.getElementById("od-blocked-search-empty");
    if (!empty && blockedSearch.closest(".od-card")) {
      empty = document.createElement("div");
      empty.id = "od-blocked-search-empty";
      empty.className = "od-empty";
      blockedSearch.closest(".od-card")?.appendChild(empty);
    }
    if (empty) {
      empty.textContent = t("noBlockedCustomersMatch", "No blocked customers match your search.");
      empty.style.display = rows.length && visible === 0 ? "block" : "none";
    }
  });

  document.querySelectorAll("[data-unblock-entry]").forEach((btn) => {
    if (btn.dataset.odUnblockBound) return;
    btn.dataset.odUnblockBound = "1";
    btn.addEventListener("click", async () => {
      if (!confirm(t("confirmUnblockCustomer", "Unblock this customer? They will be able to book again."))) return;
      const entryId = btn.dataset.unblockEntry;
      const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
      if (window.OwnerAjax) window.OwnerAjax.setButtonLoading(btn, true);
      try {
        const resp = await fetch(`/owner/customers/block/${entryId}/unblock/`, {
          method: "POST",
          headers: { "X-CSRFToken": csrf, "X-Requested-With": "fetch" },
        });
        const data = await resp.json();
        if (!resp.ok || !data.ok) throw new Error(data.error || "Request failed");
        btn.closest("tr")?.remove();
        showToast(t("customerUnblocked", "Customer unblocked."));
      } catch (err) {
        showToast(err.message || t("somethingWentWrong", "Something went wrong. Please try again."), "error");
      } finally {
        if (window.OwnerAjax) window.OwnerAjax.setButtonLoading(btn, false);
      }
    });
  });

  document.addEventListener("od:customer-blocked", async () => {
    showSection("blocked-customers");
    history.replaceState(null, "", "#blocked-customers");
    syncBottomNav("blocked-customers");
    if (window.OwnerAjax) {
      await window.OwnerAjax.refreshSection("od-sec-blocked-customers", window.odRebindDashboard);
    }
  });

  document.addEventListener("od:customer-unblocked", (event) => {
    const entryId = event.detail?.id;
    if (entryId) {
      document.querySelector(`tr[data-block-entry-id="${entryId}"]`)?.remove();
    }
  });

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

  function syncFixedStartTimesPolicyFields() {
    const toggle = document.getElementById("id_use_fixed_start_times");
    const fixedField = document.getElementById("od-fixed-times-field");
    const intervalField = document.getElementById("od-slot-interval-field");
    if (!toggle) return;
    const fixedOn = toggle.checked;
    if (fixedField) fixedField.classList.toggle("od-field-disabled", !fixedOn);
    if (intervalField) intervalField.classList.toggle("od-field-disabled", fixedOn);
  }

  function syncEmailVerificationPolicyFields() {
    const toggle = document.getElementById("id_email_verification_required");
    const expiryField = document.getElementById("od-email-verification-expiry-field");
    if (!toggle || !expiryField) return;
    expiryField.classList.toggle("od-field-disabled", !toggle.checked);
  }
  const fixedStartToggle = document.getElementById("id_use_fixed_start_times");
  if (fixedStartToggle) {
    fixedStartToggle.addEventListener("change", syncFixedStartTimesPolicyFields);
    syncFixedStartTimesPolicyFields();
  }
  const emailVerifyToggle = document.getElementById("id_email_verification_required");
  if (emailVerifyToggle) {
    emailVerifyToggle.addEventListener("change", syncEmailVerificationPolicyFields);
    syncEmailVerificationPolicyFields();
  }

  function rebindDashboardInteractions() {
    document.querySelectorAll("[data-bk-action]").forEach(bindBkAction);
    document.querySelectorAll("[data-add-service]").forEach(btn => {
      if (btn.dataset.odAddSvcBound) return;
      btn.dataset.odAddSvcBound = "1";
      btn.addEventListener("click", () => openServiceModal(null));
    });
    document.querySelectorAll("[data-edit-booking]").forEach(btn => {
      if (btn.dataset.odEditBkBound) return;
      btn.dataset.odEditBkBound = "1";
      btn.addEventListener("click", () => openBookingModal(btn.dataset.editBooking));
    });
    document.querySelectorAll("[data-edit-service]").forEach(btn => {
      if (btn.dataset.odEditSvcBound) return;
      btn.dataset.odEditSvcBound = "1";
      btn.addEventListener("click", () => openServiceModal(btn.dataset.editService));
    });
    bindPriceListInteractions();
    document.querySelectorAll("[data-edit-customer]").forEach(btn => {
      if (btn.dataset.odEditCustBound) return;
      btn.dataset.odEditCustBound = "1";
      btn.addEventListener("click", () => openCustomerModal(btn.dataset.editCustomer));
    });
    document.querySelectorAll("[data-unblock-entry]").forEach((btn) => {
      if (btn.dataset.odUnblockBound) return;
      btn.dataset.odUnblockBound = "1";
      btn.addEventListener("click", async () => {
        if (!confirm(t("confirmUnblockCustomer", "Unblock this customer? They will be able to book again."))) return;
        const entryId = btn.dataset.unblockEntry;
        const csrf = document.querySelector("[name=csrfmiddlewaretoken]")?.value;
        if (window.OwnerAjax) window.OwnerAjax.setButtonLoading(btn, true);
        try {
          const resp = await fetch(`/owner/customers/block/${entryId}/unblock/`, {
            method: "POST",
            headers: { "X-CSRFToken": csrf, "X-Requested-With": "fetch" },
          });
          const data = await resp.json();
          if (!resp.ok || !data.ok) throw new Error(data.error || "Request failed");
          btn.closest("tr")?.remove();
          showToast(t("customerUnblocked", "Customer unblocked."));
        } catch (err) {
          showToast(err.message || t("somethingWentWrong", "Something went wrong. Please try again."), "error");
        } finally {
          if (window.OwnerAjax) window.OwnerAjax.setButtonLoading(btn, false);
        }
      });
    });
    if (window.odBindInlineDeleteForms) window.odBindInlineDeleteForms();
    initToggles();
    syncFixedStartTimesPolicyFields();
    syncEmailVerificationPolicyFields();
  }
  window.odRebindDashboard = rebindDashboardInteractions;
  document.addEventListener("od:rebind", rebindDashboardInteractions);
}
