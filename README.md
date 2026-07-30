# MalviyaConnect

Local business directory for Malviya Nagar, New Delhi.
MK 621 Digital Marketing live project.

## What this is

A static site generator. `build.py` reads `data/shops.csv` and writes a
complete site into `dist/` — one page per business, one page per category,
plus `sitemap.xml` and `robots.txt`.

90 listings, 95 pages.

## Build it

```bash
python3 build.py
```

No dependencies. Standard library only.

Preview locally:

```bash
cd dist && python3 -m http.server 8000
```

Then open http://localhost:8000

## Deploy

Vercel serves `dist/` directly — there is no build step on their side.
So: run `build.py`, commit the updated `dist/`, push. Vercel redeploys.

```bash
python3 build.py
git add -A && git commit -m "rebuild" && git push
```

## Editing

**Add or change a business** — edit `data/shops.csv`, rebuild.

**Write real descriptions** — fill the `description` column. The build
prints how many are still empty. Templated listings are thin content;
original copy is what makes these pages worth indexing.

**Rename or add a category** — edit `CATEGORIES` at the top of `build.py`.
Changing a `slug` changes the URL, so settle slugs before submitting the
sitemap to Search Console.

**Change the live URL** — set `SITE_URL` in `build.py` after your first
deploy. It drives canonical tags and the sitemap; leaving it wrong will
break both.

## Before submitting to Search Console

1. Set `SITE_URL` to the real Vercel URL and rebuild
2. Verify the property in Google Search Console
3. Submit `sitemap.xml`
4. Run URL Inspection on one shop page, confirm Google sees the content
5. Test a shop page in Google's Rich Results Test for LocalBusiness schema

## Photos

Put shop photos in `images/` named after the slug — the last part of the
shop's URL. So the page `/food-and-cafes/rose-cafe/` takes `images/rose-cafe.jpg`.

Accepted: `.jpg` `.jpeg` `.png` `.webp`

The build prints how many photos it found. Shops without one get a
placeholder tile with their initials, so the site never looks broken.

Resize to roughly 800px wide before adding — full-size phone photos are
several MB each and will slow the site down.

**Use your own photos.** Pulling images off Google Maps or shop websites
means republishing someone else's copyrighted work. Walking the market with
a phone also gives you original content, which is what the report's content
strategy section needs.

## About page: video and market photos

The **About Malviya Nagar** tab holds your timelapse video, market photos,
and the neighbourhood write-up.

**Timelapse video.** Upload to YouTube first — never put video files in the
repo. Then copy the video ID from the URL:

    https://www.youtube.com/watch?v=dQw4w9WgXcQ
                                    ^^^^^^^^^^^ this part

Paste it into `ABOUT_VIDEO` near the top of `build.py`, rebuild. Leave it
empty and the video section simply doesn't appear.

**Market photos.** Drop them into `images/gallery/`. The filename becomes
the caption, so name them descriptively:

    main-market-at-dusk.jpg   ->  "Main market at dusk"
    khirki-extension-lane.jpg ->  "Khirki extension lane"

Resize to ~800px wide first.

**The write-up.** The "Why Malviya Nagar" paragraph is a placeholder in
italics. Replace it with your group's reasoning — it's also section 1 of
the report, so write it once and use it twice.
