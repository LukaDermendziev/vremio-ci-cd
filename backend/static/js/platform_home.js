(function () {
  "use strict";

  var navToggle = document.getElementById("vm-nav-toggle");
  var navMenu = document.getElementById("vm-nav-menu");

  if (navToggle && navMenu) {
    navToggle.addEventListener("click", function () {
      var open = navMenu.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });

    navMenu.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () {
        navMenu.classList.remove("is-open");
        navToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener("click", function (event) {
      var targetId = anchor.getAttribute("href");
      if (!targetId || targetId === "#") return;
      var target = document.querySelector(targetId);
      if (!target) return;
      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
      if (history.replaceState) {
        history.replaceState(null, "", targetId);
      }
    });
  });

  if (window.location.hash) {
    var el = document.querySelector(window.location.hash);
    if (el) {
      window.setTimeout(function () {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }
  }

  var searchForm = document.getElementById("vm-business-search");
  var searchInput = document.getElementById("vm-search-q");
  var categoryPills = document.getElementById("vm-category-pills");
  var businessGrid = document.getElementById("vm-business-grid");
  var emptyState = document.getElementById("vm-business-empty");
  var activeCategory = "all";
  var filterTimer = null;

  function readInitialParams() {
    var params = new URLSearchParams(window.location.search);
    activeCategory = params.get("category") || "all";
    if (searchInput && params.get("q")) {
      searchInput.value = params.get("q");
    }
    if (categoryPills) {
      categoryPills.querySelectorAll("[data-category]").forEach(function (pill) {
        pill.classList.toggle("is-active", pill.dataset.category === activeCategory);
      });
    }
  }

  function syncUrl() {
    if (!history.replaceState) return;
    var q = searchInput ? searchInput.value.trim() : "";
    var params = new URLSearchParams();
    if (q) params.set("q", q);
    if (activeCategory && activeCategory !== "all") params.set("category", activeCategory);
    var query = params.toString();
    var url = query ? "/?" + query + "#businesses" : "/#businesses";
    history.replaceState(null, "", url);
  }

  function applyBusinessFilter() {
    if (!businessGrid) return;
    var q = searchInput ? searchInput.value.trim().toLowerCase() : "";
    var cards = businessGrid.querySelectorAll(".vm-business-card");
    var visible = 0;
    cards.forEach(function (card) {
      var category = card.dataset.category || "";
      var searchText = card.dataset.search || card.textContent.toLowerCase();
      var categoryOk = activeCategory === "all" || category === activeCategory;
      var searchOk = !q || searchText.indexOf(q) !== -1;
      var show = categoryOk && searchOk;
      card.hidden = !show;
      if (show) visible += 1;
    });
    if (emptyState) {
      emptyState.hidden = visible > 0;
    }
    syncUrl();
  }

  if (searchForm) {
    searchForm.addEventListener("submit", function (event) {
      event.preventDefault();
      applyBusinessFilter();
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", function () {
      clearTimeout(filterTimer);
      filterTimer = setTimeout(applyBusinessFilter, 200);
    });
  }

  if (categoryPills) {
    categoryPills.addEventListener("click", function (event) {
      var pill = event.target.closest("[data-category]");
      if (!pill) return;
      activeCategory = pill.dataset.category || "all";
      categoryPills.querySelectorAll("[data-category]").forEach(function (btn) {
        btn.classList.toggle("is-active", btn === pill);
      });
      applyBusinessFilter();
    });
  }

  readInitialParams();
  applyBusinessFilter();
})();
