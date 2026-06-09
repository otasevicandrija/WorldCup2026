import urllib.request
import json
import os
from datetime import datetime, timezone, timedelta

FIXTURES_URL = "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json"
RESULTS_FILE = "results.json"
MATCH_DURATION_HOURS = 3

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "worldcup-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())

def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_results(data):
    with open(RESULTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def parse_match_time(date_str, time_str):
    # openfootball times are local kickoff times, stored as UTC here
    dt_str = f"{date_str}T{time_str}:00+00:00"
    return datetime.fromisoformat(dt_str)

def is_match_finished(kickoff_dt):
    now = datetime.now(timezone.utc)
    return now >= kickoff_dt + timedelta(hours=MATCH_DURATION_HOURS)

def main():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Fetching fixtures...")
    
    try:
        data = fetch_json(FIXTURES_URL)
    except Exception as e:
        print(f"ERROR fetching fixtures: {e}")
        return

    results = load_results()
    updated = 0

    rounds = data.get("rounds", [])
    for rnd in rounds:
        round_name = rnd.get("name", "")
        # Only process group stage (first 72 matches)
        if not any(x in round_name.lower() for x in ["group", "matchday"]):
            continue

        for match in rnd.get("matches", []):
            match_num = match.get("num")
            if match_num is None:
                continue

            key = str(match_num)
            date_str = match.get("date", "")
            time_str = match.get("time", "12:00")

            if not date_str:
                continue

            # If openfootball already has a score, use it directly
            score1 = match.get("score1")
            score2 = match.get("score2")

            if score1 is not None and score2 is not None:
                team1 = match.get("team1", {})
                team2 = match.get("team2", {})
                results[key] = {
                    "num": match_num,
                    "round": round_name,
                    "date": date_str,
                    "time": time_str,
                    "team1": team1.get("name", "") if isinstance(team1, dict) else str(team1),
                    "team2": team2.get("name", "") if isinstance(team2, dict) else str(team2),
                    "score1": score1,
                    "score2": score2,
                    "status": "finished",
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }
                updated += 1
            else:
                # No score yet — check if match should be finished by now
                try:
                    kickoff = parse_match_time(date_str, time_str)
                    if is_match_finished(kickoff) and key not in results:
                        # Mark as pending — score not available yet in source
                        team1 = match.get("team1", {})
                        team2 = match.get("team2", {})
                        results[key] = {
                            "num": match_num,
                            "round": round_name,
                            "date": date_str,
                            "time": time_str,
                            "team1": team1.get("name", "") if isinstance(team1, dict) else str(team1),
                            "team2": team2.get("name", "") if isinstance(team2, dict) else str(team2),
                            "score1": None,
                            "score2": None,
                            "status": "pending",
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }
                except Exception as e:
                    print(f"  Skipping match {key}: {e}")

    save_results(results)
    print(f"Done. {updated} results saved to {RESULTS_FILE}.")

if __name__ == "__main__":
    main()
