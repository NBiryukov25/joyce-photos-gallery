# Manus Asset Migration

All images previously hosted on the Manus CDN (`files.manuscdn[.]com`) have been
downloaded into this repository and every reference updated to a relative path
under `assets/`. GitHub Pages now serves every image directly from the repo,
with **zero** remaining dependencies on Manus-hosted files.

- **Source host retired:** `https://files.manuscdn[.]com/user\_upload\_by\_module/session\_file/310519663401710643/` (host token defused so this report itself stays out of the zero-reference search)
- **Unique images migrated:** 18
- **New images downloaded:** 5 (1 background + 4 covers)
- **Reused existing local copies:** 13 (Domestic Helper photos — verified byte-identical via MD5 to the CDN originals, so no duplicate copies were added)

## Asset map

| # | Original Manus URL (filename) | New repository asset path | Notes |
|---|-------------------------------|---------------------------|-------|
| 1 | `…/KlxdYsobDXQekTOC.png` | `assets/backgrounds/site-portrait.png` | Site background (referenced from `gallery.css`) — new download |
| 2 | `…/yjLUpdTMxDrcHfxp.png` | `assets/covers/morning-softness.png` | Gallery/story cover — new download |
| 3 | `…/AUvEUSpKITgngsrV.png` | `assets/covers/the-green-hour.png` | Gallery/story cover — new download |
| 4 | `…/ZfqjNowUERNCvoDV.jpg` | `assets/covers/number-19.jpg` | Gallery/story cover — new download (extension preserved) |
| 5 | `…/wksapShkdqVsDvFp.png` | `assets/covers/bohemian-adventures.png` | Gallery/story cover — new download |
| 6 | `…/fYFNVUHVWfWVQthx.png` | `assets/domestic-helper/domestic-helper-01.png` | Domestic Helper 01 — reused existing (MD5-identical) |
| 7 | `…/AsFBDnbHTegVCYUH.png` | `assets/domestic-helper/domestic-helper-03.png` | Domestic Helper 03 — reused existing (MD5-identical) |
| 8 | `…/GGhlWaAMkFbzGbWn.png` | `assets/domestic-helper/domestic-helper-05.png` | Domestic Helper 05 — reused existing (MD5-identical) |
| 9 | `…/bBWgfqedHQxwBRph.png` | `assets/domestic-helper/domestic-helper-06.png` | Domestic Helper 06 — reused existing (MD5-identical) |
| 10 | `…/sMxkWJMssOaaXfne.png` | `assets/domestic-helper/domestic-helper-08.png` | Domestic Helper 08 — reused existing (MD5-identical) |
| 11 | `…/wZrKEuzEjOUJbBCi.png` | `assets/domestic-helper/domestic-helper-09.png` | Domestic Helper 09 — reused existing (MD5-identical) |
| 12 | `…/PALmeZnxUZqcJwaM.png` | `assets/domestic-helper/domestic-helper-10.png` | Domestic Helper 10 — reused existing (MD5-identical) |
| 13 | `…/IumOXVGIIISVHSuv.png` | `assets/domestic-helper/domestic-helper-11.png` | Domestic Helper 11 — reused existing (MD5-identical) |
| 14 | `…/VxcoEOpcNBIaPuww.png` | `assets/domestic-helper/domestic-helper-12.png` | Domestic Helper 12 — reused existing (MD5-identical) |
| 15 | `…/hTOCURipdZVcZFmm.png` | `assets/domestic-helper/domestic-helper-14.png` | Domestic Helper 14 — reused existing (MD5-identical) |
| 16 | `…/vkwwDGHWfyHhPyAL.png` | `assets/domestic-helper/domestic-helper-16.png` | Domestic Helper 16 — reused existing (MD5-identical) |
| 17 | `…/yZkNpVTARacNRaGs.png` | `assets/domestic-helper/domestic-helper-17.png` | Domestic Helper 17 — reused existing (MD5-identical) |
| 18 | `…/mChWOFWTbMHwrQYR.png` | `assets/domestic-helper/domestic-helper-19.png` | Domestic Helper 19 — reused existing (MD5-identical) |

> Full original prefix for every row above: `https://files.manuscdn[.]com/user\_upload\_by\_module/session\_file/310519663401710643/`

## Files updated

| File | Manus references replaced |
|------|---------------------------|
| `index.html` | 6 (background, 4 covers, Domestic Helper cover) |
| `gallery.html` | 4 (3 covers, Domestic Helper cover) |
| `stories.html` | 4 (4 covers) |
| `gallery.css` | 1 (background image) |
| `build_site_actions.py` | 1 (background image in generated-page CSS) |
| `galleries/domestic-helper.html` | 13 (all grid photos, via `../assets/…`) |

New asset files added:
- `assets/backgrounds/site-portrait.png`
- `assets/covers/morning-softness.png`
- `assets/covers/the-green-hour.png`
- `assets/covers/number-19.jpg`
- `assets/covers/bohemian-adventures.png`

## Verification

- `git grep` for the four target patterns (`files.manuscdn[.]com`, `manuscdn[.]com`,
  `user\_upload\_by\_module`, `session\_file`) across the whole repository returns
  **0 matches** — including this report, whose tokens are intentionally defused.
- All 18 migrated asset paths were confirmed to resolve to existing files on disk
  (accounting for the `../` prefix used inside `galleries/`).
- The 13 Domestic Helper images were MD5-compared against their freshly downloaded
  CDN originals and matched exactly — original quality preserved, no re-encoding.
- File extensions were preserved from the original URLs (e.g. `number-19.jpg`).

## Unresolved issues

None. Every Manus-hosted image was reachable, downloaded/verified, relocated, and
re-referenced. No broken links or missing originals were encountered.
