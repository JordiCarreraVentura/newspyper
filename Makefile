PY := bin/python

install:
	@if [ ! -d bin ] ; \
		then echo "No virtual environment found. Creating one..." ; \
		virtualenv . \
		$(PY) -m pip install --upgrade pip ; \
	fi
	@echo "Installing dependencies..."
	$(PY) -m pip install -r requirements.txt

run:
	@$(PY) src/__main__.py

clean:
	rm -rf bin lib pyvenv.cfg etc share

build:
	@$(PY) -m build
	@$(PY) -m twine upload --repository pypi dist/*

all: install run

.PHONY: all build install run clean