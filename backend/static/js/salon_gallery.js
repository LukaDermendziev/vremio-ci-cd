(function () {
  'use strict';

  var motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');

  function configureImageLoading() {
    document.querySelectorAll('.sp-gallery-col').forEach(function (col) {
      var hidden = window.getComputedStyle(col).display === 'none';
      col.querySelectorAll('.sp-gal-card').forEach(function (img) {
        img.decoding = 'async';
        img.loading = hidden ? 'lazy' : 'eager';
      });
    });
  }

  function applyMotionPreference() {
    var reduce = motionQuery.matches;
    document.querySelectorAll('.sp-gallery-track').forEach(function (track) {
      track.style.animationPlayState = reduce ? 'paused' : 'running';
      track.style.webkitAnimationPlayState = reduce ? 'paused' : 'running';
    });
  }

  function nudgeAnimations() {
    if (motionQuery.matches) return;
    document.querySelectorAll('.sp-gallery-track').forEach(function (track) {
      track.style.animationPlayState = 'running';
      track.style.webkitAnimationPlayState = 'running';
    });
  }

  function init() {
    if (!document.querySelector('.sp-gallery')) return;

    configureImageLoading();
    applyMotionPreference();

    if (typeof motionQuery.addEventListener === 'function') {
      motionQuery.addEventListener('change', applyMotionPreference);
    } else if (typeof motionQuery.addListener === 'function') {
      motionQuery.addListener(applyMotionPreference);
    }

    window.addEventListener('resize', configureImageLoading);

    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') nudgeAnimations();
    });

    window.addEventListener('pageshow', function (event) {
      if (event.persisted) {
        configureImageLoading();
        nudgeAnimations();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
