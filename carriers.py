#!/usr/bin/env python3
"""US carrier band requirements and the compatibility verdict.

Unlike the band scrape, this data is stable and public: four networks, a
fixed set of LTE bands each. MVNOs inherit their host network entirely --
Mint is T-Mobile, Visible is Verizon, Cricket is AT&T -- so they need no
separate entries.

The verdict deliberately separates two questions people conflate:

  "Will it get a signal?"  -> bands, which we can compute
  "Will calls work?"       -> VoLTE, which we CANNOT compute

VoLTE approval is a per-IMEI allowlist held inside each carrier. It is not
public and not derivable from a spec sheet. With 2G/3G shut down, a phone
that fails VoLTE gets data but cannot make calls -- so every verdict here
carries an explicit "IMEI check still required" caveat. This module tells
you which phones are worth checking, not which phones will work.
"""

# Band -> what it does for you in practice.
BAND_ROLES = {
    12: "low-band (building penetration)",
    13: "low-band (building penetration)",
    17: "low-band (building penetration)",
    5:  "low-band (coverage)",
    71: "600 MHz low-band (rural + indoor)",
    14: "FirstNet / low-band",
    26: "low-band (extended range)",
    2:  "mid-band (primary capacity)",
    4:  "mid-band (primary capacity)",
    66: "mid-band (AWS-3 capacity)",
    25: "mid-band (capacity)",
    30: "mid-band (capacity)",
    41: "high-capacity (dense urban)",
    38: "high-capacity (TDD)",
    40: "high-capacity (TDD)",
    7:  "mid-band (capacity, intl)",
    3:  "mid-band (capacity, intl)",
    1:  "mid-band (capacity, intl)",
    8:  "low-band (intl)",
    20: "low-band (intl / EU 800)",
    28: "low-band (intl / APAC 700)",
}

# essential: without these the phone is effectively unusable on that network
# important: expect dead spots indoors / rurally without them
# nice:      capacity, improves speed in busy areas
CARRIERS = {
    "tmobile": {
        "name": "T-Mobile",
        "mvnos": ["Mint Mobile", "Metro", "Google Fi", "Ultra Mobile", "Tello"],
        "essential": [2, 4],
        "important": [12, 71],
        "nice": [5, 25, 41, 66],
    },
    "verizon": {
        "name": "Verizon",
        "mvnos": ["Visible", "Total Wireless", "Straight Talk"],
        "essential": [13],
        "important": [2, 4],
        "nice": [5, 66],
        # Verizon historically gatekeeps non-Verizon hardware hardest.
        "note": "Verizon is the strictest about activating devices it never sold.",
    },
    "att": {
        "name": "AT&T",
        "mvnos": ["Cricket", "Consumer Cellular", "H2O"],
        "essential": [2, 4],
        "important": [12, 17],
        "nice": [5, 14, 29, 30, 66],
    },
    "usmobile": {
        "name": "US Mobile (multi-network)",
        "mvnos": [],
        "essential": [2, 4],
        "important": [12, 13, 71],
        "nice": [5, 25, 41, 66],
        "note": "Can ride T-Mobile or Verizon; band needs depend on chosen network.",
    },
}


def score(lte_bands, carrier_key):
    """Rate a phone against one carrier.

    Returns a dict with a verdict, the bands it has/misses, and an explicit
    statement that VoLTE is unverifiable from this data.
    """
    c = CARRIERS[carrier_key]
    if not lte_bands:
        return {
            "carrier": c["name"], "verdict": "unknown", "rank": 0,
            "reason": "No band data available for this phone.",
            "has": [], "missing_essential": [], "missing_important": [],
            "volte_note": "VoLTE support must be confirmed with an IMEI check.",
        }

    have = set(lte_bands)
    miss_e = [b for b in c["essential"] if b not in have]
    miss_i = [b for b in c["important"] if b not in have]
    has_nice = [b for b in c["nice"] if b in have]

    if miss_e:
        verdict, rank = "incompatible", 1
        reason = (f"Missing band {', '.join(map(str, miss_e))} — "
                  f"required for basic {c['name']} service.")
    elif len(miss_i) == len(c["important"]):
        verdict, rank = "poor", 2
        reason = (f"Has core bands but lacks all low-band "
                  f"({', '.join(map(str, c['important']))}) — expect no signal "
                  f"indoors or outside cities.")
    elif miss_i:
        verdict, rank = "partial", 3
        reason = (f"Works, but missing band {', '.join(map(str, miss_i))} — "
                  f"weaker coverage indoors and in rural areas.")
    else:
        verdict, rank = "good", 4
        reason = f"Has all essential and low-bands for {c['name']}."
        if has_nice:
            reason += f" Plus capacity bands {', '.join(map(str, has_nice))}."

    return {
        "carrier": c["name"], "verdict": verdict, "rank": rank, "reason": reason,
        "has": sorted(have & set(c["essential"] + c["important"] + c["nice"])),
        "missing_essential": miss_e, "missing_important": miss_i,
        "volte_note": ("Band match only. VoLTE approval is a per-IMEI carrier "
                       "allowlist and cannot be determined from specs — with "
                       "2G/3G shut down, a phone without it gets data but "
                       "cannot make calls. Check the IMEI before buying."),
    }


def score_all(lte_bands):
    return {k: score(lte_bands, k) for k in CARRIERS}
