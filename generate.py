"""
Codeforces Daily Practice Generator

Generates index.html with filtered problems and starts a local HTTP server
for marking problems as done.

Usage:
    python generate.py
"""

import json
import random
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import webbrowser
import time


# ============================================================================
# CONFIGURATION & DATA LOADING
# ============================================================================


def load_problems():
    """Load problems from problems.json"""
    if not os.path.exists("problems.json"):
        print("\n❌ ERROR: problems.json not found!")
        print("   Please run: python scrape.py")
        sys.exit(1)

    with open("problems.json", "r") as f:
        return json.load(f)


def load_done():
    """Load completed problem IDs from done.txt"""
    done_set = set()
    if os.path.exists("done.txt"):
        try:
            with open("done.txt", "r") as f:
                done_set = set(line.strip() for line in f if line.strip())
        except Exception as e:
            print(f"⚠️  Warning: Could not read done.txt: {e}")
    return done_set


def get_available_tags(problems):
    """Extract all unique tags from problems"""
    tags = set()
    for p in problems:
        tags.update(p.get("tags", []))
    return sorted(tags)


# ============================================================================
# USER INPUT PROMPTS
# ============================================================================


def prompt_difficulty_range(problems):
    """Prompt user for min and max difficulty rating"""
    rated = [p for p in problems if p.get("rating") is not None]

    if not rated:
        print("❌ No rated problems available!")
        sys.exit(1)

    ratings = [p["rating"] for p in rated]
    min_rating = min(ratings)
    max_rating = max(ratings)

    print("\n" + "=" * 60)
    print("DIFFICULTY RANGE")
    print("=" * 60)
    print(f"Available range: {min_rating} – {max_rating}")

    while True:
        try:
            user_min = int(
                input(f"\nMin difficulty (default {min_rating}): ") or min_rating
            )
            user_max = int(
                input(f"Max difficulty (default {max_rating}): ") or max_rating
            )

            if user_min > user_max:
                print("⚠️  Min must be ≤ Max. Try again.")
                continue

            if user_min < min_rating or user_max > max_rating:
                print(f"⚠️  Range must be within {min_rating}–{max_rating}. Try again.")
                continue

            return user_min, user_max
        except ValueError:
            print("⚠️  Invalid input. Please enter integers.")


def prompt_num_problems(available_count):
    """Prompt user for number of problems"""
    print("\n" + "=" * 60)
    print("NUMBER OF PROBLEMS")
    print("=" * 60)
    print(f"Available: {available_count} problems after filtering")

    while True:
        try:
            num = int(
                input(f"\nHow many problems? (default 10, max {available_count}): ")
                or 10
            )
            if num <= 0:
                print("⚠️  Please enter a positive number.")
                continue
            if num > available_count:
                print(f"⚠️  Only {available_count} available. Using that instead.")
                return available_count
            return num
        except ValueError:
            print("⚠️  Invalid input. Please enter an integer.")


def prompt_tag_filter(available_tags):
    """Prompt user to filter by tags"""
    print("\n" + "=" * 60)
    print("TAG FILTERING")
    print("=" * 60)
    print("\nAvailable tags:")
    for i, tag in enumerate(available_tags, 1):
        print(f"  {i:2d}. {tag}")

    print("\nOptions:")
    print("  [Enter]        Include ALL tags (no filtering)")
    print("  [1,2,3...]     Select specific tags (comma-separated numbers)")
    print("  [*]            Show this list again")

    while True:
        choice = input("\nYour choice: ").strip()

        if not choice or choice.lower() == "all":
            print("✓ Using all tags")
            return None  # None means "accept all tags"

        if choice == "*":
            print("\nAvailable tags:")
            for i, tag in enumerate(available_tags, 1):
                print(f"  {i:2d}. {tag}")
            continue

        try:
            indices = [int(x.strip()) - 1 for x in choice.split(",")]
            if any(i < 0 or i >= len(available_tags) for i in indices):
                print("⚠️  Some indices out of range. Try again.")
                continue

            selected = [available_tags[i] for i in indices]
            print(f"✓ Selected tags: {', '.join(selected)}")
            return selected
        except ValueError:
            print("⚠️  Invalid input. Use comma-separated numbers or press Enter.")


# ============================================================================
# PROBLEM FILTERING & SELECTION
# ============================================================================


def filter_problems(problems, done_set, min_rating, max_rating, selected_tags):
    """
    Filter problems by:
    - Not in done_set
    - Rating in [min_rating, max_rating]
    - Contains ANY of selected_tags (if specified)
    """
    filtered = []

    for p in problems:
        # Skip if already done
        if p["id"] in done_set:
            continue

        # Skip if unrated
        if p.get("rating") is None:
            continue

        # Check rating range
        if not (min_rating <= p["rating"] <= max_rating):
            continue

        # Check tags
        if selected_tags is not None:
            problem_tags = set(p.get("tags", []))
            if not problem_tags.intersection(selected_tags):
                continue

        filtered.append(p)

    return filtered


def select_problems_by_band(filtered, num_problems):
    """
    Select problems by spreading across rating bands.
    If a band is empty, overflow to other bands.
    """
    if not filtered:
        return []

    if len(filtered) <= num_problems:
        return filtered

    # Divide rating range into 3 bands
    ratings = [p["rating"] for p in filtered]
    min_r = min(ratings)
    max_r = max(ratings)

    if min_r == max_r:
        # All problems have same rating, just pick randomly
        random.shuffle(filtered)
        return filtered[:num_problems]

    band_size = (max_r - min_r) / 3
    bands = {0: [], 1: [], 2: []}

    for p in filtered:
        if p["rating"] == max_r:
            band = 2
        else:
            band = int((p["rating"] - min_r) / band_size)
            band = min(band, 2)
        bands[band].append(p)

    # Shuffle each band
    for band in bands:
        random.shuffle(bands[band])

    # Pick evenly from each band
    selected = []
    per_band = num_problems // 3
    remainder = num_problems % 3

    for band in [0, 1, 2]:
        count = per_band + (1 if band < remainder else 0)
        selected.extend(bands[band][:count])

    # If we don't have enough, fill from remaining
    if len(selected) < num_problems:
        remaining = [p for p in filtered if p not in selected]
        random.shuffle(remaining)
        selected.extend(remaining[: num_problems - len(selected)])

    # Shuffle final selection for randomness
    random.shuffle(selected)
    return selected[:num_problems]


# ============================================================================
# HTML GENERATION
# ============================================================================


def generate_html(selected_problems, done_set):
    """Generate index.html from selected problems"""

    # Build table rows
    rows = []
    for p in selected_problems:
        is_done = p["id"] in done_set
        completed_class = ' class="completed"' if is_done else ""
        checked = "checked" if is_done else ""

        row = f'''                <tr class="problem-row" data-problem-id="{p["id"]}"{completed_class}>
                    <td class="checkbox-cell">
                        <input type="checkbox" class="problem-checkbox" {checked}>
                    </td>
                    <td class="problem-name">{p["name"]}</td>
                    <td class="rating">{p["rating"]}</td>
                    <td class="link-cell">
                        <a href="{p["url"]}" target="_blank">Open</a>
                    </td>
                </tr>'''
        rows.append(row)

    rows_html = "\n".join(rows)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Codeforces Daily Practice</title>
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
            max-width: 900px;
            margin: 0 auto;
            background-color: white;
            padding: 60px 50px;
            box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
        }}

        h1 {{
            text-align: center;
            font-size: 28px;
            margin-bottom: 10px;
            font-weight: normal;
            letter-spacing: 1px;
        }}

        .subtitle {{
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 40px;
            text-transform: uppercase;
            letter-spacing: 2px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }}

        thead {{
            border-bottom: 2px solid black;
            border-top: 2px solid black;
        }}

        th {{
            text-align: left;
            padding: 15px 10px;
            font-weight: normal;
            font-size: 13px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #333;
        }}

        td {{
            padding: 16px 10px;
            border-bottom: 1px solid #ddd;
            font-size: 14px;
        }}

        tr:last-child td {{
            border-bottom: 2px solid black;
        }}

        .problem-name {{
            font-weight: 500;
            color: #000;
        }}

        .rating {{
            text-align: center;
            min-width: 60px;
            color: #555;
        }}

        .checkbox-cell {{
            text-align: center;
            width: 50px;
        }}

        .checkbox-cell input[type="checkbox"] {{
            width: 18px;
            height: 18px;
            cursor: pointer;
            accent-color: black;
        }}

        .link-cell {{
            text-align: center;
        }}

        .link-cell a {{
            color: #0066cc;
            text-decoration: none;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .link-cell a:hover {{
            text-decoration: underline;
        }}

        tr.completed .problem-name {{
            color: #999;
            text-decoration: line-through;
        }}

        tr.completed {{
            background-color: #f9f9f9;
        }}

        .footer {{
            text-align: center;
            color: #999;
            font-size: 12px;
            margin-top: 40px;
            border-top: 1px solid #ddd;
            padding-top: 20px;
        }}

        .stats {{
            display: flex;
            justify-content: space-around;
            margin-bottom: 30px;
            padding: 15px;
            background-color: #fafaf8;
            border: 1px solid #e0e0d8;
        }}

        .stat-item {{
            text-align: center;
        }}

        .stat-number {{
            font-size: 24px;
            font-weight: bold;
            color: #000;
        }}

        .stat-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #666;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Daily Practice Set</h1>
        <p class="subtitle">Codeforces Problem Selection</p>

        <div class="stats">
            <div class="stat-item">
                <div class="stat-number" id="total-count">{len(selected_problems)}</div>
                <div class="stat-label">Total Problems</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" id="completed-count">0</div>
                <div class="stat-label">Completed</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" id="remaining-count">{len(selected_problems)}</div>
                <div class="stat-label">Remaining</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 40px;"></th>
                    <th>Problem</th>
                    <th style="width: 70px;">Rating</th>
                    <th style="width: 60px;">Link</th>
                </tr>
            </thead>
            <tbody id="problems-tbody">
{rows_html}
            </tbody>
        </table>

        <div class="footer">
            <p>Check the box to mark problems as completed. Changes are saved automatically.</p>
        </div>
    </div>

    <script>
        // Track completed problems
        const doneSet = new Set();

        // Load done list from server
        async function loadDone() {{
            try {{
                const res = await fetch('/done-list');
                if (res.ok) {{
                    const data = await res.json();
                    data.forEach(id => doneSet.add(id));
                    updateUI();
                }}
            }} catch (err) {{
                console.log('Note: Could not load done list from server');
            }}
        }}

        // Mark problem as done
        async function markDone(problemId, isDone) {{
            try {{
                const method = isDone ? 'POST' : 'DELETE';
                const res = await fetch('/done', {{
                    method: method,
                    body: problemId
                }});
                
                if (res.ok) {{
                    if (isDone) {{
                        doneSet.add(problemId);
                    }} else {{
                        doneSet.delete(problemId);
                    }}
                    updateUI();
                }}
            }} catch (err) {{
                console.error('Error marking problem:', err);
            }}
        }}

        // Update UI based on done state
        function updateUI() {{
            const rows = document.querySelectorAll('.problem-row');
            let completed = 0;

            rows.forEach(row => {{
                const problemId = row.dataset.problemId;
                const checkbox = row.querySelector('.problem-checkbox');
                const isDone = doneSet.has(problemId);

                checkbox.checked = isDone;
                if (isDone) {{
                    row.classList.add('completed');
                    completed++;
                }} else {{
                    row.classList.remove('completed');
                }}
            }});

            const total = rows.length;
            document.getElementById('completed-count').textContent = completed;
            document.getElementById('remaining-count').textContent = total - completed;
            document.getElementById('total-count').textContent = total;
        }}

        // Attach checkbox listeners
        document.querySelectorAll('.problem-checkbox').forEach(checkbox => {{
            checkbox.addEventListener('change', (e) => {{
                const problemId = e.target.closest('.problem-row').dataset.problemId;
                markDone(problemId, e.target.checked);
            }});
        }});

        // Load done list on page load
        window.addEventListener('DOMContentLoaded', loadDone);
    </script>
</body>
</html>"""

    return html_content


# ============================================================================
# HTTP SERVER FOR MARKING DONE
# ============================================================================


class DoneHandler(BaseHTTPRequestHandler):
    """HTTP handler for marking problems as done"""

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

    def do_GET(self):
        """GET /done-list: Return JSON array of completed problem IDs"""
        if self.path == "/done-list":
            try:
                done_set = load_done()
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(list(done_set)).encode())
            except Exception as e:
                self.send_error(500, str(e))

        elif self.path == "/":
            try:
                with open("index.html", "rb") as f:
                    self.send_response(200)
                    self.send_header("Content-type", "text/html")
                    self.end_headers()
                    self.wfile.write(f.read())
            except Exception as e:
                self.send_error(404, "index.html not found")
        else:
            self.send_error(404)

    def do_POST(self):
        """POST /done: Mark problem as done (append to done.txt)"""
        if self.path == "/done":
            try:
                length = int(self.headers.get("Content-Length", 0))
                problem_id = self.rfile.read(length).decode().strip()

                if problem_id:
                    with open("done.txt", "a") as f:
                        f.write(problem_id + "\n")

                    self.send_response(200)
                    self.end_headers()
                else:
                    self.send_error(400, "Empty problem ID")
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)

    def do_DELETE(self):
        """DELETE /done: Unmark problem as done (remove from done.txt)"""
        if self.path == "/done":
            try:
                length = int(self.headers.get("Content-Length", 0))
                problem_id = self.rfile.read(length).decode().strip()

                if problem_id:
                    done_set = load_done()
                    done_set.discard(problem_id)

                    with open("done.txt", "w") as f:
                        for pid in sorted(done_set):
                            f.write(pid + "\n")

                    self.send_response(200)
                    self.end_headers()
                else:
                    self.send_error(400, "Empty problem ID")
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404)


# ============================================================================
# MAIN EXECUTION
# ============================================================================


def main():
    print("\n" + "=" * 60)
    print("CODEFORCES DAILY PRACTICE GENERATOR")
    print("=" * 60)

    # Load data
    print("\n📂 Loading problems.json...")
    problems = load_problems()
    print(f"✓ Loaded {len(problems)} problems")

    print("\n📋 Loading done.txt...")
    done_set = load_done()
    print(f"✓ Loaded {len(done_set)} completed problems")

    # Get available tags
    available_tags = get_available_tags(problems)
    print(f"✓ Found {len(available_tags)} unique tags")

    # Prompt user for preferences
    min_rating, max_rating = prompt_difficulty_range(problems)

    # Filter by difficulty
    difficulty_filtered = [
        p
        for p in problems
        if p.get("rating") is not None
        and min_rating <= p["rating"] <= max_rating
        and p["id"] not in done_set
    ]
    print(f"\n✓ {len(difficulty_filtered)} problems in range {min_rating}–{max_rating}")

    # Prompt for tags
    selected_tags = prompt_tag_filter(available_tags)

    # Apply tag filter
    if selected_tags is not None:
        tag_filtered = [
            p
            for p in difficulty_filtered
            if any(tag in p.get("tags", []) for tag in selected_tags)
        ]
        print(f"✓ {len(tag_filtered)} problems match tags")
    else:
        tag_filtered = difficulty_filtered

    if not tag_filtered:
        print("\n❌ No problems match your criteria!")
        print("Try adjusting difficulty range or tag selection.")
        sys.exit(1)

    # Prompt for number of problems
    num_problems = prompt_num_problems(len(tag_filtered))

    # Select problems by band
    print(f"\n⚙️  Selecting {num_problems} problems across rating bands...")
    selected_problems = select_problems_by_band(tag_filtered, num_problems)
    print(f"✓ Selected {len(selected_problems)} problems")

    # Generate HTML
    print("\n📝 Generating index.html...")
    html_content = generate_html(selected_problems, done_set)
    with open("index.html", "w") as f:
        f.write(html_content)
    print("✓ Generated index.html")

    # Start HTTP server
    print("\n" + "=" * 60)
    print("STARTING LOCAL SERVER")
    print("=" * 60)
    print("\n🌐 Server running at: http://localhost:8000")
    print("   Opening in browser...")
    print("\n   Press Ctrl+C to stop the server")
    print("=" * 60)

    # Open browser
    try:
        webbrowser.open("http://localhost:8000")
    except Exception as e:
        print(f"\n⚠️  Could not open browser automatically: {e}")
        print("   Visit http://localhost:8000 manually")

    # Start server
    try:
        server = HTTPServer(("localhost", 8000), DoneHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped. Your progress has been saved to done.txt")
        sys.exit(0)
    except OSError as e:
        print(f"\n❌ Error: {e}")
        print("   Port 8000 may already be in use. Try:")
        print("   - Kill the process: lsof -ti:8000 | xargs kill -9")
        print("   - Or try a different port by editing this file")
        sys.exit(1)


if __name__ == "__main__":
    main()
