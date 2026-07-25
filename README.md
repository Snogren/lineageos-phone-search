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
