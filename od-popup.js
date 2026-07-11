/* ============================================================
   od-popup.js — generic "Featuring" popup engine
   ------------------------------------------------------------
   Drives every .od-overlay popup on the page independently, so
   any number of popups can coexist. Each popup runs its own
   slideshow (with the slow Ken-Burns zoom), progress bar, dots,
   and close handling.

   Behaviour:
     • Popups are shown ONE AT A TIME (sequential). The first
       auto-opens; closing it reveals the next, and so on.
     • Add data-od-auto="false" to a popup to exclude it from the
       auto-open queue (open it yourself via el._odOpen()).
     • Optional data-od-interval="8000" sets the per-popup autoplay
       speed in milliseconds (default 8000).
     • Dots are generated automatically from the number of slides
       if the .od-dots container is left empty.

   Required markup per popup (see tools/popup-template.html):
     <div class="od-overlay od-hidden" data-od-popup>
       <div class="od-modal">
         <button class="od-close" data-od-close>✕</button>
         <div class="od-header"><h2 class="od-title">…</h2><hr class="od-rule"></div>
         <div class="od-slides-wrap">
           <div class="od-slide active"><img src="…"></div>
           <div class="od-slide"><img src="…"></div>
         </div>
         <div class="od-progress"><div class="od-bar"></div></div>
         <div class="od-dots"></div>
         <div class="od-message">…</div>
         <div class="od-footer"><button class="od-enter" data-od-close>Enter</button></div>
       </div>
     </div>
   ============================================================ */
(function () {
  'use strict';

  function initPopup(overlay) {
    var slides   = overlay.querySelectorAll('.od-slide');
    var dotsWrap = overlay.querySelector('.od-dots');
    var bar      = overlay.querySelector('.od-bar');
    var N        = slides.length;
    var INTERVAL = parseInt(overlay.getAttribute('data-od-interval'), 10) || 8000;
    var cur = 0, timer = null, onClose = function () {};

    // Build dots automatically when the container is empty.
    if (dotsWrap && !dotsWrap.children.length && N > 1) {
      for (var k = 0; k < N; k++) {
        var b = document.createElement('button');
        b.className = 'od-dot' + (k === 0 ? ' active' : '');
        b.type = 'button';
        b.setAttribute('aria-label', 'Go to slide ' + (k + 1));
        dotsWrap.appendChild(b);
      }
    }
    var dots = overlay.querySelectorAll('.od-dot');

    function resetBar() {
      if (!bar) return;
      bar.style.transition = 'none';
      bar.style.width = '0%';
      requestAnimationFrame(function () {
        requestAnimationFrame(function () {
          bar.style.transition = 'width ' + INTERVAL + 'ms linear';
          bar.style.width = '100%';
        });
      });
    }

    function show(n) {
      if (!N) return;
      slides[cur].classList.remove('active');
      if (dots[cur]) dots[cur].classList.remove('active');
      cur = (n + N) % N;
      slides[cur].classList.add('active');
      if (dots[cur]) dots[cur].classList.add('active');
      resetBar();
    }

    function start() { if (!timer && N > 1) timer = setInterval(function () { show(cur + 1); }, INTERVAL); }
    function stop()  { clearInterval(timer); timer = null; }

    Array.prototype.forEach.call(dots, function (d, i) {
      d.addEventListener('click', function () { stop(); show(i); start(); });
    });
    Array.prototype.forEach.call(overlay.querySelectorAll('[data-od-close]'), function (btn) {
      btn.addEventListener('click', function () { close(); });
    });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) close(); });

    function open()  { overlay.classList.remove('od-hidden'); cur = 0; show(0); start(); }
    function close() { overlay.classList.add('od-hidden'); stop(); onClose(); onClose = function () {}; }

    overlay._odOpen = open;
    overlay._odClose = close;
    overlay._odOnClose = function (fn) { onClose = fn; };
  }

  document.addEventListener('DOMContentLoaded', function () {
    var overlays = Array.prototype.slice.call(document.querySelectorAll('.od-overlay'));
    if (!overlays.length) return;
    overlays.forEach(function (o) { o.classList.add('od-hidden'); initPopup(o); });

    // Close the visible popup on Escape.
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape') return;
      overlays.forEach(function (o) { if (!o.classList.contains('od-hidden')) o._odClose(); });
    });

    // Sequential auto-open queue.
    var queue = overlays.filter(function (o) { return o.getAttribute('data-od-auto') !== 'false'; });
    var i = 0;
    (function next() {
      if (i >= queue.length) return;
      var o = queue[i++];
      o._odOnClose(next);
      o._odOpen();
    })();
  });
})();
