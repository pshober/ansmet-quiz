# Dominion Range Field Quiz

**Play it: <https://planetarypat.com/ansmet-quiz/>**

An unofficial photo quiz for anyone heading out to search for meteorites in Antarctica: is the rock
in this field photo a meteorite or an Earth rock, and if it's a meteorite, which group? Every photo
is an ANSMET field photo taken on the ice at collection time, from the public
[NASA JSC Antarctic Meteorite database](https://www-curator.jsc.nasa.gov/antmet/classdb.cfm).

This is an independent study aid, not an ANSMET or NASA product, and it doesn't speak for either.

## Play it

Use the link above, or open `quiz/index.html` in a browser. It works offline too: copy the whole
`quiz/` folder (or a zip of it) and open `index.html`. Progress is saved in each player's own browser.

- **Learn mode**: answer, then see the classification, the curator's field description and a
  tip for that meteorite group. Groups you get wrong come up more often (gently: each group's share
  stays between 0.5x and 2x its base share). Earth rocks are never more than half of a round
  (40–50%, an exact count per round), so the quiz never trains people to leave rocks on the ice.
- **Test mode**: 30 rocks, the same mix every time, no feedback until the end. Scored out of 100
  (2 points per right call, 1 more for naming a meteorite's group), with a per-group breakdown
  and test history.
- **Field notebook**: recent accuracy per group, across both modes.
- **How the quiz works** (`#how`): the mix in each mode next to what was really collected at the
  Dominion Range, and how Learn mode adapts. Built from the same settings the quiz uses.
- **See the meteorites**: a photo album for each meteorite type (and Earth rocks), grouped by
  subtype, e.g. pallasites vs mesosiderites. Tap a photo for a large view with the curator's notes;
  arrows or swipe to move through the album. The common types open on a representative 60 photos
  that cover every subtype (with "Show all"); rarer types show every photo. Each album has its own
  link to share, e.g. <https://planetarypat.com/ansmet-quiz/#album-iron>. Photos opened in the album
  count as seen, so the quiz prefers photos you haven't studied.

Progress (notebook, scores, photos seen) is stored in each player's own browser on their own device.
Nothing is sent anywhere, so every team member has their own, and it doesn't sync between devices.

## What's in the photo pool

Built by `scraper/scrape.py`:

- every terrestrial rock from the Dominion Range (DOM) and nearby icefields: Miller Range (MIL),
  MacAlpine Hills (MAC), Lewis Cliff (LEW), Grosvenor Mountains (GRO), Queen Alexandra Range (QUE)
- every non-ordinary-chondrite meteorite from those same sites
- every iron, stony-iron, lunar and Martian meteorite from **any** ANSMET icefield (they look the
  same wherever they're found, and they're rare), via the database's by-type tables
- 60 each of H, L and LL ordinary chondrites from DOM (random, `--seed 1`)

Only field photos are used (no lab or thin-section photos), at NASA's full resolution (1280 px on
the long side) as WebP quality 86 (~160 KB each) in `quiz/photos/`, plus 520 px thumbnails in
`quiz/thumbs/` for the album grids. To re-encode after changing the size/quality settings at the
top of the scraper, delete those two folders and run it again.
Samples without a field photo are skipped. The pool is large on purpose, so players learn the
features rather than memorising individual photos. Current pool: 1,198 photos (143 Earth rocks,
171 ordinary chondrites, 508 carbonaceous, 122 HED, 99 irons, 43 stony-irons, 42 enstatite,
33 other achondrites, 26 lunar, 11 Martian).

## Tuning the mix

How often each group appears is set by `MIX` near the top of the script in `quiz/index.html`
(percent of rocks shown). The photo pool doesn't need to change when you retune it.

## Rebuilding the data

```
python3 scraper/scrape.py            # options: --ordinary-per-group 60 --seed 1
```

Needs Python 3 and Pillow. Pages and original photos are cached in `scraper/cache/` (not in git),
so re-runs only fetch what's new. The scraper waits 0.5 s between requests to go easy on NASA's server.
It also stamps a content hash on the page's `samples.js?v=…` link, because Cloudflare tells browsers to
cache `.js` files for 4 hours; without the stamp, a browser could pair the new page with an old photo list.

## Tools

Browser tests (`tools/test-harness.html`) load the quiz in a frame, play it automatically with known
answers, and write what happened to a hidden `out` block. Serve the repo root and dump the page:

```
python3 -m http.server 8000
google-chrome --headless=new --virtual-time-budget=120000 --dump-dom \
  "http://127.0.0.1:8000/tools/test-harness.html?s=learn"
```

Scenarios: `s=learn`, `s=test` (three tests in a row), `s=adapt&rounds=12` (checks the adaptive mix),
`s=album` (every album, the viewer, show-all and navigation) and `s=deeplink&hash=album-iron`.
Each ends with `page errors: none` when all is well.

The link-preview card (`quiz/og-card.jpg`) comes from `tools/og-card.html`: screenshot it at
1200 x 800 in Chrome and keep the top 1200 x 630.

## Deploying

Pushing to `main` deploys the `quiz/` folder to GitHub Pages
([`.github/workflows/pages.yml`](.github/workflows/pages.yml)). GitHub serves it at
planetarypat.com/ansmet-quiz/ because planetarypat.com is the custom domain of the
`pshober.github.io` user site. Nothing in that site's repo needs to change.

Field photos courtesy of the ANSMET program (Case Western Reserve University and the University
of Utah), via NASA JSC Astromaterials Curation.
