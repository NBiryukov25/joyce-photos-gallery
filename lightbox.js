(function () {
  'use strict';

  var reduceMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ------------------------------------------------------------------ *
   * 1. Scroll-reveal — subtle fade/rise as cards enter the viewport.
   *    Progressive enhancement: nothing is hidden unless JS + IO run,
   *    and it fully respects prefers-reduced-motion.
   * ------------------------------------------------------------------ */
  function initReveal() {
    if (reduceMotion || !('IntersectionObserver' in window)) return;
    var targets = document.querySelectorAll('.gallery-item, .photo-item, .stories-grid > *');
    if (!targets.length) return;

    document.documentElement.classList.add('js-reveal');
    var io = new IntersectionObserver(function (entries, obs) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('reveal-in');
          obs.unobserve(entry.target);
        }
      });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.05 });

    targets.forEach(function (el, i) {
      el.classList.add('reveal');
      // Small staggered delay for a graceful cascade, capped so long
      // galleries don't feel sluggish.
      el.style.setProperty('--reveal-delay', Math.min(i % 6, 5) * 60 + 'ms');
      io.observe(el);
    });
  }

  function hiRes(src) {
    if (src.includes('drive.google.com/thumbnail')) {
      return src.replace(/sz=w\d+/, 'sz=w4096');
    }
    return src;
  }

  function downloadUrl(src) {
    if (src.includes('drive.google.com/thumbnail')) {
      var m = src.match(/[?&]id=([^&]+)/);
      if (m) return 'https://drive.google.com/uc?export=download&id=' + m[1];
    }
    return hiRes(src);
  }

  function buildLightbox() {
    const overlay = document.createElement('div');
    overlay.className = 'lb-overlay';
    overlay.innerHTML =
      '<button class="lb-close" aria-label="Close">&#x2715;</button>' +
      '<button class="lb-arrow lb-prev" aria-label="Previous">&#8592;</button>' +
      '<div class="lb-img-wrap">' +
        '<div class="lb-spinner"></div>' +
        '<img class="lb-img" src="" alt="">' +
      '</div>' +
      '<button class="lb-arrow lb-next" aria-label="Next">&#8594;</button>' +
      '<div class="lb-caption"></div>' +
      '<div class="lb-counter"></div>' +
      '<div class="lb-thumbs" role="tablist" aria-label="Photo thumbnails"></div>' +
      '<div class="lb-actions">' +
        '<button class="lb-action-btn" id="lb-zoom" aria-label="Zoom" title="Zoom">' +
          '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M15.5 14h-.79l-.28-.27a6.5 6.5 0 1 0-.7.7l.27.28v.79l5 5L20.49 19l-5-5zm-6 0A4.5 4.5 0 1 1 14 9.5 4.5 4.5 0 0 1 9.5 14zM7 9h5v1H7z"/></svg>' +
        '</button>' +
        '<button class="lb-action-btn" id="lb-heart" aria-label="Favourite" title="Favourite">' +
          '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 21.593c-5.63-5.539-11-10.297-11-14.402 0-3.791 3.068-5.191 5.281-5.191 1.312 0 4.151.501 5.719 4.457 1.59-3.968 4.464-4.447 5.726-4.447 2.54 0 5.274 1.621 5.274 5.181 0 4.069-5.136 8.625-11 14.402z"/></svg>' +
        '</button>' +
        '<a class="lb-action-btn" id="lb-download" aria-label="Download" title="Download">' +
          '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z"/></svg>' +
        '</a>' +
        '<button class="lb-action-btn" id="lb-share" aria-label="Share" title="Share">' +
          '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92 1.61 0 2.92-1.31 2.92-2.92s-1.31-2.92-2.92-2.92z"/></svg>' +
        '</button>' +
      '</div>';
    document.body.appendChild(overlay);
    return overlay;
  }

  document.addEventListener('DOMContentLoaded', function () {
    initReveal();

    const imgs = Array.from(
      document.querySelectorAll('.photo-item img, .photo-grid img, .bento-item img, .story-card-img, .story-detail-cover-img, .story-inline-img, .love-letter-img, .friends-photo')
    ).filter(function (el) {
      return el.offsetParent !== null && el.src;
    });

    if (!imgs.length) return;

    const overlay  = buildLightbox();
    const wrap     = overlay.querySelector('.lb-img-wrap');
    const lbImg    = overlay.querySelector('.lb-img');
    const spinner  = overlay.querySelector('.lb-spinner');
    const caption  = overlay.querySelector('.lb-caption');
    const counter  = overlay.querySelector('.lb-counter');
    const btnClose = overlay.querySelector('.lb-close');
    const btnPrev  = overlay.querySelector('.lb-prev');
    const btnNext  = overlay.querySelector('.lb-next');
    const btnZoom  = overlay.querySelector('#lb-zoom');
    const btnHeart = overlay.querySelector('#lb-heart');
    const btnDl    = overlay.querySelector('#lb-download');
    const btnShare = overlay.querySelector('#lb-share');
    const thumbBar = overlay.querySelector('.lb-thumbs');

    let current = 0;
    let lastFocused = null;
    const hearted = {};

    /* ---- thumbnail filmstrip ---- */
    const thumbEls = [];
    if (imgs.length > 1) {
      imgs.forEach(function (img, idx) {
        const t = document.createElement('button');
        t.className = 'lb-thumb';
        t.type = 'button';
        t.setAttribute('role', 'tab');
        t.setAttribute('aria-label', 'Photo ' + (idx + 1));
        // Reuse the grid's already-loaded thumbnail source — no extra fetch.
        t.style.backgroundImage = 'url("' + img.src.replace(/"/g, '\\"') + '")';
        t.addEventListener('click', function (e) {
          e.stopPropagation();
          show(idx);
        });
        thumbBar.appendChild(t);
        thumbEls.push(t);
      });
    } else {
      thumbBar.style.display = 'none';
    }

    function syncThumbs() {
      if (!thumbEls.length) return;
      thumbEls.forEach(function (t, i) {
        const on = i === current;
        t.classList.toggle('active', on);
        t.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      const active = thumbEls[current];
      if (active && active.scrollIntoView) {
        active.scrollIntoView({ block: 'nearest', inline: 'center' });
      }
    }

    /* ---- zoom / pan state ---- */
    let scale = 1, panX = 0, panY = 0;
    const MAX_SCALE = 4, MIN_SCALE = 1;

    function applyTransform(animate) {
      lbImg.style.transition = animate ? 'transform 0.25s ease' : 'none';
      lbImg.style.transform = 'translate(' + panX + 'px,' + panY + 'px) scale(' + scale + ')';
      const zoomed = scale > 1.01;
      overlay.classList.toggle('lb-zoomed', zoomed);
      btnZoom.classList.toggle('hearted', zoomed);
      lbImg.style.cursor = zoomed ? 'grab' : 'zoom-in';
      // Hide nav arrows while zoomed so panning doesn't fight navigation.
      btnPrev.classList.toggle('hidden', zoomed || current === 0);
      btnNext.classList.toggle('hidden', zoomed || current === imgs.length - 1);
    }

    function resetZoom(animate) {
      scale = 1; panX = 0; panY = 0;
      applyTransform(animate);
    }

    // Clamp pan so the image can't be dragged entirely off-screen.
    function clampPan() {
      const r = lbImg.getBoundingClientRect();
      const overX = Math.max(0, (r.width - window.innerWidth) / 2 + 20);
      const overY = Math.max(0, (r.height - window.innerHeight) / 2 + 20);
      panX = Math.max(-overX, Math.min(overX, panX));
      panY = Math.max(-overY, Math.min(overY, panY));
    }

    // Zoom toward a point (px,py in viewport coords) to a target scale.
    function zoomTo(target, px, py) {
      target = Math.max(MIN_SCALE, Math.min(MAX_SCALE, target));
      const rect = lbImg.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const ratio = target / scale;
      // Keep the tapped point stationary as we scale.
      panX = (panX - (px - cx)) * ratio + (px - cx);
      panY = (panY - (py - cy)) * ratio + (py - cy);
      scale = target;
      if (scale <= MIN_SCALE + 0.01) { panX = 0; panY = 0; }
      clampPan();
      applyTransform(true);
    }

    function toggleZoom(px, py) {
      if (scale > 1.01) resetZoom(true);
      else zoomTo(2.5, px == null ? window.innerWidth / 2 : px,
                       py == null ? window.innerHeight / 2 : py);
    }

    function getCaptionFor(idx) {
      const item = imgs[idx].closest('.photo-item, .bento-item');
      if (!item) return '';
      const p = item.querySelector('.photo-caption, figcaption');
      return p ? p.textContent.trim() : '';
    }

    function show(idx) {
      current = Math.max(0, Math.min(idx, imgs.length - 1));
      const src = hiRes(imgs[current].src);

      resetZoom(false);
      lbImg.classList.remove('loaded');
      spinner.style.display = 'block';
      caption.textContent = getCaptionFor(current);
      counter.textContent = (current + 1) + ' / ' + imgs.length;

      btnPrev.classList.toggle('hidden', current === 0);
      btnNext.classList.toggle('hidden', current === imgs.length - 1);

      btnHeart.classList.toggle('hearted', !!hearted[current]);
      btnDl.href = downloadUrl(imgs[current].src);
      btnDl.download = (imgs[current].alt || 'photo') + '-' + (current + 1);
      syncThumbs();

      const tmp = new Image();
      tmp.onload = function () {
        lbImg.src = src;
        lbImg.alt = imgs[current].alt || '';
        spinner.style.display = 'none';
        lbImg.classList.add('loaded');
      };
      tmp.onerror = function () {
        lbImg.src = imgs[current].src;
        spinner.style.display = 'none';
        lbImg.classList.add('loaded');
      };
      tmp.src = src;

      overlay.classList.add('active');
      document.body.style.overflow = 'hidden';
      btnClose.focus();
    }

    function close() {
      overlay.classList.remove('active');
      document.body.style.overflow = '';
      resetZoom(false);
      lbImg.src = '';
      lbImg.classList.remove('loaded');
      if (lastFocused && typeof lastFocused.focus === 'function') {
        lastFocused.focus();
      }
    }

    imgs.forEach(function (img, idx) {
      // Make every trigger reachable and operable by keyboard, not just mouse.
      if (!img.hasAttribute('tabindex')) { img.setAttribute('tabindex', '0'); }
      if (!img.hasAttribute('role'))     { img.setAttribute('role', 'button'); }

      function open(e) {
        e.preventDefault();
        lastFocused = img;
        show(idx);
      }

      img.addEventListener('click', open);
      img.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
          open(e);
        }
      });
    });

    btnClose.addEventListener('click', close);
    btnPrev.addEventListener('click', function (e) { e.stopPropagation(); show(current - 1); });
    btnNext.addEventListener('click', function (e) { e.stopPropagation(); show(current + 1); });
    btnZoom.addEventListener('click', function (e) { e.stopPropagation(); toggleZoom(); });

    btnHeart.addEventListener('click', function (e) {
      e.stopPropagation();
      hearted[current] = !hearted[current];
      btnHeart.classList.toggle('hearted', hearted[current]);
    });

    btnDl.addEventListener('click', function (e) {
      e.stopPropagation();
    });

    btnShare.addEventListener('click', function (e) {
      e.stopPropagation();
      const url = window.location.href;
      if (navigator.share) {
        navigator.share({ url: url }).catch(function () {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function () {
          const orig = btnShare.title;
          btnShare.title = 'Copied!';
          setTimeout(function () { btnShare.title = orig; }, 1600);
        }).catch(function () {});
      }
    });

    /* ---- desktop: double-click zoom, wheel zoom ---- */
    lbImg.addEventListener('dblclick', function (e) {
      e.preventDefault();
      toggleZoom(e.clientX, e.clientY);
    });
    wrap.addEventListener('wheel', function (e) {
      e.preventDefault();
      zoomTo(scale - e.deltaY * 0.0025 * scale, e.clientX, e.clientY);
    }, { passive: false });

    /* ---- mouse drag to pan while zoomed ---- */
    let mouseDown = false, mStartX = 0, mStartY = 0, mBaseX = 0, mBaseY = 0;
    lbImg.addEventListener('mousedown', function (e) {
      if (scale <= 1.01) return;
      e.preventDefault();
      mouseDown = true;
      mStartX = e.clientX; mStartY = e.clientY;
      mBaseX = panX; mBaseY = panY;
      lbImg.style.cursor = 'grabbing';
    });
    window.addEventListener('mousemove', function (e) {
      if (!mouseDown) return;
      panX = mBaseX + (e.clientX - mStartX);
      panY = mBaseY + (e.clientY - mStartY);
      clampPan();
      applyTransform(false);
    });
    window.addEventListener('mouseup', function () {
      if (!mouseDown) return;
      mouseDown = false;
      lbImg.style.cursor = 'grab';
    });

    /* ---- touch: swipe to navigate, drag to pan, pinch to zoom, double-tap to zoom ---- */
    let touchMode = null;           // 'swipe' | 'pan' | 'pinch'
    let tStartX = 0, tStartY = 0, tBaseX = 0, tBaseY = 0;
    let pinchStartDist = 0, pinchStartScale = 1, pinchMidX = 0, pinchMidY = 0;
    let lastTap = 0;

    function dist(t1, t2) {
      const dx = t1.clientX - t2.clientX, dy = t1.clientY - t2.clientY;
      return Math.sqrt(dx * dx + dy * dy);
    }

    wrap.addEventListener('touchstart', function (e) {
      if (e.touches.length === 2) {
        touchMode = 'pinch';
        pinchStartDist = dist(e.touches[0], e.touches[1]);
        pinchStartScale = scale;
        pinchMidX = (e.touches[0].clientX + e.touches[1].clientX) / 2;
        pinchMidY = (e.touches[0].clientY + e.touches[1].clientY) / 2;
      } else if (e.touches.length === 1) {
        const t = e.touches[0];
        tStartX = t.clientX; tStartY = t.clientY;
        tBaseX = panX; tBaseY = panY;
        touchMode = scale > 1.01 ? 'pan' : 'swipe';
        // Double-tap detection.
        const now = e.timeStamp;
        if (now - lastTap < 300) {
          toggleZoom(t.clientX, t.clientY);
          lastTap = 0;
        } else {
          lastTap = now;
        }
      }
    }, { passive: true });

    wrap.addEventListener('touchmove', function (e) {
      if (touchMode === 'pinch' && e.touches.length === 2) {
        e.preventDefault();
        const d = dist(e.touches[0], e.touches[1]);
        zoomTo(pinchStartScale * (d / pinchStartDist), pinchMidX, pinchMidY);
      } else if (touchMode === 'pan' && e.touches.length === 1) {
        e.preventDefault();
        const t = e.touches[0];
        panX = tBaseX + (t.clientX - tStartX);
        panY = tBaseY + (t.clientY - tStartY);
        clampPan();
        applyTransform(false);
      }
    }, { passive: false });

    wrap.addEventListener('touchend', function (e) {
      if (touchMode === 'swipe' && e.changedTouches.length) {
        const t = e.changedTouches[0];
        const dx = t.clientX - tStartX, dy = t.clientY - tStartY;
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
          if (dx < 0) show(current + 1); else show(current - 1);
        } else if (Math.abs(dx) < 10 && Math.abs(dy) > 90) {
          close(); // swipe down to dismiss
        }
      }
      if (e.touches.length === 0) touchMode = null;
    });

    overlay.addEventListener('click', function (e) {
      // Don't close on background click while zoomed (user is likely panning).
      if (e.target === overlay && scale <= 1.01) close();
    });

    document.addEventListener('keydown', function (e) {
      if (!overlay.classList.contains('active')) return;
      if (e.key === 'Escape')     close();
      if (e.key === 'ArrowLeft')  show(current - 1);
      if (e.key === 'ArrowRight') show(current + 1);
      if (e.key === '+' || e.key === '=') zoomTo(scale + 0.5, window.innerWidth / 2, window.innerHeight / 2);
      if (e.key === '-' || e.key === '_') zoomTo(scale - 0.5, window.innerWidth / 2, window.innerHeight / 2);
      if (e.key === '0') resetZoom(true);
    });
  });
})();
