"""
Codeforces User Report Generator

Fetches user's solved problems from Codeforces API and generates
a statistics report with visualizations.

Usage:
    python report.py
"""

import json
import sys
import time
from datetime import datetime

try:
    import cloudscraper
except ImportError:
    print("Missing dependency. Please run:")
    print("  pip install cloudscraper")
    sys.exit(1)


# ============================================================================
# USER API FETCHING
# ============================================================================


def fetch_user_submissions(username, retries=3, delay=2):
    """Fetch user's accepted submissions from Codeforces API"""
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )

    url = f"https://codeforces.com/api/user.status?handle={username}&from=1"

    print(f"\n🔍 Fetching submissions for user: {username}")

    for attempt in range(retries):
        try:
            print(f"  GET {url}")
            res = scraper.get(url, timeout=30)
            print(f"  HTTP {res.status_code}")

            if res.status_code != 200:
                print(f"  Non-200 response")
                if attempt < retries - 1:
                    print(f"  Retrying in {delay}s...")
                    time.sleep(delay)
                continue

            data = res.json()

            if data.get("status") == "OK":
                return data.get("result", [])
            else:
                comment = data.get("comment", "unknown error")
                print(f"  API error: {comment}")

                if "does not exist" in comment.lower():
                    print(f"\n❌ User '{username}' not found!")
                    return None

                if "limit" in comment.lower():
                    print(f"  Rate limited — waiting 5s...")
                    time.sleep(5)

        except json.JSONDecodeError as e:
            print(f"  JSON parse error: {e}")
        except Exception as e:
            print(f"  Error: {e}")

        if attempt < retries - 1:
            time.sleep(delay)

    return None


def fetch_user_info(username, retries=3, delay=2):
    """Fetch user info (rating, rank, etc.)"""
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )

    url = f"https://codeforces.com/api/user.info?handles={username}"

    for attempt in range(retries):
        try:
            res = scraper.get(url, timeout=30)

            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "OK":
                    return data.get("result", [{}])[0]
        except Exception as e:
            pass

        if attempt < retries - 1:
            time.sleep(delay)

    return {}


# ============================================================================
# DATA PROCESSING
# ============================================================================


def extract_solved_problems(submissions):
    """Extract unique solved problems from submissions"""
    solved = {}

    for sub in submissions:
        # Only count accepted verdicts
        if sub.get("verdict") != "OK":
            continue

        problem = sub.get("problem", {})
        contest_id = problem.get("contestId")
        index = problem.get("index")

        if not contest_id or not index:
            continue

        problem_id = f"{contest_id}_{index}"

        # Store first solve (earliest)
        if problem_id not in solved:
            solved[problem_id] = {
                "name": problem.get("name", ""),
                "rating": problem.get("rating"),
                "tags": problem.get("tags", []),
                "contestId": contest_id,
                "index": index,
                "timestamp": sub.get("creationTimeSeconds"),
            }

    return solved


def load_problems_db():
    """Load problems.json for enrichment"""
    try:
        with open("problems.json") as f:
            problems = json.load(f)
            return {p["id"]: p for p in problems}
    except FileNotFoundError:
        return {}


def enrich_solved_problems(solved, problems_db):
    """Enrich solved problems with additional data from problems.json"""
    for pid, prob in solved.items():
        if pid in problems_db:
            db_prob = problems_db[pid]
            # Fill in missing data
            if not prob["rating"]:
                prob["rating"] = db_prob.get("rating")
            if not prob["tags"]:
                prob["tags"] = db_prob.get("tags", [])

    return solved


def calculate_statistics(solved, user_info):
    """Calculate statistics from solved problems"""
    stats = {
        "username": user_info.get("handle", "Unknown"),
        "current_rating": user_info.get("rating", 0),
        "max_rating": user_info.get("maxRating", 0),
        "rank": user_info.get("rank", "Unrated"),
        "total_solved": len(solved),
        "rating_distribution": {},
        "tag_distribution": {},
        "solve_timeline": {},
    }

    # Rating distribution
    for prob in solved.values():
        rating = prob.get("rating")
        if rating:
            bucket = (rating // 100) * 100
            stats["rating_distribution"][bucket] = (
                stats["rating_distribution"].get(bucket, 0) + 1
            )

    # Tag distribution
    for prob in solved.values():
        for tag in prob.get("tags", []):
            stats["tag_distribution"][tag] = stats["tag_distribution"].get(tag, 0) + 1

    # Timeline (by month)
    for prob in solved.values():
        ts = prob.get("timestamp")
        if ts:
            dt = datetime.utcfromtimestamp(ts)
            month_key = dt.strftime("%Y-%m")
            stats["solve_timeline"][month_key] = (
                stats["solve_timeline"].get(month_key, 0) + 1
            )

    return stats


# ============================================================================
# HTML GENERATION
# ============================================================================


def generate_report_html(stats, solved):
    """Generate report.html with statistics and visualizations"""

    # Top tags
    top_tags = sorted(stats["tag_distribution"].items(), key=lambda x: -x[1])[:10]

    # Top rating buckets
    rating_dist = sorted(stats["rating_distribution"].items())

    # Timeline
    timeline = sorted(stats["solve_timeline"].items())

    # Build rating distribution bars
    rating_bars = ""
    max_count = (
        max(stats["rating_distribution"].values())
        if stats["rating_distribution"]
        else 1
    )
    for rating, count in rating_dist:
        pct = (count / max_count) * 100
        rating_bars += f"""
                <tr>
                    <td>{rating}–{rating + 99}</td>
                    <td class="bar-container">
                        <div class="bar" style="width: {pct}%"></div>
                    </td>
                    <td>{count}</td>
                </tr>"""

    # Build tag bars
    tag_bars = ""
    max_tag_count = max(c for _, c in top_tags) if top_tags else 1
    for tag, count in top_tags:
        pct = (count / max_tag_count) * 100
        tag_bars += f"""
                <tr>
                    <td>{tag}</td>
                    <td class="bar-container">
                        <div class="bar" style="width: {pct}%"></div>
                    </td>
                    <td>{count}</td>
                </tr>"""

    # Build timeline
    timeline_html = ""
    max_month = max(c for _, c in timeline) if timeline else 1
    for month, count in timeline:
        pct = (count / max_month) * 100
        timeline_html += f"""
                <tr>
                    <td>{month}</td>
                    <td class="bar-container">
                        <div class="bar" style="width: {pct}%"></div>
                    </td>
                    <td>{count}</td>
                </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Codeforces Report: {stats["username"]}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: "Georgia", "Times New Roman", serif;
            background-color: #f5f5f0;
            padding: 40px 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background-color: white;
            padding: 60px 50px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        }}

        h1 {{
            text-align: center;
            font-size: 32px;
            margin-bottom: 10px;
            font-weight: normal;
            letter-spacing: 1px;
        }}

        .username {{
            text-align: center;
            color: #0066cc;
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 30px;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            margin-bottom: 50px;
        }}

        .stat-card {{
            text-align: center;
            padding: 20px;
            border: 1px solid #ddd;
            background-color: #fafaf8;
        }}

        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            color: #000;
            margin-bottom: 5px;
        }}

        .stat-label {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #666;
        }}

        .section {{
            margin-bottom: 50px;
        }}

        .section-title {{
            font-size: 20px;
            font-weight: normal;
            letter-spacing: 1px;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #000;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}

        th {{
            text-align: left;
            padding: 12px;
            font-weight: normal;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #333;
            border-bottom: 1px solid #ddd;
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid #ddd;
            font-size: 14px;
        }}

        tr:hover {{
            background-color: #f9f9f9;
        }}

        .bar-container {{
            position: relative;
            height: 24px;
            background-color: #e0e0d8;
            min-width: 200px;
        }}

        .bar {{
            height: 100%;
            background-color: #333;
            transition: width 0.3s ease;
        }}

        .count {{
            text-align: right;
            min-width: 50px;
        }}

        .footer {{
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 50px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}

        .generated-at {{
            font-size: 11px;
            color: #999;
        }}

        .rating-positive {{
            color: #0066cc;
        }}

        .rating-neutral {{
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Codeforces Report</h1>
        <div class="username">{stats["username"]}</div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{stats["current_rating"]}</div>
                <div class="stat-label">Current Rating</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats["max_rating"]}</div>
                <div class="stat-label">Max Rating</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats["rank"]}</div>
                <div class="stat-label">Rank</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{stats["total_solved"]}</div>
                <div class="stat-label">Problems Solved</div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Problems by Difficulty</div>
            <table>
                <thead>
                    <tr>
                        <th>Rating Range</th>
                        <th>Distribution</th>
                        <th class="count">Count</th>
                    </tr>
                </thead>
                <tbody>
{rating_bars}
                </tbody>
            </table>
        </div>

        <div class="section">
            <div class="section-title">Top Tags</div>
            <table>
                <thead>
                    <tr>
                        <th>Tag</th>
                        <th>Distribution</th>
                        <th class="count">Count</th>
                    </tr>
                </thead>
                <tbody>
{tag_bars}
                </tbody>
            </table>
        </div>

        <div class="section">
            <div class="section-title">Solve Timeline (by Month)</div>
            <table>
                <thead>
                    <tr>
                        <th>Month</th>
                        <th>Distribution</th>
                        <th class="count">Count</th>
                    </tr>
                </thead>
                <tbody>
{timeline_html}
                </tbody>
            </table>
        </div>

        <div class="footer">
            <p>Report generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
            <p class="generated-at">Data fetched from Codeforces API</p>
        </div>
    </div>
</body>
</html>"""

    return html


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def main():
    print("\n" + "=" * 60)
    print("CODEFORCES USER REPORT GENERATOR")
    print("=" * 60)

    # Prompt for username
    username = input("\nEnter your Codeforces username: ").strip()
    if not username:
        print("❌ Username cannot be empty")
        sys.exit(1)

    # Fetch user info
    user_info = fetch_user_info(username)
    if not user_info or not user_info.get("handle"):
        print(f"\n❌ Could not find user '{username}'")
        sys.exit(1)

    print(f"✓ Found user: {user_info.get('handle')}")
    print(f"  Current rating: {user_info.get('rating', 0)}")
    print(f"  Rank: {user_info.get('rank', 'Unrated')}")

    # Fetch submissions
    submissions = fetch_user_submissions(username)
    if submissions is None:
        print(f"\n❌ Could not fetch submissions for '{username}'")
        sys.exit(1)

    print(f"✓ Fetched {len(submissions)} submissions")

    # Extract solved problems
    print("\n📊 Processing solved problems...")
    solved = extract_solved_problems(submissions)
    print(f"✓ Found {len(solved)} unique solved problems")

    # Enrich with local data
    problems_db = load_problems_db()
    if problems_db:
        print(f"✓ Enriching with {len(problems_db)} local problems")
        solved = enrich_solved_problems(solved, problems_db)

    # Calculate statistics
    stats = calculate_statistics(solved, user_info)

    # Update done.txt
    print("\n💾 Updating done.txt...")
    existing_done = set()
    try:
        with open("done.txt") as f:
            existing_done = set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        pass

    new_problems = set(solved.keys()) - existing_done
    if new_problems:
        with open("done.txt", "a") as f:
            for pid in sorted(new_problems):
                f.write(pid + "\n")
        print(f"✓ Added {len(new_problems)} new problems to done.txt")
        print(
            f"  (Already had {len(existing_done)}, now at {len(existing_done) + len(new_problems)} total)"
        )
    else:
        print(f"✓ No new problems to add (all {len(solved)} already in done.txt)")

    # Generate report HTML
    print("\n📝 Generating report.html...")
    html_content = generate_report_html(stats, solved)
    with open("report.html", "w") as f:
        f.write(html_content)
    print("✓ Generated report.html")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Username: {stats['username']}")
    print(f"Current rating: {stats['current_rating']}")
    print(f"Max rating: {stats['max_rating']}")
    print(f"Total solved: {stats['total_solved']}")
    print(f"New problems added: {len(new_problems)}")
    print(f"\n✓ Report saved to report.html")
    print("  Open it in your browser to view statistics")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
