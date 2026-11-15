.PHONY: install-dependencies install-osqp configure build run run-sparse run-diverse compare clean

# Debian and Ubuntu package setup. This target requires sudo privileges.
install-dependencies:
	sudo apt-get update
	sudo apt-get install -y build-essential cmake pkg-config libnlopt-cxx-dev

# Build and install OSQP v1.x locally; does not require sudo.
OSQP_SOURCE ?= $(HOME)/src/osqp
OSQP_PREFIX ?= $(HOME)/.local
install-osqp:
	cmake -S "$(OSQP_SOURCE)" -B "$(OSQP_SOURCE)/build" \
		-DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$(OSQP_PREFIX)"
	cmake --build "$(OSQP_SOURCE)/build" --parallel
	cmake --build "$(OSQP_SOURCE)/build" --target install

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
