#!/usr/bin/env python3
"""Build the quiz dataset from the NASA JSC Antarctic Meteorite database.

Downloads ANSMET *field* photos (not lab/thin-section photos) for:
  - every non-ordinary-chondrite meteorite from DOM and nearby sites (MIL, MAC, LEW, GRO, QUE),
  - a large random set of DOM ordinary chondrites (H, L, LL), and
  - every terrestrial rock from DOM and the nearby sites.
The pool is deliberately big so players rarely see the same photo twice; how often each
meteorite group appears in the game is set in quiz/index.html (GROUP_WEIGHT), not here.

Output:
  quiz/photos/<SAMPLE>.webp  (NASA's full resolution, 1280 px on the long side; for the quiz and viewer)
  quiz/thumbs/<SAMPLE>.webp  (520 px thumbnails for the album grids)
  To re-encode after changing PHOTO_* / THUMB_* settings, delete quiz/photos and quiz/thumbs.
  quiz/samples.js            (window.SAMPLES = [...])
  scraper/cache/             (raw HTML cache so re-runs are cheap)

Usage: python3 scraper/scrape.py [--ordinary-per-group 60] [--seed 1]
"""
import argparse
import html
import io
import json
import random
import re
import sys
import time
import urllib.request
from pathlib import Path

from PIL import Image

BASE = "https://www-curator.jsc.nasa.gov"
SEARCH = (BASE + "/cfc/GenerateTable.cfc?method=returnSearchTable&returnformat=plain"
          "&samplenumber={prefix}&keyword=&classification=All&weathering=All&fracturing=All"
          "&year=All&site=All&nl=All&nlyear=All&si=&sortOptions=")
TYPE_TABLE = (BASE + "/cfc/GenerateTable.cfc?method=createTable&returnformat=plain"
              "&tabtype={tab}&subclass={sub}&sortOptions=sample")
PETDES = BASE + "/antmet/samples/petdes.cfm?sample={sample}"
IMG = BASE + "/antmet/samples/images/{name}"

METEORITE_SITE = "DOM"
NEARBY_SITES = ["MIL", "MAC", "LEW", "GRO", "QUE"]
TERRESTRIAL_SITES = [METEORITE_SITE] + NEARBY_SITES
# Rare groups that look the same wherever they were found: take every sample with a field photo
# from every ANSMET icefield, via the database's by-type tables (tab code, subclass; "" = all).
ALL_SITE_TYPES = [("IR", ""), ("SI", ""), ("AC", "LUNAR"), ("AC", "MARTIAN")]
DELAY = 0.5  # seconds between requests -- be polite to NASA's server
PHOTO_MAX, PHOTO_QUALITY = 1600, 86   # NASA's originals are 1280 px, so this keeps full resolution
THUMB_MAX, THUMB_QUALITY = 520, 78
UA = "Mozilla/5.0 (ANSMET field-training quiz builder)"

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scraper" / "cache"
OUT = ROOT / "quiz"


def fetch(url, cache_name=None, binary=False):
    if cache_name:
        p = CACHE / cache_name
        if p.exists():
            return p.read_bytes() if binary else p.read_text(errors="replace")
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            break
        except Exception as e:  # noqa: BLE001
            if attempt == 2:
                raise
            print(f"  retry {url}: {e}", file=sys.stderr)
            time.sleep(3)
    time.sleep(DELAY)
    if cache_name:
        p = CACHE / cache_name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return data if binary else data.decode("utf-8", errors="replace")


def text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def search_site(prefix):
    return parse_rows(fetch(SEARCH.format(prefix=prefix), f"search_{prefix}.html"))


def search_type(tab, sub=""):
    """Every sample of one type from all ANSMET sites (the database's by-type tabs)."""
    return parse_rows(fetch(TYPE_TABLE.format(tab=tab, sub=sub), f"type_{tab}_{sub or 'ALL'}.html"))


def parse_rows(t):
    rows = []
    for r in re.findall(r"<tr>(.*?)</tr>", t, re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)
        m = re.search(r"sample=(\w+)", r)
        if len(tds) < 2 or not m:
            continue
        cls = html.unescape(re.sub(r"<[^>]+>", "", tds[1])).strip().split("\n")[0].strip()
        rows.append({"id": m.group(1), "classification": cls})
    return rows


def group_of(cls):
    """Map a detailed classification to a broad, field-guessable group."""
    c = cls.lower()
    if c.startswith("terrestrial"):
        return "Terrestrial"
    if "lunar" in c:
        return "Lunar"
    if re.search(r"martian|shergottite|nakhlite|chassignite|\bsnc\b", c):
        return "Martian"
    if c.startswith("iron"):
        return "Iron"
    if "mesosiderite" in c or "pallasite" in c:
        return "Stony-iron"
    if re.match(r"^(eucrite|howardite|diogenite)", c):
        return "HED achondrite"
    if re.match(r"^(ureilite|winonaite|acapulcoite|lodranite|achon|angrite|aubrite|brachinite)", c):
        return "Other achondrite"
    if re.match(r"^e[hl]?\s?\d|^e[hl]? chon|^enstatite", c):
        return "Enstatite chondrite"
    if re.match(r"^c[a-z]{0,2}\s?\d|^c[a-z]{1,2} ", c):
        return "Carbonaceous chondrite"
    if re.match(r"^(h|l|ll)[\s\d-]", c) or re.match(r"^(h|l|ll) (chon|melt)", c):
        return "Ordinary chondrite"
    return "Other"


def oc_subgroup(cls):
    m = re.match(r"^(LL|L|H)\b|^(LL|L|H)(?=\d)", cls)
    return (m.group(1) or m.group(2)) if m else None


def sample_details(sid):
    t = fetch(PETDES.format(sample=sid), f"petdes/{sid}.html")

    body = text(re.sub(r"<script.*?</script>", "", t, flags=re.S))
    body = body[body.rfind("Sample Number"):]

    def after(label, stop):
        m = re.search(re.escape(label) + r"\s*(.*?)\s*(?:" + stop + ")", body)
        return m.group(1).strip() if m else ""

    # Description is the <td> after the "Macroscopic Description - <author>" cell
    m = re.search(r"Macroscopic Description[^<]*</td>.*?<td[^>]*>(.*?)</td>", t, re.S)
    macro = text(m.group(1)) if m else ""
    if re.match(r"^(no description|none|n/?a)\b", macro, re.I):
        macro = ""
    if macro and macro[0].islower():
        macro = macro[0].upper() + macro[1:]

    photos = re.findall(
        r'href="antmet_img\.cfm\?image=([\w.-]+?\.jpe?g)[^"]*"[^>]*>\s*<img[^>]*alt="(ANSMET[^"]*)"', t, re.S | re.I)
    return {
        "location": after("Location", "Field Number"),
        "dimensions": after("Dimensions (cm)", "Weight"),
        "weight": after("Weight (g)", "Original Classification|Weathering|Macroscopic"),
        "macro": macro,
        "photos": [p[0] for p in photos],
    }


def save_image(name, sid):
    """Write the full-resolution photo and its album thumbnail; returns False if the image is bad."""
    photo, thumb = OUT / "photos" / f"{sid}.webp", OUT / "thumbs" / f"{sid}.webp"
    if photo.exists() and thumb.exists():
        return True
    raw = fetch(IMG.format(name=name), f"img/{name}", binary=True)
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception as e:  # noqa: BLE001
        print(f"  bad image {name}: {e}", file=sys.stderr)
        return False
    for dest, size, q in ((photo, PHOTO_MAX, PHOTO_QUALITY), (thumb, THUMB_MAX, THUMB_QUALITY)):
        out = im.copy()
        out.thumbnail((size, size), getattr(Image, "Resampling", Image).LANCZOS)
        dest.parent.mkdir(parents=True, exist_ok=True)
        out.save(dest, "WEBP", quality=q, method=6)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ordinary-per-group", type=int, default=60,
                    help="how many H, L and LL chondrites each to include")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()
    rng = random.Random(args.seed)

    # 1. Choose samples
    picks = []
    sites = {site: search_site(site) for site in TERRESTRIAL_SITES}
    for site, rows in sites.items():
        print(f"{site}: {len(rows)} samples")

    # Ordinary chondrites: a large random set each of H, L, LL from the Dominion Range
    oc = {"H": [], "L": [], "LL": []}
    for r in sites[METEORITE_SITE]:
        if group_of(r["classification"]) == "Ordinary chondrite":
            sg = oc_subgroup(r["classification"])
            if sg:
                oc[sg].append(r)
    for sg, rows in oc.items():
        for r in rng.sample(rows, min(args.ordinary_per_group, len(rows))):
            picks.append({**r, "group": "Ordinary chondrite"})

    # Every other meteorite (carbonaceous, HED, lunar, iron, ...) from DOM and the nearby sites
    for site in TERRESTRIAL_SITES:
        for r in sites[site]:
            g = group_of(r["classification"])
            if g not in ("Ordinary chondrite", "Terrestrial", "Other"):
                picks.append({**r, "group": g})

    # Irons, stony-irons, lunar and Martian from every ANSMET icefield
    have_ids = {p["id"] for p in picks}
    for tab, sub in ALL_SITE_TYPES:
        rows = search_type(tab, sub)
        new = [r for r in rows if r["id"] not in have_ids and group_of(r["classification"]) != "Other"]
        print(f"all sites {tab} {sub or 'ALL'}: {len(rows)} samples, {len(new)} not already picked")
        for r in new:
            picks.append({**r, "group": group_of(r["classification"])})
            have_ids.add(r["id"])

    for site in TERRESTRIAL_SITES:
        terr = [r for r in sites[site] if group_of(r["classification"]) == "Terrestrial"]
        print(f"{site}: {len(terr)} terrestrial")
        picks += [{**r, "group": "Terrestrial"} for r in terr]

    others = [p for p in picks if p["group"] == "Other"]
    if others:
        print("Unmapped classifications:", sorted({p["classification"] for p in others}))

    # 2. Fetch details + field photo
    out = []
    for i, p in enumerate(picks, 1):
        sid = p["id"]
        try:
            d = sample_details(sid)
        except Exception as e:  # noqa: BLE001
            print(f"[{i}/{len(picks)}] {sid}: page failed ({e})", file=sys.stderr)
            continue
        if not d["photos"]:
            print(f"[{i}/{len(picks)}] {sid}: no field photo, skipped")
            continue
        if not save_image(d["photos"][0], sid):
            continue
        img = OUT / "photos" / f"{sid}.webp"
        name = re.sub(r"^([A-Z]+)(\d+)$", r"\1 \2", sid)
        with Image.open(img) as im:
            w, h = im.size  # the album lays photos out by their real shape
        out.append({
            "id": sid, "name": name, "classification": p["classification"],
            "group": p["group"], "location": d["location"], "dimensions": d["dimensions"],
            "weight": d["weight"], "description": d["macro"], "image": f"photos/{sid}.webp", "thumb": f"thumbs/{sid}.webp", "w": w, "h": h,
            "photo": d["photos"][0],
        })
        print(f"[{i}/{len(picks)}] {sid} {p['classification']}", flush=True)

    OUT.mkdir(exist_ok=True)
    (OUT / "samples.js").write_text(
        "// Generated by scraper/scrape.py from the NASA JSC Antarctic Meteorite database.\n"
        "window.SAMPLES = [\n" + ",\n".join(json.dumps(s, ensure_ascii=False, separators=(",", ":")) for s in out)
        + "\n];\n", encoding="utf-8")
    keep = {f"{s['id']}.webp" for s in out}
    for folder in ("photos", "thumbs"):
        for f in (OUT / folder).glob("*"):
            if f.name not in keep:
                f.unlink()
    old = OUT / "images"  # pre-HD 900 px photos
    if old.exists():
        for f in old.glob("*"):
            f.unlink()
        old.rmdir()
    from collections import Counter
    print("\nDone:", len(out), "samples")
    for g, n in Counter(s["group"] for s in out).most_common():
        print(f"  {n:4d}  {g}")


if __name__ == "__main__":
    main()
