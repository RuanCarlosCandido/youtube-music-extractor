SHELL := /bin/bash

PYTHON := python3
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
SCRIPT := export_youtube_music.py
ENV_FILE := .env

.PHONY: help venv install run clean clean-all check

help:
	@echo "Targets disponíveis:"
	@echo "  make run        -> cria venv, instala dependências e executa o script"
	@echo "  make install    -> cria venv e instala dependências"
	@echo "  make venv       -> cria ambiente virtual"
	@echo "  make check      -> valida arquivos obrigatórios"
	@echo "  make clean      -> remove arquivos gerados"
	@echo "  make clean-all  -> remove arquivos gerados e o ambiente virtual"

venv:
	@if [ ! -d "$(VENV)" ]; then \
		$(PYTHON) -m venv $(VENV); \
	fi

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install requests

check:
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "Erro: arquivo $(ENV_FILE) não encontrado."; \
		echo "Crie um arquivo .env no mesmo diretório com:"; \
		echo "API_KEY=sua_api_key"; \
		exit 1; \
	fi
	@if [ ! -f "$(SCRIPT)" ]; then \
		echo "Erro: arquivo $(SCRIPT) não encontrado."; \
		exit 1; \
	fi
	@if ! grep -q '^API_KEY=' "$(ENV_FILE)"; then \
		echo "Erro: API_KEY não encontrada em $(ENV_FILE)."; \
		exit 1; \
	fi

run: install check
	set -a && source $(ENV_FILE) && set +a && $(PY) $(SCRIPT)

clean:
	rm -f youtube_music_export.json youtube_music_export.csv

clean-all: clean
	rm -rf $(VENV)
