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

The site is now **fully self-contained**: every photo from the five linked
Unscripted galleries was downloaded into the repository, the five previously-empty
local gallery pages were populated with those photos, and every Unscripted link
(both the cover `<a>` and the "View full series" `<a>`, in `index.html` and
`gallery.html`) now points to the local page. **Zero Unscripted image hosts and
zero Unscripted links remain.**

### Download method
- Each gallery photo is served in three Cloudflare variants (`limit_900`,
  `limit_1800`, `limit_2500`). The **`limit_2500`** (highest-quality accessible)
  version was downloaded for every photo.
- Each file's true format was detected from its magic bytes and the file was
  named accordingly (some URLs use a `.png`/`.PNG` suffix while the bytes are
  JPEG). Images were **not** cropped, resized, recompressed, or altered.
- In-gallery duplicates (photos the source gallery displays more than once) were
  stored **once** and referenced from each position — no duplicate files.
- Display order was preserved from each source page's markup.

### Per-gallery results
| Gallery | Local page populated | Asset folder | Photo refs | Unique files stored |
|---------|----------------------|--------------|-----------:|--------------------:|
| Number 19 | `galleries/number-19.html` | `assets/Number-19/` | 7 | 7 |
| The Green Hour | `galleries/the-green-hour.html` | `assets/The-Green-Hour/` | 6 | 5 |
| Morning Softness | `galleries/morning-softness.html` | `assets/Morning-Softness/` | 17 | 17 |
| The Bedroom Suite | `galleries/the-bedroom-suite.html` | `assets/The-Bedroom-Suite/` | 21 | 20 |
| Shadowed Affections | `galleries/shadowed-affections-a-nights-embrace.html` | `assets/Shadowed-Affections/` | 21 | 19 |

- **68 unique image files** stored total; **72 photo references** (difference = 4
  legitimate in-gallery duplicates deduped to a single stored file).
- Source galleries carried no per-photo captions; images use descriptive `alt`
  text (`"<Gallery> — N"`). The one pre-existing caption, **"Come here…Love"** on
  the Shadowed Affections page (`assets/Shadowed-Affections/come-here-love.jpg`,
  downloaded in the prior commit), was preserved in place and reused (not
  re-downloaded).

### Links updated to local
Both `<a>` links per card (cover image + "View full series") were repointed and
cleaned to same-tab internal navigation, in **`index.html`** and **`gallery.html`**:

| Former Unscripted destination | Now points to |
|-------------------------------|---------------|
| `…/basementinnovations/number-19` | `galleries/number-19.html` |
| `…/1386771/the-green-hour` | `galleries/the-green-hour.html` |
| `…/basementinnovations/joyce-morning-softness` | `galleries/morning-softness.html` |
| `…/basementinnovations/the-bedroom-suite` | `galleries/the-bedroom-suite.html` |
| `…/basementinnovations/shadowed-affections-a-night-s-embrace` | `galleries/shadowed-affections-a-nights-embrace.html` |

---

## Preserved External Links

**None remain.** All five Unscripted destinations were converted to local gallery
links now that the repository contains the complete photo sets. No intentional
Unscripted website links are left.

---

## Failures or Unresolved Items

- **1 Morning Softness photo could not be downloaded.** Source stem
  `can5euacvkjwp014wi3vzfu2ltav` (display position 4) returns **HTTP 404** at every
  variant (`limit_2500`/`1800`/`900`) — it is no longer hosted on Unscripted's CDN.
  It is **not** claimed as migrated; the Morning Softness gallery contains the
  remaining 17 of 18 photos. No other assets failed.

---

## Final Totals

| Metric | Count |
|--------|------|
| Manus references remaining (live image/asset) | 0 |
| Unscripted image URLs found | 73 (across 5 galleries) |
| Unique Unscripted images added | 68 |
| Local gallery pages populated | 5 |
| Repository references updated | 72 image refs + 20 link href (10 per file × 2 files) |
| Intentional Unscripted destination links preserved | 0 (all converted to local) |
| Failed or unresolved assets | 1 (Morning Softness photo, 404 at source) |
