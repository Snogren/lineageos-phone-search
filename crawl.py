#!/usr/bin/env python3
"""Crawl LineageOS device data and emit the filtered set as JSON.

Source of truth is the lineage_wiki repo's _data/devices/*.yml -- the same
files that render wiki.lineageos.org/devices/. Each YAML file is one device
identity, NOT one codename: 88 codenames have multiple variant files (miatoll
covers six distinct retail phones). Rows are keyed by file stem so variants
stay separate.

The wiki hides discontinued devices by default; that list is only available
from the rendered index page, so we fetch it to classify.
"""

import json
import io
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

import yaml

WIKI_TARBALL = "https://github.com/LineageOS/lineage_wiki/archive/refs/heads/main.tar.gz"
DEVICE_INDEX = "https://wiki.lineageos.org/devices/"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0"

OUT = Path(__file__).parent / "data" / "phones.json"

# --- filter spec -----------------------------------------------------------
SCREEN_MIN = 4.0
SCREEN_MAX = 6.5
NET_REQUIRE = "4G"      # substring match
NET_EXCLUDE = "5G NR"
JACK = "3.5mm jack"
# sdcard is deliberately not a criterion.


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def load_devices() -> dict[str, dict]:
    """Return {file_stem: parsed_yaml} for every device file in the repo."""
    print(f"fetching {WIKI_TARBALL} ...", file=sys.stderr)
    raw = fetch(WIKI_TARBALL)
    devices: dict[str, dict] = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        for m in tf.getmembers():
            if "/_data/devices/" not in m.name or not m.name.endswith(".yml"):
                continue
            f = tf.extractfile(m)
            if not f:
                continue
            try:
                d = yaml.safe_load(f.read())
            except yaml.YAMLError as e:
                print(f"  ! yaml error in {m.name}: {e}", file=sys.stderr)
                continue
            if isinstance(d, dict):
                devices[Path(m.name).stem] = d
    print(f"  parsed {len(devices)} device files", file=sys.stderr)
    return devices


def load_active_codenames() -> set[str]:
    """Codenames the wiki shows by default (i.e. not marked discontinued)."""
    print(f"fetching {DEVICE_INDEX} ...", file=sys.stderr)
    html = fetch(DEVICE_INDEX).decode("utf-8", "replace")
    active = set()
    for cls, codename in re.findall(
        r'<div class="item([^"]*)"[^>]*data-codename="([^"]+)"', html
    ):
        if "discontinued" not in cls:
            active.add(codename)
    print(f"  {len(active)} active codenames", file=sys.stderr)
    return active


def screen_sizes(screen) -> list[float]:
    """All panel sizes on a device, in inches.

    `screen` is usually a dict, but is a list for multi-panel devices
    (foldables: cover+inner; some phones: per-variant panels) and a bare
    string on a few non-phones. Returns [] when no size is parseable.
    """
    out = []

    def take(v):
        if isinstance(v, (int, float)):
            out.append(float(v))

    if isinstance(screen, dict):
        take(screen.get("size"))
    elif isinstance(screen, list):
        for entry in screen:
            if isinstance(entry, dict):
                for v in entry.values():
                    if isinstance(v, dict):
                        take(v.get("size"))
                    else:
                        take(entry.get("size"))
    return out


def networks(d: dict) -> list[str]:
    """Network tokens as a clean list.

    Guard: `network` is the string "None" on Wi-Fi-only devices. Iterating a
    string yields characters, so a naive loop invents 'N','o','n','e' tokens.
    """
    net = d.get("network")
    if isinstance(net, list):
        return [str(x) for x in net]
    return []


def release_key(rel) -> str:
    """Sortable YYYY-MM string; '' when missing so it sorts last."""
    if rel is None:
        return ""
    s = str(rel).strip()
    m = re.match(r"^(\d{4})(?:-(\d{1,2}))?", s)
    if not m:
        return ""
    return f"{m.group(1)}-{int(m.group(2) or 0):02d}"


def ebay_query(d: dict) -> str:
    """Human-buyable search string: vendor + retail name + model numbers.

    Codenames are useless on eBay -- nobody lists a phone as 'miatoll'.
    Model numbers are what distinguish variants, so they're included.

    Multiple models are joined with eBay's OR syntax "(a,b)". Space-separating
    them instead would AND the terms, and no single listing contains two
    different model numbers -- that returns an empty result page.
    """
    parts = [str(d.get("vendor") or "").strip(), str(d.get("name") or "").strip()]
    models = [str(m).strip() for m in (d.get("models") or []) if str(m).strip()]
    # eBay's OR list rejects internal spaces, so only use bare model codes.
    codes = [m for m in models if " " not in m][:4]
    if len(codes) == 1:
        parts.append(codes[0])
    elif len(codes) > 1:
        parts.append("(" + ",".join(codes) + ")")
    return " ".join(p for p in parts if p)


def build_row(stem: str, d: dict, active: bool) -> dict:
    sizes = screen_sizes(d.get("screen"))
    net = networks(d)
    peri = d.get("peripherals") or []
    if not isinstance(peri, list):
        peri = []
    models = d.get("models") or []
    if not isinstance(models, list):
        models = [models]

    return {
        "id": stem,
        "codename": d.get("codename") or stem,
        "vendor": d.get("vendor") or "",
        "name": d.get("name") or "",
        "models": [str(m) for m in models],
        "type": d.get("type") or "",
        "release": str(d.get("release") or ""),
        "release_key": release_key(d.get("release")),
        "screen_sizes": sizes,
        "screen_size": min(sizes) if sizes else None,
        "screen_tech": (d.get("screen") or {}).get("technology")
        if isinstance(d.get("screen"), dict)
        else "",
        "networks": net,
        "has_4g": any(NET_REQUIRE in x for x in net),
        "has_5g": any(NET_EXCLUDE in x for x in net),
        "has_jack": JACK in peri,
        "peripherals": [str(p) for p in peri],
        "versions": [str(v) for v in (d.get("versions") or [])],
        "active": active,
        "wiki_url": f"https://wiki.lineageos.org/devices/{d.get('codename') or stem}/",
        "ebay_query": ebay_query(d),
    }


def passes(r: dict) -> bool:
    """The filter spec. sdcard and device type are intentionally not tested."""
    if not r["active"]:
        return False
    if r["screen_size"] is None:
        return False
    if not (SCREEN_MIN <= r["screen_size"] <= SCREEN_MAX):
        return False
    if not r["has_4g"] or r["has_5g"]:
        return False
    if not r["has_jack"]:
        return False
    return True


def main() -> int:
    devices = load_devices()
    active = load_active_codenames()

    rows = [
        build_row(stem, d, (d.get("codename") or stem) in active)
        for stem, d in devices.items()
    ]
    kept = [r for r in rows if passes(r)]

    # release desc; undated last, then vendor/name for stability
    kept.sort(key=lambda r: (r["release_key"] or "0000-00", r["vendor"], r["name"]),
              reverse=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "filters": {
            "screen_min": SCREEN_MIN, "screen_max": SCREEN_MAX,
            "network_require": NET_REQUIRE, "network_exclude": NET_EXCLUDE,
            "peripheral_require": JACK, "active_only": True,
            "sdcard": "ignored", "device_type": "not filtered",
        },
        "source": "https://github.com/LineageOS/lineage_wiki/tree/main/_data/devices",
        "total_devices": len(rows),
        "matched": len(kept),
        "phones": kept,
    }, indent=2), encoding="utf-8")

    print(f"\n{len(kept)} / {len(rows)} devices matched -> {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
