#!/usr/bin/env python3
"""Attach LTE band data from GSMArena to the phones in data/phones.json.

Why this is careful rather than a simple scrape: GSMArena will serve a
COMPLETELY DIFFERENT PHONE at HTTP 200 if an ID is stale. Requesting
motorola_moto_g32-11757.php returns "BLU Bold N2"; another guessed ID
returned a Xiaomi smartwatch. Nothing in the response signals the mismatch.

Wrong bands are worse than no bands -- you'd buy a phone on them. So:

  1. Device IDs are never guessed. They come from GSMArena's own brand
     index pages, which map real names to real IDs.
  2. Every fetched page's <title> must still match the name we matched on.
     A mismatch discards the row instead of storing it.
  3. Anything unresolved is recorded as null, and the UI says "unknown"
     rather than implying compatibility.

Requires browser cookies (GSMArena Turnstile-blocks bare requests). Pass a
cookie string via --cookie or the GSMARENA_COOKIE env var; get it from
DevTools > Network > any gsmarena request > Cookie header.

Politeness: one request at a time with a delay. ~40 brand pages + ~111
device pages. Results cache to data/gsmarena_cache.json so reruns are cheap.
"""

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
PHONES = ROOT / "data" / "phones.json"
CACHE = ROOT / "data" / "gsmarena_cache.json"
OUT = ROOT / "data" / "phones.json"

BASE = "https://www.gsmarena.com/"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0"

# LineageOS vendor name -> GSMArena brand slug
VENDOR_SLUG = {
    "Xiaomi": "xiaomi", "LG": "lg", "Motorola": "motorola", "Samsung": "samsung",
    "Google": "google", "Sony": "sony", "OnePlus": "oneplus", "Asus": "asus",
    "Nokia": "nokia", "HTC": "htc", "Huawei": "huawei", "ZTE": "zte",
    "Lenovo": "lenovo", "Nubia": "zte", "Essential": "essential",
    "F(x)tec": "fxtec", "Fairphone": "fairphone", "Razer": "razer",
    "BQ": "bq", "Wileyfox": "wileyfox", "Yandex": "yandex",
    "Micromax": "micromax", "Realme": "realme", "Oppo": "oppo",
    "Vivo": "vivo", "Meizu": "meizu", "Alcatel": "alcatel",
    "Blackberry": "blackberry", "Honor": "honor", "Poco": "xiaomi",
    "Redmi": "xiaomi", "Sharp": "sharp", "TCL": "tcl", "Umidigi": "umidigi",
    "Unihertz": "unihertz", "Teracube": "teracube", "SHIFT": "shift",
    "Banana Pi": None, "Radxa": None, "Raspberry Pi": None,
}


def http_get(url: str, cookie: str, tries: int = 3) -> str | None:
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cookie": cookie,
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Connection": "keep-alive",
    }
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=45) as r:
                html = r.read().decode("utf-8", "replace")
            if "turnstile" in html.lower() or "just a moment" in html.lower():
                print("    ! Turnstile challenge -- cookies stale?", file=sys.stderr)
                return None
            return html
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            print(f"    ! HTTP {e.code} on {url}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - network flakiness
            print(f"    ! {type(e).__name__} on {url}", file=sys.stderr)
        time.sleep(2 + attempt * 3)
    return None


def norm(s: str) -> str:
    """Loose key for matching phone names across the two sources."""
    s = s.lower()
    s = re.sub(r"\(.*?\)", " ", s)             # drop "(International)" etc
    s = s.replace("+", " plus ")
    s = re.sub(r"\b(5g|4g|lte|dual|sim|ds)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def brand_index(slug: str, brand_id: str, cookie: str, delay: float) -> dict[str, str]:
    """{normalized name: device_id} for a whole brand, walking pagination."""
    found: dict[str, str] = {}
    page1 = http_get(f"{BASE}{slug}-phones-{brand_id}.php", cookie)
    if not page1:
        return found

    def harvest(html: str):
        for url, _did, name in re.findall(
            r'<a href="([a-z0-9_.\-]+-(\d+)\.php)">\s*<img[^>]*>\s*<strong><span>(.*?)</span>',
            html, re.S,
        ):
            # Store GSMArena's own URL. Rebuilding it from the name and ID
            # produces slugs that redirect to unrelated phones.
            found.setdefault(norm(re.sub(r"<[^>]+>", "", name)), url)

    harvest(page1)
    # The pager only prints the first and last page numbers for long brands
    # (Samsung shows p2 and p29, nothing between), so walk the full range
    # rather than the links that happen to be rendered.
    nums = [int(n) for n in
            re.findall(rf'{slug}-phones-f-{brand_id}-0-p(\d+)\.php', page1)]
    pages = range(2, max(nums) + 1) if nums else []
    for p in pages:
        time.sleep(delay + random.uniform(0, 0.6))
        html = http_get(f"{BASE}{slug}-phones-f-{brand_id}-0-p{p}.php", cookie)
        if html:
            harvest(html)
    return found


def parse_bands(html: str) -> dict:
    """Pull band lists out of a device page."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)

    def grab(label: str) -> str:
        m = re.search(re.escape(label) + r"\s+(.{0,400}?)(?:2G bands|3G bands|4G bands|5G bands|Speed|Announced|GPRS|EDGE|$)", text)
        return m.group(1).strip() if m else ""

    lte_raw = grab("4G bands")
    # LTE band numbers, ignoring MHz values that appear in 2G/3G rows
    lte = sorted({int(n) for n in re.findall(r"\b(\d{1,2})\b", lte_raw)
                  if 1 <= int(n) <= 88})
    return {
        "lte_bands": lte,
        "lte_raw": lte_raw[:400],
        "bands_2g": grab("2G bands")[:200],
        "bands_3g": grab("3G bands")[:200],
        "bands_5g": grab("5G bands")[:200],
    }


def title_of(html: str) -> str:
    m = re.search(r"<title>(.*?)</title>", html, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cookie", default=os.environ.get("GSMARENA_COOKIE", ""))
    ap.add_argument("--delay", type=float, default=2.5, help="seconds between requests")
    ap.add_argument("--limit", type=int, default=0, help="only N phones (for testing)")
    args = ap.parse_args()

    if not args.cookie:
        print("Need a cookie: --cookie 'lpe=...; DeviceID=...' or $GSMARENA_COOKIE\n"
              "Get it from DevTools > Network > a gsmarena.com request > Cookie header.",
              file=sys.stderr)
        return 2

    data = json.loads(PHONES.read_text())
    phones = data["phones"]
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}

    # --- brand indexes (cached) -------------------------------------------
    vendors = sorted({p["vendor"] for p in phones})
    brands = cache.setdefault("brands", {})
    makers = http_get(f"{BASE}makers.php3", args.cookie)
    brand_ids = {}
    if makers:
        for _u, bid, bname in re.findall(
            r'href="([a-z0-9_\-]+-phones-(\d+)\.php)"[^>]*>(?:<span>)?(.*?)<', makers, re.S
        ):
            brand_ids[re.sub(r"<[^>]+>", "", bname).strip().lower()] = bid

    for v in vendors:
        slug = VENDOR_SLUG.get(v)
        if not slug or v in brands:
            continue
        bid = brand_ids.get(slug) or brand_ids.get(v.lower())
        if not bid:
            print(f"  ? no GSMArena brand for {v}", file=sys.stderr)
            brands[v] = {}
            continue
        print(f"  indexing {v} ...", file=sys.stderr)
        brands[v] = brand_index(slug, bid, args.cookie, args.delay)
        print(f"    {len(brands[v])} devices", file=sys.stderr)
        CACHE.write_text(json.dumps(cache))
        time.sleep(args.delay)

    # --- per-phone band fetch ---------------------------------------------
    devices = cache.setdefault("devices", {})
    todo = [p for p in phones if p["id"] not in devices]
    if args.limit:
        todo = todo[: args.limit]
    print(f"\nfetching bands for {len(todo)} phones ...", file=sys.stderr)

    matched = mismatched = unresolved = 0
    for i, p in enumerate(todo, 1):
        idx = brands.get(p["vendor"], {})
        key = norm(p["name"])
        path = idx.get(key)
        if not path:  # try with the vendor prefixed, e.g. "poco m5s"
            path = idx.get(norm(f"{p['vendor']} {p['name']}"))
        if not path:
            devices[p["id"]] = {"status": "no_match", "name": p["name"]}
            unresolved += 1
            continue

        did = re.search(r"-(\d+)\.php$", path)
        did = did.group(1) if did else ""
        url = BASE + path
        html = http_get(url, args.cookie)
        time.sleep(args.delay + random.uniform(0, 0.8))
        if not html:
            devices[p["id"]] = {"status": "fetch_failed", "name": p["name"]}
            unresolved += 1
            continue

        # GUARD: the page must actually be the phone we asked for.
        title = title_of(html)
        if norm(p["name"]) not in norm(title):
            print(f"  ! MISMATCH {p['name']!r} -> {title!r} (discarded)", file=sys.stderr)
            devices[p["id"]] = {"status": "title_mismatch", "name": p["name"],
                                "got": title}
            mismatched += 1
            continue

        rec = parse_bands(html)
        # An empty band list means the parse failed or the page wasn't the
        # phone we wanted -- never store that as a successful lookup, or the
        # UI would render "no bands" as though it were a real finding.
        if not rec["lte_bands"]:
            print(f"  ! no bands parsed for {p['name']!r} (discarded)", file=sys.stderr)
            devices[p["id"]] = {"status": "no_bands_parsed", "name": p["name"],
                                "got": title}
            unresolved += 1
            continue

        rec.update({"status": "ok", "gsmarena_id": did, "gsmarena_title": title,
                    "url": url})
        devices[p["id"]] = rec
        matched += 1
        if i % 10 == 0:
            CACHE.write_text(json.dumps(cache))
            print(f"  {i}/{len(todo)} ok={matched} mismatch={mismatched} "
                  f"unresolved={unresolved}", file=sys.stderr)

    CACHE.write_text(json.dumps(cache, indent=1))

    # --- merge into phones.json -------------------------------------------
    for p in phones:
        rec = devices.get(p["id"], {})
        p["lte_bands"] = rec.get("lte_bands") if rec.get("status") == "ok" else None
        p["bands_source"] = rec.get("url") if rec.get("status") == "ok" else None
        p["bands_status"] = rec.get("status", "not_fetched")

    OUT.write_text(json.dumps(data, indent=2))
    print(f"\nok={matched} mismatch={mismatched} unresolved={unresolved} -> {OUT}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
