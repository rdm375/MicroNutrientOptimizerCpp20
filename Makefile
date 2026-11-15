.PHONY: install-dependencies install-osqp download-fooddata download-full foundation-candidates audit-fooddata audit-fooddata-sr-legacy configure build run run-sparse run-diverse compare clean

# Debian and Ubuntu package setup. This target requires sudo privileges.
install-dependencies:
	sudo apt-get update
	sudo apt-get install -y build-essential cmake pkg-config python3 libnlopt-cxx-dev

# Build and install OSQP v1.x locally; does not require sudo.
OSQP_SOURCE ?= $(HOME)/src/osqp
OSQP_PREFIX ?= $(HOME)/.local
install-osqp:
	cmake -S "$(OSQP_SOURCE)" -B "$(OSQP_SOURCE)/build" \
		-DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$(OSQP_PREFIX)"
	cmake --build "$(OSQP_SOURCE)/build" --parallel
	cmake --build "$(OSQP_SOURCE)/build" --target install

FDC_SR_LEGACY ?= data/source/FoodData_Central_sr_legacy_food_csv_2018-04.zip
FDC_FULL ?= data/source/FoodData_Central_csv_2026-10-29.zip
download-full:
	python3 scripts/download_fooddata_full.py "$(FDC_FULL)"

download-fooddata: download-full
	python3 scripts/download_fooddata_sr_legacy.py "$(FDC_SR_LEGACY)"

foundation-candidates: download-full
	python3 scripts/list_foundation_candidates.py --foundation "$(FDC_FULL)"

audit-fooddata: download-fooddata
	python3 scripts/audit_fooddata_priority.py --foundation "$(FDC_FULL)" --sr-legacy "$(FDC_SR_LEGACY)"

audit-fooddata-sr-legacy: download-fooddata
	python3 scripts/audit_fooddata_central.py --sr-legacy "$(FDC_SR_LEGACY)"

configure:
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -Dosqp_ROOT="$(OSQP_PREFIX)"

build: configure
	cmake --build build --parallel

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
