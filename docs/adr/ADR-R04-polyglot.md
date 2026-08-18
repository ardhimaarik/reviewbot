# ADR-R04: Go + Python Polyglot, Not Monoglot

**Date**: 2026-08-18
**Status**: Accepted
**Decider**: Ardhis

---

## Context

This project has two distinct domains:
1. **Service runtime**: webhook handling, GitHub API, routing decisions, Prometheus metrics, Postgres storage — high concurrency, low latency, production reliability
2. **AI/LLM interaction**: LLM clients, prompt management, structured output parsing, eval harness, data scripting — Python-first ecosystem

---

## Options Considered

**Option 1: Monoglot Go**
- Single language, single Dockerfile
- Go AI ecosystem is immature (no native Anthropic/OpenAI SDK quality)
- Writing LLM client in Go = reinventing wheel without gain
- Eval scripting in Go = painful (no pandas, no tqdm, no psycopg2 equivalents)

**Option 2: Monoglot Python**
- AI ecosystem native
- Loses Go depth as an interview signal
- Python webhook server has worse performance characteristics
- Not idiomatic for production service layer

**Option 3: Go service + Python AI layer (polyglot)**
- Each language used in its strongest domain
- Go handles: webhook, routing, GitHub API, metrics, orchestration
- Python handles: LLM client, prompt management, static analysis wrapper, eval
- Communication: HTTP JSON (simple, debuggable, no gRPC overhead at MVP)

---

## Decision

**Option 3: Polyglot.**

```
service/   ← Go (core service)
ai/        ← Python (AI layer + eval)
eval/      ← Python (offline eval harness)
```

Internal API: Go service → `POST http://reviewbot-ai:8081/review` → Python AI layer.

---

## Consequences

**Positive:**
- Go depth as interview signal (not "I just used Python for everything")
- Python AI ecosystem: Anthropic SDK, OpenAI SDK, Pydantic, psycopg2, eval tooling
- Clean separation of concerns between service runtime and AI logic
- Each service independently deployable and scalable

**Negative:**
- Two Dockerfiles
- Two dependency management systems (go.mod + requirements.txt)
- HTTP overhead between Go and Python (~5ms, acceptable)
- Two languages to maintain

**Fallback option** (if deploy complexity becomes issue): Python AI layer can be embedded as subprocess from Go via `exec.Command`. Not done at MVP — HTTP is simpler to debug.

---

## Interview Note

"I chose Go for the service layer because that's my home turf and it signals depth. Python for the AI layer because the ecosystem (Anthropic SDK, Pydantic, eval tooling) is all Python-first. Pragmatism over dogma — right tool per domain. The services communicate via HTTP JSON, which means I can swap either side independently."
