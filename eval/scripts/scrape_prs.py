#!/usr/bin/env python3
"""scrape_prs.py — Fetch historical PRs from public Go repos."""

import json
import os
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

TARGET_REPOS = [
    "prometheus/prometheus",
    "hashicorp/terraform",
    "grafana/grafana",
    "gin-gonic/gin",
    "go-chi/chi",
]

OUTPUT_DIR = Path("eval/dataset/historical")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

MAX_PRS_PER_REPO = 25


def get_merged_prs(repo, max_count):
    prs = []
    page = 1

    print(f"\nScraping {repo}...")

    while len(prs) < max_count and page <= 10:
        url = f"https://api.github.com/repos/{repo}/pulls"
        params = {"state": "closed", "per_page": 30, "page": page, "sort": "updated", "direction": "desc"}

        resp = requests.get(url, headers=HEADERS, params=params)
        if resp.status_code == 403:
            reset = resp.headers.get("X-RateLimit-Reset", "")
            print(f"  Rate limited. Reset: {reset}. Waiting 60s...")
            time.sleep(60)
            continue
        if resp.status_code != 200:
            print(f"  Error {resp.status_code}: {resp.text[:200]}")
            break

        batch = resp.json()
        if not batch:
            break

        for pr in batch:
            if len(prs) >= max_count:
                break
            if not pr.get("merged_at"):
                continue

            # Fetch individual PR for file count
            pr_detail = requests.get(
                f"https://api.github.com/repos/{repo}/pulls/{pr['number']}",
                headers=HEADERS
            )
            if pr_detail.status_code != 200:
                continue
            detail = pr_detail.json()
            time.sleep(0.3)

            # Filter: not too big, not doc-only
            if detail.get("changed_files", 0) > 10:
                print(f"  ⏭️ PR #{pr['number']}: too many files ({detail['changed_files']})")
                continue
            if detail.get("additions", 0) + detail.get("deletions", 0) > 500:
                print(f"  ⏭️ PR #{pr['number']}: too large ({detail['additions']}+{detail['deletions']} lines)")
                continue
            if detail.get("review_comments", 0) < 1:
                continue

            pr_data = fetch_pr_details(repo, pr["number"])
            if pr_data:
                prs.append(pr_data)
                print(f"  ✅ PR #{pr['number']}: {pr['title'][:60]} ({detail['review_comments']} comments)")
                time.sleep(0.5)

        page += 1
        time.sleep(1)

    return prs


def fetch_pr_details(repo, pr_number):
    # Get files
    files_resp = requests.get(
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files",
        headers=HEADERS
    )
    if files_resp.status_code != 200:
        return None

    files = files_resp.json()
    diff = ""
    file_paths = []
    for f in files:
        file_paths.append(f["filename"])
        if f.get("patch"):
            diff += f"diff --git a/{f['filename']} b/{f['filename']}\n{f['patch']}\n"

    go_files = [f for f in file_paths if f.endswith(".go")]
    if not go_files:
        return None

    time.sleep(0.3)

    # Get review comments
    comments_resp = requests.get(
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}/comments",
        headers=HEADERS
    )
    if comments_resp.status_code != 200:
        return None

    comments = comments_resp.json()
    human_labels = []
    for c in comments:
        human_labels.append({
            "comment_id": str(c["id"]),
            "file": c.get("path", ""),
            "line": c.get("original_line") or c.get("line") or 0,
            "body": c["body"],
            "type": "",
            "severity": "",
            "catchable_by_llm": None,
            "already_caught_by_linter": False,
        })

    return {
        "id": f"{repo.replace('/', '_')}_{pr_number}",
        "source": "historical",
        "repo": repo,
        "pr_number": pr_number,
        "pr_url": f"https://github.com/{repo}/pull/{pr_number}",
        "diff": diff,
        "files": file_paths,
        "go_files": go_files,
        "linter_json": "[]",
        "human_labels": human_labels,
        "labeled": False,
    }


def main():
    if not GITHUB_TOKEN:
        print("❌ GITHUB_TOKEN not set")
        return

    # Check rate limit
    rl = requests.get("https://api.github.com/rate_limit", headers=HEADERS)
    if rl.status_code == 200:
        remaining = rl.json()["rate"]["remaining"]
        print(f"GitHub API rate limit remaining: {remaining}")
        if remaining < 100:
            print("⚠️ Low rate limit. Scraping may be slow.")

    all_prs = []
    for repo in TARGET_REPOS:
        prs = get_merged_prs(repo, MAX_PRS_PER_REPO)
        all_prs.extend(prs)

        repo_slug = repo.replace("/", "_")
        output_file = OUTPUT_DIR / f"{repo_slug}.jsonl"
        with open(output_file, "w") as f:
            for pr in prs:
                f.write(json.dumps(pr) + "\n")
        print(f"  Saved {len(prs)} PRs to {output_file}")

    print(f"\n✅ Total: {len(all_prs)} PRs scraped")


if __name__ == "__main__":
    main()
