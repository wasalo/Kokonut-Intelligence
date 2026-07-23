.PHONY: help seed seed-pilot ci test smoke fmt lint typecheck \
	up down logs bootstrap metrics verify sast secrets audit \
	forge-build forge-fmt hooks-build \
	test-cli test-attestation test-directus test-platform test-agent-safety test-seeds

help:
	@echo "Kokonut Intelligence — common commands"
	@echo ""
	@echo "  Setup"
	@echo "  ─────────────────────────────────────"
	@echo "  make seed            Apply base schemas and seeds"
	@echo "  make seed-pilot      Apply pilot farm data"
	@echo "  make bootstrap       Full setup: seed + pilot + metrics + verify"
	@echo ""
	@echo "  Docker"
	@echo "  ─────────────────────────────────────"
	@echo "  make up              Start all services"
	@echo "  make down            Stop all services"
	@echo "  make logs            Tail service logs"
	@echo ""
	@echo "  Quality"
	@echo "  ─────────────────────────────────────"
	@echo "  make ci              Run full CI check"
	@echo "  make test            Run all Python tests"
	@echo "  make smoke           Run smoke tests only"
	@echo "  make lint            Run ruff linter"
	@echo "  make fmt             Run ruff formatter"
	@echo "  make typecheck       Run mypy type checker"
	@echo "  make audit           Run pip-audit dependency scan"
	@echo "  make sast            Run static analysis (Slither, Semgrep)"
	@echo "  make secrets         Check for tracked secrets"
	@echo ""
	@echo "  Metrics & Verification"
	@echo "  ─────────────────────────────────────"
	@echo "  make metrics         Compute all metrics"
	@echo "  make verify          Verify platform definition of done"
	@echo ""
	@echo "  Contracts"
	@echo "  ─────────────────────────────────────"
	@echo "  make forge-build     Build Solidity contracts"
	@echo "  make forge-test      Run Solidity tests"
	@echo "  make forge-fmt       Format Solidity"
	@echo ""
	@echo "  Directus Hooks"
	@echo "  ─────────────────────────────────────"
	@echo "  make hooks-build     Build Directus hooks"
	@echo "  make hooks-test      Run Directus hooks tests"
	@echo ""
	@echo "  Focused Test Suites"
	@echo "  ─────────────────────────────────────"
	@echo "  make test-cli              Run CLI tests"
	@echo "  make test-attestation      Run attestation tests"
	@echo "  make test-directus         Run Directus metadata tests"
	@echo "  make test-platform         Run platform integrity tests"
	@echo "  make test-agent-safety     Run agent safety tests"
	@echo "  make test-seeds            Run seed idempotency tests"

seed:
	./scripts/seed.sh

seed-pilot:
	./scripts/seed-pilot.sh

ci:
	./scripts/ci-check.sh

test:
	python3 -m pytest tests/ -v

smoke:
	python3 -m tests.test_smoke

lint:
	ruff check services/ tests/

typecheck:
	mypy services/ --ignore-missing-imports

fmt:
	ruff format services/ tests/

# --- Docker ---

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# --- Setup ---

bootstrap:
	./scripts/seed.sh
	./scripts/seed-pilot.sh
	./scripts/compute-metrics.sh
	./scripts/verify-platform.sh

# --- Quality ---

metrics:
	./scripts/compute-metrics.sh

verify:
	./scripts/verify-platform.sh

sast:
	./scripts/static-analysis.sh

secrets:
	./scripts/check-tracked-secrets.sh

audit:
	pip-audit

# --- Contracts ---

forge-build:
	cd contracts && forge build

forge-test:
	cd contracts && forge test

forge-fmt:
	cd contracts && forge fmt

# --- Directus Hooks ---

hooks-build:
	cd extensions/kokonut-hooks && npm run build

hooks-test:
	cd extensions/kokonut-hooks && npm test

# --- Focused Test Suites ---

test-cli:
	python3 -m pytest tests/test_cli.py tests/test_cli_governance.py tests/test_cli_guilds.py -v

test-attestation:
	python3 -m pytest tests/test_attestation.py -v

test-directus:
	python3 -m pytest tests/test_directus_metadata.py -v

test-platform:
	python3 -m pytest tests/test_migration.py tests/test_gateway_auth.py tests/test_scheduler_durability.py tests/test_event_bus_durability.py tests/test_carbon_credits.py tests/test_threatcasting.py tests/test_backcasting_enhancements.py tests/test_delphi.py -v

test-agent-safety:
	python3 -m pytest tests/test_agent_safety.py -v

test-seeds:
	python3 -m pytest tests/test_seed_idempotency.py -v
