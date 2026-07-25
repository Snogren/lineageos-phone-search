# LineageOS Phone Search

Find phones that still run [LineageOS](https://lineageos.org/) **and** have a
headphone jack, a normal-sized screen, and no 5G.

**[→ Browse the phones](https://snogren.github.io/lineageos-phone-search/)**

Click any phone to search eBay for it.

## The filter

| Spec | Rule |
|---|---|
| LineageOS support | Actively maintained (discontinued devices excluded) |
| Screen size | 4″ – 6.5″ |
| Cellular | Has 4G, does **not** have 5G |
| Audio | Has a 3.5 mm headphone jack |
| SD card slot | Not considered either way |

111 of 726 devices match.

## Where the data comes from

Everything comes from one canonical source: the
[`lineage_wiki`](https://github.com/LineageOS/lineage_wiki) repo's
`_data/devices/*.yml` files. These are the same files that render
wiki.lineageos.org, maintained by the device maintainers themselves — so
there's no scraping of third-party spec sites and no per-vendor parsers.

The one thing not in the YAML is whether a device is still maintained, so
`crawl.py` also reads the rendered device index to tell active from
discontinued.

### One codename is not one phone

88 codenames cover multiple distinct retail devices. `miatoll` alone is six:
a POCO M2 Pro, a Redmi Note 9S, three Note 9 Pro regional variants, and a
Redmi Note 10 Lite. They share a LineageOS build but are different products
with different model numbers and very different eBay listings.

So rows are keyed by **variant file**, not codename, and each row carries its
own model numbers. Searching eBay for `miatoll` finds nothing; searching for
`Xiaomi Redmi Note 9 Pro M2003J6B2G` finds the phone.

## Carrier compatibility

Each phone is scored against T-Mobile (and its MVNOs — Mint, Metro, Google Fi),
Verizon, and AT&T. MVNOs inherit their host network's bands, so Mint is scored
as T-Mobile.

The verdict is **a band match only**, and that distinction matters:

| Question | Answerable from specs? |
|---|---|
| Will it get a signal? | Yes — from LTE bands |
| Will calls work? | **No** — VoLTE is a per-IMEI carrier allowlist |

With 2G and 3G shut down, voice rides VoLTE. Carriers keep private per-IMEI
allowlists, and imported or uncommon models frequently aren't on them — so the
phone gets data but **cannot make calls**. No public dataset can predict this.
Get the IMEI from the eBay listing and run your carrier's checker before buying.

Band data comes from GSMArena via `crawl_bands.py`. It needs browser cookies,
because GSMArena Turnstile-blocks bare requests:

```bash
python3 crawl_bands.py --cookie 'lpe=122; keyw=Xiaomi; DeviceID=10587'
```

Get the cookie from DevTools → Network → any gsmarena.com request → Cookie
header. Results cache to `data/gsmarena_cache.json`, so reruns only fetch what's
missing.

### Why that script is defensive

**GSMArena serves a different phone at HTTP 200 when an ID is stale.** Asking
for `motorola_moto_g32-11757.php` returns "BLU Bold N2"; another guessed ID
returned a Xiaomi smartwatch. Nothing in the response signals the swap — and
band data for the wrong phone is worse than none, because you'd buy on it.

So the script never guesses URLs. It reads GSMArena's own brand index pages for
real name→URL mappings, then verifies every fetched page's `<title>` still
matches the phone it asked for. Mismatches and unparseable pages are recorded as
`null`, and the UI shows "band data unavailable" rather than implying anything.

## Running it

```bash
python3 crawl.py          # writes data/phones.json
python3 -m http.server 8000
# open http://localhost:8000
```

`crawl.py` needs `pyyaml`. The UI is one static HTML file with no build step
and no dependencies — it just reads `data/phones.json`.

Opening `index.html` directly with `file://` won't work; browsers block the
`fetch` for local files. Use the server.

## Changing the filter

The thresholds are constants at the top of `crawl.py`:

```python
SCREEN_MIN  = 4.0
SCREEN_MAX  = 6.5
NET_REQUIRE = "4G"
NET_EXCLUDE = "5G NR"
JACK        = "3.5mm jack"
```

Edit and re-run. Device type isn't filtered at all — no tablet has both
cellular 4G and a screen under 6.5″, so the result is phones regardless.

## Staying current

A GitHub Action re-runs the crawler weekly and commits any changes, so the
published list follows LineageOS as devices are added and dropped.

## License

MIT. Device data belongs to the LineageOS wiki contributors
([CC BY-SA 3.0](https://github.com/LineageOS/lineage_wiki/blob/main/LICENSE)).
