# Eval Methodology

## Overview

Reviewbot uses an offline evaluation harness to measure review quality objectively.
Every prompt change, model swap, or architectural decision is measured against this dataset.

## Dataset Composition

| Source | Count | Purpose |
|---|---|---|
| Historical PRs | 111 | Ground truth from human reviewers |
| Synthetic bugs | 10 | 100% catchable — measures recall floor |
| Clean PRs | 3 | Should NOT trigger — measures false positive rate |
| **Total** | **124** | — |

### Historical PRs (Source A)

Scraped from public Go repos with strong review culture:
- `prometheus/prometheus` — 25 PRs
- `hashicorp/terraform` — 25 PRs
- `grafana/grafana` — 25 PRs
- `go-chi/chi` — 25 PRs
- `gin-gonic/gin` — 11 PRs

**Selection criteria:**
- Merged PRs only
- Changed files <= 10
- Total diff <= 500 lines
- At least 1 human review comment

### Synthetic Bugs (Source B)

10 hand-crafted Go files with injected bugs:
nil map write, race condition, missing error check, context leak,
integer overflow, SQL injection, defer-in-loop, MD5 password hashing,
nil pointer dereference, mutex copied by value.

Ground truth = 100%. Bot must catch these.

### Clean PRs (Source C)

3 correct Go implementations with no bugs.
Bot should return empty issues or minor-only.
Measures **false positive rate** — the most important trust metric.

## Labeling Schema

```json
{
  "comment_id": "string",
  "file": "path/to/file.go",
  "line": 42,
  "type": "bug|perf|style|clarity|test|nit",
  "severity": "blocker|major|minor|nit",
  "catchable_by_llm": true|false,
  "already_caught_by_linter": false
}
```

`catchable_by_llm`: false if issue requires project-specific context.
Issues marked false are excluded from recall calculation.

## Matching Rules

Bot issue matches human label when:
1. Same file (or human label has no file info)
2. `abs(bot_line - human_line) <= 5`
3. Same category (or human label has no type info)

**Limitation**: Line numbers may differ due to diff context. Tolerance of 5 lines
is pragmatic, not exact. This limitation is acceptable for v1 eval.

## Metrics

| Metric | Formula | Target |
|---|---|---|
| Precision | TP / (TP + FP) | >= 60% |
| Recall | TP / (TP + FN) | >= 40% |
| Synthetic Recall | synthetic TP / total synthetic | >= 70% |
| False Positive Rate | clean PRs with issues / total clean | <= 20% |
| Latency p50 | median end-to-end | < 60s |
| Latency p95 | 95th percentile | < 120s |
| Hallucination Rate | issues with non-existent file/line | 0% |

## Versioning

Each eval run stored in Postgres `eval_runs` table with:
- `git_sha` — code version
- `prompt_version` — prompt version string
- `model` — model used
- `dataset_version` — dataset version
- `metrics` — full metrics JSON

This enables trend charts in Grafana.

## Limitations

1. Historical labels are not manually verified — scraped human comments as-is
2. Matching is approximate (line tolerance, category matching)
3. Dataset size (124 cases) is small — results are directional, not statistically significant
4. Model non-determinism: temperature=0.2, results may vary ±5%
5. golangci-lint not installed in eval environment — linter pre-filter disabled

## Running Eval

```bash
# Full eval run (~90 minutes for 124 cases)
python3 -m eval.scripts.run_eval

# Check latest results
cat eval/reports/$(ls -t eval/reports/*.md | head -1)

# Query trend from Postgres
docker exec homelab-postgres psql -U homelab -d reviewbot \
  -c "SELECT created_at, model, metrics->>'precision' as precision, metrics->>'recall' as recall FROM eval_runs ORDER BY created_at DESC LIMIT 10;"
```

## Baseline Results (2026-08-18, qwen3.5:9b, prompt v1)

| Metric | Baseline | Target | Notes |
|---|---|---|---|
| Precision | 14.5% | 60% | Low — historical labels not manually verified |
| Recall | 6.5% | 40% | Low — file mismatch issue (see Limitation #6) |
| Synthetic Recall | 10% | 70% | Primary metric for Week 2 |
| False Positive Rate | 66.7% | 20% | Critical — too noisy |
| Hallucinations | 0% | 0% | ✅ Perfect |
| Latency p50 | 56.9s | <60s | Borderline |
| Latency p95 | 120s | <120s | At limit |

### Limitation #6: File Mismatch in Historical Labels

GitHub review comments are often posted on files different from those changed in the PR diff. Example: PR changes `promql/engine.go` but reviewer comments on `promql/engine_test.go`. Bot reviews only files in the diff — matching is impossible for cross-file comments.

**Impact**: Precision and recall for historical source are underestimated.

**Mitigation for v2**: Manual labeling pass — mark `catchable_by_llm: false` for cross-file comments. Filter these from recall calculation.

**Primary metric for now**: Synthetic Recall (ground truth = 100% catchable, no file mismatch).

### Key Finding

False positive rate of 66.7% on clean PRs is the most critical issue. Bot is too noisy — engineers will lose trust quickly. Priority for Week 3: confidence gating (threshold 0.7) should reduce this significantly.
