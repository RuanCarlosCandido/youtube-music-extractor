SHELL := /bin/bash
PYTHON := python3
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
ENV_FILE := .env

.PHONY: help venv install install-deezer deezer-login deezer-run deezer-cdp deezer-publish deezer-backup check run publish backup retry-drive test clean clean-all
help:
	@echo "make backup (YouTube) | make deezer-login | make deezer-backup | make test"
install-deezer: venv
	$(PIP) install playwright
	$(VENV)/bin/playwright install chromium
deezer-login: install-deezer
	$(PY) export_deezer.py --login
deezer-run: install-deezer
	$(PY) export_deezer.py
deezer-cdp: install-deezer
	$(PY) export_deezer.py --cdp http://127.0.0.1:9222
deezer-publish: venv
	set -a; if test -f "$(ENV_FILE)"; then source "$(ENV_FILE)"; fi; set +a; $(PY) publish_backups.py --provider deezer
deezer-backup: deezer-run deezer-publish
venv:
	@test -d "$(VENV)" || $(PYTHON) -m venv "$(VENV)"
install: venv
	$(PIP) install requests
check:
	@test -f "$(ENV_FILE)" || (echo "Create .env with API_KEY" && exit 1)
	@grep -q '^API_KEY=' "$(ENV_FILE)" || (echo "Missing API_KEY" && exit 1)
run: install check
	set -a && source $(ENV_FILE) && set +a && $(PY) export_youtube_music.py
publish: install check
	set -a && source $(ENV_FILE) && set +a && $(PY) publish_backups.py
backup: run publish
retry-drive: install
	set -a && test -f "$(ENV_FILE)" && source $(ENV_FILE) && set +a && $(PY) publish_backups.py --drive-only
test: install
	$(PY) -m unittest discover -s tests -v
clean:
	@echo "Snapshots are never deleted automatically"
clean-all:
	rm -rf "$(VENV)"
