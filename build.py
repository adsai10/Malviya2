#!/usr/bin/env python3
"""
MalviyaConnect - static site generator.

Reads data/shops.csv and writes a complete, SEO-ready static site into dist/.

Run:  python3 build.py
Then: commit dist/ and push. Vercel serves it.
"""

import csv
import html
import io
import json
import mimetypes
import os
import re
import shutil
import unicodedata
import urllib.request
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------------
# CONFIG - edit this block. Everything else is machinery.
# ----------------------------------------------------------------------------

SITE_NAME = "MalviyaConnect"
SITE_TAGLINE = "Every shop and service in Malviya Nagar, in one place"
AREA = "Malviya Nagar"
CITY = "New Delhi"

# Set this to your real Vercel URL after first deploy. It drives canonical
# tags and sitemap.xml, so get it right before submitting to Search Console.
SITE_URL = "https://malviya2.vercel.app"

# CATEGORIES - the keyword research output goes HERE.
# `slug` becomes the URL, so changing it changes the URL. Decide slugs before
# you submit the sitemap to Google; changing them later means redirects.
CATEGORIES = [
    {
        "name": "Food & Cafes",
        "slug": "food-and-cafes",
        "accent": "#E39A2B",
        "tint": "#FBF1DF",
        "title": f"Restaurants, Cafes & Bakeries in {AREA}, {CITY}",
        "meta": f"Find restaurants, cafes, bakeries and sweet shops in {AREA}, {CITY}. Addresses, phone numbers and ratings for every place, updated by hand.",
        "blurb": "Bakeries that have been on the same corner for thirty years, chain outlets on the main market road, and coffee shops that opened last season.",
    },
    {
        "name": "Shopping",
        "slug": "shopping",
        "accent": "#C74B52",
        "tint": "#FAE9E9",
        "title": f"Clothing, Jewellery & Electronics Shops in {AREA}, {CITY}",
        "meta": f"Garment shops, jewellers, footwear, electronics and general stores in {AREA}, {CITY}. Full addresses, phone numbers and ratings.",
        "blurb": "The garment shops, jewellers and electrical stores that make up the bulk of the main market and the ITI lanes behind it.",
    },
    {
        "name": "Beauty & Healthcare",
        "slug": "salons-and-pharmacies",
        "accent": "#1E7F91",
        "tint": "#E3F1F3",
        "title": f"Salons, Spas & Pharmacies in {AREA}, {CITY}",
        "meta": f"Unisex salons, beauty parlours, nail studios, opticians, chemists and dental clinics in {AREA}, {CITY}. Addresses and phone numbers.",
        "blurb": "Salons and nail studios alongside the chemists, opticians and clinics that stay open when everything else on the road has shuttered.",
    },
    {
        "name": "Local Services",
        "slug": "local-services",
        "accent": "#6E8F3A",
        "tint": "#EEF3E3",
        "title": f"Dry Cleaners, Tailors & Repair Shops in {AREA}, {CITY}",
        "meta": f"Laundry and dry cleaning, tailors, print shops, mobile repair and courier services in {AREA}, {CITY}. Contact details and ratings.",
        "blurb": "The trades the neighbourhood actually runs on: laundries, tailors, print shops, mobile repair and the key maker outside the market.",
    },
]

# ABOUT PAGE
# Paste the YouTube video ID between the quotes to show your timelapse.
# From https://www.youtube.com/watch?v=dQw4w9WgXcQ  the ID is  dQw4w9WgXcQ
# Leave it empty and the video section simply won't appear.
ABOUT_VIDEO = ""
ABOUT_VIDEO_CAPTION = "A morning walk through the main market, filmed in July 2026."

# HOMEPAGE HERO
# Same idea as ABOUT_VIDEO above - paste a YouTube video ID to show a short
# clip in the hero, next to the headline. Leave it empty and the hero just
# stays text-only (today's layout).
HERO_VIDEO = "0mNoliWVk4M"
HERO_VIDEO_CAPTION = f"A quick look at {AREA}."

# Market photos go in images/gallery/ - any .jpg/.png/.webp is picked up.
# The filename becomes the caption, so name them properly:
#   main-market-at-dusk.jpg  ->  "Main market at dusk"
GALLERY = Path("images/gallery")

# BLOGS & EVENTS
# Blog posts: data/blog_posts.csv - columns are title, date (YYYY-MM-DD),
# author, excerpt, body (and optionally image_url). Write the body as one
# paragraph per line in the cell - Alt+Enter between paragraphs in Excel or
# Google Sheets - and each line becomes its own <p> automatically.
# Cover photos also work the local-file way, same as shops:
#   images/blog/<slug-of-the-title>.jpg
#
# Events: data/events.csv - columns are title, date (YYYY-MM-DD), time,
# location, description, link. Anything dated today or later shows up under
# "Upcoming events", soonest first - past events drop off the page on their
# own, no manual cleanup needed.
BLOG_SLUG = "blog-events"
BLOG_DATA = Path("data/blog_posts.csv")
EVENTS_DATA = Path("data/events.csv")
BLOG_IMAGES = Path("images/blog")

OUT = Path("dist")
DATA = Path("data/shops.csv")
ASSETS = Path("assets")
IMAGES = Path("images")

# Drop shop photos into images/ named after the slug, e.g. images/rose-cafe.jpg
# The build finds them automatically. Missing photos get a designed placeholder.
#
# For any shop with no local file, the build tries two fallbacks, in order:
#   1. Google Places Photos, using the `placeId` column your CSV already has -
#      this is the actual photo Google shows for that exact listing on Maps.
#      Requires a Google Maps Platform API key with the Places API (New)
#      enabled, set as an environment variable before you run the build:
#         export GOOGLE_PLACES_API_KEY="your-key-here"
#      Leave it unset and this step is simply skipped.
#   2. A URL in an `image_url` column in shops.csv, if you've filled one in.
# Either way, once a photo is downloaded it's a normal local file - re-running
# the build won't re-fetch or re-download it unless you delete it.
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp")
GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()

# ----------------------------------------------------------------------------
# HELPERS
# ----------------------------------------------------------------------------


def read_csv_rows(path: Path):
    """Read a CSV into a list of dict rows, tolerant of whatever encoding
    Excel actually saved it in. Excel's plain "CSV (Comma delimited)" option
    on Windows writes Windows-1252, not UTF-8 - so an accented character
    (cafe with an accent, a curly "smart quote" from autocorrect, etc.) can
    otherwise crash the build with a UnicodeDecodeError. This tries UTF-8
    first (the correct, portable choice) and quietly falls back if needed."""
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("utf-8", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def slugify(text: str) -> str:
    """Turn a shop name into a clean, URL-safe slug."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-{2,}", "-", text).strip("-") or "shop"


def esc(text) -> str:
    """Escape text for safe insertion into HTML."""
    return html.escape(str(text or ""), quote=True)


def truncate(text: str, limit: int = 155) -> str:
    """Trim a meta description to a sensible length on a word boundary."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",.;:") + "..."


def paragraphs_html(text: str) -> str:
    """Turn a blog post body into <p> tags. Each non-blank line in the
    source CSV cell becomes one paragraph - so in Excel/Sheets, paragraphs
    are just separate lines within the cell (Alt+Enter between them)."""
    lines = [ln.strip() for ln in re.split(r"\r\n|\r|\n", text or "")]
    return "".join(f"<p>{esc(ln)}</p>" for ln in lines if ln)


def find_image_in(folder: Path, slug: str):
    """Return the filename of a photo for this slug inside `folder`, or None."""
    for ext in IMAGE_EXT:
        if (folder / f"{slug}{ext}").exists():
            return f"{slug}{ext}"
    return None


def find_image(slug: str):
    """Return the filename of a shop photo for this slug, or None."""
    return find_image_in(IMAGES, slug)


def download_image_to(folder: Path, url: str, slug: str):
    """Download url into folder/<slug>.<ext>. Returns the filename, or None
    on failure (a missing/broken URL just falls back to the placeholder tile,
    it never stops the build)."""
    url = (url or "").strip()
    if not url:
        return None

    existing = find_image_in(folder, slug)
    if existing:  # already downloaded (or hand-placed) - don't re-fetch
        return existing

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "Mozilla/5.0 (compatible; MalviyaConnectBot/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except Exception as e:
        print(f"  ! Could not download image for '{slug}': {e}")
        return None

    # Prefer the extension in the URL itself; fall back to sniffing Content-Type.
    ext = Path(url.split("?")[0]).suffix.lower()
    if ext not in IMAGE_EXT:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".jpg"
        ext = ".jpg" if ext == ".jpe" else ext
        if ext not in IMAGE_EXT:
            ext = ".jpg"

    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{slug}{ext}"
    dest.write_bytes(data)
    print(f"  + downloaded {dest.name}")
    return dest.name


def download_image(url: str, slug: str):
    """Download a shop photo url into images/<slug>.<ext>."""
    return download_image_to(IMAGES, url, slug)


def fetch_place_photo(place_id: str, slug: str):
    """Fetch the photo Google has on file for this exact business (via its
    Places `placeId`) and save it into images/<slug>.<ext>. Returns the
    filename, or None if there's no API key, no placeId, no photo on file,
    or the request fails - any of which just falls back to image_url or the
    placeholder tile, never stops the build."""
    place_id = (place_id or "").strip()
    if not place_id or not GOOGLE_PLACES_API_KEY:
        return None

    existing = find_image(slug)
    if existing:
        return existing

    # Step 1: ask Place Details (New) for this place's photo list. Field mask
    # is restricted to "photos" alone to stay on the cheapest applicable SKU.
    details_req = urllib.request.Request(
        f"https://places.googleapis.com/v1/places/{place_id}",
        headers={
            "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
            "X-Goog-FieldMask": "photos",
        },
    )
    try:
        with urllib.request.urlopen(details_req, timeout=15) as resp:
            details = json.loads(resp.read())
    except Exception as e:
        print(f"  ! Places lookup failed for '{slug}': {e}")
        return None

    photos = details.get("photos") or []
    if not photos:
        return None

    # Step 2: resolve that photo resource to actual image bytes.
    photo_name = photos[0]["name"]  # "places/{place_id}/photos/{photo_ref}"
    media_url = (
        f"https://places.googleapis.com/v1/{photo_name}/media"
        f"?maxWidthPx=800&key={GOOGLE_PLACES_API_KEY}"
    )
    try:
        with urllib.request.urlopen(media_url, timeout=15) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "")
    except Exception as e:
        print(f"  ! Places photo download failed for '{slug}': {e}")
        return None

    ext = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".jpg"
    ext = ".jpg" if ext in (".jpe", ".jfif") else ext
    if ext not in IMAGE_EXT:
        ext = ".jpg"

    IMAGES.mkdir(parents=True, exist_ok=True)
    dest = IMAGES / f"{slug}{ext}"
    dest.write_bytes(data)
    print(f"  + fetched {dest.name} from Google Places")
    return dest.name


def initials(title: str) -> str:
    """Two-letter monogram for the placeholder tile."""
    words = [w for w in re.split(r"[^A-Za-z]+", title) if w]
    if not words:
        return "MN"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def photo_block(shop, root: str, klass: str) -> str:
    """Render a photo, or a placeholder tile keyed to the shop name."""
    if shop["image"]:
        return (
            f'<img class="{klass}" src="{root}img/{esc(shop["image"])}" '
            f'alt="{esc(shop["title"])} in {esc(AREA)}" loading="lazy" decoding="async">'
        )
    cat = shop["category"]
    tone = sum(ord(c) for c in shop["slug"]) % 3
    return (
        f'<div class="{klass} ph ph-{tone}" aria-hidden="true" '
        f'style="--a:{cat["accent"]};--t:{cat["tint"]}">'
        f'<span>{esc(initials(shop["title"]))}</span></div>'
    )


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ----------------------------------------------------------------------------
# LOAD
# ----------------------------------------------------------------------------


def load_shops():
    cat_by_name = {c["name"]: c for c in CATEGORIES}
    shops, skipped, seen = [], [], set()

    for row in read_csv_rows(DATA):
        title = (row.get("title") or "").strip()
        cat_name = (row.get("Category") or "").strip()

        if not title or cat_name not in cat_by_name:
            skipped.append(title or "(untitled row)")
            continue

        slug = slugify(title)
        while slug in seen:  # guarantee unique URLs
            slug += "-2"
        seen.add(slug)

        try:
            rating = float(row.get("totalScore") or 0)
        except ValueError:
            rating = 0.0
        try:
            reviews = int(float(row.get("reviewsCount") or 0))
        except ValueError:
            reviews = 0

        shops.append(
            {
                "title": title,
                "slug": slug,
                "category": cat_by_name[cat_name],
                "type": (row.get("categoryName") or "").strip(),
                "address": (row.get("address") or "").strip(),
                "phone": (row.get("phone") or "").strip(),
                "phone_raw": (row.get("phoneUnformatted") or "").strip(),
                "website": (row.get("website") or "").strip(),
                "rating": rating,
                "reviews": reviews,
                "maps": (row.get("url") or "").strip(),
                "postcode": (row.get("postalCode") or "110017").strip(),
                # Your own writing goes in the CSV's `description` column.
                "blurb": (row.get("description") or "").strip(),
                "image": find_image(slug)
                or fetch_place_photo((row.get("placeId") or "").strip(), slug)
                or download_image(row.get("image_url"), slug),
            }
        )

    return shops, skipped


def load_blog_posts():
    """Read data/blog_posts.csv into a list of post dicts, newest first.
    Missing file or empty rows just mean no posts - never an error."""
    posts, seen = [], set()
    if not BLOG_DATA.exists():
        return posts

    for row in read_csv_rows(BLOG_DATA):
        title = (row.get("title") or "").strip()
        if not title:
            continue

        slug = slugify(title)
        while slug in seen:
            slug += "-2"
        seen.add(slug)

        try:
            date = datetime.strptime((row.get("date") or "").strip(), "%Y-%m-%d").date()
        except ValueError:
            date = datetime.today().date()

        posts.append(
            {
                "title": title,
                "slug": slug,
                "date": date,
                "date_display": date.strftime("%d %b %Y"),
                "author": (row.get("author") or "").strip(),
                "excerpt": (row.get("excerpt") or "").strip(),
                "body_html": paragraphs_html(row.get("body")),
                "image": find_image_in(BLOG_IMAGES, slug)
                or download_image_to(BLOG_IMAGES, row.get("image_url"), slug),
            }
        )

    posts.sort(key=lambda p: p["date"], reverse=True)
    return posts


def load_events():
    """Read data/events.csv into a list of upcoming event dicts, soonest
    first. Events dated before today are dropped automatically - no manual
    cleanup needed. Missing file just means no events, never an error."""
    events = []
    if not EVENTS_DATA.exists():
        return events

    today = datetime.today().date()
    for row in read_csv_rows(EVENTS_DATA):
        title = (row.get("title") or "").strip()
        if not title:
            continue
        try:
            date = datetime.strptime((row.get("date") or "").strip(), "%Y-%m-%d").date()
        except ValueError:
            continue  # no usable date - can't judge "upcoming", so skip it
        if date < today:
            continue

        events.append(
            {
                "title": title,
                "date": date,
                "day": date.strftime("%d"),
                "mon": date.strftime("%b").upper(),
                "date_display": date.strftime("%A, %d %b %Y"),
                "time": (row.get("time") or "").strip(),
                "location": (row.get("location") or "").strip(),
                "description": (row.get("description") or "").strip(),
                "link": (row.get("link") or "").strip(),
            }
        )

    events.sort(key=lambda e: e["date"])
    return events


# ----------------------------------------------------------------------------
# TEMPLATES
# ----------------------------------------------------------------------------


def page(*, title, meta, canonical, body, schema=None, depth=1, image=None):
    """Wrap body content in the site shell. `depth` sets relative asset paths."""
    root = "../" * depth if depth else ""
    schema_tag = ""
    if schema:
        schema_tag = (
            '<script type="application/ld+json">'
            + json.dumps(schema, ensure_ascii=False)
            + "</script>"
        )

    og_image = (
        f'\n<meta property="og:image" content="{SITE_URL}/img/{image}">' if image else ""
    )

    nav = "".join(
        f'<a href="{root}{c["slug"]}/">{esc(c["name"])}</a>' for c in CATEGORIES
    )
    nav += f'<a href="{root}{BLOG_SLUG}/">Blogs &amp; Events</a>'
    nav += f'<a class="nav-about" href="{root}about-malviya-nagar/">About {esc(AREA)}</a>' 

    return f"""<!DOCTYPE html>
<html lang="en-IN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(meta)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(meta)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{esc(SITE_NAME)}">
<meta name="twitter:card" content="summary_large_image">{og_image}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anek+Latin:wdth,wght@75..100,400..800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{root}style.css">
{schema_tag}
</head>
<body>
<header class="masthead">
  <div class="wrap masthead-inner">
    <a class="wordmark" href="{root}">
      <span class="wordmark-name">{esc(SITE_NAME)}</span>
      <span class="wordmark-sub">{esc(AREA)} &middot; {esc(CITY)}</span>
    </a>
    <nav class="nav">{nav}</nav>
  </div>
</header>
<main>
{body}
</main>
<footer class="footer">
  <div class="wrap">
    <p class="footer-note">{esc(SITE_NAME)} is a student-built directory of independent
    businesses in {esc(AREA)}, {esc(CITY)}. Listings are compiled from public sources and
    verified by hand. We are not affiliated with any business listed.</p>
    <p class="footer-meta">MK 621 Digital Marketing live project</p>
  </div>
</footer>
</body>
</html>"""


def rating_plate(shop):
    if not shop["rating"]:
        return ""
    return (
        f'<span class="plate" style="--a:{shop["category"]["accent"]}">'
        f'<b>{shop["rating"]:.1f}</b>'
        f'<span class="plate-count">{shop["reviews"]} reviews</span></span>'
    )


def shop_card(shop, root=""):
    href = f"{shop['slug']}/"
    a = shop["category"]["accent"]
    hay = f"{shop['title']} {shop['type']} {shop['address']}".lower()
    return f"""<li class="card" style="--a:{a}" data-search="{esc(hay)}">
  <a class="card-photo-link" href="{href}" tabindex="-1" aria-hidden="true">
    {photo_block(shop, root, "card-photo")}
  </a>
  <div class="card-body">
    <h3 class="card-name">{esc(shop['title'])}</h3>
    <p class="card-type">{esc(shop['type'])}</p>
    <div class="card-meta">
      {rating_plate(shop)}
      <span class="card-addr">{esc(truncate(shop['address'], 60))}</span>
    </div>
    <a class="card-more" href="{href}">Show more details
      <span aria-hidden="true">&rarr;</span></a>
  </div>
</li>"""


def blog_card(post, root=""):
    href = f"{post['slug']}/"
    img_html = (
        f'<img class="blog-card-photo" src="{root}img/blog/{esc(post["image"])}" '
        f'alt="{esc(post["title"])}" loading="lazy" decoding="async">'
        if post["image"] else ""
    )
    meta = esc(post["date_display"])
    if post["author"]:
        meta += f" &middot; {esc(post['author'])}"
    return f"""<li class="blog-card">
  <a class="blog-card-photo-link" href="{href}" tabindex="-1" aria-hidden="true">{img_html}</a>
  <div class="blog-card-body">
    <p class="blog-card-date">{meta}</p>
    <h3 class="blog-card-title"><a href="{href}">{esc(post['title'])}</a></h3>
    <p class="blog-card-excerpt">{esc(truncate(post['excerpt'], 140))}</p>
    <a class="blog-card-more" href="{href}">Read more <span aria-hidden="true">&rarr;</span></a>
  </div>
</li>"""


def event_row(ev):
    link_html = ""
    if ev["link"]:
        link_html = (
            f'<a class="event-link" href="{esc(ev["link"])}" rel="nofollow noopener" '
            f'target="_blank">More info <span aria-hidden="true">&rarr;</span></a>'
        )
    meta = " &middot; ".join(esc(b) for b in (ev["time"], ev["location"]) if b)
    return f"""<li class="event-row">
  <div class="event-date"><span class="day">{esc(ev['day'])}</span><span class="mon">{esc(ev['mon'])}</span></div>
  <div class="event-body">
    <h3 class="event-title">{esc(ev['title'])}</h3>
    <p class="event-meta">{meta}</p>
    <p class="event-desc">{esc(ev['description'])}</p>
    {link_html}
  </div>
</li>"""


# ----------------------------------------------------------------------------
# PAGE BUILDERS
# ----------------------------------------------------------------------------


def build_home(shops):
    tiles = ""
    for cat in CATEGORIES:
        members = [s for s in shops if s["category"] is cat]
        tiles += f"""<a class="tile" href="{cat['slug']}/" style="--a:{cat['accent']};--t:{cat['tint']}">
      <span class="tile-top">
        <span class="tile-count">{len(members)}</span>
        <span class="tile-label">listings</span>
      </span>
      <span class="tile-name">{esc(cat['name'])}</span>
      <span class="tile-blurb">{esc(cat['blurb'])}</span>
      <span class="tile-go">Browse <span aria-hidden="true">&rarr;</span></span>
    </a>"""

    top = sorted(shops, key=lambda s: (s["rating"], s["reviews"]), reverse=True)[:6]
    top_html = "".join(
        f'<li style="--a:{s["category"]["accent"]}">'
        f'<a href="{s["category"]["slug"]}/{s["slug"]}/">{esc(s["title"])}</a>'
        f'<span class="tl-type">{esc(s["type"])}</span>'
        f'<span class="tl-rate">{s["rating"]:.1f}</span></li>'
        for s in top
    )

    # ticker: real shop names, doubled so the loop is seamless
    names = [s["title"] for s in sorted(shops, key=lambda x: -x["reviews"])[:26]]
    strip = "".join(
        f'<span class="tick">{esc(n)}</span><span class="tick-dot" aria-hidden="true">&bull;</span>'
        for n in names
    )

    hero_video = ""
    hero_class = "hero-inner"
    if HERO_VIDEO.strip():
        hero_class += " hero-inner--split"
        hero_video = f"""<div class="hero-video">
      <iframe src="https://www.youtube-nocookie.com/embed/{esc(HERO_VIDEO.strip())}"
        title="{esc(HERO_VIDEO_CAPTION)}" loading="lazy" allowfullscreen
        allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
        referrerpolicy="strict-origin-when-cross-origin"></iframe>
    </div>"""

    body = f"""<section class="hero">
  <div class="hero-glow" aria-hidden="true"></div>
  <div class="wrap {hero_class}">
    <div class="hero-copy">
      <p class="eyebrow">{len(shops)} businesses &middot; {len(CATEGORIES)} categories &middot; {esc(AREA)}</p>
      <h1 class="hero-title">{esc(SITE_TAGLINE)}</h1>
      <p class="hero-lede">A working directory of the shops, salons, laundries and
      kitchens between the main market and Khirki Extension. Addresses, phone
      numbers and directions, checked by hand rather than scraped and forgotten.</p>
      <div class="hero-cta">
        <a class="btn" href="#browse">Browse the directory</a>
        <span class="hero-note">No sign-up. No app. Just the list.</span>
      </div>
    </div>
    {hero_video}
  </div>
  <div class="ticker" aria-hidden="true"><div class="ticker-run">{strip}{strip}</div></div>
</section>

<section class="wrap section" id="browse">
  <h2 class="section-head">Browse by category</h2>
  <div class="tiles">{tiles}</div>
</section>

<section class="wrap section">
  <h2 class="section-head">Highest rated right now</h2>
  <ol class="toplist">{top_html}</ol>
</section>"""

    schema = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": SITE_URL,
        "description": SITE_TAGLINE,
    }

    write(
        OUT / "index.html",
        page(
            title=f"{SITE_NAME} - Local Business Directory for {AREA}, {CITY}",
            meta=f"Directory of {len(shops)} shops, restaurants, salons and services in {AREA}, {CITY}. Addresses, phone numbers and ratings for every listing.",
            canonical=f"{SITE_URL}/",
            body=body,
            schema=schema,
            depth=0,
        ),
    )


def build_category(cat, shops):
    members = sorted(
        [s for s in shops if s["category"] is cat],
        key=lambda s: (-s["rating"], s["title"]),
    )
    cards = "".join(shop_card(s, root="../") for s in members)

    body = f"""<section class="band" style="--a:{cat['accent']};--t:{cat['tint']}">
  <div class="wrap">
    <nav class="crumbs"><a href="../">Home</a> <span>/</span> {esc(cat['name'])}</nav>
    <p class="eyebrow">{len(members)} listings in {esc(AREA)}</p>
    <h1 class="page-title">{esc(cat['title'])}</h1>
    <p class="lede">{esc(cat['blurb'])}</p>
  </div>
</section>
<section class="wrap section">
  <div class="searchbar">
    <input type="search" id="q" class="search-input"
           placeholder="Filter by name, type or street&hellip;"
           aria-label="Filter {esc(cat['name'])} listings" autocomplete="off">
    <p class="search-count" id="count" role="status">{len(members)} shown</p>
  </div>
  <ul class="cards" id="grid">{cards}</ul>
  <p class="empty" id="empty" hidden>Nothing matches that. Try a shorter word.</p>
</section>
<script>
(function () {{
  var q = document.getElementById('q'),
      grid = document.getElementById('grid'),
      count = document.getElementById('count'),
      empty = document.getElementById('empty'),
      cards = Array.prototype.slice.call(grid.children);
  function run() {{
    var t = q.value.trim().toLowerCase(), n = 0;
    cards.forEach(function (c) {{
      var hit = !t || c.dataset.search.indexOf(t) > -1;
      c.hidden = !hit;
      if (hit) n++;
    }});
    count.textContent = n + ' shown';
    empty.hidden = n > 0;
  }}
  q.addEventListener('input', run);
}})();
</script>"""

    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": cat["title"],
        "description": cat["meta"],
        "url": f"{SITE_URL}/{cat['slug']}/",
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(members),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i,
                    "name": s["title"],
                    "url": f"{SITE_URL}/{cat['slug']}/{s['slug']}/",
                }
                for i, s in enumerate(members, 1)
            ],
        },
    }

    write(
        OUT / cat["slug"] / "index.html",
        page(
            title=f"{cat['title']} | {SITE_NAME}",
            meta=cat["meta"],
            canonical=f"{SITE_URL}/{cat['slug']}/",
            body=body,
            schema=schema,
            depth=1,
        ),
    )
    return members


def build_shop(shop, siblings):
    cat = shop["category"]
    url = f"{SITE_URL}/{cat['slug']}/{shop['slug']}/"

    # Internal linking: point at the next few shops in the same category.
    idx = siblings.index(shop)
    nearby = (siblings[idx + 1 :] + siblings[:idx])[:4]
    nearby_html = "".join(
        f'<li><a href="../{s["slug"]}/">{esc(s["title"])}</a>'
        f'<span>{esc(s["type"])}</span></li>'
        for s in nearby
    )

    rows = ""
    if shop["address"]:
        rows += f'<div class="row"><dt>Address</dt><dd>{esc(shop["address"])}</dd></div>'
    if shop["phone"]:
        tel = re.sub(r"[^\d+]", "", shop["phone_raw"] or shop["phone"])
        rows += f'<div class="row"><dt>Phone</dt><dd><a href="tel:{esc(tel)}">{esc(shop["phone"])}</a></dd></div>'
    if shop["website"]:
        rows += f'<div class="row"><dt>Website</dt><dd><a href="{esc(shop["website"])}" rel="nofollow noopener" target="_blank">Visit site</a></dd></div>'
    if shop["maps"]:
        rows += f'<div class="row"><dt>Map</dt><dd><a href="{esc(shop["maps"])}" rel="nofollow noopener" target="_blank">Open in Google Maps</a></dd></div>'

    # Fall back to a factual line when nobody has written copy yet.
    if shop["blurb"]:
        intro = esc(shop["blurb"])
    else:
        rate = (
            f" It holds a {shop['rating']:.1f} rating across {shop['reviews']} Google reviews."
            if shop["rating"]
            else ""
        )
        intro = (
            f"{esc(shop['title'])} is a {esc(shop['type'].lower() or 'business')} in "
            f"{esc(AREA)}, {esc(CITY)}.{rate}"
        )

    body = f"""<section class="band" style="--a:{cat['accent']};--t:{cat['tint']}">
  <div class="wrap">
    <nav class="crumbs">
      <a href="../../">Home</a> <span>/</span>
      <a href="../">{esc(cat['name'])}</a> <span>/</span> {esc(shop['title'])}
    </nav>
    <p class="eyebrow">{esc(shop['type'])}</p>
    <h1 class="page-title">{esc(shop['title'])}</h1>
    {rating_plate(shop)}
  </div>
</section>
<article class="wrap section shop" style="--a:{cat['accent']}">
  {photo_block(shop, "../../", "shop-photo")}
  <p class="lede">{intro}</p>

  <h2 class="section-head">Contact and location</h2>
  <dl class="rows">{rows}</dl>

  <h2 class="section-head">More {esc(cat['name'].lower())} nearby</h2>
  <ol class="toplist">{nearby_html}</ol>
</article>"""

    schema = {
        "@context": "https://schema.org",
        "@type": "LocalBusiness",
        "name": shop["title"],
        "url": url,
        "address": {
            "@type": "PostalAddress",
            "streetAddress": shop["address"],
            "addressLocality": AREA,
            "addressRegion": "Delhi",
            "postalCode": shop["postcode"],
            "addressCountry": "IN",
        },
    }
    if shop["phone"]:
        schema["telephone"] = shop["phone"]
    if shop["image"]:
        schema["image"] = f"{SITE_URL}/img/{shop['image']}"
    if shop["rating"] and shop["reviews"]:
        schema["aggregateRating"] = {
            "@type": "AggregateRating",
            "ratingValue": round(shop["rating"], 1),
            "reviewCount": shop["reviews"],
        }

    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": f"{SITE_URL}/"},
            {
                "@type": "ListItem",
                "position": 2,
                "name": cat["name"],
                "item": f"{SITE_URL}/{cat['slug']}/",
            },
            {"@type": "ListItem", "position": 3, "name": shop["title"], "item": url},
        ],
    }

    meta = truncate(
        shop["blurb"]
        or f"{shop['title']} - {shop['type']} in {AREA}, {CITY}. "
        f"{shop['address']}. Phone number, rating and directions."
    )

    write(
        OUT / cat["slug"] / shop["slug"] / "index.html",
        page(
            title=f"{shop['title']} - {shop['type']} in {AREA} | {SITE_NAME}",
            meta=meta,
            canonical=url,
            body=body,
            schema=[schema, breadcrumb],
            depth=2,
            image=shop["image"],
        ),
    )


def build_about(shops):
    """The About page: timelapse video + market photo gallery + neighbourhood copy.

    This page is also section 1 of the report (Neighbourhood Overview), so the
    prose below is worth writing properly rather than leaving as-is.
    """
    # --- video ---
    video = ""
    if ABOUT_VIDEO.strip():
        vid = ABOUT_VIDEO.strip()
        video = f"""<h2 class="section-head">The market, start to finish</h2>
  <div class="video">
    <iframe src="https://www.youtube-nocookie.com/embed/{esc(vid)}"
      title="Timelapse of {esc(AREA)} market" loading="lazy" allowfullscreen
      allow="accelerometer; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
      referrerpolicy="strict-origin-when-cross-origin"></iframe>
  </div>
  <p class="caption">{esc(ABOUT_VIDEO_CAPTION)}</p>"""

    # --- gallery ---
    shots = []
    if GALLERY.exists():
        shots = sorted(
            f for f in GALLERY.iterdir()
            if f.suffix.lower() in IMAGE_EXT and not f.name.startswith(".")
        )

    if shots:
        figs = ""
        for f in shots:
            cap = f.stem.replace("-", " ").replace("_", " ").strip().capitalize()
            figs += (
                f'<figure class="shot">'
                f'<img src="../img/gallery/{esc(f.name)}" alt="{esc(cap)}, {esc(AREA)}"'
                f' loading="lazy" decoding="async">'
                f'<figcaption>{esc(cap)}</figcaption></figure>'
            )
        gallery = f"""<h2 class="section-head">The market, photographed</h2>
  <div class="shots">{figs}</div>"""
    else:
        gallery = """<h2 class="section-head">The market, photographed</h2>
  <p class="lede">Photographs go in <code>images/gallery/</code>. Name each file
  after what it shows &mdash; <code>main-market-at-dusk.jpg</code> &mdash; and the
  caption writes itself.</p>"""

    counts = ", ".join(
        f"{len([s for s in shops if s['category'] is c])} {c['name'].lower()}"
        for c in CATEGORIES
    )

    body = f"""<section class="band" style="--a:#1E7F91;--t:#E3F1F3">
  <div class="wrap">
    <nav class="crumbs"><a href="../">Home</a> <span>/</span> About {esc(AREA)}</nav>
    <p class="eyebrow">Neighbourhood profile</p>
    <h1 class="page-title">About {esc(AREA)}</h1>
    <p class="lede">A dense South Delhi neighbourhood where a planned DDA colony,
    an old village settlement and one of the city&rsquo;s busiest market roads sit
    within a few hundred metres of each other.</p>
  </div>
</section>

<article class="wrap section prose">
  <h2 class="section-head">What this directory covers</h2>
  <p>{esc(SITE_NAME)} lists {len(shops)} businesses across {esc(AREA)} and the lanes
  around it &mdash; the main market, the ITI road, Khirki Extension and Shivalik.
  The split is {esc(counts)}.</p>
  <p>Every entry was checked by hand: address, phone number and category confirmed
  rather than taken on trust from a scrape. Where a listing looked stale or the
  business had moved, it was dropped.</p>

  <h2 class="section-head">Why {esc(AREA)}</h2>
  <p><em>Replace this paragraph with your group&rsquo;s reasoning &mdash; why you
  picked this neighbourhood, what its service ecosystem looks like, and which gaps
  you found in how it is currently covered online. This is section 1 of the report,
  so it is worth writing once and using twice.</em></p>

  {video}

  {gallery}
</article>"""

    schema = {
        "@context": "https://schema.org",
        "@type": "AboutPage",
        "name": f"About {AREA}",
        "url": f"{SITE_URL}/about-malviya-nagar/",
        "description": f"Neighbourhood profile of {AREA}, {CITY}, and what this directory covers.",
    }

    write(
        OUT / "about-malviya-nagar" / "index.html",
        page(
            title=f"About {AREA}, {CITY} - Neighbourhood Guide | {SITE_NAME}",
            meta=f"A guide to {AREA}, {CITY}: the markets, the streets and the {len(shops)} local businesses listed in this directory. Photos and video from the market.",
            canonical=f"{SITE_URL}/about-malviya-nagar/",
            body=body,
            schema=schema,
            depth=1,
        ),
    )


def build_blog_events(posts, events):
    """The Blogs & Events landing page: recent posts + upcoming events."""
    if posts:
        posts_html = f'<ul class="blog-cards">{"".join(blog_card(p) for p in posts)}</ul>'
    else:
        posts_html = """<p class="lede">No posts yet. Add rows to <code>data/blog_posts.csv</code>
    &mdash; title, date, author, excerpt and body &mdash; and each one gets its own page here.</p>"""

    if events:
        events_html = f'<ul class="events-list">{"".join(event_row(e) for e in events)}</ul>'
    else:
        events_html = """<p class="lede">No upcoming events right now. Add rows to
    <code>data/events.csv</code> and anything dated today or later shows up here automatically
    &mdash; past events drop off on their own.</p>"""

    body = f"""<section class="band" style="--a:#C74B52;--t:#FAE9E9">
  <div class="wrap">
    <nav class="crumbs"><a href="../">Home</a> <span>/</span> Blogs &amp; Events</nav>
    <p class="eyebrow">From the desk of {esc(SITE_NAME)}</p>
    <h1 class="page-title">Blogs &amp; Upcoming Events</h1>
    <p class="lede">Notes on the neighbourhood, and what&rsquo;s happening in {esc(AREA)} next.</p>
  </div>
</section>

<section class="wrap section">
  <h2 class="section-head">From the blog</h2>
  {posts_html}
</section>

<section class="wrap section">
  <h2 class="section-head">Upcoming events</h2>
  {events_html}
</section>"""

    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Blogs & Upcoming Events",
        "url": f"{SITE_URL}/{BLOG_SLUG}/",
        "description": f"Blog posts and upcoming events in {AREA}, {CITY}.",
    }

    write(
        OUT / BLOG_SLUG / "index.html",
        page(
            title=f"Blogs & Upcoming Events in {AREA} | {SITE_NAME}",
            meta=f"Neighbourhood blog posts and upcoming local events in {AREA}, {CITY}.",
            canonical=f"{SITE_URL}/{BLOG_SLUG}/",
            body=body,
            schema=schema,
            depth=1,
        ),
    )


def build_blog_post(post, posts):
    """One blog post's own page, plus a 'more from the blog' list."""
    url = f"{SITE_URL}/{BLOG_SLUG}/{post['slug']}/"

    idx = posts.index(post)
    more = (posts[idx + 1 :] + posts[:idx])[:4]
    more_html = "".join(
        f'<li><a href="../{p["slug"]}/">{esc(p["title"])}</a>'
        f'<span>{esc(p["date_display"])}</span></li>'
        for p in more
    )

    cover = ""
    if post["image"]:
        cover = (
            f'<img class="article-cover" src="../../img/blog/{esc(post["image"])}" '
            f'alt="{esc(post["title"])}" loading="lazy" decoding="async">'
        )

    meta_line = esc(post["date_display"])
    if post["author"]:
        meta_line += f" &middot; {esc(post['author'])}"

    body = f"""<section class="band" style="--a:#C74B52;--t:#FAE9E9">
  <div class="wrap">
    <nav class="crumbs">
      <a href="../../">Home</a> <span>/</span>
      <a href="../">Blogs &amp; Events</a> <span>/</span> {esc(post['title'])}
    </nav>
    <p class="eyebrow">Blog</p>
    <h1 class="page-title">{esc(post['title'])}</h1>
    <p class="article-meta">{meta_line}</p>
  </div>
</section>
<article class="wrap section prose">
  {cover}
  {post['body_html'] or f'<p>{esc(post["excerpt"])}</p>'}

  <h2 class="section-head">More from the blog</h2>
  <ol class="toplist">{more_html}</ol>
</article>"""

    schema = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post["title"],
        "datePublished": post["date"].isoformat(),
        "url": url,
        "author": {"@type": "Person", "name": post["author"] or SITE_NAME},
    }
    if post["image"]:
        schema["image"] = f"{SITE_URL}/img/blog/{post['image']}"

    write(
        OUT / BLOG_SLUG / post["slug"] / "index.html",
        page(
            title=f"{post['title']} | {SITE_NAME} Blog",
            meta=truncate(post["excerpt"] or post["title"]),
            canonical=url,
            body=body,
            schema=schema,
            depth=2,
            image=(f"blog/{post['image']}" if post["image"] else None),
        ),
    )


def build_sitemap(shops, posts):
    urls = [f"{SITE_URL}/", f"{SITE_URL}/about-malviya-nagar/", f"{SITE_URL}/{BLOG_SLUG}/"]
    urls += [f"{SITE_URL}/{c['slug']}/" for c in CATEGORIES]
    urls += [f"{SITE_URL}/{s['category']['slug']}/{s['slug']}/" for s in shops]
    urls += [f"{SITE_URL}/{BLOG_SLUG}/{p['slug']}/" for p in posts]

    entries = "".join(f"\n  <url><loc>{u}</loc></url>" for u in urls)
    write(
        OUT / "sitemap.xml",
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{entries}\n</urlset>\n",
    )
    write(
        OUT / "robots.txt",
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n",
    )
    return len(urls)


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    shops, skipped = load_shops()
    if not shops:
        raise SystemExit("No shops loaded - check data/shops.csv has a Category column.")
    posts = load_blog_posts()
    events = load_events()

    build_home(shops)
    build_about(shops)
    for cat in CATEGORIES:
        members = build_category(cat, shops)
        for shop in members:
            build_shop(shop, members)

    build_blog_events(posts, events)
    for post in posts:
        build_blog_post(post, posts)

    total_urls = build_sitemap(shops, posts)
    shutil.copy(ASSETS / "style.css", OUT / "style.css")
    if IMAGES.exists() and any(IMAGES.rglob("*")):
        shutil.copytree(IMAGES, OUT / "img", dirs_exist_ok=True)

    missing = [s["title"] for s in shops if not s["blurb"]]
    no_photo = [s for s in shops if not s["image"]]

    print(f"Built {total_urls} pages into {OUT}/")
    for cat in CATEGORIES:
        n = len([s for s in shops if s["category"] is cat])
        print(f"  {cat['name']:<22} {n:>3}  ->  /{cat['slug']}/")
    print(f"  {'Blogs & Events':<22} {len(posts):>3}  ->  /{BLOG_SLUG}/")
    print(f"\nPhotos: {len(shops) - len(no_photo)} of {len(shops)} listings have one.")
    if no_photo:
        print("Add more as images/<slug>.jpg - the slug is the URL segment above.")
    print(f"Blog: {len(posts)} post(s) in data/blog_posts.csv.")
    print(f"Events: {len(events)} upcoming in data/events.csv (past ones drop off automatically).")
    if skipped:
        print(f"\nSkipped {len(skipped)} rows with no matching Category.")
    if missing:
        print(
            f"\n{len(missing)} of {len(shops)} listings have no hand-written description."
        )
        print("Fill the `description` column in data/shops.csv - this is the")
        print("thin-content risk your report's content strategy section has to answer.")


if __name__ == "__main__":
    main()
