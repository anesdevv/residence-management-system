#!/usr/bin/env python3
"""Fetch the real thing: web pages, app icons and screens, site icons, brand logos, book covers and people.

  source.py page <url> --out assets/web/x.png [--size 1280x800] [--full] [--dark] [--wait 1.5] [--crop x,y,w,h]
                                              [--scale 2]
  source.py app  "<App Store name>" --out assets/logos/x.png [--size 512]
  source.py screens "<App Store name>" --out assets/ref/x/ [--ipad] [--country us]
  source.py site <domain> --out assets/logos/x.png
  source.py logo <simple-icons slug> --out assets/logos/x.svg [--color ffffff]
  source.py book "<title>" [--author "<name>"] --out assets/covers/x.jpg [--pick N]
  source.py person "<name>" --out assets/photos/x.jpg [--site <url>] [--pick N]
  source.py photo "<search>" --out assets/photos/x.jpg [--pick 0]

page    captures the live site with Playwright driving the Google Chrome already installed, in a clean profile
        (no logins or cookies of yours). --size is the viewport in CSS px; the image is --scale times larger (2 by
        default, crisp when the camera pushes in). --full takes the whole scrollable page (scroll beats); --dark asks
        the site for dark mode; --crop keeps a region, in CSS px. Logins, cookie walls and bot checks don't capture:
        open the image and pick another page if it shows one.
app     the App Store icon (iTunes Search API), the real rounded-square icon people know.
screens the app's App Store screenshots at full size (01.png, 02.png ... and screens.json) in the --out folder:
        references to rebuild its screens from with the UI kit, not footage. They are Apple marketing shots (captions,
        device frames, staged data), so they never go on screen themselves.
site    the site's apple-touch-icon, or a 256 px favicon when it has none.
logo    a one-colour brand mark from Simple Icons (CC0), as SVG; --color recolours it.
book    the biggest real front cover of the book's English editions: Open Library's original uploads (it sizes every
        edition's cover) and Google Books' largest image, preferring publisher images and the edition Open Library
        shows for the book over library scans (barcode stickers); prints its size and the other candidates (--pick N
        takes another). Pass --author: a title alone can match a summary or another book.
person  a real photo of a person: the image Wikidata lists for them on Wikimedia Commons, else a Commons file named
        after them, with its credit line (as photo); else a capture of their own site or about page (--site, or the
        website Wikidata lists) cropped to their portrait, credited to the site ("Photo: lennysnewsletter.com"). It
        lists the portrait candidates it found on the page; --pick N takes another.
photo   a freely licensed photo from Wikimedia Commons (public figures, places, products). Writes <out>.credit.txt
        with the line to show on screen ("Photo: <author>, <licence>"); show it small in a corner of the photo.
Each command prints what it saved. Standard library only, except page and person --site (need npx) and --crop
(needs Pillow).
"""
import argparse, json, os, re, struct, subprocess, sys, tempfile, time, unicodedata, urllib.error, urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

UA = "charles-arcade-assets/1.0 (video editing tool)"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/130.0.0.0 Safari/537.36")
SIMPLE_ICONS = "13.0.0"
PLAYWRIGHT = "1.55.0"


def fetch(url, ua=UA, tries=2, timeout=60):
    """(bytes, content type, final url); retries a failed or 5xx request once."""
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.headers.get("Content-Type", ""), r.geturl()
        except urllib.error.HTTPError as e:
            if e.code < 500 or k == tries - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if k == tries - 1:
                raise
        time.sleep(1.5)


def get(url, binary=False):
    data = fetch(url)[0]
    return data if binary else json.loads(data)


def save(out, data):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    print(f"saved: {out} ({len(data):,} bytes)")
    return out


def image_size(b):
    """(width, height) of a PNG, GIF or JPEG, else None."""
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", b[16:24])
    if b[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", b[6:10])
    if b[:2] != b"\xff\xd8":
        return None
    i = 2
    while i < len(b) - 9:
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        if m in (0xD8, 0x01, 0xFF) or 0xD0 <= m <= 0xD7:
            i += 2 if m != 0xFF else 1
            continue
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    return None


def plain(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def run_playwright(script, args):
    """Run a Node script with Playwright (from npx's cache) in reach; returns its stdout."""
    with tempfile.TemporaryDirectory() as d:
        js = Path(d) / "run.js"
        js.write_text(script)
        r = subprocess.run(["npx", "--yes", "-p", f"playwright@{PLAYWRIGHT}", "node", str(js)] + args,
                           capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"capture failed: {(r.stderr or r.stdout)[-600:]}")
    return r.stdout


def cmd_page(a):
    w, h = (int(x) for x in a.size.split("x"))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["npx", "--yes", f"playwright@{PLAYWRIGHT}", "screenshot", "--channel", "chrome",
           "--viewport-size", f"{w},{h}", "--wait-for-timeout", str(int(a.wait * 1000))]
    if a.scale == 2:
        cmd[6:6] = ["--device", "Desktop Chrome HiDPI"]
    if a.full:
        cmd.append("--full-page")
    if a.dark:
        cmd += ["--color-scheme", "dark"]
    r = subprocess.run(cmd + [a.url, str(out)], capture_output=True, text=True)
    if r.returncode or not out.exists():
        sys.exit(f"capture failed: {r.stderr[-600:] or r.stdout[-600:]}")
    if a.crop:
        from PIL import Image  # only --crop needs Pillow (run it with the repo venv)
        im = Image.open(out)
        x, y, cw, ch = (int(v) * a.scale for v in a.crop.split(","))
        im.crop((x, y, x + cw, y + ch)).save(out)
    print(f"saved: {out}; open it: a login wall or cookie banner means pick another page")


def find_app(name, country="us"):
    q = urllib.parse.urlencode({"term": name, "entity": "software", "limit": 5, "country": country})
    res = get(f"https://itunes.apple.com/search?{q}").get("results", [])
    if not res:
        sys.exit(f"no App Store app found for '{name}'")
    exact = [r for r in res if plain(r["trackName"]).split(":")[0].strip() == plain(name).strip()]
    return (exact or res)[0], res


def cmd_app(a):
    q = urllib.parse.urlencode({"term": a.name, "entity": "software", "limit": 5})
    res = get(f"https://itunes.apple.com/search?{q}").get("results", [])
    if not res:
        sys.exit(f"no App Store app found for '{a.name}'")
    app = res[0]
    url = re.sub(r"/\d+x\d+bb\.(jpg|png)$", f"/{a.size}x{a.size}bb.png", app["artworkUrl512"])
    save(a.out, get(url, binary=True))
    print(f"app: {app['trackName']} by {app.get('sellerName', '?')}"
          + (f" (other matches: {', '.join(r['trackName'] for r in res[1:4])})" if len(res) > 1 else ""))


def cmd_screens(a):
    app, res = find_app(a.name, a.country)
    urls = app.get("ipadScreenshotUrls" if a.ipad else "screenshotUrls") or []
    kind = "iPad" if a.ipad else "iPhone"
    if not urls:
        other = app.get("screenshotUrls" if a.ipad else "ipadScreenshotUrls") or []
        if not other:
            sys.exit(f"{app['trackName']} lists no App Store screenshots in the {a.country.upper()} store")
        urls, kind = other, ("iPhone" if a.ipad else "iPad")
        print(f"note: no {'iPad' if a.ipad else 'iPhone'} screenshots; these are the {kind} ones")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    full = [re.sub(r"/[^/]+$", "/9999x9999bb.png", u) for u in urls]   # the store serves its full size

    def one(k_u):
        k, u = k_u
        data = fetch(u)[0]
        p = out / f"{k + 1:02d}.png"
        p.write_bytes(data)
        return p, image_size(data), len(data)
    with ThreadPoolExecutor(6) as pool:
        got = list(pool.map(one, enumerate(full)))
    for p, size, n in got:
        print(f"saved: {p} ({size[0]}x{size[1]}, {n:,} bytes)" if size else f"saved: {p} ({n:,} bytes)")
    (out / "screens.json").write_text(json.dumps({
        "app": app["trackName"], "seller": app.get("sellerName"), "store": app.get("trackViewUrl"),
        "device": kind, "country": a.country, "files": [p.name for p, _, _ in got], "sources": urls,
        "use": "references for rebuilding the app's screens with the UI kit; App Store marketing shots, never shown "
               "as footage"}, indent=1) + "\n")
    others = [r["trackName"] for r in res if r is not app][:3]
    print(f"app: {app['trackName']} by {app.get('sellerName', '?')}"
          + (f" (other matches: {', '.join(others)})" if others else ""))
    print(f"{len(got)} {kind} App Store screenshots in {out}/ (with screens.json). They are REFERENCES, not footage: "
          "Apple marketing shots with captions, device frames and staged data. Rebuild the screen you need with the "
          "UI kit from them (exact layout, copy, colours) with the real icon and name; never show these images.")


def cmd_site(a):
    for url in (f"https://{a.domain}/apple-touch-icon.png", f"https://www.{a.domain}/apple-touch-icon.png"):
        try:
            data = get(url, binary=True)
            if data[:4] == b"\x89PNG" and len(data) > 1500:
                save(a.out, data)
                return
        except Exception:
            pass
    save(a.out, get(f"https://www.google.com/s2/favicons?domain={a.domain}&sz=256", binary=True))


def cmd_logo(a):
    try:
        svg = get(f"https://cdn.jsdelivr.net/npm/simple-icons@{SIMPLE_ICONS}/icons/{a.slug}.svg", binary=True).decode()
    except Exception:
        sys.exit(f"no Simple Icons logo '{a.slug}': check the slug at simpleicons.org, or use `site`/`app`")
    if a.color:
        svg = svg.replace("<svg ", f'<svg fill="#{a.color.lstrip("#")}" ', 1)
    save(a.out, svg.encode())


# ---- book covers ----

NOT_THE_BOOK = re.compile(r"\b(summary|summaries|workbook|study guide|analysis|notes on|key takeaways|cliffsnotes|"
                          r"quicklet|companion|journal|audiobook|audio cd)\b", re.I)


def title_words(s):
    return [w for w in re.findall(r"[a-z0-9$]+", plain(s)) if w not in ("the", "a", "an", "of", "and")]


def same_book(want, have):
    have_words = set(title_words(have))
    return all(w in have_words for w in title_words(want)) and not (NOT_THE_BOOK.search(have)
                                                                  and not NOT_THE_BOOK.search(want))


def english_edition(ed):
    langs = [l.get("key", "") for l in ed.get("languages", []) or []]
    if langs:
        return "/languages/eng" in langs
    isbns = (ed.get("isbn_13") or []) + (ed.get("isbn_10") or [])
    return not isbns or any(english_isbn(i) for i in isbns)


def english_isbn(i):
    i = i.replace("-", "")
    return i.startswith(("9780", "9781")) if len(i) == 13 else (len(i) == 10 and i[0] in "01")


def open_library_covers(title, author):
    params = {"title": title, "limit": 8, "fields": "key,title,author_name,cover_i,edition_count,first_publish_year"}
    if author:
        params["author"] = author
    docs = [d for d in get("https://openlibrary.org/search.json?" + urllib.parse.urlencode(params)).get("docs", [])
            if same_book(title, d.get("title", ""))]
    if not docs:
        return None, [], [], []
    work = docs[0]
    eds = get(f"https://openlibrary.org{work['key']}/editions.json?limit=100").get("entries", [])
    covers, isbns = {}, []                        # cover id -> edition label
    if work.get("cover_i"):
        covers[work["cover_i"]] = ""
    for e in eds:
        label = " ".join(x for x in (e.get("title", ""), e.get("subtitle", "")) if x)
        if not english_edition(e) or not same_book(title, label):
            continue
        year = re.search(r"\d{4}", e.get("publish_date", "") or "")
        tag = f"{label[:60]}, {', '.join((e.get('publishers') or ['?'])[:1])}{' ' + year.group(0) if year else ''}"
        for c in e.get("covers") or []:
            if c and c > 0:
                covers[c] = covers.get(c) or tag
        isbns += [i for i in (e.get("isbn_13") or []) + (e.get("isbn_10") or []) if english_isbn(i)]

    def meta(c):
        try:
            return c, get(f"https://covers.openlibrary.org/b/id/{c}.json")
        except Exception:
            return c, None
    with ThreadPoolExecutor(8) as pool:
        metas = list(pool.map(meta, list(covers)[:40]))
    rep_ed = next((m.get("olid") for c, m in metas if m and c == work.get("cover_i")), None)
    rep_isbns = []
    if rep_ed:
        try:
            ed = get(f"https://openlibrary.org/books/{rep_ed}.json")
            rep_isbns = [i for i in (ed.get("isbn_13") or []) + (ed.get("isbn_10") or []) if english_isbn(i)]
            covers[work["cover_i"]] = covers[work["cover_i"]] or ed.get("title", "")
        except Exception:
            pass
    cands = []
    for c, m in metas:
        if not m or not m.get("width") or not m.get("height"):
            continue
        src = m.get("source_url") or ""
        kind = "library scan" if "archive.org" in src else "publisher image" if re.search(
            r"amazon|google|ingram|bookshop|barnes|penguin|harper|simon|macmillan|hachette", src) else "upload"
        cands.append({"from": "Open Library", "w": m["width"], "h": m["height"], "kind": kind,
                      "rep": c == work.get("cover_i") or m.get("olid") == rep_ed, "label": covers[c],
                      "url": f"https://covers.openlibrary.org/b/id/{c}.jpg?default=false", "data": None})
    return work, cands, rep_isbns + [i for i in dict.fromkeys(isbns) if i not in rep_isbns], rep_isbns


def google_covers(title, author, isbns, rep_isbns):
    """Google Books' largest front covers for the API's matches (when its shared quota allows) and these ISBNs."""
    vids = {}
    q = f'intitle:"{title}"' + (f" inauthor:{author}" if author else "")
    try:
        api = get("https://www.googleapis.com/books/v1/volumes?" +
                  urllib.parse.urlencode({"q": q, "maxResults": 10, "printType": "books"}))
        for it in api.get("items", []):
            vi = it.get("volumeInfo", {})
            label = " ".join(x for x in (vi.get("title", ""), vi.get("subtitle", "")) if x)
            if same_book(title, label) and (vi.get("language") in (None, "en")):
                vids.setdefault(it["id"], (label[:60], False))
    except Exception:
        pass                                      # the anonymous quota is often used up: the ISBNs still work

    def by_isbn(isbn):
        try:
            data, _, url = fetch(f"https://books.google.com/books?vid=ISBN{isbn}", ua=BROWSER_UA)
            m = re.search(r"[?&]id=([A-Za-z0-9_-]{12})", url) or re.search(r"books\?id=([A-Za-z0-9_-]{12})",
                                                                         data.decode("utf8", "ignore"))
            return isbn, m.group(1) if m else None
        except Exception:
            return isbn, None
    with ThreadPoolExecutor(8) as pool:
        for isbn, vid in pool.map(by_isbn, isbns[:10]):
            if vid:
                vids.setdefault(vid, (f"ISBN {isbn}", isbn in rep_isbns))

    def cover(item):
        vid, (label, rep) = item
        try:
            data, ctype, _ = fetch(f"https://books.google.com/books/content?id={vid}&printsec=frontcover&img=1"
                                   f"&zoom=1&fife=w1600-h2400", ua=BROWSER_UA)
        except Exception:
            return None
        size = image_size(data)
        # a missing cover comes back as an "image not available" PNG or a blurry grey generic book
        if "jpeg" not in ctype or not size or len(data) / (size[0] * size[1]) < 0.035:
            return None
        return {"from": "Google Books", "w": size[0], "h": size[1], "kind": "publisher image", "rep": rep,
                "label": label, "url": f"https://books.google.com/books?id={vid}", "data": data}
    with ThreadPoolExecutor(8) as pool:
        return [c for c in pool.map(cover, list(vids.items())[:12]) if c]


def cmd_book(a):
    work, cands, isbns, rep_isbns = open_library_covers(a.title, a.author)
    cands += google_covers(a.title, a.author, isbns, rep_isbns)
    cands = [c for c in cands if 1.15 <= c["h"] / c["w"] <= 1.9]          # a book's shape: not audiobook squares
    if not cands:
        sys.exit(f"no cover found for '{a.title}'" + ("" if a.author else ": try --author"))
    # big enough and not a library copy's scan first, then the edition Open Library shows, then publisher
    # images, then size
    cands.sort(key=lambda c: (c["h"] >= 800 and c["kind"] != "library scan", c["rep"], c["kind"] == "publisher image",
                              min(c["h"], 2400), c["h"]), reverse=True)
    if a.pick >= len(cands):
        sys.exit(f"--pick {a.pick}: only {len(cands)} candidates")
    for i, c in enumerate(cands[:8]):
        print(f"  {i}: {c['w']}x{c['h']} {c['from']}, {c['kind']}{', the edition it shows' if c['rep'] else ''}"
              f"{': ' + c['label'] if c['label'] else ''}")
    c = cands[a.pick]
    data = c["data"]
    if data is None:
        for k in range(3):                        # archive.org sometimes answers with an error page
            data = fetch(c["url"], timeout=120)[0]
            if image_size(data):
                break
            time.sleep(2)
    size = image_size(data)
    if not size:
        sys.exit(f"the cover at {c['url']} did not download as an image; try --pick {a.pick + 1}")
    save(a.out, data)
    by = ", ".join((work or {}).get("author_name", []) or ["?"])
    print(f"book: {(work or {}).get('title', a.title)} by {by}; cover {size[0]}x{size[1]} px from {c['from']} "
          f"({c['kind']})" + ("" if size[1] >= 800 else "; under 800 px tall: the largest real cover found"))
    print("open it: a barcode sticker, a library stamp, another edition's design or a different book means "
          "--pick another")


# ---- photos and people ----

def commons_info(title):
    q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
                                "iiurlwidth": 1600, "format": "json"})
    pages = get(f"https://commons.wikimedia.org/w/api.php?{q}").get("query", {}).get("pages", {})
    for p in pages.values():
        if p.get("imageinfo"):
            return p["imageinfo"][0]
    return None


def save_commons(info, out):
    meta = info.get("extmetadata", {})
    strip = lambda s: re.sub(r"<[^>]+>", "", s or "").strip()
    artist = strip(meta.get("Artist", {}).get("value")) or "Unknown"
    lic = strip(meta.get("LicenseShortName", {}).get("value")) or "see source"
    out = save(out, get(info.get("thumburl") or info["url"], binary=True))
    credit = f"Photo: {artist}, {lic}"
    Path(str(out) + ".credit.txt").write_text(credit + "\n" + info.get("descriptionurl", "") + "\n")
    return out, credit


def cmd_photo(a):
    q = urllib.parse.urlencode({"action": "query", "generator": "search", "gsrnamespace": 6, "gsrsearch": a.query,
                                "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|extmetadata|mime",
                                "iiurlwidth": 1600, "format": "json"})
    pages = sorted(get(f"https://commons.wikimedia.org/w/api.php?{q}").get("query", {}).get("pages", {}).values(),
                   key=lambda p: p.get("index", 99))
    pages = [p for p in pages if p.get("imageinfo") and p["imageinfo"][0].get("mime") in ("image/jpeg", "image/png")]
    if len(pages) <= a.pick:
        sys.exit(f"no photo found for '{a.query}'")
    for i, p in enumerate(pages[:5]):
        print(f"  {i}: {p['title']}")
    p = pages[a.pick]
    out, credit = save_commons(p["imageinfo"][0], a.out)
    print(f"picked {pages[a.pick]['title']}; credit: {credit} (written to {out}.credit.txt)")


def wikidata_person(name):
    """(label, description, [Commons file names], official website) of the best Wikidata match that is a human."""
    q = urllib.parse.urlencode({"action": "wbsearchentities", "search": name, "language": "en", "type": "item",
                                "limit": 6, "format": "json"})
    hits = get(f"https://www.wikidata.org/w/api.php?{q}").get("search", [])
    if not hits:
        return None
    q = urllib.parse.urlencode({"action": "wbgetentities", "ids": "|".join(h["id"] for h in hits), "format": "json",
                                "props": "claims|labels|descriptions", "languages": "en"})
    ents = get(f"https://www.wikidata.org/w/api.php?{q}").get("entities", {})
    want = plain(name).strip()
    best = None
    for h in hits:
        e = ents.get(h["id"], {})
        claims = e.get("claims", {})
        vals = lambda p: [c.get("mainsnak", {}).get("datavalue", {}).get("value") for c in claims.get(p, [])]
        if not any(isinstance(v, dict) and v.get("id") == "Q5" for v in vals("P31")):
            continue
        label = e.get("labels", {}).get("en", {}).get("value", h.get("label", ""))
        found = (label, e.get("descriptions", {}).get("en", {}).get("value", ""),
                 [v for v in vals("P18") if isinstance(v, str)], next((v for v in vals("P856") if v), None))
        if plain(label).strip() == want and (found[2] or not best):
            best = found
            if found[2]:
                break
        elif not best:
            best = found
    return best


def commons_named(name):
    """Commons photos whose file name has the person's whole name in it, as a phrase ("Harry Dry", not "Dry stone
    wall, top of Harry's Bank")."""
    q = urllib.parse.urlencode({"action": "query", "list": "search", "srnamespace": 6, "srsearch": f'"{name}"',
                                "srlimit": 20, "format": "json"})
    parts = re.findall(r"[a-z]+", plain(name))
    phrase = re.compile(r"(?<![a-z])" + r"[^a-z]+".join(parts) + r"(?![a-z])")
    hits = get(f"https://commons.wikimedia.org/w/api.php?{q}").get("query", {}).get("search", [])
    return [h["title"] for h in hits if phrase.search(plain(h["title"]))
            and h["title"].lower().endswith((".jpg", ".jpeg", ".png"))]


PORTRAIT_JS = r"""
const path = require('path'), fs = require('fs');
const bin = (process.env.PATH || '').split(path.delimiter).find(p => fs.existsSync(path.join(p, '..', 'playwright', 'package.json')));
const { chromium } = require(path.join(bin, '..', 'playwright'));
const bigger = u => {                          // the same image, larger: behind an image proxy, or a bigger size
  const out = [];
  const inner = /(https?%3A%2F%2F[^?&#]+)/i.exec(u) || /[?&]url=([^&]+)/.exec(u);
  if (inner) { try { out.push(new URL(decodeURIComponent(inner[1]), u).href); } catch (e) {} }
  out.push(u.replace(/([,/])w_\d+(,h_\d+)?/g, (m, a) => `${a}w_1200`).replace(/,c_\w+/g, ''),
           u.replace(/([?&])(w|width)=\d+/g, '$1$2=1200').replace(/([?&])(h|height)=\d+&?/g, '$1'),
           u.replace(/=s\d+(?=-|$)/, '=s1200'), u.replace(/\/tr:[^/]+\//, '/'));
  return [...new Set(out)].filter(x => x !== u);
};
(async () => {
  const [url, out, name, pick] = process.argv.slice(2);
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2, locale: 'en-US' });
  const page = await ctx.newPage();
  try { await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 }); }
  catch (e) { try { await page.waitForLoadState('load', { timeout: 10000 }); } catch (e2) {} }
  await page.waitForTimeout(1200);
  await page.evaluate(async () => {            // scroll down and back so lazy images load
    for (let y = 0; y < Math.min(document.body.scrollHeight, 9000); y += 700) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 150)); }
    window.scrollTo(0, 0);
  });
  await page.waitForTimeout(1000);
  const cands = await page.evaluate((name) => {
    const parts = name.toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '').split(/\s+/).filter(p => p.length > 1);
    const out = [];
    let n = 0;
    for (const el of document.querySelectorAll('body *')) {
      const tag = el.tagName.toLowerCase();
      const r = el.getBoundingClientRect();
      if (r.width < 36 || r.height < 36) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity) < 0.2) continue;
      let src = '', nat = [0, 0], srcs = [];
      if (tag === 'img') {
        nat = [el.naturalWidth || 0, el.naturalHeight || 0];
        if (nat[0] < 40 || nat[1] < 40) continue;
        src = el.currentSrc || el.src || '';
        srcs = (el.getAttribute('srcset') || '').split(',').map(x => x.trim().split(/\s+/)).filter(x => x[0])
          .map(x => [new URL(x[0], location.href).href, parseFloat(x[1]) || 0]).sort((a, b) => b[1] - a[1]).map(x => x[0]);
      } else {
        const m = /url\(["']?([^"')]+)/.exec(cs.backgroundImage || '');
        if (!m || m[1].startsWith('data:')) continue;
        src = new URL(m[1], location.href).href;
      }
      let box = el, text = '';                 // the words next to it: the smallest box around it with a little text
      for (let k = 0; k < 4 && box.parentElement; k++) {
        box = box.parentElement;
        const t = (box.innerText || '').trim();
        if (t.length > 300) break;
        text = t;
      }
      const file = decodeURIComponent(src.split('?')[0].split('/').pop() || '');
      const said = [el.alt, el.title, el.getAttribute('aria-label'), file].join(' ').toLowerCase();
      const near = (said + ' ' + String(el.className || '') + ' ' + el.id + ' ' + text).toLowerCase();
      let s = 0; const why = [];
      const ownNamed = parts.filter(p => said.includes(p)).length, named = parts.filter(p => near.includes(p)).length;
      const altSays = (el.alt || el.title || '').trim().length > 2;
      if (ownNamed === parts.length) { s += 10; why.push('named in its own alt or file name'); }
      else if (ownNamed) { s += 3; why.push('first or last name'); }
      else if (named === parts.length) { s += altSays ? 1 : 5; why.push(altSays ? 'named nearby, its alt names something else' : 'named nearby'); }
      if (/headshot|portrait|profile|avatar|author|founder|about|\bbio\b|selfie|\bme\b|photo of/.test(near)) { s += 3; why.push('portrait words'); }
      if (/logo|icon|sprite|badge|emoji|banner|\bbook|cover|product|screenshot|thumbnail|chart|graph|illustration|pattern|background|mockup|artwork|episode|course|podcast/.test(said)) { s -= 4; why.push('other words'); }
      if (/\.svg(\?|$)/.test(src) || src.startsWith('data:image/svg')) { s -= 8; why.push('svg'); }
      const ar = r.width / r.height;
      if (ar >= 0.6 && ar <= 1.45) { s += 3; why.push('portrait shape'); } else if (ar >= 1.6) { s -= 3; why.push('video shape'); } else if (ar < 0.4) s -= 4;
      if (parseFloat(cs.borderRadius) >= Math.min(r.width, r.height) * 0.3) { s += 2; why.push('round'); }
      if (r.width > innerWidth * 0.7 || r.width * r.height > innerWidth * innerHeight * 0.35) { s -= 5; why.push('page-wide'); }
      s += Math.max(-3, Math.min(3, Math.log2(r.width * r.height / 40000)));
      if (r.top + window.scrollY < window.innerHeight * 2) s += 1;
      el.setAttribute('data-arcade-cand', String(n));
      out.push({ n, score: Math.round(s * 10) / 10, w: Math.round(r.width), h: Math.round(r.height), nat, tag, src, srcs,
                 alt: (el.alt || '').slice(0, 60), why: why.join(', ') });
      n++;
    }
    return out.sort((a, b) => b.score - a.score);
  }, name);
  if (!cands.length) { console.log(JSON.stringify({ error: 'no images on the page (a block page or a script-only site?)' })); await browser.close(); return; }
  const chosen = cands[Math.min(parseInt(pick || '0', 10), cands.length - 1)];
  let saved = null, how = 'as the page shows it';
  if (/^https?:/.test(chosen.src)) {           // the image itself, at its largest, alone on a page
    const ctx1 = await browser.newContext({ deviceScaleFactor: 1, viewport: { width: 800, height: 800 } });
    for (const u of [...bigger(chosen.src), ...chosen.srcs, chosen.src]) {
      try {
        const p = await ctx1.newPage();
        const resp = await p.goto(u, { timeout: 20000 });
        if (!resp || !resp.ok() || !/^image\//.test(resp.headers()['content-type'] || '') || /svg/.test(resp.headers()['content-type'])) { await p.close(); continue; }
        const size = await p.evaluate(() => { const i = document.querySelector('img'); return i ? [i.naturalWidth, i.naturalHeight] : null; });
        if (!size || size[0] < Math.max(300, chosen.w * 2) * 0.9) { await p.close(); continue; }
        const fmt = /\.png$/i.test(out) ? 'image/png' : 'image/jpeg';
        const data = await p.evaluate((fmt) => {     // the decoded image through a canvas: any format in, png or jpg out
          const i = document.querySelector('img'), c = document.createElement('canvas');
          c.width = i.naturalWidth; c.height = i.naturalHeight;
          const g = c.getContext('2d');
          if (fmt === 'image/jpeg') { g.fillStyle = '#ffffff'; g.fillRect(0, 0, c.width, c.height); }
          g.drawImage(i, 0, 0);
          return c.toDataURL(fmt, 0.95);
        }, fmt);
        fs.writeFileSync(out, Buffer.from(data.split(',')[1], 'base64'));
        saved = size; how = 'the image file itself, at ' + size[0] + 'x' + size[1];
        await p.close();
        break;
      } catch (e) {}
    }
  }
  if (!saved) {
    await page.evaluate(() => {                  // hide cookie bars, sticky headers and chat bubbles
      for (const el of document.querySelectorAll('body *')) {
        const p = getComputedStyle(el).position;
        if ((p === 'fixed' || p === 'sticky') && !el.querySelector('[data-arcade-cand]') && !el.hasAttribute('data-arcade-cand')) el.style.setProperty('visibility', 'hidden', 'important');
      }
    });
    const el = await page.$(`[data-arcade-cand="${chosen.n}"]`);
    await el.scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
    await el.screenshot({ path: out });
  }
  console.log(JSON.stringify({ chosen, cands: cands.slice(0, 10).map(c => ({ ...c, srcs: undefined })), title: await page.title(), how }));
  await browser.close();
})().catch(e => { console.log(JSON.stringify({ error: String(e) })); process.exit(0); });
"""


def capture_portrait(site, name, out, pick):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = run_playwright(PORTRAIT_JS, [site, str(out.resolve()), name, str(pick)])
    line = next((l for l in raw.splitlines()[::-1] if l.startswith("{")), "{}")
    res = json.loads(line)
    if res.get("error") or not out.exists():
        sys.exit(f"no portrait captured from {site}: {res.get('error', raw[-300:])}")
    for i, c in enumerate(res["cands"]):
        mark = ">" if c["n"] == res["chosen"]["n"] else " "
        print(f" {mark}{i}: {c['w']}x{c['h']} on the page, score {c['score']}"
              f" ({c['why'] or 'size only'}) {c['alt'] or c['src'].split('?')[0].rsplit('/', 1)[-1][:50]}")
    host = urllib.parse.urlparse(site).netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    credit = f"Photo: {host}"
    Path(str(out) + ".credit.txt").write_text(credit + "\n" + site + "\n")
    size = image_size(out.read_bytes())
    print(f"saved: {out} ({size[0]}x{size[1]} px, {res.get('how', '')})" if size else f"saved: {out}")
    if size and min(size) < 400:
        print(f"note: only {size[0]}x{size[1]}: find a page with a bigger portrait (an about, press or speaker page) "
              f"or show it small")
    print(f"person: {name} from their site {site} ({res.get('title', '')[:60]}); credit: {credit} (written to "
          f"{out}.credit.txt). Open it: if it is not their portrait, --pick another candidate above")


def cmd_person(a):
    found = None
    try:
        found = wikidata_person(a.name)
    except Exception as e:
        print(f"note: Wikidata lookup failed ({e}); trying Commons search")
    files = ["File:" + f for f in (found[2] if found else [])]
    try:
        files = files or commons_named(a.name)
    except Exception:
        pass
    for i, f in enumerate(files[:5]):
        print(f"  {i}: {f}")
    if a.pick < len(files):
        info = commons_info(files[a.pick])
        if info and info.get("mime") in ("image/jpeg", "image/png"):
            out, credit = save_commons(info, a.out)
            who = f"{found[0]} ({found[1]})" if found and found[1] else a.name
            how = "the photo Wikidata lists for them" if found and found[2] else "a file named after them"
            print(f"person: {who}; {how}, {files[a.pick]}, from Wikimedia Commons; credit: {credit} (written to "
                  f"{out}.credit.txt). Open it: check it is them")
            return
    site = a.site or (found[3] if found else None)
    if not site:
        sys.exit(f"no free photo of {a.name} on Wikimedia Commons, and no website for them on Wikidata: pass "
                 f"--site <their own site or about page> to capture their portrait from it")
    print(f"no free photo of {a.name} on Wikimedia Commons; capturing their portrait from "
          f"{'their site' if a.site else 'the website Wikidata lists'}: {site}")
    capture_portrait(site, a.name, a.out, 0 if files else a.pick)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("page"); p.add_argument("url"); p.add_argument("--out", required=True)
    p.add_argument("--size", default="1280x800"); p.add_argument("--full", action="store_true")
    p.add_argument("--dark", action="store_true"); p.add_argument("--wait", type=float, default=1.5)
    p.add_argument("--crop"); p.add_argument("--scale", type=int, default=2, choices=[1, 2])
    s = sub.add_parser("app"); s.add_argument("name"); s.add_argument("--out", required=True)
    s.add_argument("--size", type=int, default=512)
    sc = sub.add_parser("screens"); sc.add_argument("name"); sc.add_argument("--out", required=True)
    sc.add_argument("--ipad", action="store_true"); sc.add_argument("--country", default="us")
    t = sub.add_parser("site"); t.add_argument("domain"); t.add_argument("--out", required=True)
    l = sub.add_parser("logo"); l.add_argument("slug"); l.add_argument("--out", required=True); l.add_argument("--color")
    b = sub.add_parser("book"); b.add_argument("title"); b.add_argument("--author"); b.add_argument("--out", required=True)
    b.add_argument("--pick", type=int, default=0)
    pe = sub.add_parser("person"); pe.add_argument("name"); pe.add_argument("--out", required=True)
    pe.add_argument("--site", help="their own site or about page, when Commons has no free photo")
    pe.add_argument("--pick", type=int, default=0)
    h = sub.add_parser("photo"); h.add_argument("query"); h.add_argument("--out", required=True)
    h.add_argument("--pick", type=int, default=0)
    a = ap.parse_args()
    {"page": cmd_page, "app": cmd_app, "screens": cmd_screens, "site": cmd_site, "logo": cmd_logo, "book": cmd_book,
     "person": cmd_person, "photo": cmd_photo}[a.cmd](a)


if __name__ == "__main__":
    main()
