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
})();
