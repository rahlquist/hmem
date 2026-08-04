# hmem pilot — automated validation and test targets
# Usage: make pilot-validate | pilot-test | pilot-dryrun
# Python 3.9+; jsonschema optional (stdlib fallback). No other deps.

PY ?= python3
PILOT = $(PY) -m pilot

.PHONY: pilot-validate pilot-test pilot-dryrun pilot-clean

pilot-validate:
	$(PILOT).cli --validate-only

pilot-test:
	$(PY) -m unittest discover -s pilot/tests -v

pilot-dryrun:
	$(PILOT).cli --out-dir pilot-out --repetitions 3 --seed 7

pilot-clean:
	rm -rf pilot-out
