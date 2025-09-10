PYTHON := python
APP_MODULE := core.main:app
UVICORN_OPTS := --host 0.0.0.0 --port 8000 --factory

.PHONY: help security test run build image release perf qa

help:
	@echo "Targets:"
	@echo "  security   - Run security baseline (lint, scan, sbom, secrets)"
	@echo "  test       - Run pytest"
	@echo "  run        - Launch dev server"
	@echo "  build      - Build docker image (dev)"
	@echo "  image      - Build production image (multi-stage)"
	@echo "  release    - Bump version & build manifest (BUMP=patch|minor|major, default patch)"
	@echo "  perf       - Run performance harness"

security:
	$(PYTHON) scripts/security_baseline.py

test:
	$(PYTHON) -m pytest -q

run:
	$(PYTHON) -m uvicorn $(APP_MODULE) $(UVICORN_OPTS)

build:
	docker build -t neuron-ai:dev .

image:
	docker build -t neuron-ai:prod --target runtime .

release:
	$(PYTHON) scripts/release_build.py --bump $(if $(BUMP),$(BUMP),patch) --git

perf:
	$(PYTHON) scripts/perf_harness.py || echo "Perf harness not yet fully implemented"

qa:
	@echo "[QA] Running snapshot + tests"
	@if [ -f scripts/metrics_audit.py ]; then \
	  $(PYTHON) scripts/metrics_audit.py --strict --pretty || exit 1; \
	else \
	  echo "metrics_audit.py missing - skipping audit"; \
	fi
	$(PYTHON) -m pytest -q || exit 1
	@echo "[QA] Success"
