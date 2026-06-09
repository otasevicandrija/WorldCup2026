"""
bootstrap_fixtures.py
─────────────────────
Pokretanje: JEDNOM, lokalno ili ručno kroz GitHub Actions.

Dohvata svih 72 grupnih mečeva WC 2026 sa football-data.org
i upisuje ih u fixtures.json.

Nakon generisanja, otvori fixtures.json na GitHubu i ručno dodaj
odds i stake za mečeve koje igraš:

  "123456": {
    ...
    "odds": 2.30,
    "stake": 2000
  }

Usage:
    FD_API_TOKEN=tvoj_token python bootstrap_fixtures.py
"""

import urllib.request
import urllib.error
import json
import os
import sys
from datetime import datetime, timezone

API_BASE  = "https://api.football-data.org/v4"
COMP_CODE = "WC"
TOKEN     = os.environ.get("FD_API_TOKEN", "")
OUT_FILE  = "fixtures.json"


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
        print(f"HTTP {e.code}: {e.read().decode()}")
        sys.exit(1)


def main():
    if not TOKEN:
        print("ERROR: Postavi FD_API_TOKEN environment varijablu.")
        sys.exit(1)

    print("Dohvatam WC 2026 mečeve sa football-data.org...")
    data = fetch(f"/competitions/{COMP_CODE}/matches?season=2026")

    all_matches   = data.get("matches", [])
    group_matches = [m for m in all_matches if m.get("stage") == "GROUP_STAGE"]
    group_matches.sort(key=lambda m: m.get("utcDate", ""))

    print(f"  Ukupno mečeva: {len(all_matches)}")
    print(f"  Grupna faza:   {len(group_matches)}")

    # Učitaj postojeći fixtures.json ako postoji,
    # kako ne bismo izgubili ručno unesene odds/stake
    existing = {}
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, "r", encoding="utf-8") as f:
            existing = json.load(f).get("matches", {})
        print(f"  Pronađen postojeći {OUT_FILE} — čuvam odds/stake.")

    fixtures = {}
    for i, m in enumerate(group_matches, 1):
        fd_id = str(m["id"])
        prev  = existing.get(fd_id, {})

        fixtures[fd_id] = {
            "fd_id":      m["id"],
            "seq":        i,
            "group":      m.get("group", ""),         # "GROUP_A" itd.
            "stage":      m.get("stage", ""),
            "matchday":   m.get("matchday"),
            "utcDate":    m.get("utcDate", ""),        # ISO8601 UTC kickoff
            "team1":      m["homeTeam"].get("name", "TBD"),
            "team2":      m["awayTeam"].get("name", "TBD"),
            "team1_tla":  m["homeTeam"].get("tla", ""),
            "team2_tla":  m["awayTeam"].get("tla", ""),
            "venue":      m.get("venue", ""),
            # Čuvamo ručno unesene vrijednosti ako već postoje
            "odds":       prev.get("odds", None),
            "stake":      prev.get("stake", None),
        }

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count":        len(fixtures),
        "matches":      fixtures,
    }

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"  Upisano {len(fixtures)} mečeva u {OUT_FILE}.")
    print()
    print("Sljedeći korak: otvori fixtures.json na GitHubu i dodaj odds/stake")
    print('za mečeve koje igraš, npr:')
    print('  "odds": 2.30,')
    print('  "stake": 2000')


if __name__ == "__main__":
    main()
