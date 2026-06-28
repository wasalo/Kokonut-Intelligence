.PHONY: help seed seed-pilot ci test smoke fmt lint typecheck

help:
	@echo "Kokonut Intelligence — common commands"
	@echo "  make seed         Apply base schemas and seeds"
	@echo "  make seed-pilot   Apply pilot farm data"
	@echo "  make ci           Run full CI check"
	@echo "  make test         Run all Python tests"
	@echo "  make smoke        Run smoke tests only"
	@echo "  make lint         Run ruff linter"
	@echo "  make typecheck    Run mypy type checker"
	@echo "  make fmt          Run ruff formatter"
	@echo "  make forge-test   Run Solidity tests"
	@echo "  make hooks-test   Run Directus hooks tests"

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

forge-test:
	cd contracts && forge test

hooks-test:
	cd extensions/kokonut-hooks && npm test
