# Define the virtual environment directory and the python path
VENV := .venv
PY := $(VENV)/bin/python

$(VENV):
	@echo "No virtual environment found. Creating one in $(VENV)..."
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip

install: $(VENV)
	@echo "Installing dependencies..."
	$(PY) -m pip install -r requirements.txt

run:
	@$(PY) src/newspyper/__main__.py

clean:
	rm -rf $(VENV)

build:
	@$(PY) -m build
	@$(PY) -m twine upload --repository pypi dist/*

all: install run

.PHONY: all build install run clean