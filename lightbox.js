(function () {
  'use strict';

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
      '<div class="lb-actions">' +
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
    const imgs = Array.from(
      document.querySelectorAll('.photo-item img, .photo-grid img, .story-card-img')
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
    const btnHeart = overlay.querySelector('#lb-heart');
    const btnDl    = overlay.querySelector('#lb-download');
    const btnShare = overlay.querySelector('#lb-share');

    let current = 0;
    const hearted = {};

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

      btnHeart.classList.toggle('hearted', !!hearted[current]);
      btnDl.href = downloadUrl(imgs[current].src);
      btnDl.download = (imgs[current].alt || 'photo') + '-' + (current + 1);

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
    }

    function close() {
      overlay.classList.remove('active');
      document.body.style.overflow = '';
      lbImg.src = '';
      lbImg.classList.remove('loaded');
    }

    imgs.forEach(function (img, idx) {
      img.addEventListener('click', function (e) {
        e.preventDefault();
        show(idx);
      });
    });

    btnClose.addEventListener('click', close);
    btnPrev.addEventListener('click', function () { show(current - 1); });
    btnNext.addEventListener('click', function () { show(current + 1); });

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

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close();
    });

    document.addEventListener('keydown', function (e) {
      if (!overlay.classList.contains('active')) return;
      if (e.key === 'Escape')     close();
      if (e.key === 'ArrowLeft')  show(current - 1);
      if (e.key === 'ArrowRight') show(current + 1);
    });
  });
})();
