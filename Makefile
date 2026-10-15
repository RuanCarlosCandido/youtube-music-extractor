SHELL := /bin/bash
PYTHON := python3
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
SCRIPT := export_youtube_music.py
ENV_FILE := .env

.PHONY: help venv install run check test clean clean-all
help:
	@echo "make run, make test, make clean-all"
venv:
	@test -d "$(VENV)" || $(PYTHON) -m venv "$(VENV)"
install: venv
	$(PIP) install requests
check:
	@test -f "$(ENV_FILE)" || (echo "Create .env with API_KEY" && exit 1)
	@grep -q '^API_KEY=' "$(ENV_FILE)" || (echo "Missing API_KEY" && exit 1)
run: install check
	set -a && source $(ENV_FILE) && set +a && $(PY) $(SCRIPT)
test: install
	$(PY) -m unittest discover -s tests -v
clean:
	@echo "No snapshots are deleted by make clean"
clean-all:
	rm -rf "$(VENV)"
