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

  /* Plan details expand */
  document.querySelectorAll("[data-plan-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var planId = btn.getAttribute("data-plan-toggle");
      var details = document.getElementById("vm-plan-details-" + planId);
      if (!details) return;
      var open = details.hasAttribute("hidden");
      if (open) {
        details.removeAttribute("hidden");
        btn.setAttribute("aria-expanded", "true");
        btn.textContent = btn.getAttribute("data-label-less") || "Less details";
      } else {
        details.setAttribute("hidden", "");
        btn.setAttribute("aria-expanded", "false");
        btn.textContent = btn.getAttribute("data-label-more") || "More details";
      }
    });
  });

  /* Plan interest form modal */
  var leadModal = document.getElementById("vm-lead-modal");
  var leadForm = document.getElementById("vm-lead-form");
  var leadFormView = document.getElementById("vm-lead-form-view");
  var leadSuccessView = document.getElementById("vm-lead-success-view");
  var leadSuccessText = document.getElementById("vm-lead-success-text");
  var leadError = document.getElementById("vm-lead-error");
  var leadSubmit = document.getElementById("vm-lead-submit");
  var leadPlanSelect = leadForm ? leadForm.querySelector('[name="plan"]') : null;
  var leadNameInput = leadForm ? leadForm.querySelector('[name="name"]') : null;
  var leadContactInput = leadForm ? leadForm.querySelector('[name="contact_value"]') : null;
  var leadContactLabel = document.getElementById("vm-lead-contact-label");

  function syncContactMethodUI() {
    if (!leadForm || !leadContactInput) return;
    var methodInput = leadForm.querySelector('[name="contact_method"]:checked');
    var method = methodInput ? methodInput.value : "instagram";
    var igPh = leadForm.getAttribute("data-placeholder-instagram") || "Instagram username";
    var phonePh = leadForm.getAttribute("data-placeholder-phone") || "Phone number";
    if (method === "phone") {
      leadContactInput.setAttribute("placeholder", phonePh);
      leadContactInput.setAttribute("type", "tel");
      leadContactInput.setAttribute("autocomplete", "tel");
      if (leadContactLabel) leadContactLabel.textContent = phonePh;
    } else {
      leadContactInput.setAttribute("placeholder", igPh);
      leadContactInput.setAttribute("type", "text");
      leadContactInput.setAttribute("autocomplete", "off");
      if (leadContactLabel) leadContactLabel.textContent = igPh;
    }
  }

  function closeLeadModal() {
    if (!leadModal) return;
    leadModal.hidden = true;
    document.body.classList.remove("vm-modal-open");
  }

  function openLeadModal(planId) {
    if (!leadModal || !leadForm) return;
    if (leadFormView) leadFormView.hidden = false;
    if (leadSuccessView) leadSuccessView.hidden = true;
    if (leadError) {
      leadError.hidden = true;
      leadError.textContent = "";
    }
    if (planId) {
      var planRadio = leadForm.querySelector(
        'input[name="plan"][value="' + planId + '"]'
      );
      if (planRadio) planRadio.checked = true;
    }
    syncContactMethodUI();
    leadModal.hidden = false;
    document.body.classList.add("vm-modal-open");
    if (leadNameInput) leadNameInput.focus();
  }

  document.querySelectorAll("[data-plan-interest]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      openLeadModal(btn.getAttribute("data-plan-id") || "starter");
    });
  });

  if (leadModal) {
    leadModal.querySelectorAll("[data-lead-close]").forEach(function (el) {
      el.addEventListener("click", closeLeadModal);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !leadModal.hidden) closeLeadModal();
    });
  }

  if (leadForm) {
    leadForm.querySelectorAll('[name="contact_method"]').forEach(function (input) {
      input.addEventListener("change", syncContactMethodUI);
    });
    syncContactMethodUI();

    leadForm.addEventListener("submit", function (event) {
      event.preventDefault();
      if (leadError) {
        leadError.hidden = true;
        leadError.textContent = "";
      }
      if (leadSubmit) {
        leadSubmit.disabled = true;
      }
      var formData = new FormData(leadForm);
      fetch(leadForm.action, {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { ok: response.ok, status: response.status, data: data };
          });
        })
        .then(function (result) {
          if (result.data && result.data.ok) {
            if (leadFormView) leadFormView.hidden = true;
            if (leadSuccessView) leadSuccessView.hidden = false;
            if (leadSuccessText && result.data.message) {
              leadSuccessText.textContent = result.data.message;
            }
            leadForm.reset();
            var starter = leadForm.querySelector('input[name="plan"][value="starter"]');
            var igMethod = leadForm.querySelector(
              'input[name="contact_method"][value="instagram"]'
            );
            if (starter) starter.checked = true;
            if (igMethod) igMethod.checked = true;
            syncContactMethodUI();
            return;
          }
          var msg =
            (result.data && result.data.error) ||
            "Something went wrong. Please try again.";
          if (leadError) {
            leadError.textContent = msg;
            leadError.hidden = false;
          }
        })
        .catch(function () {
          if (leadError) {
            leadError.textContent = "Something went wrong. Please try again.";
            leadError.hidden = false;
          }
        })
        .finally(function () {
          if (leadSubmit) leadSubmit.disabled = false;
        });
    });
  }
})();
