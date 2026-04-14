"""
Codeforces Problem Scraper
Requires: pip install cloudscraper

cloudscraper is a drop-in replacement for requests that handles
Cloudflare's JS/bot challenges, which is why CF returns HTTP 200
but an empty body to plain requests calls.
"""

import json
import time
import sys
from datetime import datetime

try:
    import cloudscraper
except ImportError:
    print("Missing dependency. Please run:")
    print("  pip install cloudscraper")
    sys.exit(1)

BASE_URLS = [
    "https://codeforces.com/api",
    "https://m1.codeforces.com/api",
    "https://m2.codeforces.com/api",
]

# Create a cloudscraper session once — reuse for all requests
scraper = cloudscraper.create_scraper(
    browser={"browser": "chrome", "platform": "windows", "mobile": False}
)


def fetch_with_retry(path, retries=3, delay=3):
    """Try each base URL in order, with retries. Returns result dict or None."""
    for base in BASE_URLS:
        url = f"{base}/{path}"
        for attempt in range(retries):
            try:
                print(f"  GET {url}")
                res = scraper.get(url, timeout=30)
                print(f"  HTTP {res.status_code}  ({len(res.content)} bytes)")

                if res.status_code != 200:
                    print(f"  Non-200, skipping this mirror...")
                    break

                if not res.content:
                    print(f"  Empty response body (Cloudflare challenge?), retrying...")
                    time.sleep(delay)
                    continue

                data = res.json()

                if data["status"] == "OK":
                    return data["result"]
                else:
                    comment = data.get("comment", "unknown error")
                    print(f"  API returned FAILED: {comment}")
                    if "limit" in comment.lower():
                        print(f"  Rate limited — waiting 5s...")
                        time.sleep(5)

            except json.JSONDecodeError as e:
                raw_preview = res.text[:200] if res else "n/a"
                print(f"  JSON parse failed: {e}")
                print(f"  Response preview: {repr(raw_preview)}")
            except Exception as e:
                print(f"  Attempt {attempt + 1} error: {e}")

            if attempt < retries - 1:
                print(f"  Retrying in {delay}s...")
                time.sleep(delay)

        time.sleep(2)  # pause before trying next mirror

    return None


def fetch_problems():
    print("\n[1/3] Fetching all problems + statistics...")
    result = fetch_with_retry("problemset.problems")
    if not result:
        print("\nERROR: Could not fetch problems from any mirror.")
        print("Troubleshooting:")
        print("  1. Make sure cloudscraper is installed: pip install cloudscraper")
        print("  2. Check your internet connection")
        print("  3. Try opening https://codeforces.com in your browser first")
        print("  4. CF may be temporarily down — try again in a few minutes")
        sys.exit(1)

    problems   = result["problems"]
    statistics = result["problemStatistics"]
    print(f"  Got {len(problems)} problems, {len(statistics)} stat entries.")
    return problems, statistics


def fetch_contests():
    print("\n[2/3] Fetching contest list...")
    time.sleep(2)  # be polite between requests
    result = fetch_with_retry("contest.list?gym=false")
    if not result:
        print("  WARNING: Could not fetch contests. Contest metadata will be absent.")
        return {}

    contest_map = {}
    for c in result:
        cid = c.get("id")
        if not cid:
            continue
        contest_map[cid] = {
            "contestName":      c.get("name", ""),
            "contestType":      c.get("type", ""),
            "contestPhase":     c.get("phase", ""),
            "contestStartTime": c.get("startTimeSeconds"),
            "contestDuration":  c.get("durationSeconds"),
            "contestStartDate": datetime.utcfromtimestamp(c["startTimeSeconds"]).strftime("%Y-%m-%d")
                                if c.get("startTimeSeconds") else None,
        }

    print(f"  Got metadata for {len(contest_map)} contests.")
    return contest_map


def build_dataset(problems, statistics, contest_map):
    print("\n[3/3] Building dataset...")

    stats_map = {}
    for s in statistics:
        key = (s.get("contestId"), s.get("index"))
        stats_map[key] = s.get("solvedCount", 0)

    dataset = []
    skipped = 0

    for p in problems:
        cid   = p.get("contestId")
        index = p.get("index")

        if not cid or not index:
            skipped += 1
            continue

        solved_count = stats_map.get((cid, index), 0)
        contest_info = contest_map.get(cid, {})

        dataset.append({
            "id":               f"{cid}_{index}",
            "contestId":        cid,
            "index":            index,
            "url":              f"https://codeforces.com/contest/{cid}/problem/{index}",
            "name":             p.get("name", ""),
            "type":             p.get("type", "PROGRAMMING"),
            "rating":           p.get("rating"),
            "tags":             p.get("tags", []),
            "solvedCount":      solved_count,
            "contestName":      contest_info.get("contestName", ""),
            "contestType":      contest_info.get("contestType", ""),
            "contestPhase":     contest_info.get("contestPhase", ""),
            "contestStartDate": contest_info.get("contestStartDate"),
            "contestStartTime": contest_info.get("contestStartTime"),
            "contestDuration":  contest_info.get("contestDuration"),
        })

    rated   = sum(1 for p in dataset if p["rating"] is not None)
    unrated = sum(1 for p in dataset if p["rating"] is None)

    print(f"  Total problems:       {len(dataset)}")
    print(f"    Rated:              {rated}")
    print(f"    Unrated:            {unrated}")
    print(f"    Skipped:            {skipped}")
    return dataset


def print_summary(dataset):
    print("\n--- Dataset Summary ---")

    rated = [p for p in dataset if p["rating"]]
    if rated:
        ratings = [p["rating"] for p in rated]
        print(f"Rating range: {min(ratings)} – {max(ratings)}")
        print("\nRating distribution:")
        buckets = {}
        for r in ratings:
            b = (r // 200) * 200
            buckets[b] = buckets.get(b, 0) + 1
        for b in sorted(buckets):
            bar = "█" * (buckets[b] // 20)
            print(f"  {b:4d}–{b+199}: {buckets[b]:5d}  {bar}")

    tag_freq = {}
    for p in dataset:
        for t in p["tags"]:
            tag_freq[t] = tag_freq.get(t, 0) + 1
    top_tags = sorted(tag_freq.items(), key=lambda x: -x[1])[:15]
    print("\nTop 15 tags:")
    for tag, count in top_tags:
        print(f"  {tag:<30} {count}")

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
    dataset              = build_dataset(problems, statistics, contest_map)

    output_file = "problems.json"
    print(f"\nSaving to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)

    size_kb = len(json.dumps(dataset)) / 1024
    print(f"Saved {len(dataset)} problems ({size_kb:.0f} KB)")

    print_summary(dataset)
    print("\nAll done! Run generate.py to create your daily practice set.")


if __name__ == "__main__":
    main()
