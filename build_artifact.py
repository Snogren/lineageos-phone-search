#!/usr/bin/env python3
"""Bake index.html + data/phones.json into one self-contained HTML file.

The Artifact host sandboxes the page and supplies its own <head>, so the
published copy can't fetch() a sibling JSON file and must not carry a doc
wrapper of its own. Everything else stays byte-identical to the local UI,
so the two can't drift.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "dist" / "artifact.html"

# Fields the UI actually reads -- keeps the inlined payload small.
KEEP = ["codename", "vendor", "name", "models", "release", "release_key",
        "screen_size", "versions", "wiki_url", "ebay_query", "lte_bands",
        "bands_status"]

SITE = "https://snogren.github.io/lineageos-phone-search/"


def main() -> None:
    html = (ROOT / "index.html").read_text()
    data = json.loads((ROOT / "data" / "phones.json").read_text())
    slim = [{k: r.get(k) for k in KEEP} for r in data["phones"]]
    payload = json.dumps(slim, separators=(",", ":"))

    style = re.search(r"<style>.*?</style>", html, re.S).group(0)
    body = html.split("</head>")[1]
    for tag in ("<body>", "</body>", "</html>"):
        body = body.replace(tag, "")
    body = body.strip()

    # Swap the fetch() bootstrap for the inlined array.
    body = re.sub(
        r"fetch\('data/phones\.json'\).*?\}\);\n",
        "PHONES = DATA;\n"
        "const vs = [...new Set(PHONES.map(p => p.vendor))].sort();\n"
        "el('vendor').append(...vs.map(v => new Option(v, v)));\n"
        "render();\n",
        body, flags=re.S,
    )
    body = body.replace("let PHONES = [];", f"const DATA = {payload};\nlet PHONES = [];")

    # Point viewers at the source, since the artifact is a frozen snapshot.
    body = body.replace(
        "Click a phone to search eBay.",
        f'Click a phone to search eBay. &middot; '
        f'<a href="{SITE}" target="_blank" rel="noopener" style="color:var(--accent)">'
        f'source &amp; live site</a>',
    )

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(f"<title>LineageOS Phone Search</title>\n{style}\n{body}\n")

    withbands = sum(1 for r in slim if r.get("lte_bands"))
    assert "fetch(" not in OUT.read_text(), "fetch() survived the rewrite"
    assert "const DATA = [" in OUT.read_text(), "data was not inlined"
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB), "
          f"{len(slim)} phones, {withbands} with band data")


if __name__ == "__main__":
    main()
