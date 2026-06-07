# Simple Gallery Pipeline

This is the easy copy/paste system for adding a new photo gallery.

## The basic idea

Every gallery has three parts:

1. An image folder inside `assets/`
2. A gallery page inside `galleries/`
3. A card/link on `gallery.html` or `stories.html`

---

## Step 1 — Create the image folder

Create a new folder inside `assets/`.

Example:

```text
assets/My-New-Gallery/
```

Put your images in that folder.

Try to keep the file names simple:

```text
photo-01.jpg
photo-02.jpg
photo-03.jpg
photo-04.jpg
```

Avoid weird names when possible. Spaces and parentheses can work, but simple names are easier.

---

## Step 2 — Copy the template page

Copy this file:

```text
galleries/_template-gallery.html
```

Rename the copy.

Example:

```text
galleries/my-new-gallery.html
```

Do not edit `_template-gallery.html` directly. Keep it clean so it can be reused.

---

## Step 3 — Edit the new gallery page

Open your copied page, for example:

```text
galleries/my-new-gallery.html
```

Find this section in the script:

```js
var galleryTitle = 'GALLERY TITLE';
var assetFolder = '../assets/ASSET-FOLDER-NAME/';
var galleryMeta = 'Digital, 2026 · Full Screen Slideshow';

var filenames = [
  'photo-01.jpg',
  'photo-02.jpg',
  'photo-03.jpg'
];
```

Change it to match your gallery.

Example:

```js
var galleryTitle = 'My New Gallery';
var assetFolder = '../assets/My-New-Gallery/';
var galleryMeta = 'Digital, 2026 · Full Screen Slideshow';

var filenames = [
  'photo-01.jpg',
  'photo-02.jpg',
  'photo-03.jpg',
  'photo-04.jpg'
];
```

That is the main part. The slideshow builds itself from the filenames.

---

## Step 4 — Add a card to `gallery.html`

Use this card when adding a gallery to the main gallery page:

```html
<div class="gallery-item">
  <a href="galleries/my-new-gallery.html">
    <img src="assets/My-New-Gallery/photo-01.jpg" alt="My New Gallery">
  </a>
  <div class="gallery-caption">
    <p class="gallery-caption-title">My New Gallery</p>
    <p class="gallery-caption-meta">Digital, 2026 · Full Screen Slideshow</p>
    <p class="gallery-caption-text">A short description of this gallery goes here.</p>
    <a class="gallery-view-link" href="galleries/my-new-gallery.html">View full series →</a>
  </div>
</div>
```

Paste it inside the gallery row where you want it to appear.

---

## Step 5 — Add a card to `stories.html`

Use this card when adding a gallery-style entry to the stories page:

```html
<article class="story-card">
  <div class="story-card-img-wrap">
    <img class="story-card-img"
         src="assets/My-New-Gallery/photo-01.jpg"
         alt="My New Gallery">
  </div>
  <p class="story-card-tag">Gallery</p>
  <h2 class="story-card-title">My New Gallery</h2>
  <p class="story-card-date">June 2026</p>
  <p class="story-card-excerpt">A short description of this gallery goes here.</p>
  <a class="story-read-link" href="galleries/my-new-gallery.html">View →</a>
</article>
```

Paste it inside:

```html
<div class="stories-grid">
```

Usually you paste the newest one near the top.

---

## Fast checklist

When a gallery does not load, check these first:

- Does the folder name in `assetFolder` exactly match the folder in `assets/`?
- Do the image names in `filenames` exactly match the real files?
- Are capital letters the same? `photo.JPG` and `photo.jpg` are not always the same.
- Is the gallery page saved inside `galleries/`?
- Does the card link point to the correct file?

---

## Example finished setup

Image folder:

```text
assets/Summer-Light/
```

Gallery page:

```text
galleries/summer-light.html
```

Inside the page:

```js
var galleryTitle = 'Summer Light';
var assetFolder = '../assets/Summer-Light/';
var galleryMeta = 'Digital, 2026 · Natural Light';

var filenames = [
  'summer-01.jpg',
  'summer-02.jpg',
  'summer-03.jpg'
];
```

Card link:

```html
<a href="galleries/summer-light.html">View full series →</a>
```
