.PHONY: all setup test lint demo clean

PYTHON ?= python3

all: test

setup:
	@echo "Checking OSS CAD Suite and Python requirements..."
	@which yosys sby verilator
	@$(PYTHON) -c "import yaml; import pytest; print('Dependencies verified.')"

lint:
	@echo "Linting all RTL designs and bug variants with verilator and yosys..."
	@for f in designs/rtl/*.v designs/rtl_bug/*.v; do \
		echo "Checking $$f..."; \
		yosys -p "read_verilog -sv $$f; hierarchy -auto-top; proc" > /dev/null || exit 1; \
		verilator --lint-only -Wall $$f || exit 1; \
	done
	@echo "All RTL designs passed lint."

test:
	PYTHONPATH=. $(PYTHON) -m pytest -v

demo:
	PYTHONPATH=. $(PYTHON) -m eng2sva demo

clean:
	rm -rf build .pytest_cache tests/__pycache__ eng2sva/__pycache__
