/**
 * Mobile owner calendar — month grid + collapsible week strip + day agenda (≤640px).
 */
(function initOwnerCalendarMobile(global) {
  const MOBILE_MQ = global.matchMedia("(max-width: 640px)");
  const COLLAPSE_SCROLL_PX = 72;
  const SWIPE_THRESHOLD = 50;

  const STATUS = {
    pending:   { color: "#D97706", labelKey: "statusPending",   fallback: "Pending" },
    approved:  { color: "#059669", labelKey: "statusApproved",  fallback: "Approved" },
    completed: { color: "#2563EB", labelKey: "statusCompleted", fallback: "Completed" },
    rejected:  { color: "#DB2777", labelKey: "statusRejected",  fallback: "Rejected" },
    cancelled: { color: "#6B7280", labelKey: "statusCancelled", fallback: "Cancelled" },
    no_show:   { color: "#C2410C", labelKey: "statusNoShow",    fallback: "No Show" },
    block:     { color: "#7C3AED", labelKey: "block",           fallback: "Block" },
  };

  let config = {};
  let mcEvents = [];
  let mcMeta = { closedDates: [], closedWeekdays: [] };
  let mcMonthDate = new Date();
  let mcSelectedDate = new Date();
  let mcGridDates = [];
  let mcEventCache = {};
  let mcInitialized = false;
  let mcFetching = false;
  let mcTouchStartX = 0;
  let mcTouchStartY = 0;
  let mcScrollRaf = null;

  const els = {};

  function t(key, fallback) {
    const i18n = global.OD_I18N || {};
    return i18n[key] != null && i18n[key] !== "" ? i18n[key] : fallback;
  }

  function tf(key, fallback, vars) {
    let text = t(key, fallback);
    if (vars) {
      Object.entries(vars).forEach(([name, value]) => {
        text = text.replace(new RegExp(`%\\(${name}\\)s`, "g"), value);
      });
    }
    return text;
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

  function mcIso(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }

  function mcMonday(d) {
    const r = new Date(d);
    r.setHours(0, 0, 0, 0);
    const day = r.getDay();
    r.setDate(r.getDate() - (day === 0 ? 6 : day - 1));
    return r;
  }

  function mcMonthKey(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  }

  function mcIsMobile() {
    return MOBILE_MQ.matches;
  }

  function mcIsClosedDay(d) {
    const ds = mcIso(d);
    const dw = (d.getDay() + 6) % 7;
    return mcMeta.closedDates.includes(ds) || mcMeta.closedWeekdays.includes(dw);
  }

  function mcLocaleTag() {
    const raw = (config.locale || global.document.documentElement.lang || "mk").toLowerCase();
    if (raw === "mk" || raw.startsWith("mk-")) return "mk-MK";
    if (raw === "en" || raw.startsWith("en-")) return "en-GB";
    return raw.includes("-") ? raw : raw;
  }

  function mcGetDowLabels() {
    const monday = mcMonday(new Date(2024, 0, 1));
    const tag = mcLocaleTag();
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      return d.toLocaleDateString(tag, { weekday: "narrow" });
    });
  }

  function mcFormatMonthYear(d) {
    return d.toLocaleDateString(mcLocaleTag(), { month: "long", year: "numeric" });
  }

  function mcNormalizeEvents(data) {
    mcMeta = { closedDates: data.closedDates || [], closedWeekdays: data.closedWeekdays || [] };
    return (data.events || []).map((ev) => {
      const s = ev.start || "";
      const ds = s.split("T")[0] || "";
      const tm = s.split("T")[1]?.slice(0, 5) || ev.time || "";
      const endS = ev.end || "";
      const endTm = endS.split("T")[1]?.slice(0, 5) || "";
      const ep = ev.extendedProps || {};
      return {
        ...ep,
        date: ds,
        time: tm,
        end_time: endTm,
        title: ev.title || "",
        bookingId: ep.bookingId,
        blockId: ep.blockId,
        type: ep.type || "booking",
        hasReferencePhoto: ep.hasReferencePhoto,
        services: ep.services || "",
        servicesLabel: ep.servicesLabel || "",
        customerName: ep.customerName || "",
        status: ep.status || "approved",
      };
    });
  }

  function mcBuildGridDates(monthDate) {
    const first = new Date(monthDate.getFullYear(), monthDate.getMonth(), 1);
    const start = mcMonday(first);
    const dates = [];
    for (let i = 0; i < 42; i += 1) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      dates.push({
        date: d,
        iso: mcIso(d),
        inMonth: d.getMonth() === monthDate.getMonth(),
      });
    }
    return dates;
  }

  function mcEventsForDate(iso) {
    return mcEvents
      .filter((ev) => ev.date === iso)
      .sort((a, b) => (a.time || "").localeCompare(b.time || ""));
  }

  function mcStatusInfo(status) {
    return STATUS[status] || STATUS.approved;
  }

  function mcDayIndicators(iso) {
    const events = mcEventsForDate(iso);
    if (!events.length) return "";
    const maxBars = 3;
    const bars = events.slice(0, maxBars).map((ev) => {
      const color = ev.type === "block" ? STATUS.block.color : mcStatusInfo(ev.status).color;
      return `<span class="mcgrid-ind-bar" style="background:${color}"></span>`;
    });
    const overflow = events.length > maxBars
      ? `<span class="mcgrid-ind-more">+${events.length - maxBars}</span>`
      : "";
    return `<div class="mcgrid-indicators">${bars.join("")}${overflow}</div>`;
  }

  function mcRenderMonthGrid() {
    if (!els.month) return;
    const today = mcIso(new Date());
    const selected = mcIso(mcSelectedDate);
    const dowLabels = mcGetDowLabels();

    let html = '<div class="mcgrid-dow-row">';
    dowLabels.forEach((label, i) => {
      html += `<span class="mcgrid-dow${i === 6 ? " mcgrid-dow-sun" : ""}">${label}</span>`;
    });
    html += '</div><div class="mcgrid-days">';

    mcGridDates.forEach(({ date, iso, inMonth }) => {
      const isToday = iso === today;
      const isSelected = iso === selected;
      const isClosed = mcIsClosedDay(date);
      let cls = "mcgrid-day";
      if (!inMonth) cls += " mcgrid-day-out";
      if (isToday) cls += " mcgrid-day-today";
      if (isSelected) cls += " mcgrid-day-selected";
      if (isClosed) cls += " mcgrid-day-closed";
      html += `<button type="button" class="${cls}" data-date="${iso}" aria-label="${iso}" aria-pressed="${isSelected}">
        <span class="mcgrid-day-num">${date.getDate()}</span>
        ${mcDayIndicators(iso)}
      </button>`;
    });
    html += "</div>";
    els.month.innerHTML = html;

    els.month.querySelectorAll(".mcgrid-day").forEach((btn) => {
      btn.addEventListener("click", () => mcSelectDate(btn.dataset.date));
    });
  }

  function mcWeekDatesForSelected() {
    const monday = mcMonday(mcSelectedDate);
    return Array.from({ length: 7 }, (_, i) => {
      const d = new Date(monday);
      d.setDate(monday.getDate() + i);
      return d;
    });
  }

  function mcRenderWeekStrip() {
    if (!els.weekStrip) return;
    const today = mcIso(new Date());
    const selected = mcIso(mcSelectedDate);
    const days = mcWeekDatesForSelected();

    els.weekStrip.innerHTML = days.map((d) => {
      const iso = mcIso(d);
      const isToday = iso === today;
      const isSelected = iso === selected;
      const isClosed = mcIsClosedDay(d);
      let cls = "mcgrid-week-day";
      if (isToday) cls += " mcgrid-week-day-today";
      if (isSelected) cls += " mcgrid-week-day-selected";
      if (isClosed) cls += " mcgrid-week-day-closed";
      const dow = d.toLocaleDateString(mcLocaleTag(), { weekday: "short" }).slice(0, 1).toUpperCase();
      return `<button type="button" class="${cls}" data-date="${iso}">
        <span class="mcgrid-week-dow">${dow}</span>
        <span class="mcgrid-week-num">${d.getDate()}</span>
        ${mcDayIndicators(iso)}
      </button>`;
    }).join("");

    els.weekStrip.querySelectorAll(".mcgrid-week-day").forEach((btn) => {
      btn.addEventListener("click", () => mcSelectDate(btn.dataset.date));
    });
  }

  function mcFormatAgendaHeader(d) {
    return d.toLocaleDateString(mcLocaleTag(), {
      weekday: "long",
      day: "numeric",
      month: "long",
    });
  }

  function mcAgendaCardHtml(ev) {
    if (ev.type === "block") {
      const timeRange = ev.end_time ? `${ev.time} – ${ev.end_time}` : ev.time;
      return `<button type="button" class="mcgrid-agenda-card mcgrid-agenda-block" data-block-id="${ev.blockId || ""}">
        <span class="mcgrid-agenda-bar" style="background:${STATUS.block.color}"></span>
        <span class="mcgrid-agenda-time">${escapeHtml(timeRange)}</span>
        <span class="mcgrid-agenda-body">
          <span class="mcgrid-agenda-name">${escapeHtml(t("blocked", "Blocked"))}</span>
          <span class="mcgrid-agenda-svc">${escapeHtml(ev.reason || t("unavailable", "Unavailable"))}</span>
        </span>
        <span class="mcgrid-agenda-status" style="color:${STATUS.block.color}">${escapeHtml(t("block", "Block"))}</span>
      </button>`;
    }

    const st = mcStatusInfo(ev.status);
    const timeRange = ev.end_time ? `${ev.time} – ${ev.end_time}` : ev.time;
    const photo = ev.hasReferencePhoto
      ? `<span class="mcgrid-agenda-photo" title="${escapeHtml(t("photoUploaded", "Photo uploaded"))}"><i class="bi bi-camera-fill"></i></span>`
      : "";
    return `<button type="button" class="mcgrid-agenda-card" data-booking-id="${ev.bookingId || ""}">
      <span class="mcgrid-agenda-bar" style="background:${st.color}"></span>
      <span class="mcgrid-agenda-time">${escapeHtml(timeRange)}</span>
      <span class="mcgrid-agenda-body">
        <span class="mcgrid-agenda-name">${escapeHtml(ev.customerName || ev.title || "")}${photo}</span>
        <span class="mcgrid-agenda-svc">${escapeHtml(ev.servicesLabel || ev.services || "")}</span>
      </span>
      <span class="mcgrid-agenda-status" style="color:${st.color}">${escapeHtml(t(st.labelKey, st.fallback))}</span>
    </button>`;
  }

  function mcRenderAgenda(animate) {
    if (!els.agendaList || !els.agendaDate || !els.agendaCount || !els.agendaEmpty) return;
    const iso = mcIso(mcSelectedDate);
    const events = mcEventsForDate(iso);
    const bookings = events.filter((ev) => ev.type === "booking");

    els.agendaDate.textContent = mcFormatAgendaHeader(mcSelectedDate);
    els.agendaCount.textContent = bookings.length === 1
      ? tf("appointmentCountSingular", "%(count)s appointment", { count: "1" })
      : tf("appointmentCountPlural", "%(count)s appointments", { count: String(bookings.length) });

    if (!events.length) {
      els.agendaList.innerHTML = "";
      els.agendaList.hidden = true;
      els.agendaEmpty.hidden = false;
    } else {
      els.agendaEmpty.hidden = true;
      els.agendaList.hidden = false;
      els.agendaList.innerHTML = events.map(mcAgendaCardHtml).join("");
      els.agendaList.querySelectorAll("[data-booking-id]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const id = btn.dataset.bookingId;
          if (id && config.openBookingModal) config.openBookingModal(id);
        });
      });
      els.agendaList.querySelectorAll("[data-block-id]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const id = btn.dataset.blockId;
          if (id && config.openBlockModal) config.openBlockModal(id);
        });
      });
    }

    if (animate && els.agendaList && !els.agendaList.hidden) {
      els.agendaList.classList.remove("mcgrid-agenda-animate");
      void els.agendaList.offsetWidth;
      els.agendaList.classList.add("mcgrid-agenda-animate");
    }
  }

  function mcUpdateMonthLabel() {
    if (!els.monthLabel) return;
    els.monthLabel.textContent = mcFormatMonthYear(mcMonthDate);
  }

  function mcSelectDate(iso, animate) {
    if (!iso) return;
    const parts = iso.split("-");
    mcSelectedDate = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10));
    if (mcSelectedDate.getMonth() !== mcMonthDate.getMonth() ||
        mcSelectedDate.getFullYear() !== mcMonthDate.getFullYear()) {
      mcMonthDate = new Date(mcSelectedDate.getFullYear(), mcSelectedDate.getMonth(), 1);
      mcFetchMonth(true).then(() => {
        mcRenderMonthGrid();
        mcRenderWeekStrip();
        mcRenderAgenda(animate !== false);
      });
      return;
    }
    mcRenderMonthGrid();
    mcRenderWeekStrip();
    mcRenderAgenda(animate !== false);
  }

  function mcSetCollapse(ratio) {
    const collapse = Math.max(0, Math.min(1, ratio));
    if (els.collapseShell) {
      els.collapseShell.style.setProperty("--mc-collapse", String(collapse));
    }
    if (els.weekStrip) {
      els.weekStrip.setAttribute("aria-hidden", collapse < 0.5 ? "true" : "false");
    }
    if (els.month) {
      els.month.style.pointerEvents = collapse > 0.85 ? "none" : "auto";
    }
    if (els.weekStrip) {
      els.weekStrip.style.pointerEvents = collapse < 0.15 ? "none" : "auto";
    }
  }

  function mcHandleScroll() {
    if (!els.scrollViewport) return;
    if (mcScrollRaf) return;
    mcScrollRaf = global.requestAnimationFrame(() => {
      mcScrollRaf = null;
      const ratio = els.scrollViewport.scrollTop / COLLAPSE_SCROLL_PX;
      mcSetCollapse(ratio);
    });
  }

  function mcResetScroll() {
    if (els.scrollViewport) els.scrollViewport.scrollTop = 0;
    mcSetCollapse(0);
  }

  function mcMergeEvents(newEvents, rangeStart, rangeEnd) {
    const start = new Date(rangeStart);
    const end = new Date(rangeEnd);
    const outside = mcEvents.filter((ev) => {
      const d = new Date(ev.date + "T12:00:00");
      return d < start || d >= end;
    });
    mcEvents = [...outside, ...newEvents];
  }

  async function mcFetchMonth(forceRefresh) {
    if (!config.eventsUrl || !mcIsMobile()) return;
    const key = mcMonthKey(mcMonthDate);
    if (!forceRefresh && mcEventCache[key]) {
      mcEvents = mcEventCache[key].events.slice();
      mcMeta = { ...mcEventCache[key].meta };
      mcGridDates = mcBuildGridDates(mcMonthDate);
      mcUpdateMonthLabel();
      mcRenderMonthGrid();
      mcRenderWeekStrip();
      mcRenderAgenda(false);
      return;
    }

    mcGridDates = mcBuildGridDates(mcMonthDate);
    const rangeStart = mcGridDates[0].iso;
    const endD = new Date(mcGridDates[mcGridDates.length - 1].date);
    endD.setDate(endD.getDate() + 1);
    const rangeEnd = mcIso(endD);

    if (mcFetching) return;
    mcFetching = true;
    if (els.root) els.root.classList.add("is-loading");

    try {
      const res = await fetch(`${config.eventsUrl}?start=${rangeStart}&end=${rangeEnd}`);
      const data = await res.json();
      const normalized = mcNormalizeEvents(data);
      mcMergeEvents(normalized, rangeStart, rangeEnd);
      mcEventCache[key] = {
        events: mcEvents.slice(),
        meta: { ...mcMeta },
      };
      mcUpdateMonthLabel();
      mcRenderMonthGrid();
      mcRenderWeekStrip();
      mcRenderAgenda(false);
    } catch (err) {
      console.error("mcgrid fetch error", err);
    } finally {
      mcFetching = false;
      if (els.root) els.root.classList.remove("is-loading");
    }
  }

  function mcGoToday() {
    const today = new Date();
    mcMonthDate = new Date(today.getFullYear(), today.getMonth(), 1);
    mcSelectedDate = new Date(today);
    mcResetScroll();
    mcFetchMonth(true);
  }

  function mcChangeMonth(delta) {
    mcMonthDate = new Date(mcMonthDate.getFullYear(), mcMonthDate.getMonth() + delta, 1);
    mcFetchMonth(false);
  }

  function mcAddBookingOnSelected() {
    if (!config.openBookingModal) return;
    config.openBookingModal(null, { date: mcIso(mcSelectedDate) });
  }

  function mcBindSwipe() {
    if (!els.collapseShell) return;
    els.collapseShell.addEventListener("touchstart", (e) => {
      mcTouchStartX = e.touches[0].clientX;
      mcTouchStartY = e.touches[0].clientY;
    }, { passive: true });

    els.collapseShell.addEventListener("touchend", (e) => {
      const dx = e.changedTouches[0].clientX - mcTouchStartX;
      const dy = e.changedTouches[0].clientY - mcTouchStartY;
      if (Math.abs(dx) < SWIPE_THRESHOLD || Math.abs(dx) < Math.abs(dy)) return;
      mcChangeMonth(dx > 0 ? -1 : 1);
    }, { passive: true });
  }

  function mcUpdateVisibility() {
    const mobile = mcIsMobile();
    if (els.root) els.root.hidden = !mobile;
    if (mobile && !mcInitialized) {
      mcBindUi();
      mcInitialized = true;
    }
  }

  function mcOnMediaChange() {
    mcUpdateVisibility();
    if (mcIsMobile()) {
      mcFetchMonth(false);
    } else if (typeof global.odCgFetchAndRender === "function") {
      global.odCgFetchAndRender();
    }
  }

  function mcBindUi() {
    els.prev?.addEventListener("click", () => mcChangeMonth(-1));
    els.next?.addEventListener("click", () => mcChangeMonth(1));
    els.today?.addEventListener("click", mcGoToday);
    els.addBooking?.addEventListener("click", mcAddBookingOnSelected);
    els.addBlock?.addEventListener("click", () => config.openBlockModal?.(null));
    els.emptyAdd?.addEventListener("click", mcAddBookingOnSelected);
    els.scrollViewport?.addEventListener("scroll", mcHandleScroll, { passive: true });
    mcBindSwipe();
    if (!MOBILE_MQ._mcBound) {
      MOBILE_MQ.addEventListener("change", mcOnMediaChange);
      MOBILE_MQ._mcBound = true;
    }
  }

  function mcCacheEls() {
    els.root = document.getElementById("od-cal-mobile");
    els.month = document.getElementById("mcgrid-month");
    els.weekStrip = document.getElementById("mcgrid-week-strip");
    els.collapseShell = document.getElementById("mcgrid-collapse-shell");
    els.scrollViewport = document.getElementById("mcgrid-scroll");
    els.agendaList = document.getElementById("mcgrid-agenda-list");
    els.agendaEmpty = document.getElementById("mcgrid-agenda-empty");
    els.agendaDate = document.getElementById("mcgrid-agenda-date");
    els.agendaCount = document.getElementById("mcgrid-agenda-count");
    els.monthLabel = document.getElementById("mc-month-label");
    els.prev = document.getElementById("mc-cal-prev");
    els.next = document.getElementById("mc-cal-next");
    els.today = document.getElementById("mc-cal-today");
    els.addBooking = document.getElementById("mc-add-booking");
    els.addBlock = document.getElementById("mc-add-block");
    els.emptyAdd = document.getElementById("mc-empty-add-booking");
  }

  function initOwnerCalendarMobile(options) {
    config = options || {};
    mcCacheEls();
    if (!els.root) return;

    mcMonthDate = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
    mcSelectedDate = new Date();
    mcSetCollapse(0);
    mcUpdateVisibility();
  }

  function odMcFetchMonth(forceRefresh) {
    if (!mcIsMobile()) return Promise.resolve();
    return mcFetchMonth(forceRefresh !== false);
  }

  function odMcRefresh() {
    if (!mcIsMobile()) return Promise.resolve();
    mcEventCache = {};
    return mcFetchMonth(true);
  }

  global.initOwnerCalendarMobile = initOwnerCalendarMobile;
  global.odMcFetchMonth = odMcFetchMonth;
  global.odMcRefresh = odMcRefresh;
  global.odMcIsMobileCalendar = mcIsMobile;
})(window);
