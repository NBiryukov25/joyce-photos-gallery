(function () {
  'use strict';

  function hiRes(src) {
    // Drive thumbnails: bump to full resolution
    if (src.includes('drive.google.com/thumbnail')) {
      return src.replace(/sz=w\d+/, 'sz=w4096');
    }
    return src;
  }

  function buildLightbox() {
    const overlay = document.createElement('div');
    overlay.className = 'lb-overlay';
    overlay.innerHTML = `
      <button class="lb-close" aria-label="Close">&#x2715;</button>
      <button class="lb-arrow lb-prev" aria-label="Previous">&#8592;</button>
      <div class="lb-img-wrap">
        <div class="lb-spinner"></div>
        <img class="lb-img" src="" alt="">
      </div>
      <button class="lb-arrow lb-next" aria-label="Next">&#8594;</button>
      <div class="lb-caption"></div>
      <div class="lb-counter"></div>
    `;
    document.body.appendChild(overlay);
    return overlay;
  }

  document.addEventListener('DOMContentLoaded', function () {
    // Collect all visible photo images (skip placeholders)
    const imgs = Array.from(
      document.querySelectorAll('.photo-item img, .photo-grid img')
    ).filter(function (el) {
      return el.offsetParent !== null && el.src;
    });

    if (!imgs.length) return;

    const overlay  = buildLightbox();
    const lbImg    = overlay.querySelector('.lb-img');
    const spinner  = overlay.querySelector('.lb-spinner');
    const caption  = overlay.querySelector('.lb-caption');
    const counter  = overlay.querySelector('.lb-counter');
    const btnClose = overlay.querySelector('.lb-close');
    const btnPrev  = overlay.querySelector('.lb-prev');
    const btnNext  = overlay.querySelector('.lb-next');

    let current = 0;

    function getCaptionFor(idx) {
      const item = imgs[idx].closest('.photo-item');
      if (!item) return '';
      const p = item.querySelector('.photo-caption');
      return p ? p.textContent.trim() : '';
    }

    function show(idx) {
      current = Math.max(0, Math.min(idx, imgs.length - 1));
      const src = hiRes(imgs[current].src);

      lbImg.classList.remove('loaded');
      spinner.style.display = 'block';
      caption.textContent = getCaptionFor(current);
      counter.textContent = (current + 1) + ' / ' + imgs.length;

      btnPrev.classList.toggle('hidden', current === 0);
      btnNext.classList.toggle('hidden', current === imgs.length - 1);

      const tmp = new Image();
      tmp.onload = function () {
        lbImg.src = src;
        lbImg.alt = imgs[current].alt || '';
        spinner.style.display = 'none';
        lbImg.classList.add('loaded');
      };
      tmp.onerror = function () {
        // Fallback to original src if hi-res fails
        lbImg.src = imgs[current].src;
        spinner.style.display = 'none';
        lbImg.classList.add('loaded');
      };
      tmp.src = src;

      overlay.classList.add('active');
      document.body.style.overflow = 'hidden';
    }

    function close() {
      overlay.classList.remove('active');
      document.body.style.overflow = '';
      lbImg.src = '';
      lbImg.classList.remove('loaded');
    }

    // Click each photo to open
    imgs.forEach(function (img, idx) {
      img.addEventListener('click', function (e) {
        e.preventDefault();
        show(idx);
      });
    });

    btnClose.addEventListener('click', close);
    btnPrev.addEventListener('click', function () { show(current - 1); });
    btnNext.addEventListener('click', function () { show(current + 1); });

    // Click overlay background to close
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });

    // Keyboard navigation
    document.addEventListener('keydown', function (e) {
      if (!overlay.classList.contains('active')) return;
      if (e.key === 'Escape')      close();
      if (e.key === 'ArrowLeft')   show(current - 1);
      if (e.key === 'ArrowRight')  show(current + 1);
    });
  });
})();
