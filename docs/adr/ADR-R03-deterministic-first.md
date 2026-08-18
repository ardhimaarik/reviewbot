# ADR-R03: Deterministic-First, LLM as Judgment Layer

**Date**: 2026-08-18
**Status**: Accepted
**Decider**: Ardhis

---

## Context

Many "review comments" are actually deterministic findings: unused variables, unformatted code, missing error checks that golangci-lint catches reliably. Using an LLM for these wastes tokens, adds latency, and introduces non-determinism where determinism is available.

The LLM's actual value is in things linters cannot catch: subtle logic bugs, race conditions in business logic, unclear API contracts, missing edge case tests.

---

## Options Considered

**Option 1: LLM only — skip static analysis**
- Simple pipeline
- LLM wastes capacity on lintable issues
- Higher cost, lower precision (linter findings mixed with LLM judgment)

**Option 2: Static analysis only**
- Deterministic, fast, cheap
- Misses logic bugs, race conditions, clarity issues
- No LLM value

**Option 3: Deterministic-first, LLM as judgment**
- Run linters first
- Pass linter output to LLM with explicit instruction: "ignore what linter caught"
- LLM focuses on judgment-layer issues only

---

## Decision

**Option 3: Deterministic-first.**

```python
# 1. Run linters (deterministic)
linter_issues = run_linters(repo_path, changed_files)

# 2. LLM review (judgment layer)
# System prompt explicitly says:
# "IGNORE issues that static analyzers already caught.
#  Focus on: logic bugs, race conditions, error handling,
#  context propagation, resource leaks, unclear naming."
result = review_diff(diff, linter_json, file_paths, model)
```

Static analysis tools: `golangci-lint` (includes staticcheck, gosec, ineffassign).

---

## Consequences

**Positive:**
- Lower token cost (LLM skips obvious findings)
- Higher precision (LLM not distracted by formatting)
- Separate reporting channels: linter issues posted as inline comments, LLM findings as review body
- Deterministic layer never hallucinates

**Negative:**
- golangci-lint must be available in Python container (or sidecar)
- Two result types to format and merge for GitHub comment
- Linter timeout risk on large repos (mitigated: 2min timeout, filter to changed files only)

**Current limitation (Week 1)**: golangci-lint not installed in Docker container. Linter step returns empty — LLM operates without pre-filter. Fix in Week 3.

---

## Interview Note

"The LLM is expensive and non-deterministic. I use it only where deterministic tools fail — logic bugs, race conditions, naming clarity. Linters run first and their output is explicitly passed to the LLM as 'already reported, ignore these.' This is the same pattern as using a compiler before a code reviewer."
