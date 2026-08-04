# hmem pilot — automated validation and test targets
# Usage: make pilot-validate | pilot-test | pilot-dryrun | pilot-eval-*
# Python 3.9+; jsonschema optional (stdlib fallback). No other deps.

PY ?= python3
PILOT = $(PY) -m pilot

.PHONY: pilot-validate pilot-test pilot-dryrun pilot-eval-convert pilot-eval-dryrun pilot-clean

pilot-validate:
	$(PILOT).cli --validate-only

pilot-test:
	$(PY) -m unittest discover -s pilot/tests -v

pilot-dryrun:
	$(PILOT).cli --out-dir pilot-out --repetitions 3 --seed 7

# Integration: convert the 30-case reviewed evaluation corpus into the pilot's
# minimal scenario schema (pilot-out/scenarios-eval), then run the documented
# clean-machine dry run against the full corpus. Hindsight and Mnemosyne are
# not-configured in this environment (provider audit); they are reported as
# unsupported, never measured.
pilot-eval-convert:
	$(PILOT).convert_eval --out pilot-out/scenarios-eval

pilot-eval-dryrun:
	$(PILOT).convert_eval --out pilot-out/scenarios-eval
	$(PILOT).cli --scenarios-dir pilot-out/scenarios-eval \
		--out-dir pilot-out/integration --repetitions 3 --seed 7 \
		--unavailable hindsight,mnemosyne

pilot-clean:
	rm -rf pilot-out
