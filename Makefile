.PHONY: up down demo export test check

up:
	docker compose up --build

down:
	docker compose down

test:
	pytest -q tests/

demo:
	python scripts/run_demo.py

export:
	python scripts/export_decision_log.py

check:
	@echo "== syntax =="; python -m py_compile backend/app.py backend/orchestrator.py agents/*.py
	@echo "== tests ==";  pytest -q tests/
