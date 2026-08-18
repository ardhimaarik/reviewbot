# ADR-R06: Repo Separation from Homelab

**Date**: 2026-08-18
**Status**: Accepted
**Decider**: Ardhis

---

## Context

Homelab infrastructure lives at `~/homelab/` — a private Git repo containing service configs, `.env` files, Docker Compose stacks, and credentials for all homelab services (Postgres password, AdGuard config, Home Assistant secrets, etc.).

Reviewbot is a public portfolio piece intended to be shared on GitHub, linked in job applications, and discussed in interviews.

---

## Options Considered

**Option 1: Reviewbot inside ~/homelab/ repo**
- Single repo for everything
- Simpler mental model
- **Fatal flaw**: pushing to public GitHub exposes homelab credentials (Postgres passwords, API keys, GitHub App private key)

**Option 2: Reviewbot as separate public repo**
- `~/Documents/reviewbot/` — public GitHub repo
- `~/homelab/` — private repo (never public)
- Reviewbot Docker Compose only contains Reviewbot services
- Homelab services (Postgres, Ollama, Prometheus) accessed as external dependencies

**Option 3: Monorepo with gitignore**
- Same repo, sensitive files gitignored
- Risk: one wrong `git add .` exposes credentials
- Not worth the risk for a portfolio piece

---

## Decision

**Option 2: Separate repos.**

```
~/homelab/                  ← PRIVATE, never public
├── stacks/
│   ├── data/              ← Postgres, Redis
│   └── ai/                ← Qdrant, Open WebUI
├── lab/litellm/
├── config/prometheus/
└── .env                   ← homelab credentials

~/Documents/reviewbot/     ← PUBLIC, GitHub portfolio
├── service/
├── ai/
├── eval/
├── .env                   ← .gitignored, reviewbot-specific
├── .env.example           ← committed, no secrets
└── secrets/               ← .gitignored
```

Reviewbot connects to homelab services via:
- `host.docker.internal:5432` — Postgres (OrbStack bridge)
- `host.docker.internal:11434` — Ollama (native on MacBook)
- `host.docker.internal:4000` — LiteLLM (Week 3+)

---

## Consequences

**Positive:**
- Zero credential leak risk
- Public repo is clean — only Reviewbot code
- Portfolio piece is self-contained with `.env.example`
- Anyone can clone and run with their own credentials

**Negative:**
- Implicit dependency on homelab services being up
- Makefile `prereq` must check external dependencies
- Two repos to manage

**Documented dependency chain** (in Makefile `prereq` target):
```
Reviewbot requires:
  - homelab-postgres running (stacks/data/)
  - Ollama running (native MacBook)
  - smee.io relay active
  - GitHub App installed on target repo
```

---

## Interview Note

"The homelab repo is private — it contains real credentials and service configs. Reviewbot is a public portfolio piece. Keeping them separate was a deliberate decision from day one. The Makefile's prereq target documents all external dependencies explicitly, so anyone cloning the public repo knows exactly what they need to provide."
