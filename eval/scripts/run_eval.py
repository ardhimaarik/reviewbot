#!/usr/bin/env python3
"""
run_eval.py — Run full evaluation dataset and compute metrics.

Usage:
    cd /Users/ardhimaarik/Documents/reviewbot
    python -m eval.scripts.run_eval

Output:
    eval/reports/eval-YYYYMMDD-HHMMSS.md
    eval/reports/eval-YYYYMMDD-HHMMSS.json
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8081")
DATASET_DIR = Path("eval/dataset")
REPORTS_DIR = Path("eval/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

LINE_TOLERANCE = 5  # lines of tolerance for issue matching


def load_dataset() -> list[dict]:
    """Load all cases from dataset directory."""
    cases = []
    for jsonl_file in DATASET_DIR.glob("**/*.jsonl"):
        for line in jsonl_file.read_text().splitlines():
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def call_ai_service(case: dict) -> Optional[dict]:
    """Call Python AI service for a single case."""
    try:
        resp = requests.post(
            f"{AI_SERVICE_URL}/review",
            json={
                "diff": case["diff"],
                "file_paths": case["files"],
                "repo_path": ".",
                "model": "qwen3.5:9b",
            },
            timeout=120,
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  ⚠️ AI service error {resp.status_code}: {resp.text[:100]}")
            return None
    except Exception as e:
        print(f"  ❌ Call failed: {e}")
        return None


def match_issues(bot_issues: list[dict], human_labels: list[dict]) -> tuple:
    """
    Match bot issues to human labels.
    
    Match criteria:
    - Same file (or empty file in human label)
    - abs(line diff) <= LINE_TOLERANCE
    - Same category/type
    
    Returns: (matched, unmatched_bot, unmatched_human)
    """
    unmatched_human = [h for h in human_labels if h.get("catchable_by_llm") is not False]
    matched = []
    unmatched_bot = []

    for bot_iss in bot_issues:
        found = False
        for i, human_iss in enumerate(unmatched_human):
            # File match (if human has file info)
            file_match = (
                case.get("source") == "historical" or  # skip file check for historical
                not human_iss.get("file") or
                bot_iss.get("file", "") == human_iss.get("file", "")
            )

            # Line match
            bot_line = bot_iss.get("line", 0)
            human_line = human_iss.get("line", 0)
            line_match = human_line == 0 or abs(bot_line - human_line) <= LINE_TOLERANCE

            # Category match (if human has type info)
            cat_match = (
                not human_iss.get("type") or
                bot_iss.get("category", "") == human_iss.get("type", "")
            )

            if file_match and line_match and cat_match:
                matched.append((bot_iss, human_iss))
                unmatched_human.pop(i)
                found = True
                break

        if not found:
            unmatched_bot.append(bot_iss)

    return matched, unmatched_bot, unmatched_human


def check_hallucination(bot_issues: list[dict], diff: str) -> int:
    """Count issues that reference files/lines not in the diff."""
    hallucinations = 0
    diff_files = set()
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            diff_files.add(line[6:])

    for iss in bot_issues:
        if iss.get("file") and diff_files and iss["file"] not in diff_files:
            hallucinations += 1

    return hallucinations


def compute_metrics(results: list[dict]) -> dict:
    """Compute precision, recall, false positive rate, latency, cost."""
    # Separate by source
    synthetic = [r for r in results if r["source"] == "synthetic"]
    historical = [r for r in results if r["source"] == "historical"]
    clean = [r for r in results if r["source"] == "clean"]

    # True positives, false positives, false negatives
    total_tp = sum(len(r["matched"]) for r in results if r["source"] != "clean")
    total_fp = sum(len(r["unmatched_bot"]) for r in results)
    total_fn = sum(len(r["unmatched_human"]) for r in results if r["source"] != "clean")

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0

    # False positive rate on clean PRs
    clean_with_issues = sum(1 for r in clean if r["bot_issue_count"] > 0)
    fpr = clean_with_issues / len(clean) if clean else 0

    # Synthetic recall (ground truth = 100% catchable)
    syn_tp = sum(len(r["matched"]) for r in synthetic)
    syn_fn = sum(len(r["unmatched_human"]) for r in synthetic)
    synthetic_recall = syn_tp / (syn_tp + syn_fn) if (syn_tp + syn_fn) > 0 else 0

    # Latency stats
    latencies = [r["latency_ms"] for r in results if r.get("latency_ms")]
    latency_p50 = sorted(latencies)[len(latencies) // 2] if latencies else 0
    latency_p95 = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0

    # Hallucinations
    total_hallucinations = sum(r.get("hallucinations", 0) for r in results)
    total_issues = sum(r["bot_issue_count"] for r in results)
    hallucination_rate = total_hallucinations / total_issues if total_issues > 0 else 0

    return {
        "total_cases": len(results),
        "successful_calls": sum(1 for r in results if r.get("success")),
        "failed_calls": sum(1 for r in results if not r.get("success")),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "false_positive_rate": round(fpr, 3),
        "synthetic_recall": round(synthetic_recall, 3),
        "latency_p50_ms": latency_p50,
        "latency_p95_ms": latency_p95,
        "hallucinations_total": total_hallucinations,
        "hallucination_rate": round(hallucination_rate, 4),
        "total_issues_found": total_issues,
        "by_source": {
            "historical": len(historical),
            "synthetic": len(synthetic),
            "clean": len(clean),
        },
    }


def generate_report(metrics: dict, results: list[dict], timestamp: str) -> str:
    """Generate markdown report."""
    git_sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True
    ).stdout.strip()

    report = f"""# Reviewbot Eval Report

**Date**: {timestamp}
**Git SHA**: {git_sha}
**Model**: qwen3.5:9b
**Prompt Version**: v1
**Dataset Version**: v1

---

## Summary Metrics

| Metric | Value | Target |
|---|---|---|
| Precision | {metrics['precision']*100:.1f}% | >= 60% |
| Recall (historical) | {metrics['recall']*100:.1f}% | >= 40% |
| Synthetic Recall | {metrics['synthetic_recall']*100:.1f}% | >= 70% |
| False Positive Rate | {metrics['false_positive_rate']*100:.1f}% | <= 20% |
| Latency p50 | {metrics['latency_p50_ms']}ms | < 60000ms |
| Latency p95 | {metrics['latency_p95_ms']}ms | < 120000ms |
| Hallucination Rate | {metrics['hallucination_rate']*100:.2f}% | 0% |

---

## Dataset Breakdown

| Source | Count |
|---|---|
| Historical PRs | {metrics['by_source']['historical']} |
| Synthetic bugs | {metrics['by_source']['synthetic']} |
| Clean PRs | {metrics['by_source']['clean']} |
| **Total** | **{metrics['total_cases']}** |

- Successful calls: {metrics['successful_calls']}
- Failed calls: {metrics['failed_calls']}
- Total issues found: {metrics['total_issues_found']}
- Hallucinations: {metrics['hallucinations_total']}

---

## Observations

### What went well
- TBD (fill after first run)

### Failure modes
- TBD (fill after first run)

### Next iteration
- TBD (fill after first run)

---

## Matching Rules

Issues matched when:
- Same file (or human label has no file info)
- `abs(bot_line - human_line) <= {LINE_TOLERANCE}`
- Same category (or human label has no type info)

**Limitation**: Matching is approximate. Line numbers may differ due to diff context. This is documented and acceptable for v1 eval.

---

*Generated by `make eval`*
"""
    return report


def save_to_db(metrics: dict, timestamp: str):
    """Save eval results to Postgres."""
    try:
        import psycopg2
        dsn = os.getenv("EVAL_POSTGRES_DSN") or os.getenv("POSTGRES_DSN")
        if not dsn:
            print("  ⚠️ POSTGRES_DSN not set, skipping DB save")
            return

        conn = psycopg2.connect(dsn)
        cur = conn.cursor()

        git_sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True
        ).stdout.strip()

        cur.execute(
            """INSERT INTO eval_runs (git_sha, model, prompt_version, dataset_version, metrics)
               VALUES (%s, %s, %s, %s, %s)""",
            (git_sha, "qwen3.5:9b", "v1", "v1", json.dumps(metrics))
        )
        conn.commit()
        conn.close()
        print("  ✅ Saved to Postgres eval_runs")
    except Exception as e:
        print(f"  ⚠️ DB save failed: {e}")


def main():
    print("🔍 Reviewbot Eval Harness")
    print("=" * 50)

    # Load dataset
    cases = load_dataset()
    if not cases:
        print("❌ No dataset found. Run scrape_prs.py and generate_synthetic.py first.")
        sys.exit(1)

    print(f"📦 Loaded {len(cases)} cases")

    # Run eval
    results = []
    start_time = time.time()

    for i, case in enumerate(cases):
        case_id = case["id"]
        source = case.get("source", "unknown")
        print(f"\n[{i+1}/{len(cases)}] {case_id} ({source})")

        # Call AI service
        t0 = time.time()
        ai_resp = call_ai_service(case)
        latency_ms = int((time.time() - t0) * 1000)

        if not ai_resp:
            results.append({
                "id": case_id,
                "source": source,
                "success": False,
                "bot_issue_count": 0,
                "matched": [],
                "unmatched_bot": [],
                "unmatched_human": case.get("human_labels", []),
                "hallucinations": 0,
                "latency_ms": latency_ms,
            })
            continue

        bot_issues = ai_resp.get("review", {}).get("issues", [])
        human_labels = case.get("human_labels", [])

        # Match issues
        matched, unmatched_bot, unmatched_human = match_issues(bot_issues, human_labels)

        # Check hallucinations
        hallucinations = check_hallucination(bot_issues, case.get("diff", ""))

        print(f"  Bot: {len(bot_issues)} issues | Matched: {len(matched)} | FP: {len(unmatched_bot)} | FN: {len(unmatched_human)} | {latency_ms}ms")

        results.append({
            "id": case_id,
            "source": source,
            "success": True,
            "bot_issue_count": len(bot_issues),
            "matched": matched,
            "unmatched_bot": unmatched_bot,
            "unmatched_human": unmatched_human,
            "hallucinations": hallucinations,
            "latency_ms": latency_ms,
        })

    # Compute metrics
    total_time = int(time.time() - start_time)
    metrics = compute_metrics(results)
    metrics["total_time_seconds"] = total_time

    # Generate timestamp
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    # Save report
    report_md = generate_report(metrics, results, timestamp)
    report_path = REPORTS_DIR / f"eval-{timestamp}.md"
    report_path.write_text(report_md)

    # Save JSON
    json_path = REPORTS_DIR / f"eval-{timestamp}.json"
    json_path.write_text(json.dumps(metrics, indent=2))

    # Save to DB
    save_to_db(metrics, timestamp)

    # Print summary
    print("\n" + "=" * 50)
    print("📊 EVAL RESULTS")
    print("=" * 50)
    print(f"  Precision:         {metrics['precision']*100:.1f}%")
    print(f"  Recall:            {metrics['recall']*100:.1f}%")
    print(f"  Synthetic Recall:  {metrics['synthetic_recall']*100:.1f}%")
    print(f"  False Positive:    {metrics['false_positive_rate']*100:.1f}%")
    print(f"  Hallucinations:    {metrics['hallucinations_total']}")
    print(f"  Latency p50:       {metrics['latency_p50_ms']}ms")
    print(f"  Latency p95:       {metrics['latency_p95_ms']}ms")
    print(f"  Total time:        {total_time}s")
    print(f"\n📄 Report: {report_path}")
    print(f"📄 JSON:   {json_path}")


if __name__ == "__main__":
    main()
