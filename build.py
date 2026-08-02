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
from urllib.parse import quote
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

CATEGORY_INTROS = {
    "food-and-cafes": {
        "heading": f"Restaurants & Cafés in {AREA}",
        "description": (
            f"Explore trusted restaurants, cafés, bakeries and local favourites "
            f"in {AREA}. Find places for casual meals, family dining, coffee, "
            f"desserts and everyday food."
        ),
    },
    "shopping": {
        "heading": f"Shopping in {AREA}",
        "description": (
            f"Browse clothing stores, jewellers, supermarkets, electronics shops, "
            f"gift stores and local retailers across {AREA}."
        ),
    },
    "salons-and-pharmacies": {
        "heading": f"Salons, Pharmacies & Healthcare in {AREA}",
        "description": (
            f"Discover trusted salons, beauty parlours, grooming studios, "
            f"pharmacies, opticians and healthcare services in {AREA}."
        ),
    },
    "local-services": {
        "heading": f"Local Services in {AREA}",
        "description": (
            f"Find reliable dry cleaners, tailors, repair shops, print services, "
            f"laundries and other everyday local services in {AREA}."
        ),
    },
}

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
# HOMEPAGE FEATURED YOUTUBE SHORTS
# Change only this URL later when you want a different featured video.
HERO_VIDEO_URL = "https://www.youtube.com/shorts/0mNoliWVk4M"

HERO_VIDEO_LABEL = "Explore Malviya Nagar"
HERO_VIDEO_DESCRIPTION = (
    "Take a quick visual tour of Malviya Nagar before exploring restaurants, "
    "cafés, shopping, salons and local services."
)

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
# EVENTS
# data/events.csv columns: Event Title, Category, Complete Description,
# Meta Description, Venue Name, Venue Address, Dates, Times, Duration,
# Ticket Price, Age Restriction, Languages, BookMyShow URL, Tags,
# Suitable For, Image.
EVENTS_SLUG = "events"
EVENTS_DATA = Path("data/events.csv")
EVENTS_IMAGES = Path("images/events")
EVENT_CATEGORY_STYLES = [
    ("#E39A2B", "#FBF1DF"),
    ("#C74B52", "#FAE9E9"),
    ("#1E7F91", "#E3F1F3"),
    ("#6E8F3A", "#EEF3E3"),
]

BLOG_SLUG = "blog"
BLOGS_DATA = Path("data/blogs.csv")
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

def youtube_video_id(url: str):
    """Extract a YouTube video ID from Shorts, embed, watch or short URLs."""
    url = (url or "").strip()

    match = re.search(
        r"(?:youtube\.com/(?:shorts/|embed/|watch\?v=)|youtu\.be/)"
        r"([A-Za-z0-9_-]{11})",
        url,
    )

    return match.group(1) if match else None

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

def csv_value(row: dict, *column_names: str) -> str:
    """Return the first usable value from possible CSV column names."""
    ignored = {"", "n/a", "na", "not available", "-", "none", "null"}

    for name in column_names:
        value = str(row.get(name) or "").strip()
        if value.lower() not in ignored:
            return value

    return ""


def csv_highlights(row: dict):
    """Read optional business highlights without hardcoding any business data.

    Recommended CSV column:
    Highlights

    Example value:
    Family Friendly, Free Wi-Fi, Card Accepted, UPI
    """
    highlights = []
    raw = csv_value(row, "Highlights", "Business Highlights", "highlights")

    if raw:
        highlights.extend(
            item.strip()
            for item in raw.split(",")
            if item.strip() and item.strip().lower() not in {"n/a", "na", "-"}
        )

    # Also support separate optional yes/no columns if they exist in the CSV.
    optional_badges = [
        ("Family Friendly", "Family Friendly"),
        ("Free Wi-Fi", "Free Wi-Fi"),
        ("Card Accepted", "Card Accepted"),
        ("UPI", "UPI"),
        ("Home Delivery", "Home Delivery"),
        ("Outdoor Seating", "Outdoor Seating"),
        ("Indoor Seating", "Indoor Seating"),
        ("Wheelchair Accessible", "Wheelchair Accessible"),
    ]

    enabled_values = {"yes", "true", "1", "available", "included"}

    for label, column in optional_badges:
        value = csv_value(row, column)
        if value.lower() in enabled_values and label not in highlights:
            highlights.append(label)

    return highlights

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

def event_photo_block(ev, root: str, klass: str) -> str:
    """Render the event image, or a placeholder tile keyed to its category
    (same pattern as the business listing photos) until a real photo is
    added to the Image column or dropped into images/events/."""
    if ev["image"]:
        return (
            f'<img class="{klass}" src="{root}img/events/{esc(ev["image"])}" '
            f'alt="{esc(ev["title"])} in {esc(AREA)}" loading="lazy" decoding="async">'
        )
    tone = sum(ord(c) for c in ev["slug"]) % 3
    return (
        f'<div class="{klass} ph ph-{tone}" aria-hidden="true" '
        f'style="--a:{ev["accent"]};--t:{ev["tint"]}">'
        f'<span>{esc(initials(ev["title"]))}</span></div>'
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
		"whatsapp": (row.get("whatsapp") or "").strip(),
                "rating": rating,
                "reviews": reviews,
                "maps": (row.get("url") or "").strip(),
                "postcode": (row.get("postalCode") or "110017").strip(),
                # Your own writing goes in the CSV's `description` column.
                "blurb": (row.get("description") or "").strip(),
                "image": find_image(slug)
                or fetch_place_photo((row.get("placeId") or "").strip(), slug)
                or download_image(row.get("image_url"), slug),
		
		"email": csv_value(row, "email", "Email"),
		"opening_hours": csv_value(
    		row, "Opening Hours", "OpeningHours", "Hours", "opening_hours"
		),
		"payment": csv_value(
    		row, "Payment", "Payment Methods", "Payment Method", "payment"
		),
		"parking": csv_value(row, "Parking", "parking"),
		"seating": csv_value(row, "Seating", "seating"),
		"delivery": csv_value(row, "Delivery", "delivery"),
		"accessibility": csv_value(
   		    row, "Accessibility", "Wheelchair Accessible", "accessibility"
		),
		"highlights": csv_highlights(row),
            }
        )

    return shops, skipped


# ── Replace load_blog_posts() + the old load_events() (build.py lines 427-502) with: ──

def event_category_style(category: str):
    """Deterministic accent/tint pair per category, cycling the same
    earthy palette the shop categories already use."""
    if not category:
        return EVENT_CATEGORY_STYLES[0]
    idx = sum(ord(c) for c in category) % len(EVENT_CATEGORY_STYLES)
    return EVENT_CATEGORY_STYLES[idx]


def event_image(row: dict, slug: str):
    """Local file named after the slug wins first (drop a photo into
    images/events/ and it's picked up with no CSV edit needed). Otherwise
    use the Image column - a filename already in images/events/, or a URL
    to download once. Empty/missing -> None, and the placeholder tile is
    used instead."""
    local = find_image_in(EVENTS_IMAGES, slug)
    if local:
        return local

    value = (row.get("Image") or "").strip()
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return download_image_to(EVENTS_IMAGES, value, slug)
    if (EVENTS_IMAGES / value).exists():
        return value
    return None


def parse_event_date(raw: str):
    """Best-effort parse of the free-text Dates column (e.g. '19 Jul 2026')
    so events can be sorted soonest-first. Free-text like 'Multiple dates'
    just sorts to the end - it never breaks the build."""
    raw = (raw or "").strip()
    match = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", raw)
    if match:
        try:
            return datetime.strptime(
                f"{match.group(1)} {match.group(2)[:3]} {match.group(3)}", "%d %b %Y"
            ).date()
        except ValueError:
            pass
    return None


def load_events():
    """Read data/events.csv into a list of event dicts. Every field comes
    straight from the sheet - no event data is ever hardcoded. Missing
    file just means no events, never an error."""
    events, seen = [], set()
    if not EVENTS_DATA.exists():
        return events

    for row in read_csv_rows(EVENTS_DATA):
        title = (row.get("Event Title") or "").strip()
        if not title:
            continue

        slug = slugify(title)
        while slug in seen:
            slug += "-2"
        seen.add(slug)

        category = (row.get("Category") or "").strip() or "Event"
        accent, tint = event_category_style(category)
        tags = [t.strip() for t in (row.get("Tags") or "").split(",") if t.strip()]
        date_sort = parse_event_date(row.get("Dates"))

        events.append(
            {
                "title": title,
                "slug": slug,
                "category": category,
                "accent": accent,
                "tint": tint,
                "description": (row.get("Complete Description") or "").strip(),
                "meta": (row.get("Meta Description") or "").strip(),
                "venue_name": (row.get("Venue Name") or "").strip(),
                "venue_address": (row.get("Venue Address") or "").strip(),
                "dates": (row.get("Dates") or "").strip(),
                "times": (row.get("Times") or "").strip(),
                "duration": (row.get("Duration") or "").strip(),
                "price": (row.get("Ticket Price") or "").strip(),
                "age_restriction": (row.get("Age Restriction") or "").strip(),
                "languages": (row.get("Languages") or "").strip(),
                "bookmyshow_url": (row.get("BookMyShow URL") or "").strip(),
                "tags": tags,
                "suitable_for": (row.get("Suitable For") or "").strip(),
                "image": event_image(row, slug),
                "date_sort": date_sort or datetime(2099, 1, 1).date(),
            }
        )

    events.sort(key=lambda e: (e["date_sort"], e["title"]))
    return events

def parse_blog_date(raw: str):
    raw = (raw or "").strip()

    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass

    return datetime.min.date()


def blog_image(row: dict, slug: str):
    """Use a local slug-named image first, then the Image CSV column."""
    local = find_image_in(BLOG_IMAGES, slug)
    if local:
        return f"blog/{local}"

    value = (row.get("Image") or "").strip()

    if not value:
        return None

    if value.startswith(("http://", "https://")):
        downloaded = download_image_to(BLOG_IMAGES, value, slug)
        return f"blog/{downloaded}" if downloaded else None

    # Example CSV value: best-cafes-in-malviya-nagar.jpg
    if (BLOG_IMAGES / value).exists():
        return f"blog/{value}"

    # Example CSV value: gallery/market-photo.jpg
    if (IMAGES / value).exists():
        return value.replace("\\", "/")

    return None


def load_blogs():
    """Read all blog content from data/blogs.csv; no article content is hardcoded."""
    blogs, skipped, seen = [], [], set()

    if not BLOGS_DATA.exists():
        return blogs, skipped

    for row in read_csv_rows(BLOGS_DATA):
        title = (row.get("Title") or "").strip()
        slug = slugify((row.get("Slug") or "").strip())

        # Slug is required so all generated URLs come directly from the CSV.
        if not title or not slug:
            skipped.append(title or "(untitled row)")
            continue

        if slug in seen:
            skipped.append(f"{title} (duplicate slug: {slug})")
            continue
        seen.add(slug)

        category = (row.get("Category") or "").strip() or "Guide"
        accent, tint = event_category_style(category)
        published_date = (row.get("Published Date") or "").strip()

        blogs.append(
            {
                "title": title,
                "slug": slug,
                "category": category,
                "accent": accent,
                "tint": tint,
                "excerpt": (row.get("Excerpt") or "").strip(),
                "content": (row.get("Content") or "").strip(),
                "meta_title": (row.get("Meta Title") or "").strip(),
                "meta_description": (row.get("Meta Description") or "").strip(),
                "reading_time": (row.get("Reading Time") or "").strip(),
                "published_date": published_date,
                "date_sort": parse_blog_date(published_date),
                "image": blog_image(row, slug),
            }
        )

    # Newest articles first.
    blogs.sort(key=lambda blog: (blog["date_sort"], blog["title"].lower()), reverse=True)
    return blogs, skipped

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
    nav += f'<a href="{root}{EVENTS_SLUG}/">Events</a>'
    nav += f'<a class="nav-about" href="{root}{BLOG_SLUG}/">Blog</a>'

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
    <p class="footer-name">{esc(SITE_NAME)}</p>

    <p class="footer-note">Helping residents and visitors discover trusted
    restaurants, cafes, shops, healthcare services, salons and local businesses
    across Malviya Nagar, New Delhi.</p>

    <p class="footer-tagline">Making local discovery simple, reliable and accessible.</p>

    <p class="footer-copyright">© 2026 {esc(SITE_NAME)}. All rights reserved.</p>

    <p class="footer-community">Built with <span aria-label="love">♥</span> for the
    Malviya Nagar community.</p>
  </div>
</footer>

<script>
  document.addEventListener("DOMContentLoaded", () => {{
    if (
      !("IntersectionObserver" in window) ||
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {{
      return;
    }}

    const targets = document.querySelectorAll(
      "main > .band, main > .section, .footer, .tiles .tile"
    );

    const observer = new IntersectionObserver((entries, currentObserver) => {{
      entries.forEach((entry) => {{
        if (!entry.isIntersecting) return;

        entry.target.classList.add("is-visible");
        currentObserver.unobserve(entry.target);
      }});
    }}, {{ threshold: 0.12 }});

    targets.forEach((element, index) => {{
      element.classList.add("reveal");

      if (element.classList.contains("tile")) {{
        element.style.setProperty(
          "--reveal-delay",
          String((index % 4) * 50) + "ms"
        );
      }}

      observer.observe(element);
    }});
  }});
</script>
</body>
</html>"""


def rating_plate(shop):
    if not shop["rating"]:
        return ""

    filled_stars = min(5, max(0, int(shop["rating"] + 0.5)))
    empty_stars = 5 - filled_stars
    review_text = f'{shop["reviews"]} reviews'

    return (
        f'<span class="rating" role="img" '
        f'aria-label="Rated {shop["rating"]:.1f} out of 5 from {review_text}">'
        f'<span class="rating-main">'
        f'<span class="rating-stars" aria-hidden="true">'
        f'<span class="rating-stars-filled">{"★" * filled_stars}</span>'
        f'<span class="rating-stars-empty">{"★" * empty_stars}</span>'
        f'</span>'
        f'<b class="rating-value">{shop["rating"]:.1f}</b>'
        f'</span>'
        f'<span class="rating-count">{review_text}</span>'
        f'</span>'
    )

def business_icon(icon_name: str) -> str:
    """Small inline SVG icons, keeping the generated website self-contained."""
    icons = {
        "address": '<path d="M12 21s7-5.2 7-12a7 7 0 1 0-14 0c0 6.8 7 12 7 12Z"/><circle cx="12" cy="9" r="2.5"/>',
        "phone": '<path d="M7.5 3.5 5.4 5.6c-1 1 1.1 6.2 4.8 9.9s8.9 5.8 9.9 4.8l2.1-2.1-3.4-3.4-2 2c-1.2-.5-2.4-1.4-3.5-2.5s-2-2.3-2.5-3.5l2-2-3.3-3.4Z"/>',
        "email": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
        "website": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.2 2.5 3.3 5.5 3.3 9S14.2 18.5 12 21c-2.2-2.5-3.3-5.5-3.3-9S9.8 5.5 12 3Z"/>',
        "map": '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3V6Z"/><path d="M9 3v15M15 6v15"/>',
        "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
        "category": '<path d="M4 4h7l9 9-7 7-9-9V4Z"/><circle cx="8" cy="8" r="1"/>',
        "payment": '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 10h18"/>',
        "parking": '<path d="M6 21V3h7a5 5 0 0 1 0 10H6"/><path d="M6 3h7a5 5 0 0 1 0 10H6"/>',
        "seating": '<path d="M5 11h14M7 11V6a3 3 0 0 1 6 0v5M5 11v8M19 11v8M7 16h10"/>',
        "delivery": '<path d="M3 6h11v10H3z"/><path d="M14 9h4l3 3v4h-7V9Z"/><circle cx="7" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
        "accessibility": '<circle cx="12" cy="5" r="2"/><path d="M12 8v5m0 0 4 2m-4-2-3 5m3-5-4-1"/>',
        "rating": '<path d="m12 3 2.7 5.5 6 .9-4.3 4.2 1 6-5.4-2.9-5.4 2.9 1-6L3.3 9.4l6-.9L12 3Z"/>',
    }

    return (
        '<svg class="business-info-icon" viewBox="0 0 24 24" '
        'fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        + icons.get(icon_name, icons["category"])
        + "</svg>"
    )


def business_info_row(icon_name: str, label: str, value_html: str) -> str:
    """Return one information row only when the field has a real value."""
    if not value_html:
        return ""

    return f"""<div class="business-info-row">
  <div class="business-info-icon-wrap">{business_icon(icon_name)}</div>
  <dt>{esc(label)}</dt>
  <dd>{value_html}</dd>
</div>"""


def business_rating_row(shop) -> str:
    """Premium Google rating display for the detail page only."""
    if not shop["rating"]:
        return ""

    stars = "★" * min(5, max(1, int(shop["rating"] + 0.5)))
    review_text = (
        f'Based on {shop["reviews"]} Google Reviews'
        if shop["reviews"]
        else "Google Rating"
    )

    return business_info_row(
        "rating",
        "Google Rating",
        f"""<span class="business-rating-stars" aria-label="{shop["rating"]:.1f} out of 5">
  {stars}
</span>
<strong class="business-rating-value">{shop["rating"]:.1f} Excellent</strong>
<span class="business-rating-reviews">{esc(review_text)}</span>""",
    )

def shop_card(shop, root=""):
    href = f"{shop['slug']}/"
    accent = shop["category"]["accent"]
    hay = f"{shop['title']} {shop['type']} {shop['address']}".lower()

    description = shop["blurb"] or (
        f"{shop['title']} is a {shop['type'].lower() or 'local business'} "
        f"in {AREA}, {CITY}."
    )

    return f"""<li class="card" style="--a:{accent}" data-search="{esc(hay)}">
  <div class="card-media">
    <a class="card-photo-link" href="{href}" tabindex="-1" aria-hidden="true">
      {photo_block(shop, root, "card-photo")}
    </a>
    <span class="card-badge">{esc(shop["type"])}</span>
  </div>

  <div class="card-body">
    <h3 class="card-name">
      <a href="{href}">{esc(shop["title"])}</a>
    </h3>

    <div class="card-rating-row">
      {rating_plate(shop)}
    </div>

    <p class="card-description">{esc(truncate(description, 175))}</p>

    <p class="card-addr">{esc(truncate(shop["address"], 65))}</p>

    <a class="card-more" href="{href}">
      View business details <span aria-hidden="true">&rarr;</span>
    </a>
  </div>
</li>"""


# ── Replace blog_card() + event_row() (build.py lines 681-718) with: ──

def event_card(ev, root=""):
    href = f"{ev['slug']}/"
    hay = f"{ev['title']} {ev['category']} {ev['languages']} {ev['suitable_for']}".lower()
    when = f"📅 {esc(ev['dates'])}"
    if ev["times"]:
        when += f" &middot; 🕒 {esc(ev['times'])}"
    suitable_html = (
        f'<span class="event-card-suitable">{esc(ev["suitable_for"])}</span>'
        if ev["suitable_for"] else ""
    )
    return f"""<li class="event-card" style="--a:{ev['accent']};--t:{ev['tint']}"
    data-search="{esc(hay)}" data-category="{esc(ev['category'])}"
    data-languages="{esc(ev['languages'].lower())}" data-suitable="{esc(ev['suitable_for'].lower())}">
  <div class="event-card-media">
    <a class="event-card-photo-link" href="{href}" tabindex="-1" aria-hidden="true">
      {event_photo_block(ev, root, "event-card-photo")}
    </a>
    <span class="event-card-badge">{esc(ev['category'])}</span>
  </div>
  <div class="event-card-body">
    <h3 class="event-card-title"><a href="{href}">{esc(ev['title'])}</a></h3>
    <p class="event-card-venue">📍 {esc(ev['venue_name'])}</p>
    <p class="event-card-when">{when}</p>
    <p class="event-card-desc">{esc(truncate(ev['meta'] or ev['description'], 140))}</p>
    <div class="event-card-foot">
      <span class="event-card-price">{esc(ev['price']) or 'See details'}</span>
      {suitable_html}
    </div>
    <a class="event-card-more" href="{href}">View Details <span aria-hidden="true">&rarr;</span></a>
  </div>
</li>"""

def blog_photo_block(blog, root: str, klass: str):
    """Display the article image, or a premium editorial SVG placeholder."""
    if blog["image"]:
        return (
            f'<img class="{klass}" src="{root}img/{esc(blog["image"])}" '
            f'alt="{esc(blog["title"])}" loading="lazy" decoding="async">'
        )

    return f"""<div class="{klass} blog-placeholder" role="img"
  aria-label="Editorial illustration for {esc(blog["title"])}">
  <svg viewBox="0 0 800 500" aria-hidden="true">
    <rect width="800" height="500" rx="28" fill="#EEF3E3"/>
    <circle cx="635" cy="105" r="115" fill="#D9E7C5"/>
    <path d="M170 350c75-140 160-165 270-70 70 60 130 54 190-12v112H170Z"
      fill="#6E8F3A" opacity=".85"/>
    <rect x="170" y="135" width="280" height="165" rx="14" fill="#FFF"/>
    <rect x="202" y="172" width="210" height="16" rx="8" fill="#D8E2D0"/>
    <rect x="202" y="207" width="160" height="13" rx="6.5" fill="#E6ECE2"/>
    <rect x="202" y="235" width="190" height="13" rx="6.5" fill="#E6ECE2"/>
  </svg>
</div>"""


def blog_card(blog, image_root="", href=None):
    """Reusable card for Blog page and related-article sections."""
    href = href or f"{BLOG_SLUG}/{blog['slug']}/"

    searchable_text = " ".join(
        [blog["title"], blog["category"], blog["excerpt"], blog["content"]]
    ).lower()

    return f"""<li class="blog-card"
  style="--a:{blog['accent']};--t:{blog['tint']}"
  data-search="{esc(searchable_text)}"
  data-category="{esc(blog['category'].lower())}">
  <div class="blog-card-media">
    <a href="{href}" tabindex="-1" aria-hidden="true">
      {blog_photo_block(blog, image_root, "blog-card-photo")}
    </a>
    <span class="blog-card-badge">{esc(blog["category"])}</span>
  </div>

  <div class="blog-card-body">
    <h3 class="blog-card-title">
      <a href="{href}">{esc(blog["title"])}</a>
    </h3>

    <p class="blog-card-excerpt">{esc(truncate(blog["excerpt"], 165))}</p>

    <p class="blog-card-meta">
      <span>{esc(blog["reading_time"])}</span>
      <span>{esc(blog["published_date"])}</span>
    </p>

    <a class="blog-card-more" href="{href}">
      Read More <span aria-hidden="true">&rarr;</span>
    </a>
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

    # A small search index for the home page. It stays entirely in the browser,
    # so visitors can find a business without choosing a category first.
    home_search_items = "".join(
        f'<li class="home-search-item" data-home-search="{esc((s["title"] + " " + s["type"] + " " + s["address"]).lower())}">'
        f'<a href="{s["category"]["slug"]}/{s["slug"]}/">'
        f'<strong>{esc(s["title"])}</strong>'
        f'<span>{esc(s["type"])} &middot; {esc(truncate(s["address"], 55))}</span>'
        f'</a></li>'
        for s in sorted(shops, key=lambda s: s["title"].lower())
    )

    # ticker: real shop names, doubled so the loop is seamless
    names = [s["title"] for s in sorted(shops, key=lambda x: -x["reviews"])[:26]]
    strip = "".join(
        f'<span class="tick">{esc(n)}</span><span class="tick-dot" aria-hidden="true">&bull;</span>'
        for n in names
    )
    
    video_id = youtube_video_id(HERO_VIDEO_URL)

    hero_class = "hero-inner"
    hero_video_html = ""

    if video_id:
        hero_class += " hero-inner--with-video"

        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        embed_url = f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0"

        hero_video_html = f"""<aside class="hero-shorts-card">
      <p class="hero-shorts-label">
        <span aria-hidden="true">▶</span> {esc(HERO_VIDEO_LABEL)}
      </p>

      <button class="hero-shorts-player" type="button"
        data-youtube-embed="{esc(embed_url)}"
        data-youtube-title="{esc(HERO_VIDEO_LABEL)}"
        aria-label="Play {esc(HERO_VIDEO_LABEL)} video">
        <img src="{esc(thumbnail_url)}"
          alt="Preview of {esc(HERO_VIDEO_LABEL)}"
          loading="lazy" decoding="async">

        <span class="hero-shorts-play" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5.5v13l10-6.5-10-6.5Z"/>
          </svg>
        </span>
      </button>

      <p class="hero-shorts-description">{esc(HERO_VIDEO_DESCRIPTION)}</p>
    </aside>"""

    gallery_files = []
    if GALLERY.exists():
        gallery_files = sorted(
            file for file in GALLERY.iterdir()
            if file.suffix.lower() in IMAGE_EXT and not file.name.startswith(".")
        )[:6]

    carousel_slides = ""
    carousel_dots = ""

    for index, photo in enumerate(gallery_files):
        caption = photo.stem.replace("-", " ").replace("_", " ").strip().capitalize()
        hidden = "" if index == 0 else " hidden"
        selected = "true" if index == 0 else "false"

        carousel_slides += (
            f'<figure class="discover-slide"{hidden} aria-hidden="{str(index != 0).lower()}">'
            f'<img src="img/gallery/{esc(photo.name)}" '
            f'alt="{esc(caption)}, {esc(AREA)}" loading="lazy" decoding="async">'
            f'</figure>'
        )

        carousel_dots += (
            f'<button class="discover-dot" type="button" data-slide="{index}" '
            f'aria-label="Show image {index + 1}" aria-pressed="{selected}"></button>'
        )

    if gallery_files:
        carousel_html = f"""<div class="discover-carousel" data-discover-carousel>
  <div class="discover-carousel-viewport">
    {carousel_slides}
  </div>

  <button class="discover-arrow discover-arrow--previous" type="button"
    aria-label="Show previous image">&#8592;</button>

  <button class="discover-arrow discover-arrow--next" type="button"
    aria-label="Show next image">&#8594;</button>

  <div class="discover-dots" aria-label="Carousel navigation">
    {carousel_dots}
  </div>
</div>"""
    else:
        carousel_html = ""
    body = f"""<section class="hero">
  <div class="hero-glow" aria-hidden="true"></div>
  <div class="hero-shape hero-shape-one" aria-hidden="true"></div>
  <div class="hero-shape hero-shape-two" aria-hidden="true"></div>

  <div class="wrap {hero_class}">
    <div class="hero-copy">
      <p class="eyebrow hero-eyebrow">Local business directory · Malviya Nagar</p>

      <h1 class="hero-title">Discover the Best Businesses in Malviya Nagar</h1>

      <p class="hero-lede">Find trusted restaurants, cafes, salons, clinics,
      shopping destinations and local services - all in one place.</p>

      <div class="home-search">
        <label for="home-search-input">Search Malviya Nagar businesses</label>

        <svg class="home-search-icon" aria-hidden="true" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="6"></circle>
          <path d="m16 16 4 4"></path>
        </svg>

        <input type="search" id="home-search-input" class="home-search-input"
          placeholder="Search restaurants, salons, shops and more"
          autocomplete="off">

        <ul class="home-search-results" id="home-search-results" hidden>{home_search_items}</ul>
        <p class="home-search-empty" id="home-search-empty" role="status" hidden>
          No matching business found.
        </p>
      </div>

      <nav class="hero-chips" aria-label="Browse popular categories">
        <a href="food-and-cafes/" class="hero-chip">Restaurants</a>
        <a href="food-and-cafes/" class="hero-chip">cafes</a>
        <a href="salons-and-pharmacies/" class="hero-chip">Salons</a>
        <a href="salons-and-pharmacies/" class="hero-chip">Clinics</a>
        <a href="salons-and-pharmacies/" class="hero-chip">Pharmacies</a>
        <a href="shopping/" class="hero-chip">Shopping</a>
      </nav>

      <ul class="trust-strip" aria-label="Directory benefits">
        <li><span aria-hidden="true">✓</span> Trusted Local Listings</li>
        <li><span aria-hidden="true">✓</span> Updated Regularly</li>
        <li><span aria-hidden="true">✓</span> Verified Information</li>
        <li><span aria-hidden="true">✓</span> Free to Explore</li>
      </ul>
    </div>

    {hero_video_html}
  </div>
</section>

<section class="wrap section discover-section" id="browse">
  <header class="discover-intro">
    <p class="eyebrow">Explore the neighbourhood</p>
    <h2 class="discover-title">Discover Malviya Nagar</h2>
    <p class="discover-subtitle">Explore one of South Delhi's most vibrant
    neighbourhoods, known for its restaurants, cafés, shopping streets,
    healthcare services and thriving local businesses.</p>
  </header>

  {carousel_html}

  <div class="discover-content">
    <h3>About Malviya Nagar</h3>

    <p>Malviya Nagar is one of South Delhi's most vibrant residential and
    commercial neighbourhoods, known for its diverse mix of local businesses,
    shopping destinations, restaurants, cafés, healthcare facilities,
    educational institutes and everyday services. Well connected by the Delhi
    Metro and major roads, the area attracts residents, students, professionals
    and visitors looking for convenient shopping and quality services.</p>

    <p>Our Malviya Nagar business directory helps you discover trusted shops in
    Malviya Nagar, including clothing stores, electronics shops, grocery stores,
    pharmacies, salons, gyms, furniture stores, bakeries, flower shops and
    jewellery stores. Whether you're searching for the best restaurants in
    Malviya Nagar, a café in Malviya Nagar, a salon in Malviya Nagar or
    essential local services, you can browse verified business listings with
    contact details, addresses, opening hours and customer information.</p>

    <p>The directory is designed to make finding local businesses simple and
    convenient. Instead of searching across multiple websites, you can explore
    businesses by category, compare nearby options and connect directly with
    service providers in Malviya Nagar. From daily essentials to dining,
    shopping, healthcare and professional services, our listings help residents
    and visitors quickly find the businesses they need.</p>
  </div>

  <ul class="discover-highlights">
    <li>
      <span aria-hidden="true">📍</span>
      <div><strong>Prime South Delhi Location</strong><p>Easy access to key city destinations.</p></div>
    </li>
    <li>
      <span aria-hidden="true">🍽</span>
      <div><strong>Diverse Food &amp; Café Culture</strong><p>From everyday favourites to cafés and bakeries.</p></div>
    </li>
    <li>
      <span aria-hidden="true">🛍</span>
      <div><strong>Shopping &amp; Local Markets</strong><p>Independent shops and daily essentials nearby.</p></div>
    </li>
    <li>
      <span aria-hidden="true">🚇</span>
      <div><strong>Well Connected by Metro</strong><p>Conveniently connected to the wider city.</p></div>
    </li>
  </ul>

  <div class="discover-cta">
    <a class="btn" href="#business-listings">Explore Businesses <span aria-hidden="true">&rarr;</span></a>
  </div>

  <div class="discover-directory" id="business-listings">
    <h3>Explore Local Businesses</h3>
    <div class="tiles">{tiles}</div>
  </div>
</section>

<script>
  (() => {{
    const input = document.getElementById('home-search-input');
    const results = document.getElementById('home-search-results');
    const empty = document.getElementById('home-search-empty');
    const items = [...results.querySelectorAll('.home-search-item')];

    input.addEventListener('input', () => {{
      const query = input.value.trim().toLowerCase();
      let matches = 0;

      items.forEach((item) => {{
        const show = query && item.dataset.homeSearch.includes(query);
        item.hidden = !show;

        if (show) matches += 1;
      }});

      results.hidden = !query || matches === 0;
      empty.hidden = !query || matches !== 0;
    }});
  }})();
</script>

<script>
  (() => {{
    const carousel = document.querySelector("[data-discover-carousel]");
    if (!carousel) return;

    const slides = [...carousel.querySelectorAll(".discover-slide")];
    const dots = [...carousel.querySelectorAll(".discover-dot")];
    const previous = carousel.querySelector(".discover-arrow--previous");
    const next = carousel.querySelector(".discover-arrow--next");
    let currentSlide = 0;

    function showSlide(index) {{
      currentSlide = (index + slides.length) % slides.length;

      slides.forEach((slide, slideIndex) => {{
        const active = slideIndex === currentSlide;
        slide.hidden = !active;
        slide.setAttribute("aria-hidden", String(!active));
      }});

      dots.forEach((dot, dotIndex) => {{
        dot.setAttribute("aria-pressed", String(dotIndex === currentSlide));
      }});
    }}

    previous.addEventListener("click", () => showSlide(currentSlide - 1));
    next.addEventListener("click", () => showSlide(currentSlide + 1));

    dots.forEach((dot, index) => {{
      dot.addEventListener("click", () => showSlide(index));
    }});
  }})();
</script>

<script>
(() => {{
  const players = document.querySelectorAll(".hero-shorts-player");

  players.forEach((button) => {{
    button.addEventListener("click", () => {{
      const iframe = document.createElement("iframe");

      iframe.className = "hero-shorts-iframe";
      iframe.src = button.dataset.youtubeEmbed + "&autoplay=1&mute=1";
      iframe.title = button.dataset.youtubeTitle;
      iframe.loading = "lazy";
      iframe.allowFullscreen = true;
      iframe.allow =
        "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
      iframe.referrerPolicy = "strict-origin-when-cross-origin";

      button.replaceWith(iframe);
    }});
  }});
}})();
</script>"""
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

    intro = CATEGORY_INTROS.get(
        cat["slug"],
        {
            "heading": f"{cat['name']} in {AREA}",
            "description": f"Explore trusted {cat['name'].lower()} businesses in {AREA}.",
        },
    )
    cards = "".join(shop_card(s, root="../") for s in members)

    body = f"""<section class="band category-hero"
  style="--a:{cat['accent']};--t:{cat['tint']}">
  <div class="wrap">
    <nav class="crumbs">
      <a href="../">Home</a> <span>/</span> {esc(cat['name'])}
    </nav>

    <p class="eyebrow">Explore {esc(cat['name'])}</p>

    <h1 class="page-title">{esc(intro['heading'])}</h1>

    <p class="category-description">{esc(intro['description'])}</p>

    <p class="category-stat">
      <strong>{len(members)}</strong>
      <span>Businesses</span>
    </p>
  </div>
</section>

<section class="wrap section category-listings">
  <div class="searchbar">
    <input type="search" id="q" class="search-input"
           placeholder="Filter by name, type or street&hellip;"
           aria-label="Filter {esc(cat['name'])} listings" autocomplete="off">
    <p class="search-count" id="count" role="status">{len(members)} shown</p>
  </div>
  <div class="category-divider" aria-hidden="true"></div>
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
        address_html = esc(shop["address"]).replace("\n", "<br>")
        rows += business_info_row("address", "Address", address_html)

    if shop["phone"]:
        tel = re.sub(r"[^\d+]", "", shop["phone_raw"] or shop["phone"])
        rows += business_info_row(
            "phone",
            "Phone",
            f'<a href="tel:{esc(tel)}">{esc(shop["phone"])}</a>',
        )

    if shop.get("email"):
        rows += business_info_row(
            "email",
            "Email",
            f'<a href="mailto:{esc(shop["email"])}">{esc(shop["email"])}</a>',
        )

    if shop["website"]:
        rows += business_info_row(
            "website",
            "Website",
            f'<a href="{esc(shop["website"])}" target="_blank" '
            f'rel="nofollow noopener noreferrer">Visit Website &rarr;</a>',
        )

    if shop["maps"]:
        rows += business_info_row(
            "map",
            "Directions",
             f'<a class="maps-link" href="{esc(shop["maps"])}" target="_blank" '
             f'rel="nofollow noopener noreferrer">Open in Google Maps &rarr;</a>',
        )

    rows += business_rating_row(shop)

    if shop.get("opening_hours"):
        rows += business_info_row(
            "clock",
            "Opening Hours",
             esc(shop["opening_hours"]).replace("\n", "<br>"),
        )

    if shop["type"]:
        rows += business_info_row("category", "Category", esc(shop["type"]))

    if shop.get("payment"):
        rows += business_info_row("payment", "Payment", esc(shop["payment"]))

    if shop.get("parking"):
        rows += business_info_row("parking", "Parking", esc(shop["parking"]))

    if shop.get("seating"):
        rows += business_info_row("seating", "Seating", esc(shop["seating"]))

    if shop.get("delivery"):
        rows += business_info_row("delivery", "Delivery", esc(shop["delivery"]))

    if shop.get("accessibility"):
        rows += business_info_row(
            "accessibility",
            "Accessibility",
            esc(shop["accessibility"]),
        )

    info_section = ""
    if rows:
        info_section = f"""<section class="business-information">
      <h2 class="section-head">Contact &amp; Business Information</h2>
      <dl class="business-info">{rows}</dl>
    </section>"""

    highlights_section = ""
    if shop.get("highlights"):
        badges = "".join(
            f'<li class="business-highlight">✓ {esc(highlight)}</li>'
            for highlight in shop["highlights"]
        )

        highlights_section = f"""<section class="business-highlights">
      <h2 class="section-head">Business Highlights</h2>
      <ul class="business-highlights-list">{badges}</ul>
    </section>"""
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

  {info_section}
  {highlights_section}

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


def build_blogs(blogs):
    """Build the Blog landing page at /blog/."""
    categories = sorted({blog["category"] for blog in blogs})
    category_options = "".join(
        f'<option value="{esc(category.lower())}">{esc(category)}</option>'
        for category in categories
    )

    if blogs:
        cards = "".join(
            blog_card(blog, image_root="../", href=f"{blog['slug']}/")
            for blog in blogs
        )
        grid_html = f'<ul class="blog-grid" id="blogGrid">{cards}</ul>'
    else:
        grid_html = ""

    body = f"""<section class="hero blog-hero">
  <div class="hero-glow" aria-hidden="true"></div>
  <div class="hero-shape hero-shape-one" aria-hidden="true"></div>
  <div class="hero-shape hero-shape-two" aria-hidden="true"></div>

  <div class="wrap hero-inner">
    <div class="hero-copy">
      <p class="eyebrow hero-eyebrow">Local guides &middot; {esc(AREA)}</p>
      <h1 class="hero-title">Malviya Nagar Blog</h1>
      <p class="hero-lede">Local guides, recommendations, neighbourhood insights
      and useful information to help you discover Malviya Nagar.</p>
    </div>
  </div>
</section>

<section class="wrap section blog-listings">
  <div class="blog-filters">
    <div class="searchbar">
      <input type="search" id="blogSearch" class="search-input"
        placeholder="Search blogs&hellip;" aria-label="Search blogs" autocomplete="off">
      <p class="search-count" id="blogCount" role="status">{len(blogs)} articles</p>
    </div>

    <div class="blog-filter-row">
      <select id="blogCategory" class="blog-filter-select"
        aria-label="Filter blogs by category">
        <option value="">All categories</option>
        {category_options}
      </select>
    </div>
  </div>

  {grid_html}

  <div class="blog-empty" id="blogEmpty" {"hidden" if blogs else ""}>
    <svg class="blog-empty-illustration" viewBox="0 0 120 120" aria-hidden="true">
      <circle cx="60" cy="60" r="52" fill="#EEF3E3"></circle>
      <path d="M35 35h50v52H35z" fill="#FFF" stroke="#6E8F3A" stroke-width="3"></path>
      <path d="M45 52h30M45 64h30M45 76h20" stroke="#6E8F3A"
        stroke-width="3" stroke-linecap="round"></path>
    </svg>
    <p class="blog-empty-text">No articles available yet.</p>
    <button type="button" class="blog-empty-reset" id="blogReset">View All Articles</button>
  </div>
</section>

<script>
(function () {{
  var grid = document.getElementById("blogGrid");
  if (!grid) return;

  var search = document.getElementById("blogSearch"),
      category = document.getElementById("blogCategory"),
      count = document.getElementById("blogCount"),
      empty = document.getElementById("blogEmpty"),
      reset = document.getElementById("blogReset"),
      cards = Array.prototype.slice.call(grid.children);

  function run() {{
    var term = search.value.trim().toLowerCase(),
        selectedCategory = category.value,
        matches = 0;

    cards.forEach(function (card) {{
      var visible = (!term || card.dataset.search.indexOf(term) > -1)
        && (!selectedCategory || card.dataset.category === selectedCategory);

      card.hidden = !visible;
      if (visible) matches++;
    }});

    count.textContent = matches + (matches === 1 ? " article" : " articles");
    grid.hidden = matches === 0;
    empty.hidden = matches > 0;
  }}

  search.addEventListener("input", run);
  category.addEventListener("change", run);

  if (reset) {{
    reset.addEventListener("click", function () {{
      search.value = "";
      category.value = "";
      run();
    }});
  }}
}})();
</script>"""

    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": f"{AREA} Blog",
        "description": (
            f"Local guides, recommendations and neighbourhood insights for "
            f"{AREA}, {CITY}."
        ),
        "url": f"{SITE_URL}/{BLOG_SLUG}/",
    }

    write(
        OUT / BLOG_SLUG / "index.html",
        page(
            title=f"Malviya Nagar Blog | {SITE_NAME}",
            meta=(
                f"Local guides, recommendations, neighbourhood insights and useful "
                f"information about {AREA}, {CITY}."
            ),
            canonical=f"{SITE_URL}/{BLOG_SLUG}/",
            body=body,
            schema=schema,
            depth=1,
        ),
    )

def blog_directory_link(blog):
    """Link an article to the most relevant business category where possible."""
    text = f"{blog['category']} {blog['title']}".lower()

    if any(word in text for word in ("salon", "spa", "beauty", "hair", "grooming")):
        return "salons-and-pharmacies"

    if any(word in text for word in ("cafe", "coffee", "restaurant", "food", "bakery")):
        return "food-and-cafes"

    if any(word in text for word in (
        "shopping", "fashion", "clothing", "jewellery", "jewelry", "electronics"
    )):
        return "shopping"

    return ""


def blog_title_words(blog):
    """Meaningful title words used for related-article matching."""
    ignored = {"the", "and", "for", "with", "from", "your", "best", "guide", "in"}
    words = re.findall(r"[a-z0-9]+", blog["title"].lower())
    return {word for word in words if len(word) > 3 and word not in ignored}


def build_blog(blog, blogs):
    """Build one article page at /blog/<slug>/."""
    url = f"{SITE_URL}/{BLOG_SLUG}/{blog['slug']}/"
    title_words = blog_title_words(blog)

    related_scored = []
    for other in blogs:
        if other is blog:
            continue

        same_category = other["category"].lower() == blog["category"].lower()
        common_words = title_words.intersection(blog_title_words(other))

        score = (10 if same_category else 0) + len(common_words)
        if score:
            related_scored.append((score, other))

    related = [
        other
        for _, other in sorted(
            related_scored,
            key=lambda item: (-item[0], -item[1]["date_sort"].toordinal(), item[1]["title"])
        )[:3]
    ]

    related_html = ""
    if related:
        related_cards = "".join(
            blog_card(
                other,
                image_root="../../",
                href=f"../{other['slug']}/",
            )
            for other in related
        )
        related_html = f"""<section class="wrap section blog-related">
  <h2 class="section-head">You May Also Like</h2>
  <ul class="blog-grid">{related_cards}</ul>
</section>"""

    category_slug = blog_directory_link(blog)
    directory_href = f"../../{category_slug}/" if category_slug else "../../"

    share_url = quote(url, safe="")
    share_title = quote(blog["title"], safe="")

    body = f"""<section class="band blog-detail-band"
  style="--a:{blog['accent']};--t:{blog['tint']}">
  <div class="wrap">
    <nav class="crumbs">
      <a href="../../">Home</a> <span>/</span>
      <a href="../">Blog</a> <span>/</span>
      {esc(blog["title"])}
    </nav>

    <p class="eyebrow">{esc(blog["category"])}</p>
    <h1 class="page-title">{esc(blog["title"])}</h1>

    <p class="blog-detail-meta">
      <span>{esc(blog["published_date"])}</span>
      <span>{esc(blog["reading_time"])}</span>
    </p>
  </div>
</section>

<article class="wrap section blog-detail" style="--a:{blog['accent']}">
  {blog_photo_block(blog, "../../", "blog-hero-photo")}

  <div class="blog-share" aria-label="Share this article">
    <span>Share:</span>
    <a href="https://www.facebook.com/sharer/sharer.php?u={share_url}"
      target="_blank" rel="noopener noreferrer">Facebook</a>
    <a href="https://twitter.com/intent/tweet?url={share_url}&text={share_title}"
      target="_blank" rel="noopener noreferrer">X</a>
    <a href="https://wa.me/?text={share_title}%20{share_url}"
      target="_blank" rel="noopener noreferrer">WhatsApp</a>
  </div>

  <div class="blog-content">
    {paragraphs_html(blog["content"])}
  </div>

  <div class="blog-business-cta">
    <a class="btn" href="{directory_href}">
      Explore Related Businesses <span aria-hidden="true">&rarr;</span>
    </a>
  </div>
</article>

{related_html}"""

    schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": blog["title"],
        "description": blog["meta_description"] or blog["excerpt"],
        "url": url,
        "mainEntityOfPage": url,
    }

    if blog["date_sort"] != datetime.min.date():
        schema["datePublished"] = blog["date_sort"].isoformat()

    if blog["image"]:
        schema["image"] = f"{SITE_URL}/img/{blog['image']}"

    write(
        OUT / BLOG_SLUG / blog["slug"] / "index.html",
        page(
            title=blog["meta_title"] or f"{blog['title']} | {SITE_NAME}",
            meta=truncate(blog["meta_description"] or blog["excerpt"] or blog["title"]),
            canonical=url,
            body=body,
            schema=schema,
            depth=2,
            image=blog["image"],
        ),
    )

# ── Replace build_blog_events() + build_blog_post() (build.py lines 1341-1460) with: ──

def build_events(events):
    """The Events landing page: hero + instant search/filters + card grid."""
    categories = sorted({e["category"] for e in events})
    languages = sorted({
        lang.strip() for e in events for lang in e["languages"].split(",") if lang.strip()
    })
    suitable = sorted({
        s.strip() for e in events for s in e["suitable_for"].split(",") if s.strip()
    })

    cat_options = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in categories)
    lang_options = "".join(
        f'<option value="{esc(l.lower())}">{esc(l)}</option>' for l in languages
    )
    suit_options = "".join(
        f'<option value="{esc(s.lower())}">{esc(s)}</option>' for s in suitable
    )

    grid_html = ""
    if events:
        cards = "".join(event_card(e) for e in events)
        grid_html = f'<ul class="event-grid" id="eventGrid">{cards}</ul>'

    body = f"""<section class="hero events-hero">
  <div class="hero-glow" aria-hidden="true"></div>
  <div class="hero-shape hero-shape-one" aria-hidden="true"></div>
  <div class="hero-shape hero-shape-two" aria-hidden="true"></div>
  <div class="wrap hero-inner">
    <div class="hero-copy">
      <p class="eyebrow hero-eyebrow">What&rsquo;s on &middot; {esc(AREA)}</p>
      <h1 class="hero-title">Upcoming Events in {esc(AREA)}</h1>
      <p class="hero-lede">Discover concerts, comedy shows, workshops, food
      festivals, exhibitions, cultural programmes and community events
      happening around {esc(AREA)}.</p>
    </div>
  </div>
</section>

<section class="wrap section events-listings">
  <div class="event-filters">
    <div class="searchbar">
      <input type="search" id="eventSearch" class="search-input"
             placeholder="Search events&hellip;" aria-label="Search events" autocomplete="off">
      <p class="search-count" id="eventCount" role="status">{len(events)} events</p>
    </div>
    <div class="event-filter-row">
      <select id="eventCategory" class="event-filter-select" aria-label="Filter by category">
        <option value="">All categories</option>
        {cat_options}
      </select>
      <select id="eventLanguage" class="event-filter-select" aria-label="Filter by language">
        <option value="">All languages</option>
        {lang_options}
      </select>
      <select id="eventSuitable" class="event-filter-select" aria-label="Filter by who it suits">
        <option value="">Suitable for anyone</option>
        {suit_options}
      </select>
    </div>
  </div>

  {grid_html}

  <div class="event-empty" id="eventEmpty" {"hidden" if events else ""}>
    <svg class="event-empty-illustration" viewBox="0 0 120 120" aria-hidden="true">
      <circle cx="60" cy="60" r="52" fill="var(--t)"></circle>
      <path d="M38 50h44v34a4 4 0 0 1-4 4H42a4 4 0 0 1-4-4V50Z" fill="none" stroke="var(--a)" stroke-width="3"></path>
      <path d="M38 50v-6a4 4 0 0 1 4-4h36a4 4 0 0 1 4 4v6" fill="none" stroke="var(--a)" stroke-width="3"></path>
      <path d="M46 34v10M74 34v10" stroke="var(--a)" stroke-width="3" stroke-linecap="round"></path>
      <path d="M48 68l24 16M72 68 48 84" stroke="var(--a)" stroke-width="3" stroke-linecap="round"></path>
    </svg>
    <p class="event-empty-text">No events found.</p>
    <button type="button" class="event-empty-reset" id="eventReset">View All Events</button>
  </div>
</section>
<script>
(function () {{
  var grid = document.getElementById('eventGrid');
  if (!grid) return;
  var q = document.getElementById('eventSearch'),
      catSel = document.getElementById('eventCategory'),
      langSel = document.getElementById('eventLanguage'),
      suitSel = document.getElementById('eventSuitable'),
      count = document.getElementById('eventCount'),
      empty = document.getElementById('eventEmpty'),
      reset = document.getElementById('eventReset'),
      cards = Array.prototype.slice.call(grid.children);

  function run() {{
    var term = q.value.trim().toLowerCase(),
        cat = catSel.value, lang = langSel.value, suit = suitSel.value, n = 0;
    cards.forEach(function (c) {{
      var hit = (!term || c.dataset.search.indexOf(term) > -1)
        && (!cat || c.dataset.category === cat)
        && (!lang || c.dataset.languages.indexOf(lang) > -1)
        && (!suit || c.dataset.suitable.indexOf(suit) > -1);
      c.hidden = !hit;
      if (hit) n++;
    }});
    count.textContent = n + (n === 1 ? ' event' : ' events');
    grid.hidden = n === 0;
    empty.hidden = n > 0;
  }}

  [q, catSel, langSel, suitSel].forEach(function (el) {{
    el.addEventListener('input', run);
    el.addEventListener('change', run);
  }});

  if (reset) {{
    reset.addEventListener('click', function () {{
      q.value = ''; catSel.value = ''; langSel.value = ''; suitSel.value = '';
      run();
    }});
  }}
}})();
</script>"""

    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": f"Events in {AREA}",
        "url": f"{SITE_URL}/{EVENTS_SLUG}/",
        "description": f"Upcoming events in {AREA}, {CITY}.",
    }

    write(
        OUT / EVENTS_SLUG / "index.html",
        page(
            title=f"Upcoming Events in {AREA} | {SITE_NAME}",
            meta=f"Concerts, workshops, food festivals and community events in {AREA}, {CITY}.",
            canonical=f"{SITE_URL}/{EVENTS_SLUG}/",
            body=body,
            schema=schema,
            depth=1,
        ),
    )


def build_event(ev, events):
    """One event's own page: hero, full info, BookMyShow CTA and related
    events (same category, or overlapping tags)."""
    url = f"{SITE_URL}/{EVENTS_SLUG}/{ev['slug']}/"
    hero_img = event_photo_block(ev, "../../", "event-hero-photo")

    rows = ""

    def add_row(label, value, icon):
        nonlocal rows
        if value:
            rows += f'<div class="row"><dt>{icon} {esc(label)}</dt><dd>{esc(value)}</dd></div>'

    add_row("Venue", ev["venue_name"], "📍")
    add_row("Address", ev["venue_address"], "📍")
    add_row("Date", ev["dates"], "📅")
    add_row("Time", ev["times"], "🕒")
    add_row("Duration", ev["duration"], "⏳")
    add_row("Ticket price", ev["price"], "💰")
    add_row("Age restriction", ev["age_restriction"], "👤")
    add_row("Languages", ev["languages"], "🌐")
    if ev["tags"]:
        add_row("Tags", ", ".join(ev["tags"]), "🏷")
    add_row("Suitable for", ev["suitable_for"], "👥")

    cta_html = ""
    if ev["bookmyshow_url"]:
        cta_html = (
            f'<a class="event-cta" href="{esc(ev["bookmyshow_url"])}" '
            f'target="_blank" rel="noopener noreferrer">'
            f"🎟 Book Tickets on BookMyShow</a>"
        )

    ev_tags = {t.lower() for t in ev["tags"]}
    related = [
        other for other in events
        if other is not ev
        and (
            other["category"] == ev["category"]
            or ev_tags.intersection(t.lower() for t in other["tags"])
        )
    ][:3]
    related_html = ""
    if related:
        related_cards = "".join(event_card(r, root="../../") for r in related)
        related_html = f"""<section class="wrap section">
  <h2 class="section-head">You May Also Like</h2>
  <ul class="event-grid">{related_cards}</ul>
</section>"""

    body = f"""<section class="band" style="--a:{ev['accent']};--t:{ev['tint']}">
  <div class="wrap">
    <nav class="crumbs">
      <a href="../../">Home</a> <span>/</span>
      <a href="../">Events</a> <span>/</span> {esc(ev['title'])}
    </nav>
    <p class="eyebrow">{esc(ev['category'])}</p>
    <h1 class="page-title">{esc(ev['title'])}</h1>
  </div>
</section>
<article class="wrap section event-detail" style="--a:{ev['accent']}">
  {hero_img}
  <p class="lede">{esc(ev['description'])}</p>

  {cta_html}

  <h2 class="section-head">Event information</h2>
  <dl class="rows">{rows}</dl>
</article>
{related_html}"""

    schema = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": ev["title"],
        "description": ev["description"] or ev["meta"],
        "url": url,
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "location": {
            "@type": "Place",
            "name": ev["venue_name"],
            "address": ev["venue_address"],
        },
    }
    if ev["image"]:
        schema["image"] = f"{SITE_URL}/img/events/{ev['image']}"
    if ev["bookmyshow_url"]:
        schema["offers"] = {"@type": "Offer", "url": ev["bookmyshow_url"]}

    write(
        OUT / EVENTS_SLUG / ev["slug"] / "index.html",
        page(
            title=f"{ev['title']} | {SITE_NAME}",
            meta=truncate(ev["meta"] or ev["description"] or ev["title"]),
            canonical=url,
            body=body,
            schema=schema,
            depth=2,
            image=(f"events/{ev['image']}" if ev["image"] else None),
        ),
    )
def build_sitemap(shops, events, blogs):
    urls = [f"{SITE_URL}/", f"{SITE_URL}/{BLOG_SLUG}/", f"{SITE_URL}/{EVENTS_SLUG}/"]
    urls += [f"{SITE_URL}/{c['slug']}/" for c in CATEGORIES]
    urls += [f"{SITE_URL}/{s['category']['slug']}/{s['slug']}/" for s in shops]
    urls += [f"{SITE_URL}/{EVENTS_SLUG}/{e['slug']}/" for e in events]
    urls += [f"{SITE_URL}/{BLOG_SLUG}/{blog['slug']}/" for blog in blogs]

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
    events = load_events()
    blogs, skipped_blogs = load_blogs()

    build_home(shops)
    build_blogs(blogs)

    for blog in blogs:
        build_blog(blog, blogs)

    for cat in CATEGORIES:
        members = build_category(cat, shops)
        for shop in members:
            build_shop(shop, members)

    build_events(events)
    for ev in events:
        build_event(ev, events)

    total_urls = build_sitemap(shops, events, blogs)
    shutil.copy(ASSETS / "style.css", OUT / "style.css")
    if IMAGES.exists() and any(IMAGES.rglob("*")):
        shutil.copytree(IMAGES, OUT / "img", dirs_exist_ok=True)

    missing = [s["title"] for s in shops if not s["blurb"]]
    no_photo = [s for s in shops if not s["image"]]

    print(f"Built {total_urls} pages into {OUT}/")
    for cat in CATEGORIES:
        n = len([s for s in shops if s["category"] is cat])
        print(f"  {cat['name']:<22} {n:>3}  ->  /{cat['slug']}/")
    print(f"  {'Events':<22} {len(events):>3}  ->  /{EVENTS_SLUG}/")
    print(f"\nPhotos: {len(shops) - len(no_photo)} of {len(shops)} listings have one.")
    if no_photo:
        print("Add more as images/<slug>.jpg - the slug is the URL segment above.")
    print(f"Events: {len(events)} in data/events.csv.")
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
