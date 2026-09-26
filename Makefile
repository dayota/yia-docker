YIA_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT ?= $(CURDIR)
CONFIG ?= $(PROJECT_ROOT)/yia.yml
PYTHON ?= $(if $(wildcard $(YIA_ROOT)/.venv/bin/python),$(YIA_ROOT)/.venv/bin/python,python3)
JSON_FLAG = $(if $(filter json,$(FORMAT)),--json,)

.PHONY: help version validate doctor test init update

help:
	@printf '%s\n' \
	  'Yia commands:' \
	  '  make version        Affiche les versions Yia et schémas' \
	  '  make validate       Valide ./yia.yml (CONFIG=..., FORMAT=json)' \
	  '  make doctor         Vérifie les dépendances de base' \
	  '  make test           Exécute les tests' \
	  '  make init           Réservé - implémentation future' \
	  '  make update         Réservé - implémentation future'

version:
	@PYTHONPATH="$(YIA_ROOT)/src" "$(PYTHON)" -m yia version $(JSON_FLAG)

validate:
	@PYTHONPATH="$(YIA_ROOT)/src" "$(PYTHON)" -m yia validate --config "$(CONFIG)" $(JSON_FLAG)

doctor:
	@PYTHONPATH="$(YIA_ROOT)/src" "$(PYTHON)" -m yia doctor $(JSON_FLAG)

test:
	@PYTHONPATH="$(YIA_ROOT)/src" "$(PYTHON)" -m pytest -q

init:
	@PYTHONPATH="$(YIA_ROOT)/src" "$(PYTHON)" -m yia init

update:
	@PYTHONPATH="$(YIA_ROOT)/src" "$(PYTHON)" -m yia update
