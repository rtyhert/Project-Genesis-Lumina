.PHONY: all proto install test lint cpp-deps cpp-build cpp-build-minimal clean check

SHELL := /bin/bash

all: install proto test lint

# ── Python ──────────────────────────────────────

install:
	cd lumina-py && pip install -r requirements.txt

proto:
	cd lumina-proto && bash ../scripts/ci-make-proto.sh

test:
	cd lumina-py && LUMINA_MOCK=1 python -m pytest tests/ -v --tb=short

lint:
	cd lumina-py && pip install ruff && ruff check src/ tests/

check:
	@echo "=== Python check ==="
	cd lumina-py && python -c "import yaml, sys; yaml.safe_load(open('config.yaml')); print('config.yaml OK')"
	cd lumina-py && python -c "import src.config_schema as cs; print('config_schema OK')"
	cd lumina-py && python -c "import src.metrics; print('metrics OK')"
	cd lumina-py && python -c "import src.thread_pool; print('thread_pool OK')"

# ── C++ ─────────────────────────────────────────

cpp-deps:
	sudo apt-get update && sudo apt-get install -y \
		build-essential cmake \
		libgrpc-dev libgrpc++-dev \
		libprotobuf-dev protobuf-compiler \
		libglfw3-dev \
		libopenal-dev \
		pkg-config

cpp-build: proto
	cd lumina-cpp && cmake -B build -DCMAKE_BUILD_TYPE=Debug \
		-DLUMINA_USE_LIVE2D=OFF
	cd lumina-cpp && cmake --build build --parallel $$(nproc)

cpp-build-minimal: proto
	cd lumina-cpp && cmake -B build -DCMAKE_BUILD_TYPE=Debug \
		-DLUMINA_BUILD_GRPC_ONLY=ON
	cd lumina-cpp && cmake --build build --parallel $$(nproc)

cpp-test: proto
	cd lumina-cpp && cmake -B build_test -S tests -DCMAKE_BUILD_TYPE=Debug
	cd lumina-cpp && cmake --build build_test --parallel $$(nproc)
	cd lumina-cpp/build_test && ctest --output-on-failure -V

# ── Release ─────────────────────────────────────

bump-patch:
	python scripts/bump_version.py patch

bump-minor:
	python scripts/bump_version.py minor

bump-major:
	python scripts/bump_version.py major

# ── Clean ────────────────────────────────────────

clean:
	rm -rf lumina-py/cache/
	rm -rf lumina-cpp/build/
	rm -rf lumina-proto/build/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
