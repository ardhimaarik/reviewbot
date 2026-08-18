# Reviewbot

AI-powered PR reviewer for Go services. Deterministic-first, LLM as judgment layer.

## Why

Most AI PR reviewers are wrappers around an LLM — they produce noise, engineers lose trust, tools get abandoned. Reviewbot is built differently: static analysis runs first (deterministic), LLM only handles what linters can't catch (judgment). Every output is structured, measured, and observable.

## Architecture

GitHub PR → smee.io relay → Go API (:8090)
↓
Python AI Service (:8081)
↓
golangci-lint (deterministic)
+
Ollama qwen3.5:9b (local)
Anthropic Claude (fallback)
↓
Structured JSON → GitHub Comment
↓
Postgres (storage)
↓
Prometheus → Grafana (Pi 5)


## Results

> Numbers will be filled after Week 2 eval run.

- Precision: TBD% on labeled dataset of TBD PRs
- Recall (catchable issues): TBD%
- False positive rate on clean PRs: TBD%
- Cost per PR: $TBD (p50), $TBD (p95)
- Latency: TBDs (p95)

Full eval methodology: [docs/eval-methodology.md](docs/eval-methodology.md)

## Design Decisions

**Deterministic-first** — golangci-lint runs before LLM. LLM is explicitly told to ignore what linters caught. Result: lower cost, higher precision, LLM focuses on logic bugs and race conditions.

**Structured JSON output** — every review is a typed schema (`severity`, `category`, `file`, `line`, `confidence`). Enables filtering, metrics, and eval matching. No regex parsing.

**Complexity router** — simple diffs go to local Ollama (qwen3.5:9b, free), complex diffs (concurrency, security, large PRs) go to Claude Haiku (cloud fallback). ~70% cost savings.

**Confidence gating** — each issue has a 0-1 confidence score. Configurable threshold filters noise before posting. Adjustable without redeploy.

**Shadow mode** — every new rollout starts silent (review stored, not posted) for 1-week canary. Compares bot output to human reviews before enabling.

**Eval-first** — built evaluation dataset before optimizing prompts. Baseline metrics recorded on first run. Prompt changes are measured against eval, not vibes.

## Infrastructure

Runs on a two-node homelab:
- **MacBook M2 16GB**: Go service (:8090), Python AI layer (:8081), Ollama qwen3.5:9b (Metal GPU), Postgres
- **Raspberry Pi 5 8GB**: Prometheus (metrics), Grafana (dashboards), Uptime Kuma (health monitoring)

Nodes connected via Tailscale mesh. Webhook relay via smee.io (CGNAT workaround). No cloud infrastructure except Anthropic API for hard-case fallback.

## Getting Started

**Prerequisites:**
- Ollama with `qwen3.5:9b` installed
- Postgres running (or use homelab stack)
- GitHub App created and installed on target repo
- smee.io channel for webhook relay

```bash
# Clone
git clone https://github.com/ardhimaarik/reviewbot.git
cd reviewbot

# Configure
cp .env.example .env
# Edit .env with your values

# Start
make up          # Terminal 1 — start services
make smee        # Terminal 2 — start webhook relay

# Verify
curl http://localhost:8090/health   # Go API
curl http://localhost:8081/health   # Python AI
```

**Test the AI layer directly:**

```bash
curl -X POST http://localhost:8081/review \
  -H "Content-Type: application/json" \
  -d '{
    "diff": "func add(a, b int) int { return a - b }",
    "file_paths": ["main.go"],
    "repo_path": "."
  }'
```

## Not Production-Grade — What Would Need to Change

This is a portfolio project running on a homelab. For production use:

- **Webhook relay**: smee.io works for dev, needs a stable public endpoint (or self-hosted) for prod
- **Golangci-lint**: currently not installed in Python container — needs to be baked into Docker image or run as sidecar
- **Model latency**: qwen3.5:9b averages ~48s on M2 — acceptable for async review, not for synchronous workflows
- **Auth**: GitHub App private key mounted as volume — needs secrets management (Vault, AWS Secrets Manager) in prod
- **Rate limiting**: no rate limiting on webhook endpoint — needs protection against replay attacks
- **Eval automation**: weekly canary eval runs manually — needs proper scheduler (cron or n8n workflow)
- **Multi-repo support**: installation ID hardcoded — needs dynamic lookup per webhook event

## Roadmap

- [ ] **Week 2**: Eval dataset (160 PRs), labeling, baseline metrics
- [ ] **Week 3**: Complexity router, confidence gating, hallucination check, shadow mode
- [ ] **Week 4**: Prometheus metrics, Grafana dashboard, weekly eval canary
- [ ] **v2**: Retrieval layer (Qdrant — past reviews as context), agent mode (cross-file analysis)

## ADRs

- [ADR-R01: Complexity-based routing](docs/adr/ADR-R01-complexity-routing.md)
- [ADR-R02: Structured JSON output](docs/adr/ADR-R02-structured-output.md)
- [ADR-R03: Deterministic-first pattern](docs/adr/ADR-R03-deterministic-first.md)
- [ADR-R04: Go + Python polyglot](docs/adr/ADR-R04-polyglot.md)
- [ADR-R05: Observability split](docs/adr/ADR-R05-observability-split.md)
- [ADR-R06: Repo separation](docs/adr/ADR-R06-repo-separation.md)

---

*Built as a portfolio piece for DevX/Platform engineering roles. Eval methodology and results: [docs/eval-methodology.md](docs/eval-methodology.md)*