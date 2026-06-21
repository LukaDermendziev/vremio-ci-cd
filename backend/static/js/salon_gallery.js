(function () {
  'use strict';

  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  function isColVisible(col) {
    return !!(col && col.offsetWidth > 0 && col.offsetHeight > 0);
  }

  function getOriginalCount(track) {
    if (track.dataset.originalCount) {
      return parseInt(track.dataset.originalCount, 10);
    }
    var count = 0;
    for (var i = 0; i < track.children.length; i++) {
      if (track.children[i].getAttribute('aria-hidden') === 'true') break;
      count++;
    }
    return count || track.children.length;
  }

  function measureLoopDistance(track, originalCount) {
    var cloneStart = track.children[originalCount];
    if (!cloneStart) return 0;
    return cloneStart.offsetTop;
  }

  function resetTrack(track) {
    var originalCount = getOriginalCount(track);
    if (!originalCount) return;

    track.dataset.originalCount = String(originalCount);

    while (track.children.length > originalCount) {
      track.removeChild(track.lastElementChild);
    }

    track.classList.remove('sp-track-ready');
    delete track.dataset.loopReady;
    track.style.removeProperty('--loop-distance');
  }

  function resetAllTracks() {
    document.querySelectorAll('.sp-gallery-track').forEach(resetTrack);
  }

  function getPendingTracks() {
    var pending = [];
    document.querySelectorAll('.sp-gallery-track').forEach(function (track) {
      if (track.dataset.loopReady === '1') return;

      var col = track.closest('.sp-gallery-col');
      if (!isColVisible(col)) return;

      var originalCount = getOriginalCount(track);
      if (!originalCount) return;

      track.dataset.originalCount = String(originalCount);

      pending.push({
        track: track,
        originalCount: originalCount,
        imgs: Array.from(track.children).slice(0, originalCount),
      });
    });
    return pending;
  }

  function initVisibleTracks() {
    var pending = getPendingTracks();
    if (!pending.length) return;

    pending.forEach(function (item) {
      if (item.track.children.length === item.originalCount) {
        item.imgs.forEach(function (node) {
          var clone = node.cloneNode(true);
          clone.setAttribute('aria-hidden', 'true');
          item.track.appendChild(clone);
        });
      }
    });

    var readyTracks = [];
    pending.forEach(function (item) {
      var loopDistance = measureLoopDistance(item.track, item.originalCount);
      if (loopDistance <= 0) return;

      item.track.style.setProperty('--loop-distance', loopDistance + 'px');
      readyTracks.push(item.track);
    });

    readyTracks.forEach(function (track) {
      track.dataset.loopReady = '1';
      track.classList.add('sp-track-ready');
    });
  }

  function restartReadyTracks() {
    document.querySelectorAll('.sp-gallery-track').forEach(function (track) {
      if (track.dataset.loopReady !== '1') return;

      var originalCount = parseInt(track.dataset.originalCount, 10);
      if (!originalCount) return;

      var loopDistance = measureLoopDistance(track, originalCount);
      if (loopDistance <= 0) return;

      track.style.setProperty('--loop-distance', loopDistance + 'px');
      track.classList.remove('sp-track-ready');
      void track.offsetHeight;
      track.classList.add('sp-track-ready');
    });
  }

  function refreshGallery() {
    if (refreshGallery.active) return;
    refreshGallery.active = true;
    resetAllTracks();
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        initVisibleTracks();
        refreshGallery.active = false;
      });
    });
  }
  refreshGallery.active = false;

  function watchGallery() {
    var gallery = document.querySelector('.sp-gallery');
    if (!gallery) return;

    gallery.querySelectorAll('.sp-gal-card').forEach(function (img) {
      img.loading = 'eager';
      img.decoding = 'async';
    });

    initVisibleTracks();

    window.addEventListener('pageshow', function (e) {
      if (e.persisted) {
        refreshGallery();
      }
    });

    window.addEventListener('pagehide', function (e) {
      if (!e.persisted) return;
      document.querySelectorAll('.sp-gallery-track.sp-track-ready').forEach(function (track) {
        track.classList.remove('sp-track-ready');
      });
    });

    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState !== 'visible' || refreshGallery.active) return;
      requestAnimationFrame(function () {
        var needsFullRefresh = false;
        document.querySelectorAll('.sp-gallery-col').forEach(function (col) {
          if (!isColVisible(col)) return;
          var track = col.querySelector('.sp-gallery-track');
          if (track && track.dataset.loopReady !== '1') {
            needsFullRefresh = true;
          }
        });
        if (needsFullRefresh) {
          initVisibleTracks();
        } else {
          restartReadyTracks();
        }
      });
    });

    if (typeof ResizeObserver !== 'undefined') {
      gallery.querySelectorAll('.sp-gallery-col').forEach(function (col) {
        var ro = new ResizeObserver(function () {
          if (!isColVisible(col)) return;
          var track = col.querySelector('.sp-gallery-track');
          if (track && track.dataset.loopReady !== '1') {
            initVisibleTracks();
          }
        });
        ro.observe(col);
      });
    }

    var breakpoints = [
      window.matchMedia('(min-width: 481px)'),
      window.matchMedia('(min-width: 900px)'),
    ];
    breakpoints.forEach(function (mql) {
      if (typeof mql.addEventListener === 'function') {
        mql.addEventListener('change', initVisibleTracks);
      } else if (typeof mql.addListener === 'function') {
        mql.addListener(initVisibleTracks);
      }
    });
  }

  watchGallery();
})();
