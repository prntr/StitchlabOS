# Agent-Kontrakt -- siehe ~/Code/_std/AGENTS.base.md
.PHONY: setup dev sim test lint check status help
.DEFAULT_GOAL := help

# Meta-Repo fuer StitchLabOS: ein Raspberry-Pi-Image, das Klipper, Moonraker,
# eine angepasste Mainsail-Oberflaeche und TurtleStitch buendelt.
#
# mainsail/, turtlestitch/ und stitchlabos-config/ sind Submodule,
# virtual-klipper-printer/ ist ein einfacher Klon ausserhalb der Versionierung.
# In allen vier Faellen gilt: Aenderungen werden DORT committet -- ein Commit
# hier haelt bei Submodulen nur den Zeiger fest, nie den Inhalt.
#
# Das Image selbst wird nicht lokal gebaut, sondern von CustomPiOS auf GitHub
# Actions: ein Tag-Push (v*) erzeugt das .img.xz als Release-Artefakt.

setup:   ## Abhaengigkeiten der Mainsail-Oberflaeche
	cd mainsail && npm ci

dev:     ## Mainsail-Oberflaeche lokal ausliefern
	cd mainsail && npm run serve

sim:     ## virtuellen Klipper-Drucker starten (Docker)
	cd virtual-klipper-printer && docker compose up -d

test:    ## Tests der Mainsail-Oberflaeche
	cd mainsail && npm test

lint:    ## Mainsail-Linter + tote Verweise in der Doku
	cd mainsail && npm run lint
	@~/Code/_std/bin/check-links docs

check: lint test  ## Tor vor jedem Commit (Hausregel: lint + test)

status:  ## Zustand aller Unter-Repos auf einen Blick
	@for r in . mainsail turtlestitch stitchlabos-config virtual-klipper-printer; do \
	  printf "  %-26s %-34s %s\n" "$$r" "$$(git -C $$r branch --show-current 2>/dev/null)" \
	    "$$(git -C $$r status --porcelain 2>/dev/null | wc -l | tr -d ' ') geaendert"; done

help:
	@grep -E '^[a-z][a-z-]*:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  make %-10s %s\n", $$1, $$2}'
