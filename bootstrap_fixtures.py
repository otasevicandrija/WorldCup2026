"""
bootstrap_fixtures.py
─────────────────────
Run ONCE locally (or manually via Actions) to populate fixtures.json.
Fetches all WC 2026 matches from football-data.org, keeps only group stage (first 72),
and writes fixtures.json that index.html + update_results.py both reference.

Usage:
    FD_API_TOKEN=your_token python bootstrap_fixtures.py
"""

import urllib.request
import urllib.error
import json
import os
import sys

API_BASE   = "https://api.football-data.org/v4"
COMP_CODE  = "WC"
TOKEN      = os.environ.get("FD_API_TOKEN", "")
OUT_FILE   = "fixtures.json"


def fetch(path):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, headers={"X-Auth-Token": TOKEN, "User-Agent": "wc2026-tracker/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code} for {url}: {body}")
        sys.exit(1)


def main():
    if not TOKEN:
        print("ERROR: Set FD_API_TOKEN environment variable.")
        sys.exit(1)

    print("Fetching WC 2026 matches from football-data.org ...")
    data = fetch(f"/competitions/{COMP_CODE}/matches?season=2026")

    matches = data.get("matches", [])
    print(f"  Total matches returned: {len(matches)}")

    # Keep only GROUP_STAGE matches (72 group stage games)
    group_matches = [m for m in matches if m.get("stage") == "GROUP_STAGE"]
    print(f"  Group stage matches: {len(group_matches)}")

    # Sort by utcDate
    group_matches.sort(key=lambda m: m.get("utcDate", ""))

    fixtures = {}
    for i, m in enumerate(group_matches, 1):
        fd_id = m["id"]  # stable unique key from football-data.org
        fixtures[str(fd_id)] = {
            "fd_id":    fd_id,
            "seq":      i,                                          # 1..72 display order
            "group":    m.get("group", ""),                        # e.g. "GROUP_A"
            "stage":    m.get("stage", ""),
            "matchday": m.get("matchday"),
            "utcDate":  m.get("utcDate", ""),                      # ISO8601 UTC kickoff
            "team1":    m["homeTeam"].get("name", "TBD"),
            "team2":    m["awayTeam"].get("name", "TBD"),
            "team1_tla": m["homeTeam"].get("tla", ""),
            "team2_tla": m["awayTeam"].get("tla", ""),
            "venue":    m.get("venue", ""),
        }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
                   "count": len(fixtures),
                   "matches": fixtures}, f, indent=2, ensure_ascii=False)

    print(f"  Written {len(fixtures)} fixtures to {OUT_FILE}")
    print("Done. Commit fixtures.json to your repo.")


if __name__ == "__main__":
    main()
