"use strict";
const https  = require("https");
const crypto = require("crypto");

// Verify a URL-safe base64 HMAC token.  Returns gallery name or null.
function verifyShareToken(raw) {
  const SECRET = process.env.SHARE_SECRET;
  if (!SECRET) return null;
  try {
    // URL-safe base64 → standard → decode
    const b64    = raw.replace(/-/g, "+").replace(/_/g, "/");
    const padded = b64 + "=".repeat((4 - b64.length % 4) % 4);
    const decoded = Buffer.from(padded, "base64").toString("utf8");

    // Format: {gallery}:{expires}:{sig16}
    const lastColon = decoded.lastIndexOf(":");
    if (lastColon < 0) return null;
    const sig = decoded.slice(lastColon + 1);
    const msg = decoded.slice(0, lastColon);

    // Verify HMAC-SHA256 (first 16 hex chars)
    const expected = crypto.createHmac("sha256", SECRET)
      .update(msg).digest("hex").slice(0, 16);
    if (sig !== expected) return null;

    // Parse: msg = {gallery}:{expires}
    const colonIdx = msg.lastIndexOf(":");
    if (colonIdx < 0) return null;
    const expires = parseInt(msg.slice(colonIdx + 1), 10);
    if (!expires || Math.floor(Date.now() / 1000) > expires) return null;

    return msg.slice(0, colonIdx) || null;
  } catch (_) {
    return null;
  }
}

const OWNER  = "NBiryukov25";
const REPO   = "joyce-photos-gallery";
const BRANCH = "main";

function ghFetch(path) {
  return new Promise((resolve, reject) => {
    const opts = {
      hostname: "api.github.com",
      path,
      headers: {
        "User-Agent": "joyce-netlify-share/1.0",
        ...(process.env.GITHUB_TOKEN
          ? { Authorization: `Bearer ${process.env.GITHUB_TOKEN}` }
          : {}),
      },
    };
    https.get(opts, (res) => {
      let buf = "";
      res.on("data", (c) => (buf += c));
      res.on("end", () => {
        try { resolve(JSON.parse(buf)); }
        catch (e) { reject(e); }
      });
    }).on("error", reject);
  });
}

function toTitle(slug) {
  return slug.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function buildHTML(gallery, filenames) {
  const title     = toTitle(gallery);
  const IMAGE_EXTS = /\.(jpg|jpeg|png|webp|gif|avif)$/i;
  const VIDEO_EXTS = /\.(mp4|mov|webm|m4v)$/i;
  const rawBase   = `https://raw.githubusercontent.com/${OWNER}/${REPO}/${BRANCH}/assets/${encodeURIComponent(gallery)}/`;
  const filesJson = JSON.stringify(filenames);
  const safeTitle = title.replace(/[&<>"']/g, (c) => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]));

  // pick first jpeg for OG preview
  const preview   = filenames.find((f) => IMAGE_EXTS.test(f)) || filenames[0] || "";
  const ogImage   = preview ? rawBase + encodeURIComponent(preview) : "";

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${safeTitle} · Sheryl Joyce</title>
  <meta property="og:title" content="${safeTitle}">
  <meta property="og:type" content="website">
  <meta property="og:image" content="${ogImage}">
  <meta property="og:description" content="A gallery by Sheryl Joyce">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400&family=Jost:wght@300&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { width: 100%; height: 100%; background: #060404; overflow: hidden; }
    .shell { position: relative; width: 100vw; height: 100vh; }
    .slide { position: absolute; inset: 0; opacity: 0; transition: opacity 0.7s ease; display: flex; align-items: center; justify-content: center; }
    .slide.active { opacity: 1; }
    .slide img { max-width: 100%; max-height: 100%; object-fit: contain; }
    .slide video { max-width: 100%; max-height: 100%; }
    .slide.active img { animation: kb 9s ease-in-out forwards; }
    @keyframes kb { from { transform: scale(1.0); } to { transform: scale(1.06); } }
    .top { position: absolute; top: 0; left: 0; right: 0; z-index: 10; padding: 1.2rem 1.5rem;
           background: linear-gradient(to bottom, rgba(0,0,0,0.6), transparent); pointer-events: none; }
    .top h1 { font-family: 'Cormorant Garamond', serif; font-size: 1rem; font-weight: 400;
              letter-spacing: 0.14em; text-transform: uppercase; color: rgba(255,255,255,0.88); }
    .bottom { position: absolute; bottom: 0; left: 0; right: 0; z-index: 10; padding: 1rem 1.5rem;
              background: linear-gradient(to top, rgba(0,0,0,0.6), transparent);
              display: flex; justify-content: space-between; align-items: flex-end; pointer-events: none; }
    .counter { font-family: 'Jost', sans-serif; font-size: 0.72rem; letter-spacing: 0.1em; color: rgba(255,255,255,0.38); }
    .credit  { font-family: 'Cormorant Garamond', serif; font-size: 0.72rem; letter-spacing: 0.22em;
               text-transform: uppercase; color: rgba(255,255,255,0.32); }
    .ctrl { position: absolute; top: 50%; transform: translateY(-50%); z-index: 10;
            width: 2.8rem; height: 2.8rem; border: 1px solid rgba(255,255,255,0.3); border-radius: 50%;
            background: rgba(0,0,0,0.2); color: rgba(255,255,255,0.75); font-size: 1.5rem;
            display: flex; align-items: center; justify-content: center; cursor: pointer; transition: background 0.2s; }
    .ctrl:hover { background: rgba(255,255,255,0.1); }
    #prev { left: 1rem; } #next { right: 1rem; }
    @media (max-width: 600px) { .ctrl { width: 2.2rem; height: 2.2rem; font-size: 1.2rem; } }
  </style>
</head>
<body>
  <div class="shell" id="shell">
    <div class="top"><h1>${safeTitle}</h1></div>
    <button class="ctrl" id="prev" aria-label="Previous">&#8249;</button>
    <button class="ctrl" id="next" aria-label="Next">&#8250;</button>
    <div class="bottom">
      <span class="counter" id="counter"></span>
      <span class="credit">Sheryl Joyce</span>
    </div>
  </div>
  <script>
    (function () {
      var BASE   = ${JSON.stringify(rawBase)};
      var files  = ${filesJson};
      var shell  = document.getElementById('shell');
      var counter= document.getElementById('counter');
      var cur = 0, slides = [];
      var VIDEO_EXTS = ['mp4','mov','webm','m4v'];
      files.forEach(function (fn, i) {
        var slide = document.createElement('div');
        slide.className = 'slide' + (i === 0 ? ' active' : '');
        var ext = fn.split('.').pop().toLowerCase();
        var el;
        if (VIDEO_EXTS.indexOf(ext) !== -1) {
          el = document.createElement('video');
          el.src = BASE + encodeURIComponent(fn);
          el.controls = true; el.playsInline = true;
        } else {
          el = document.createElement('img');
          el.src = BASE + encodeURIComponent(fn);
          el.alt = ${JSON.stringify(title)} + ' ' + (i + 1);
        }
        slide.appendChild(el);
        shell.insertBefore(slide, document.getElementById('prev'));
        slides.push(slide);
      });
      function show(n) {
        slides[cur].classList.remove('active');
        cur = (n + slides.length) % slides.length;
        slides[cur].classList.add('active');
        counter.textContent = (cur + 1) + ' / ' + slides.length;
      }
      document.getElementById('prev').addEventListener('click', function () { show(cur - 1); });
      document.getElementById('next').addEventListener('click', function () { show(cur + 1); });
      window.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowLeft')  show(cur - 1);
        if (e.key === 'ArrowRight') show(cur + 1);
      });
      show(0);
    })();
  </script>
</body>
</html>`;
}

const DENIED_HTML = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Access Required · Sheryl Joyce</title>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400&family=Jost:wght@200;300&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html, body { height: 100%; background: #0c0a09; color: rgba(247,241,238,0.72);
      font-family: 'Jost', sans-serif; display: flex; align-items: center; justify-content: center; text-align: center; }
    .wrap { padding: 2rem; max-width: 420px; }
    .lock { font-size: 2.6rem; opacity: 0.4; margin-bottom: 1.4rem; }
    h1 { font-family: 'Cormorant Garamond', serif; font-weight: 300; font-size: 1.8rem;
         letter-spacing: 0.1em; color: rgba(247,241,238,0.88); margin-bottom: 0.75rem; }
    p { font-size: 0.82rem; letter-spacing: 0.12em; line-height: 1.7; color: rgba(247,241,238,0.42); }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="lock">🔒</div>
    <h1>Private Gallery</h1>
    <p>This content is shared by invitation only.<br>Please use the link you received.</p>
  </div>
</body>
</html>`;

exports.handler = async (event) => {
  const raw   = (event.queryStringParameters || {}).t || "";
  const token = raw.replace(/[^a-zA-Z0-9_-]/g, "");

  if (!token) {
    return { statusCode: 200, headers: { "Content-Type": "text/html" }, body: DENIED_HTML };
  }

  const gallery = verifyShareToken(token);
  if (!gallery) {
    return { statusCode: 200, headers: { "Content-Type": "text/html" }, body: DENIED_HTML };
  }

  // Fetch file list from GitHub
  let filenames = [];
  try {
    const apiPath = `/repos/${OWNER}/${REPO}/contents/assets/${encodeURIComponent(gallery)}?ref=${BRANCH}`;
    const items = await ghFetch(apiPath);
    if (Array.isArray(items)) {
      const MEDIA = /\.(jpg|jpeg|png|webp|gif|avif|mp4|mov|webm|m4v)$/i;
      filenames = items
        .filter((f) => f.type === "file" && MEDIA.test(f.name))
        .map((f) => f.name)
        .sort();
    }
  } catch (err) {
    console.error("GitHub fetch error:", err.message);
    return { statusCode: 500, body: "Error loading gallery." };
  }

  if (!filenames.length) {
    return { statusCode: 404, headers: { "Content-Type": "text/html" }, body: DENIED_HTML };
  }

  const html = buildHTML(gallery, filenames);
  return {
    statusCode: 200,
    headers: { "Content-Type": "text/html; charset=utf-8" },
    body: html,
  };
};
