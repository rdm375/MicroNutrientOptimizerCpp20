.PHONY: install-dependencies configure build run run-sparse run-diverse compare clean

# Debian and Ubuntu package setup. This target requires sudo privileges.
install-dependencies:
	sudo apt-get update
	sudo apt-get install -y build-essential cmake pkg-config libnlopt-cxx-dev

configure:
	cmake -S . -B build -DCMAKE_BUILD_TYPE=Release

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
