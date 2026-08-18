# ADR-R01: Route Based on Complexity, Not a Single Model

**Date**: 2026-08-18
**Status**: Accepted
**Decider**: Ardhis

---

## Context

PR review has a wide spectrum of difficulty. A typo fix in a comment vs a subtle race condition in concurrent code are 100x different in complexity. Using one model for everything means either:
- Wasting money on a cloud model for trivial diffs, or
- Getting poor results from a local model on complex ones

---

## Options Considered

**Option 1: Single model for all PRs**
- Simple implementation
- Predictable cost
- Suboptimal quality on hard cases OR wasteful on easy cases

**Option 2: Rule-based routing by complexity signals**
- More complex implementation
- Optimizes cost vs quality per PR
- Explainable decisions (no ML black box)

**Option 3: ML classifier to predict complexity**
- Best theoretical routing accuracy
- Requires training data (which we don't have at MVP)
- Adds significant complexity and maintenance burden

---

## Decision

**Option 2: Rule-based routing.**

```go
type Signals struct {
    LinesChanged   int
    FilesChanged   int
    HasConcurrency bool  // "sync.", "goroutine", "chan ", "context."
    HasSecurity    bool  // "crypto/", "auth", "token", "password"
}

func Route(s Signals) Complexity {
    if s.FilesChanged > 5 || s.LinesChanged > 500 { return Complex }
    if s.HasConcurrency || s.HasSecurity { return Complex }
    return Simple
}

// Simple → qwen3.5:9b via Ollama (local, free)
// Complex → Claude Haiku via Anthropic (cloud, paid)
```

---

## Consequences

**Positive:**
- ~70% cost savings (most PRs are simple)
- Explainable routing — can tell engineers why a PR went to cloud
- No training data required
- New metric: routing accuracy (are hard cases actually going to cloud?)

**Negative:**
- Heuristic may misclassify edge cases
- Adds routing logic to orchestrator
- Requires two LLM clients

**Metrics added:**
- `reviewbot_router_decisions_total{decision="simple|complex"}`

---

## Future

If volume grows, can train a binary classifier on accumulated routing decisions + outcomes. Rules give us a baseline dataset for free.

Interview note: "I started with rule-based routing. The rules cover 80% of cases with zero training cost. At scale, I'd layer a classifier on top of the dataset these rules generate."
