"""
update_results.py
─────────────────
Pokretanje: GitHub Actions svakih 30 minuta.

- Čita fixtures.json (raspored + odds/stake koje si unio ručno)
- Poziva football-data.org API za sve WC 2026 mečeve
- Za svaki meč sa uplaćenim tiketom (stake > 0):
    - Ako je poluvrijeme završeno: auto-resolve ticket (3+ golova u HT → won, inače lost)
    - Upisuje HT i FT rezultat, status, ticket u results.json
"""

import urllib.request
import urllib.error
import json
import os
import sys
from datetime import datetime, timezone, timedelta

API_BASE   = "https://api.football-data.org/v4"
COMP_CODE  = "WC"
TOKEN      = os.environ.get("FD_API_TOKEN", "")
FIXTURES_F = "fixtures.json"
RESULTS_F  = "results.json"

# Koliko minuta nakon kickoffa čekamo prije nego provjeravamo HT
# (HT se obično dešava 45-50 min od starta)
HT_CHECK_AFTER_MIN = 50


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
        return None


def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def resolve_ticket(ht_home, ht_away, our_status):
    """
    Tip tiketa: 3+ golova u prvom poluvremenu.
    Vraća: 'won', 'lost', ili 'open'
    """
    if ht_home is None or ht_away is None:
        return "open"  # HT podaci još nisu dostupni
    ht_total = ht_home + ht_away
    if ht_total >= 3:
        return "won"
    # Lost tek kad je meč završen (ne za vrijeme HT pauze)
    if our_status == "finished":
        return "lost"
    return "open"


def main():
    if not TOKEN:
        print("ERROR: FD_API_TOKEN nije postavljen.")
        sys.exit(1)

    fixtures_data = load_json(FIXTURES_F, {})
    if not fixtures_data:
        print(f"ERROR: {FIXTURES_F} nije pronađen ili je prazan. Pokreni bootstrap_fixtures.py prvo.")
        sys.exit(1)

    fixtures  = fixtures_data.get("matches", {})
    results   = load_json(RESULTS_F, {"matches": {}})
    existing  = results.get("matches", {})
    now       = datetime.now(timezone.utc)

    print(f"[{now.isoformat()}] Fetching WC 2026 matches...")

    data = fetch(f"/competitions/{COMP_CODE}/matches?season=2026")
    if not data:
        print("Nije moguće dohvatiti podatke. Prekidam.")
        sys.exit(1)

    api_matches = {str(m["id"]): m for m in data.get("matches", [])}
    print(f"  API vratio {len(api_matches)} mečeva.")

    updated = 0
    for fd_id_str, fixture in fixtures.items():
        api_match = api_matches.get(fd_id_str)
        if not api_match:
            continue

        # ── API podaci ──────────────────────────────────────────────────────
        api_status = api_match.get("status", "SCHEDULED")
        score_ft   = api_match.get("score", {}).get("fullTime", {})
        score_ht   = api_match.get("score", {}).get("halfTime", {})
        ft_home    = score_ft.get("home")
        ft_away    = score_ft.get("away")
        ht_home    = score_ht.get("home")
        ht_away    = score_ht.get("away")

        # ── Naš status ──────────────────────────────────────────────────────
        if api_status == "FINISHED":
            our_status = "finished"
        elif api_status in ("IN_PLAY", "PAUSED", "HALFTIME", "LIVE"):
            our_status = "live"
        else:
            # Fallback: ako je kickoff bio više od 50 min nazad, vjerojatno je live/HT
            try:
                kickoff = datetime.fromisoformat(fixture["utcDate"].replace("Z", "+00:00"))
                elapsed = (now - kickoff).total_seconds() / 60
                if elapsed >= HT_CHECK_AFTER_MIN:
                    our_status = "live"
                else:
                    our_status = "scheduled"
            except Exception:
                our_status = "scheduled"

        # ── Ticket auto-resolve (samo za mečeve sa uplatom) ─────────────────
        has_bet = bool(fixture.get("stake"))
        if has_bet:
            ticket = resolve_ticket(ht_home, ht_away, our_status)
        else:
            ticket = ""

        existing[fd_id_str] = {
            "fd_id":      int(fd_id_str),
            "status":     our_status,
            "api_status": api_status,
            "score1":     ft_home,
            "score2":     ft_away,
            "ht1":        ht_home,
            "ht2":        ht_away,
            "ticket":     ticket,
            "updated_at": now.isoformat(),
        }
        updated += 1

        if has_bet:
            ht_str = f"HT {ht_home}-{ht_away}" if ht_home is not None else "HT n/a"
            print(f"  [{fd_id_str}] {fixture.get('team1')} vs {fixture.get('team2')} | "
                  f"{our_status} | {ht_str} | ticket={ticket}")

    save_json(RESULTS_F, {"generated_at": now.isoformat(), "matches": existing})
    print(f"Gotovo. {updated} mečeva upisano u {RESULTS_F}.")


if __name__ == "__main__":
    main()
