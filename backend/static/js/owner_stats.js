// Owner dashboard statistics charts (Chart.js).
// All three time ranges are injected via json_script; toggling updates KPIs,
// charts, and the top-services list without another request.
(function () {
  "use strict";

  var charts = {};
  var initialized = false;
  var ranges = null;
  var currentRange = "month";
  var palette = null;

  function readJSON(id) {
    var el = document.getElementById(id);
    if (!el) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return null;
    }
  }

  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name);
    return (v && v.trim()) || fallback;
  }

  function getPalette() {
    return {
      primary: cssVar("--od-accent", "#4F6AF5"),
      primarySoft: "rgba(79, 106, 245, 0.35)",
      accent: cssVar("--od-accent", "#4F6AF5"),
      rose: "#ec4899",
      violet: "#a855f7",
      muted: "#94a3b8",
      grid: "rgba(148, 163, 184, 0.15)",
    };
  }

  function bookingsFill(ctx) {
    var chart = ctx.chart;
    var area = chart.chartArea;
    if (!area) return "rgba(236, 72, 153, 0.18)";
    var g = chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
    g.addColorStop(0, "rgba(236, 72, 153, 0.38)");
    g.addColorStop(0.55, "rgba(168, 85, 247, 0.16)");
    g.addColorStop(1, "rgba(168, 85, 247, 0.02)");
    return g;
  }

  function currencySuffix() {
    var el = document.querySelector("#od-sec-statistics .od-stat-revenue small");
    return el ? el.textContent.trim() : "";
  }

  function baseOptions(opts) {
    opts = opts || {};
    var suffix = currencySuffix();
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function (ctx) {
              var v = ctx.parsed.y;
              return opts.money ? v.toLocaleString() + (suffix ? " " + suffix : "") : v;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: palette.muted, maxRotation: 0, autoSkip: true },
        },
        y: {
          beginAtZero: true,
          grid: { color: palette.grid },
          ticks: {
            color: palette.muted,
            precision: 0,
            callback: function (value) {
              if (opts.integer && !Number.isInteger(value)) return null;
              return value;
            },
          },
        },
      },
    };
  }

  function weekdayColors(counts) {
    var max = Math.max.apply(null, counts.concat([0]));
    return counts.map(function (c) {
      return c === max && max > 0 ? palette.accent : palette.primarySoft;
    });
  }

  function ensureCharts() {
    if (initialized || typeof Chart === "undefined") return;
    var data = ranges[currentRange];
    if (!data) return;

    var revenueCanvas = document.getElementById("od-chart-revenue");
    var bookingsCanvas = document.getElementById("od-chart-bookings");
    var weekdayCanvas = document.getElementById("od-chart-weekday");

    if (revenueCanvas) {
      charts.revenue = new Chart(revenueCanvas, {
        type: "bar",
        data: {
          labels: data.trend.map(function (m) { return m.label; }),
          datasets: [{
            data: data.trend.map(function (m) { return m.revenue; }),
            backgroundColor: palette.primarySoft,
            hoverBackgroundColor: palette.primary,
            borderRadius: 6,
            maxBarThickness: 46,
          }],
        },
        options: baseOptions({ money: true }),
      });
    }
    if (bookingsCanvas) {
      charts.bookings = new Chart(bookingsCanvas, {
        type: "line",
        data: {
          labels: data.trend.map(function (m) { return m.label; }),
          datasets: [{
            data: data.trend.map(function (m) { return m.bookings; }),
            borderColor: palette.rose,
            backgroundColor: bookingsFill,
            fill: true,
            tension: 0.4,
            borderWidth: 2.5,
            pointRadius: 4,
            pointHoverRadius: 6,
            pointBackgroundColor: "#fff",
            pointBorderColor: palette.violet,
            pointBorderWidth: 2,
          }],
        },
        options: baseOptions({ integer: true }),
      });
    }
    if (weekdayCanvas) {
      var counts = data.weekday_distribution.map(function (d) { return d.count; });
      charts.weekday = new Chart(weekdayCanvas, {
        type: "bar",
        data: {
          labels: data.weekday_distribution.map(function (d) { return d.label; }),
          datasets: [{
            data: counts,
            backgroundColor: weekdayColors(counts),
            borderRadius: 6,
            maxBarThickness: 34,
          }],
        },
        options: baseOptions({ integer: true }),
      });
    }
    initialized = true;
  }

  function updateCharts(data) {
    if (!initialized) {
      ensureCharts();
      return;
    }
    if (charts.revenue) {
      charts.revenue.data.labels = data.trend.map(function (m) { return m.label; });
      charts.revenue.data.datasets[0].data = data.trend.map(function (m) { return m.revenue; });
      charts.revenue.update();
    }
    if (charts.bookings) {
      charts.bookings.data.labels = data.trend.map(function (m) { return m.label; });
      charts.bookings.data.datasets[0].data = data.trend.map(function (m) { return m.bookings; });
      charts.bookings.update();
    }
    if (charts.weekday) {
      var counts = data.weekday_distribution.map(function (d) { return d.count; });
      charts.weekday.data.labels = data.weekday_distribution.map(function (d) { return d.label; });
      charts.weekday.data.datasets[0].data = counts;
      charts.weekday.data.datasets[0].backgroundColor = weekdayColors(counts);
      charts.weekday.update();
    }
  }

  function setText(el, value) {
    if (el) el.textContent = value;
  }

  function renderTopServices(items) {
    var list = document.querySelector("[data-stats-top-list]");
    var empty = document.querySelector("[data-stats-top-empty]");
    if (!list) return;
    list.innerHTML = "";
    if (!items || !items.length) {
      list.hidden = true;
      if (empty) empty.hidden = false;
      return;
    }
    items.forEach(function (svc, i) {
      var li = document.createElement("li");
      li.className = "od-top-item";
      if (i < 3) li.classList.add("od-top-item--medal-" + (i + 1));
      var rank = document.createElement("span");
      rank.className = "od-top-rank" + (i < 3 ? " od-top-rank--" + (i + 1) : "");
      rank.textContent = String(i + 1);
      var name = document.createElement("span");
      name.className = "od-top-name";
      name.textContent = svc.name;
      var count = document.createElement("span");
      count.className = "od-top-count";
      count.textContent = svc.count + "\u00d7";
      li.appendChild(rank);
      li.appendChild(name);
      li.appendChild(count);
      list.appendChild(li);
    });
    list.hidden = false;
    if (empty) empty.hidden = true;
  }

  function renderBusiest(data) {
    var note = document.querySelector("[data-stats-busiest]");
    if (!note) return;
    var text = note.querySelector("[data-stats-busiest-text]");
    if (!data.busiest_weekday) {
      note.hidden = true;
      return;
    }
    var template = note.getAttribute("data-template") || "%(day)s";
    setText(text, template.replace("%(day)s", data.busiest_weekday.label));
    note.hidden = false;
  }

  function applyRange(key) {
    if (!ranges || !ranges[key]) return;
    currentRange = key;
    var data = ranges[key];
    setText(document.querySelector('[data-stats-kpi="revenue"]'), data.revenue);
    setText(document.querySelector('[data-stats-kpi="completed"]'), data.completed);
    setText(document.querySelector('[data-stats-kpi="no_show_rate"]'), data.no_show_rate);
    setText(document.querySelector('[data-stats-kpi="online_share"]'), data.online_share);
    renderTopServices(data.top_services);
    renderBusiest(data);
    updateCharts(data);

    document.querySelectorAll("[data-stats-range]").forEach(function (btn) {
      var active = btn.getAttribute("data-stats-range") === key;
      btn.classList.toggle("is-active", active);
      btn.setAttribute("aria-selected", active ? "true" : "false");
    });
  }

  function initStatsCharts() {
    ranges = readJSON("od-stats-ranges");
    if (!ranges) return;
    palette = getPalette();
    applyRange(currentRange);
    if (initialized) {
      Object.keys(charts).forEach(function (k) {
        if (charts[k] && typeof charts[k].resize === "function") charts[k].resize();
      });
    }
  }

  window.odInitStatsCharts = initStatsCharts;

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-stats-range]");
    if (!btn || !btn.closest("[data-stats-range-toggle]")) return;
    e.preventDefault();
    applyRange(btn.getAttribute("data-stats-range"));
  });

  document.addEventListener("DOMContentLoaded", function () {
    var section = document.getElementById("od-sec-statistics");
    if (section && section.classList.contains("active")) {
      initStatsCharts();
    }
  });
})();
