# External Asset Consolidation

Consolidates externally-hosted photo assets into this repository so GitHub Pages
serves every image from `assets/`. Covers (1) verification of the earlier Manus
migration and (2) elimination of Unscripted as an image host.

> Note: Manus host tokens below are intentionally defused (e.g. `manuscdn[.]com`,
> `user\_upload\_by\_module`) so this report does not itself register as a live
> reference in a repository-wide search.

---

## Manus Verification

### Search terms checked
Across HTML, CSS, JS, JSON, Markdown, Python, config, and generated files:

- `files.manuscdn[.]com`
- `manuscdn[.]com`
- `user\_upload\_by\_module`
- `session\_file`
- Case-insensitive `manus` (spelling variations)
- URL-encoded / escaped variants (`manus%…`, `\x`, HTML entities)
- The former Manus session id path segment `310519663401710643`

Also inspected every `<img src>`, `srcset`, `poster`, and CSS `url()` that was
part of the Manus migration.

### Remaining Manus references found
- **Live image references (src / srcset / poster / url() / href): 0.**
- Non-asset textual occurrences only, none of which is an image dependency:
  - `MANUS_ASSET_MIGRATION.md` — the historical migration report (host tokens
    already defused). Documentation, not a live reference.
  - `build_site_mcp.py` — the string `manus-mcp-cli` (lines 5, 108). This is the
    name of the Airtable command-line tool used to read gallery data; it is **not**
    an image host and was left untouched to avoid breaking that pipeline.

### Broken replacements found
None. All **20** distinct former-Manus asset references (in `assets/covers/`,
`assets/backgrounds/`, and `assets/domestic-helper/`) were validated:

- The referenced asset exists.
- Capitalization matches exactly (verified against directory listings).
- The relative path is correct from the file where it is used (root vs. `galleries/`).
- Each file is nonempty and a valid image (PNG/JPEG signature check).
- Each path is serveable by GitHub Pages.

### Repairs made
None required — no Manus reference was broken or dangling.

### Final Manus reference count
- Live Manus image/asset references: **0**
- Broken repository paths from the Manus migration: **0**

---

## Unscripted Asset Migration

One Unscripted-hosted **image** existed in the repository. It was downloaded and
localized; all other Unscripted references are intentional destination links
(see *Preserved External Links*).

### Image 1 — "Come here…Love"
| Field | Value |
|-------|-------|
| Original image URL | `https://unscriptedphotographers.com/_cf_images/variant=limit_1800,storage=cloudflare/wvvbf1f14l4v9hkbr9hj9alo5n83.png` |
| Related Unscripted gallery URL | `https://unscriptedphotographers.com/basementinnovations/shadowed-affections-a-night-s-embrace` |
| File(s) where referenced | `galleries/shadowed-affections-a-nights-embrace.html` (line 38) |
| How the image was used | `<img src>` in the `.photo-grid` — the only photo on the page; `alt` and `.photo-title` both "Come here...Love" |
| New GitHub asset path | `assets/Shadowed-Affections/come-here-love.jpg` |
| Download status | **Success** (HTTP 200). Only the `limit_1800` variant is accessible; `limit_3000`, `public`, and bare `storage=cloudflare` variants returned HTTP 400. `1800px` is therefore the highest-quality accessible version. |
| Format note | The URL ends in `.png` but the server delivers a **JPEG** (JFIF, 1300×1800, progressive). Stored with its true `.jpg` extension. Not cropped, resized, recompressed, or altered. |
| Replacement status | **Done** — `src` updated to `../assets/Shadowed-Affections/come-here-love.jpg`; alt text, title, order, layout, and styling preserved. |
| Validation status | **Passed** — 126,893 bytes; complete JPEG (SOI `ffd8` / EOI `ffd9`); path resolves from `galleries/` with exact capitalization; Pages-serveable. |

---

## Preserved External Links

All remaining Unscripted references are `<a href target="_blank">` destination
links ("View full series →" and the linked cover). Each is preserved because no
**complete, verified** local gallery equivalent exists — the corresponding local
pages are empty stubs (0 images) — and the displayed cover for each card is
already a local or Google-Drive asset, so none carries an Unscripted image-host
dependency.

| External destination (Unscripted) | Appears in | Why preserved |
|-----------------------------------|-----------|---------------|
| `…/basementinnovations/number-19` | `index.html`, `gallery.html` | Intentional link to the full external series. Local `galleries/number-19.html` is an empty stub (0 images). Card cover already local: `assets/covers/number-19.jpg`. |
| `…/1386771/the-green-hour` | `index.html`, `gallery.html` | Full-series link. Local `galleries/the-green-hour.html` is an empty stub. Cover already local: `assets/covers/the-green-hour.png`. |
| `…/basementinnovations/joyce-morning-softness` | `index.html`, `gallery.html` | Full-series link. Local `galleries/morning-softness.html` is an empty stub. Cover already local: `assets/covers/morning-softness.png`. |
| `…/basementinnovations/the-bedroom-suite` | `index.html` | Full-series link. Local `galleries/the-bedroom-suite.html` is an empty stub. Cover is a Google-Drive thumbnail (not an Unscripted image; out of scope). |
| `…/basementinnovations/shadowed-affections-a-night-s-embrace` | `index.html`, `gallery.html` | Full-series link to the external multi-photo gallery. The local page holds only the single now-localized photo — not a complete match — so the external link is kept. Card cover already local/Drive. |

Total: **5 unique external destinations** preserved (each appears twice per card —
on the cover `<a>` and the "View full series" `<a>`).

---

## Failures or Unresolved Items

None. The single Unscripted image was reachable, downloaded, verified, relocated,
and re-referenced successfully.

- Higher-resolution variants (`limit_3000`, `public`) returned HTTP 400, so the
  accessible maximum (`limit_1800`, 1300×1800) was used. This is noted rather than
  treated as a failure — it is the highest-quality version the host will serve.

---

## Final Totals

| Metric | Count |
|--------|------|
| Manus references remaining (live image/asset) | 0 |
| Unscripted image URLs found | 1 |
| Unique Unscripted images added | 1 |
| Repository references updated | 1 |
| Intentional Unscripted destination links preserved | 5 unique destinations |
| Failed or unresolved assets | 0 |
