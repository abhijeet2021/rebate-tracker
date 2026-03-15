#!/usr/bin/env python3
"""
fetch_clickup.py
Fetches all tasks from the Rebate Tracker ClickUp list and rewrites
the DATA block in index.html with live data.

Usage:
    CLICKUP_API_TOKEN=your_token python fetch_clickup.py

Requires: pip install requests
"""
import os
import sys
import re
import json
import time
from datetime import date, datetime

LIST_ID = "2kzkcy0m-5718"
CLICKUP_URL = "https://app.clickup.com/90181105684/v/l/2kzkcy0m-5718"
API_BASE = "https://api.clickup.com/api/v2"
INDEX_HTML = "index.html"


def get_token():
    token = os.environ.get("CLICKUP_API_TOKEN")
    if not token:
        print("ERROR: CLICKUP_API_TOKEN environment variable is not set.", file=sys.stderr)
        sys.exit(1)
    return token


def fetch_tasks(token):
    headers = {"Authorization": token}
    all_tasks = []
    page = 0
    while True:
        url = f"{API_BASE}/list/{LIST_ID}/task?page={page}&include_closed=true"
        resp = _get_with_retry(url, headers)
        tasks = resp.get("tasks", [])
        if not tasks:
            break
        all_tasks.extend(tasks)
        page += 1
    return all_tasks


def _get_with_retry(url, headers):
    import requests
    resp = requests.get(url, headers=headers)
    if resp.status_code == 429:
        print("Rate limited. Waiting 60s...", file=sys.stderr)
        time.sleep(60)
        resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"ERROR: API returned {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)
    return resp.json()


def parse_date(ms_str):
    """Convert ClickUp millisecond timestamp string to YYYY-MM-DD or None."""
    if not ms_str:
        return None
    try:
        return datetime.utcfromtimestamp(int(ms_str) / 1000).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def transform_tasks(raw_tasks):
    today = date.today()
    tasks = []
    for t in raw_tasks:
        status = t.get("status", {}).get("status", "To Do")
        assignee = ""
        assignees = t.get("assignees", [])
        if assignees:
            assignee = assignees[0].get("username") or assignees[0].get("email", "")

        priority_raw = t.get("priority")
        priority = priority_raw.get("priority", "") if priority_raw else ""

        created_at = parse_date(t.get("date_created"))
        updated_at = parse_date(t.get("date_updated"))
        due_date = parse_date(t.get("due_date"))
        date_closed = parse_date(t.get("date_closed"))

        if date_closed:
            closed_d = date.fromisoformat(date_closed)
            created_d = date.fromisoformat(created_at) if created_at else today
            days_open = (closed_d - created_d).days
        elif created_at:
            days_open = (today - date.fromisoformat(created_at)).days
        else:
            days_open = 0

        if updated_at:
            time_in_status = (today - date.fromisoformat(updated_at)).days
        else:
            time_in_status = 0

        is_overdue = False
        if due_date and status != "Done":
            is_overdue = date.fromisoformat(due_date) < today

        tasks.append({
            "id": t.get("id", ""),
            "name": t.get("name", ""),
            "status": status,
            "assignee": assignee,
            "priority": priority,
            "created_at": created_at or "",
            "updated_at": updated_at or "",
            "due_date": due_date,
            "date_closed": date_closed,
            "task_url": t.get("url", ""),
            "is_overdue": is_overdue,
            "days_open": days_open,
            "time_in_current_status": time_in_status,
        })
    return tasks


def compute_summary(tasks):
    done = [t for t in tasks if t["status"] == "Done"]
    open_tasks = [t for t in tasks if t["status"] != "Done"]
    overdue = [t for t in tasks if t["is_overdue"]]
    in_progress = [t for t in tasks if t["status"] == "In Progress"]
    approval = [t for t in tasks if t["status"] == "Approval & Invoice"]
    todo = [t for t in tasks if t["status"] == "To Do"]

    avg_resolution = None
    if done:
        avg_resolution = round(sum(t["days_open"] for t in done) / len(done))

    max_time = max((t["days_open"] for t in tasks), default=0)
    approval_wait_total = sum(t["time_in_current_status"] for t in approval)
    approval_wait_avg = round(approval_wait_total / len(approval)) if approval else 0

    return {
        "total": len(tasks),
        "open": len(open_tasks),
        "done": len(done),
        "overdue": len(overdue),
        "in_progress": len(in_progress),
        "approval_invoice": len(approval),
        "todo": len(todo),
        "max_time_taken_days": max_time,
        "avg_resolution_days": avg_resolution,
        "avg_approval_wait_days": approval_wait_avg,
        "total_approval_wait_days": approval_wait_total,
    }


def build_data_block(tasks, summary):
    data = {
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "clickup_url": CLICKUP_URL,
    }
    tasks_json = json.dumps(tasks, indent=2)
    summary_json = json.dumps(summary, indent=2)

    block = (
        "<!-- DATA_BLOCK_START -->\n"
        "<script>\n"
        "const DATA = {\n"
        f'  generated_at: "{data["generated_at"]}",\n'
        f'  clickup_url: "{data["clickup_url"]}",\n'
        f"  tasks: {tasks_json}\n"
        "};\n"
        "\n"
        "(function() {\n"
        f"  DATA.summary = {summary_json};\n"
        "})();\n"
        "</script>\n"
        "<!-- DATA_BLOCK_END -->"
    )
    return block


def rewrite_index(new_block):
    if not os.path.exists(INDEX_HTML):
        print(f"ERROR: {INDEX_HTML} not found.", file=sys.stderr)
        sys.exit(1)
    with open(INDEX_HTML, "r", encoding="utf-8") as f:
        html = f.read()
    pattern = r"<!-- DATA_BLOCK_START -->.*?<!-- DATA_BLOCK_END -->"
    updated = re.sub(pattern, new_block, html, flags=re.DOTALL)
    if updated == html:
        print("WARNING: DATA block sentinels not found in index.html. File unchanged.", file=sys.stderr)
        sys.exit(1)
    with open(INDEX_HTML, "w", encoding="utf-8", newline="\n") as f:
        f.write(updated)
    print("index.html updated successfully.")


def main():
    token = get_token()
    print("Fetching tasks from ClickUp...")
    raw = fetch_tasks(token)
    print(f"Fetched {len(raw)} tasks.")
    tasks = transform_tasks(raw)
    summary = compute_summary(tasks)
    print(f"Summary: {summary}")
    block = build_data_block(tasks, summary)
    rewrite_index(block)
    print("Done.")


if __name__ == "__main__":
    main()
