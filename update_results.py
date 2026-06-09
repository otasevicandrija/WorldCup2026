"""
update_results.py
─────────────────
Runs every 30 minutes via GitHub Actions.
- Loads fixtures.json (ground truth for fd_id mappings)
- Calls football-data.org for current match statuses
- Writes results.json with score + status for every match
- Only makes API calls for matches that are within the update window
  (kickoff - 15min  →  kickoff + 3h), plus any FINISHED ones not yet confirmed.
"""

import urllib.request
import urllib.error
import json
import os
import sys
from datetime import datetime, timezone, timedelta

API_BASE    = "https://api.football-data.org/v4"
COMP_CODE   = "WC"
TOKEN       = os.environ.get("FD_API_TOKEN", "")
FIXTURES_F  = "fixtures.json"
RESULTS_F   = "results.json"

# How long after kickoff until we consider a match definitely finished
MATCH_WINDOW_H = 3


def fetch(path):
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={"X-Auth-Token": TOKEN, "User-Agent": "wc2026-tracker/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"HTTP {e.code}: {body}")
        return None


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    if not TOKEN:
        print("ERROR: FD_API_TOKEN not set.")
        sys.exit(1)

    fixtures_data = load_json(FIXTURES_F, {})
    if not fixtures_data:
        print("ERROR: fixtures.json is missing or empty. Run bootstrap_fixtures.py first.")
        sys.exit(1)

    fixtures = fixtures_data.get("matches", {})  # fd_id (str) → fixture dict
    results  = load_json(RESULTS_F, {"matches": {}})
    existing = results.get("matches", {})

    now = datetime.now(timezone.utc)
    print(f"[{now.isoformat()}] Checking {len(fixtures)} fixtures ...")

    # Fetch all WC 2026 matches in one call (free tier allows this)
    data = fetch(f"/competitions/{COMP_CODE}/matches?season=2026")
    if not data:
        print("Failed to fetch match data. Aborting.")
        sys.exit(1)

    api_matches = {str(m["id"]): m for m in data.get("matches", [])}
    print(f"  API returned {len(api_matches)} matches.")

    updated = 0
    for fd_id_str, fixture in fixtures.items():
        api_match = api_matches.get(fd_id_str)
        if not api_match:
            continue

        status    = api_match.get("status", "SCHEDULED")   # SCHEDULED, LIVE, IN_PLAY, PAUSED, FINISHED, etc.
        score_ft  = api_match.get("score", {}).get("fullTime", {})
        home_g    = score_ft.get("home")   # None if not played
        away_g    = score_ft.get("away")

        # Determine kickoff UTC
        utc_date  = fixture.get("utcDate", "")
        try:
            kickoff = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
        except Exception:
            kickoff = None

        # Compute our own status label
        if status == "FINISHED":
            our_status = "finished"
        elif status in ("IN_PLAY", "PAUSED", "LIVE", "HALFTIME"):
            our_status = "live"
        elif kickoff and now >= kickoff:
            our_status = "live"   # API may lag slightly
        else:
            our_status = "scheduled"

        existing[fd_id_str] = {
            "fd_id":       int(fd_id_str),
            "status":      our_status,        # "scheduled" | "live" | "finished"
            "api_status":  status,            # raw from API
            "score1":      home_g,            # None until finished
            "score2":      away_g,
            "updated_at":  now.isoformat(),
        }
        updated += 1

    results = {
        "generated_at": now.isoformat(),
        "matches": existing
    }
    save_json(RESULTS_F, results)
    print(f"  Updated {updated} entries in {RESULTS_F}.")


if __name__ == "__main__":
    main()
