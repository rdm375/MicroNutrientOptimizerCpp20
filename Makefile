.PHONY: install-dependencies install-python-dependencies install-osqp download-fooddata download-full foundation-candidates ingredient-candidates ingredient-fallback-candidates explore-ingredients explore-ingredients-diverse audit-fooddata audit-fooddata-sr-legacy audit-sr-legacy-migration apply-sr-legacy-fallbacks audit-dri-coverage configure build test run run-sparse run-diverse compare clean

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

# Debian and Ubuntu package setup. This target requires sudo privileges.
install-dependencies:
	sudo apt-get update
	sudo apt-get install -y build-essential cmake python3 python3-venv git

install-python-dependencies:
	python3 -m venv .venv
	.venv/bin/python -m pip install --requirement requirements.txt

# Build and install OSQP v1.x locally; does not require sudo.
OSQP_SOURCE ?= $(HOME)/src/osqp
OSQP_PREFIX ?= $(HOME)/.local
OSQP_REF ?= v1.0.0
install-osqp:
	git -C "$(OSQP_SOURCE)" fetch --tags
	git -C "$(OSQP_SOURCE)" checkout --detach "$(OSQP_REF)"
	cmake -S "$(OSQP_SOURCE)" -B "$(OSQP_SOURCE)/build" \
		-DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$(OSQP_PREFIX)"
	cmake --build "$(OSQP_SOURCE)/build" --parallel
	cmake --build "$(OSQP_SOURCE)/build" --target install

FDC_SR_LEGACY ?= data/source/FoodData_Central_sr_legacy_food_csv_2018-04.zip
FDC_FULL ?= data/source/FoodData_Central_csv_2026-10-29.zip
download-full:
	$(PYTHON) scripts/download_fooddata_full.py "$(FDC_FULL)"

download-fooddata: download-full
	$(PYTHON) scripts/download_fooddata_sr_legacy.py "$(FDC_SR_LEGACY)"

foundation-candidates: download-full
	$(PYTHON) scripts/list_foundation_candidates.py --foundation "$(FDC_FULL)"

# Produce a review CSV of Foundation plant-food candidates. This is discovery
# only: humans must confirm food identity and portion bounds before solving.
ingredient-candidates: download-full
	$(PYTHON) scripts/discover_plant_candidates.py --foundation "$(FDC_FULL)"

# Show exact-description SR Legacy records that could fill missing Foundation
# fields. This is a review aid and never approves or selects a fallback.
ingredient-fallback-candidates: download-full
	$(PYTHON) scripts/suggest_sr_legacy_matches.py --full "$(FDC_FULL)"

# Explore reviewed candidates with an LP that minimizes total salad mass.
explore-ingredients:
	$(PYTHON) scripts/explore_ingredients.py --review data/reports/plant_candidate_review.csv --sr-legacy "$(FDC_SR_LEGACY)" --profile sparse

explore-ingredients-diverse:
	$(PYTHON) scripts/explore_ingredients.py --review data/reports/plant_candidate_review.csv --sr-legacy "$(FDC_SR_LEGACY)" --profile diverse

audit-fooddata: download-fooddata
	$(PYTHON) scripts/audit_fooddata_priority.py --foundation "$(FDC_FULL)" --sr-legacy "$(FDC_SR_LEGACY)"

audit-fooddata-sr-legacy: download-fooddata
	$(PYTHON) scripts/audit_fooddata_central.py --sr-legacy "$(FDC_SR_LEGACY)"

# Preview the exact-match fallback decisions using the preserved pre-migration
# audit. Applying them updates only exact identities with reported SR values.
audit-sr-legacy-migration:
	$(PYTHON) scripts/apply_sr_legacy_fallbacks.py --audit data/reports/legacy_table_before_sr_legacy_update.csv

apply-sr-legacy-fallbacks:
	$(PYTHON) scripts/apply_sr_legacy_fallbacks.py --audit data/reports/legacy_table_before_sr_legacy_update.csv --apply

# Compare the DRI reference inventory with exact FoodData Central nutrient
# definitions and report record/food coverage for the existing candidate review.
# This intentionally does not regenerate the manually reviewed candidate file.
audit-dri-coverage: download-full
	$(PYTHON) scripts/audit_dri_coverage.py --full "$(FDC_FULL)" --review data/reports/plant_candidate_review.csv

configure:
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -Dosqp_ROOT="$(OSQP_PREFIX)"

build: configure
	cmake --build build --parallel

test: build
	ctest --test-dir build --output-on-failure

run: build
	./build/diet_optimizer --sparse

run-sparse: run

run-diverse: build
	./build/diet_optimizer --diverse

compare: build
	./build/diet_optimizer --sparse
	./build/diet_optimizer --diverse

clean:
	rm -rf build
