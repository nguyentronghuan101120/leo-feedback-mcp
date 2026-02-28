.PHONY: init build upload

init:
	@bash scripts/init.sh

build:
	@bash scripts/build.sh

upload:
	@bash scripts/upload.sh
