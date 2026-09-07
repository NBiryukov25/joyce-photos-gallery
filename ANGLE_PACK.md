# ANGLE PACK on the Joyce site

1. Deploy the separate ANGLE PACK backend repository to Render using its README. This site remains on GitHub Pages.
2. assets/angle-pack/config.js now points to https://angle-pack.onrender.com. This is the only backend URL setting. Never put keys or passwords in site files.
3. Commit portrait.html, ANGLE_PACK.md, and the five files under assets/angle-pack/. Publish through your existing GitHub Pages workflow.
4. Open portrait.html → **ANGLE PACK**. Enter your app password. Select **MOCK**, upload a photo, generate one image, try **CHANGE ANGLE**, and download the result. Select **LIVE** only when you want paid generation.
5. Repeat on iPhone Safari. Download PNGs to Files; use the Share menu to save an opened image to Photos. Download the manifest too. Files may disappear after a Render restart/redeploy.

Local preview (from the separate ANGLE PACK backend directory):

```powershell
npm ci
node scripts/preview-pages.js "C:/Users/rcrom/OneDrive/02_DOCUMENTS_RECORDS/Joyce-photos-gallery"
```

Open http://127.0.0.1:8080/portrait.html. Preview password: local-preview-password. This command forces mock mode and does not read .env. Stop with Ctrl+C. The config automatically uses backend port 3210 for localhost pages.

The interface is a native custom element, not an iframe. Styles are isolated to preserve navigation, Three Faces and Transcribe. Crop Zoom, Outpaint Zoom, Generative Angle, all presets, preservation settings, five-image packs, saved sessions and individual revisions remain. Automatic packs use optional reference-angle labels to avoid repeated views.

Sign-in tokens stay in browser memory, so refresh/restart can require signing in again. Requests and downloads go through Render; this site never calls fal.ai directly. Temporary storage expiration, provider failures and backend connection problems are displayed.

app.js is the site-specific interface; api-client.js and presets.js are shared source copies also retained in the backend public/ directory. Backend scripts/check-pages.js checks that those copies match. No frontend build step or npm installation is required for GitHub Pages.

Transcribe uses a separate runtime access-token field. Enter the token accepted by the existing transcription backend; the former frontend-only password gate was removed. The token stays in tab memory and is cleared from the input immediately on submission. Refresh to forget it. Existing HTTPS query-token upload/polling routes are retained for backend compatibility. Previously published transcription credentials should be rotated on that backend; removing source values does not erase Git history.
