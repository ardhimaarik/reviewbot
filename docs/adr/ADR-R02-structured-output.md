# ADR-R02: Structured Output via JSON Schema

**Date**: 2026-08-18
**Status**: Accepted
**Decider**: Ardhis

---

## Context

LLM free-text output cannot be reliably parsed, cannot be filtered, and cannot be measured. A review that says "there might be a bug around line 40-ish" is useless for:
- Precise GitHub inline comments
- Eval matching (line number needed)
- Confidence-based filtering
- Metrics aggregation by severity/category

---

## Options Considered

**Option 1: Free-text output**
- Simple prompt
- Unparseable programmatically
- Cannot filter by confidence
- Cannot measure in eval

**Option 2: JSON schema enforced by Pydantic**
- More complex prompt
- Fully parseable, filterable, measurable
- Enables confidence gating
- Enables eval matching

**Option 3: LLM function calling / tool use**
- Most structured
- API-specific (Anthropic vs OpenAI different syntax)
- Overkill for MVP

---

## Decision

**Option 2: JSON schema enforced by Pydantic.**

```python
class ReviewIssue(BaseModel):
    severity: str    # blocker | major | minor | nit
    category: str    # bug | perf | style | security | clarity | test
    file: str
    line: int
    message: str
    suggestion: str
    confidence: float  # 0.0-1.0

class ReviewOutput(BaseModel):
    summary: str
    issues: list[ReviewIssue] = []
```

If LLM returns invalid JSON → retry once with temperature=0.0 and stricter prompt.

---

## Consequences

**Positive:**
- Filter issues by confidence threshold (configurable)
- Count issues by severity/category in Prometheus metrics
- Eval matching uses file + line + category
- Consistent GitHub comment format

**Negative:**
- More complex system prompt (~300 tokens overhead)
- Occasional parse failures require retry (adds latency)
- LLM may "fight" the schema for complex reasoning

**Mitigation:**
- Retry logic with temperature=0 for determinism
- Log all parse failures for monitoring

---

## Interview Note

"Free-text LLM output is a dead end for production systems. You can't filter it, can't measure it, can't build eval on it. Structured output was the first architectural decision — everything else (confidence gating, eval harness, Prometheus metrics) depends on it."
