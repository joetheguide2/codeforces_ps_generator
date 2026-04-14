import requests
import json
import time
import sys
from datetime import datetime

BASE_URL = "https://codeforces.com/api"

def fetch_with_retry(url, retries=3, delay=2):
    for attempt in range(retries):
        try:
            print(f"  Fetching: {url}")
            res = requests.get(url, timeout=15)
            data = res.json()
            if data["status"] == "OK":
                return data["result"]
            else:
                print(f"  API error: {data.get('comment', 'unknown')}")
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
        if attempt < retries - 1:
            print(f"  Retrying in {delay}s...")
            time.sleep(delay)
    return None


def fetch_problems():
    print("\n[1/3] Fetching all problems + statistics...")
    result = fetch_with_retry(f"{BASE_URL}/problemset.problems")
    if not result:
        print("ERROR: Could not fetch problems. Exiting.")
        sys.exit(1)

    problems   = result["problems"]
    statistics = result["problemStatistics"]

    print(f"  Got {len(problems)} problems, {len(statistics)} statistics entries.")
    return problems, statistics


def fetch_contests():
    print("\n[2/3] Fetching contest list...")
    result = fetch_with_retry(f"{BASE_URL}/contest.list?gym=false")
    if not result:
        print("  WARNING: Could not fetch contests. Contest metadata will be missing.")
        return {}

    contest_map = {}
    for c in result:
        cid = c.get("id")
        if not cid:
            continue
        contest_map[cid] = {
            "contestName":        c.get("name", ""),
            "contestType":        c.get("type", ""),        # CF, IOI, ICPC
            "contestPhase":       c.get("phase", ""),       # BEFORE, CODING, FINISHED, etc.
            "contestStartTime":   c.get("startTimeSeconds"),
            "contestDuration":    c.get("durationSeconds"),
            "contestStartDate":   datetime.utcfromtimestamp(c["startTimeSeconds"]).strftime("%Y-%m-%d")
                                  if c.get("startTimeSeconds") else None,
        }

    print(f"  Got metadata for {len(contest_map)} contests.")
    return contest_map


def build_dataset(problems, statistics, contest_map):
    print("\n[3/3] Building dataset...")

    # Build stats lookup: (contestId, index) -> solvedCount
    stats_map = {}
    for s in statistics:
        key = (s.get("contestId"), s.get("index"))
        stats_map[key] = s.get("solvedCount", 0)

    dataset = []
    skipped_no_contest = 0
    skipped_no_rating  = 0

    for p in problems:
        cid   = p.get("contestId")
        index = p.get("index")
        name  = p.get("name", "")
        rating = p.get("rating")        # can be None for unrated problems
        tags  = p.get("tags", [])
        ptype = p.get("type", "PROGRAMMING")

        if not cid or not index:
            skipped_no_contest += 1
            continue

        # We keep unrated problems too but flag them clearly
        solved_count = stats_map.get((cid, index), 0)
        contest_info = contest_map.get(cid, {})

        problem_id = f"{cid}_{index}"
        url = f"https://codeforces.com/contest/{cid}/problem/{index}"

        entry = {
            # --- Core identifiers ---
            "id":             problem_id,
            "contestId":      cid,
            "index":          index,
            "url":            url,

            # --- Problem info ---
            "name":           name,
            "type":           ptype,
            "rating":         rating,         # None if unrated
            "tags":           tags,
            "solvedCount":    solved_count,

            # --- Contest metadata (from contest.list join) ---
            "contestName":    contest_info.get("contestName", ""),
            "contestType":    contest_info.get("contestType", ""),
            "contestPhase":   contest_info.get("contestPhase", ""),
            "contestStartDate": contest_info.get("contestStartDate"),
            "contestStartTime": contest_info.get("contestStartTime"),
            "contestDuration":  contest_info.get("contestDuration"),
        }

        dataset.append(entry)

    rated   = sum(1 for p in dataset if p["rating"] is not None)
    unrated = sum(1 for p in dataset if p["rating"] is None)

    print(f"  Total problems kept:   {len(dataset)}")
    print(f"    Rated problems:      {rated}")
    print(f"    Unrated problems:    {unrated}")
    print(f"  Skipped (no cid/idx): {skipped_no_contest}")

    return dataset


def print_summary(dataset):
    print("\n--- Dataset Summary ---")

    # Rating distribution
    rated = [p for p in dataset if p["rating"]]
    if rated:
        ratings = [p["rating"] for p in rated]
        print(f"Rating range:    {min(ratings)} – {max(ratings)}")
        buckets = {}
        for r in ratings:
            b = (r // 200) * 200
            buckets[b] = buckets.get(b, 0) + 1
        print("Rating buckets:")
        for b in sorted(buckets):
            bar = "█" * (buckets[b] // 20)
            print(f"  {b:4d}–{b+199}: {buckets[b]:5d}  {bar}")

    # Tag frequency (top 15)
    tag_freq = {}
    for p in dataset:
        for t in p["tags"]:
            tag_freq[t] = tag_freq.get(t, 0) + 1
    top_tags = sorted(tag_freq.items(), key=lambda x: -x[1])[:15]
    print("\nTop 15 tags:")
    for tag, count in top_tags:
        print(f"  {tag:<30} {count}")

    # Contest type breakdown
    type_freq = {}
    for p in dataset:
        t = p["contestType"] or "unknown"
        type_freq[t] = type_freq.get(t, 0) + 1
    print("\nContest types:")
    for t, count in sorted(type_freq.items(), key=lambda x: -x[1]):
        print(f"  {t:<20} {count}")


def main():
    print("=" * 50)
    print("  Codeforces Problem Scraper")
    print("=" * 50)

    problems, statistics = fetch_problems()
    contest_map          = fetch_contests()

    # CF API rate limit: max 1 request per 2 seconds (or 5/s — being safe)
    time.sleep(1)

    dataset = build_dataset(problems, statistics, contest_map)

    output_file = "problems.json"
    print(f"\nSaving to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    size_kb = len(json.dumps(dataset)) / 1024
    print(f"Done! Saved {len(dataset)} problems ({size_kb:.1f} KB)")

    print_summary(dataset)
    print("\nYou can now run generate.py to create your daily practice set.")


if __name__ == "__main__":
    main()
