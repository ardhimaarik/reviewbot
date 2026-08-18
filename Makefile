.PHONY: prereq up down dev logs eval test smee help

DOCKER_COMPOSE=docker compose -f docker-compose.yml --env-file .env

# ── Help ──
help:
	@echo "Reviewbot Week 1 Tasks"
	@echo ""
	@echo "make prereq     — verify homelab Postgres + Ollama"
	@echo "make up         — start Reviewbot services (Go + Python)"
	@echo "make dev        — start with hot reload (volumes mounted)"
	@echo "make down       — stop services"
	@echo "make logs       — tail logs from both services"
	@echo "make smee       — start webhook relay (separate terminal)"
	@echo "make test       — run basic connectivity tests"
	@echo ""

# ── Prerequisites ──
prereq:
	@echo "🔍 Checking prerequisites..."
	@echo ""
	@echo "1. Postgres database 'reviewbot'..."
	@docker exec homelab-postgres psql -U homelab -d reviewbot -c "SELECT 1" > /dev/null 2>&1 && echo "   ✅ Postgres OK" || echo "   ❌ Postgres failed — run: docker exec homelab-postgres psql -U homelab -c 'CREATE DATABASE reviewbot;'"
	@echo ""
	@echo "2. Ollama qwen3.5:9b..."
	@curl -s http://localhost:11434/api/tags | grep -q qwen3.5 && echo "   ✅ Ollama OK" || echo "   ❌ Ollama not running or qwen3.5:9b not installed"
	@echo ""
	@echo "3. GitHub App setup..."
	@[ -f secrets/github-app.pem ] && echo "   ✅ Private key found" || echo "   ❌ Missing secrets/github-app.pem"
	@grep -q "GITHUB_APP_ID" .env && echo "   ✅ GitHub App ID set" || echo "   ❌ GITHUB_APP_ID not in .env"
	@echo ""
	@echo "4. Smee.io URL..."
	@grep -q "SMEE_URL" .env && echo "   ✅ Smee URL set" || echo "   ❌ SMEE_URL not in .env"
	@echo ""
	@echo "✅ Prerequisites check complete. Ready to start?"

# ── Reviewbot Services ──
up: prereq
	@echo "Starting Reviewbot services..."
	$(DOCKER_COMPOSE) up -d --build
	@echo ""
	@echo "✅ Services started:"
	@echo "   Go API:    http://localhost:8090"
	@echo "   Python AI: http://localhost:8081"
	@echo ""
	@echo "Next: make smee (in separate terminal)"

dev: prereq
	@echo "Starting Reviewbot in dev mode (hot reload)..."
	$(DOCKER_COMPOSE) -f deploy/docker-compose.dev.yml up --build

down:
	@echo "Stopping Reviewbot services..."
	$(DOCKER_COMPOSE) down

logs:
	$(DOCKER_COMPOSE) logs -f

# ── Webhook Relay ──
smee:
	@echo "Starting smee.io webhook relay..."
	@echo "Relaying to: http://localhost:8090/webhook"
	@echo ""
	smee -u $$(grep SMEE_URL .env | cut -d= -f2) -t http://localhost:8090/webhook

# ── Testing ──
test: up
	@echo "Testing Reviewbot connectivity..."
	@echo ""
	@echo "1. Go API health..."
	@curl -s http://localhost:8090/health || echo "   ❌ Go API not responding"
	@echo ""
	@echo "2. Python AI health..."
	@curl -s http://localhost:8081/health || echo "   ❌ Python AI not responding"
	@echo ""
	@echo "3. Ollama from Python..."
	@curl -s http://localhost:11434/api/tags | grep -q qwen3.5 && echo "   ✅ Python can reach Ollama" || echo "   ❌ Python cannot reach Ollama"
	@echo ""
	@echo "4. Postgres from Go..."
	@curl -s http://localhost:8081/health && echo "   ✅ Services talking" || echo "   ❌ Services cannot communicate"

# ── Evaluation (Week 2+) ──
eval:
	cd eval && python -m scripts.run_eval

# ── Cleanup ──
clean:
	$(DOCKER_COMPOSE) down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete