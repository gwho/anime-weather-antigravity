SHELL := /bin/sh
PYTHON := python3

ifneq ("$(wildcard .venv/bin/python)","")
PYTHON := .venv/bin/python
endif

.PHONY: dev backend frontend install check clean

dev:
	@set -e; \
	$(MAKE) backend & \
	backend_pid=$$!; \
	$(MAKE) frontend & \
	frontend_pid=$$!; \
	trap 'kill $$backend_pid $$frontend_pid 2>/dev/null || true' INT TERM EXIT; \
	wait $$backend_pid $$frontend_pid

backend:
	cd backend && uvicorn anime_weather.main:app --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev -- --host 0.0.0.0 --port 5173

install:
	$(PYTHON) -m pip install -r backend/requirements.txt
	cd frontend && npm install

check:
	$(PYTHON) -m mypy --config-file mypy.ini backend/anime_weather
	cd frontend && npx tsc --noEmit

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	rm -rf .mypy_cache backend/.mypy_cache frontend/node_modules frontend/dist
