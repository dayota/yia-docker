YIA_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT ?= $(CURDIR)
CONFIG ?= $(PROJECT_ROOT)/yia.yml
PYTHON ?= $(if $(wildcard $(YIA_ROOT)/.venv/bin/python),$(YIA_ROOT)/.venv/bin/python,python3)
JSON_FLAG = $(if $(filter json,$(FORMAT)),--json,)
FOLLOW_FLAG = $(if $(filter 1,$(FOLLOW)),--follow,)
YES_FLAG = $(if $(filter 1,$(YES)),--yes,)
CLI = PYTHONPATH="$(YIA_ROOT)/src" "$(PYTHON)" -m yia

export YIA_EXEC_CMD := $(value CMD)
export YIA_SERVICE := $(value SERVICE)

.PHONY: help install check-install version init validate config generate update up down restart ps status doctor logs shell exec build rebuild test clean reset destroy destroy-data

help:
	@printf '%s\n' \
	  'Yia commands:' \
	  '  make install                         Installe les dépendances via APT' \
	  '  make check-install                   Vérifie les prérequis système' \
	  '  make version [FORMAT=json]           Affiche les versions Yia et schémas' \
	  '  make init                            Initialise un projet sans démarrer Docker' \
	  '  make validate [FORMAT=json]          Valide yia.yml et les variables requises' \
	  '  make config                          Affiche la configuration normalisée' \
	  '  make generate                        Génère .yia-runtime sans démarrer Docker' \
	  '  make update                          Réservé à la phase 13' \
	  '  make up                              Démarre l’environnement généré' \
	  '  make down                            Arrête sans supprimer les données' \
	  '  make restart                         Redémarre sans supprimer les données' \
	  '  make ps [FORMAT=json]                Affiche les containers du projet' \
	  '  make status [FORMAT=json]            Affiche l’état fonctionnel du projet' \
	  '  make doctor [FORMAT=json]            Diagnostique le projet et les dépendances' \
	  '  make logs [SERVICE=x] [FOLLOW=1]     Affiche les logs, sans suivi par défaut' \
	  '  make shell SERVICE=x                 Ouvre un shell dans un service logique' \
	  '  make exec SERVICE=x CMD="..."        Exécute une commande sans passer par un shell' \
	  '  make build                           Construit les images' \
	  '  make rebuild                         Reconstruit sans supprimer les données' \
	  '  make test                            Lance les tests Yia ou valide le projet consommateur' \
	  '  make clean                           Supprime seulement .yia-runtime' \
	  '  make reset                           Reconstruit sans supprimer les volumes' \
	  '  make destroy                         Supprime containers/réseaux, conserve les volumes' \
	  '  make destroy-data [YES=1]            DESTRUCTIF : supprime les volumes du projet'

install:
	@$(CLI) install

check-install:
	@$(CLI) check-install --project-root "$(PROJECT_ROOT)"

version:
	@$(CLI) version $(JSON_FLAG)

init:
	@$(CLI) init --config "$(CONFIG)"

validate:
	@$(CLI) validate --config "$(CONFIG)" $(JSON_FLAG)

config:
	@$(CLI) config --config "$(CONFIG)"

generate:
	@$(CLI) generate --config "$(CONFIG)"

update:
	@$(CLI) update --config "$(CONFIG)"

up:
	@$(CLI) up --config "$(CONFIG)"

down:
	@$(CLI) down --config "$(CONFIG)"

restart:
	@$(CLI) restart --config "$(CONFIG)"

ps:
	@$(CLI) ps --config "$(CONFIG)" $(JSON_FLAG)

status:
	@$(CLI) status --config "$(CONFIG)" $(JSON_FLAG)

doctor:
	@$(CLI) doctor --config "$(CONFIG)" $(JSON_FLAG)

logs:
	@$(CLI) logs --config "$(CONFIG)" $(if $(strip $(SERVICE)),--service "$$YIA_SERVICE",) $(FOLLOW_FLAG)

shell:
	@$(CLI) shell --config "$(CONFIG)" --service "$$YIA_SERVICE"

exec:
	@$(CLI) exec --config "$(CONFIG)" --service "$$YIA_SERVICE" --command "$$YIA_EXEC_CMD"

build:
	@$(CLI) build --config "$(CONFIG)"

rebuild:
	@$(CLI) rebuild --config "$(CONFIG)"

test:
	@$(CLI) test --config "$(CONFIG)" --project-root "$(PROJECT_ROOT)"

clean:
	@$(CLI) clean --config "$(CONFIG)"

reset:
	@$(CLI) reset --config "$(CONFIG)"

destroy:
	@$(CLI) destroy --config "$(CONFIG)"

destroy-data:
	@$(CLI) destroy-data --config "$(CONFIG)" $(YES_FLAG)
