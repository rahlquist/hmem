# hmem pilot — automated validation and test targets
# Usage: make pilot-validate | pilot-test | pilot-dryrun | pilot-eval-*
#        | pilot-measured-baseline
# Python 3.9+; jsonschema optional (stdlib fallback). No other deps.

PY ?= python3
PILOT = $(PY) -m pilot

.PHONY: pilot-validate pilot-test pilot-dryrun pilot-eval-convert pilot-eval-dryrun pilot-measured-baseline pilot-clean

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

# Measured lexical baseline: three isolated full-corpus runs of the REAL
# in-process Okapi BM25 ranker (pilot/lexical.py), then aggregate them into
# the category-first measured baseline report with cross-run variance.
# Every run writes into its own unique <out>/runs/<manifest_id>/ directory
# (--isolated); results are measurement_kind=measured / hmem-measured ONLY
# via the real measured path. Simulated stubs are never relabeled.
pilot-measured-baseline:
	$(PILOT).convert_eval --out pilot-out/scenarios-eval
	for i in 1 2 3; do \
		$(PILOT).cli --mode measured --isolated \
			--measured lexical_baseline --providers lexical_baseline \
			--scenarios-dir pilot-out/scenarios-eval \
			--out-dir pilot-out/measured-runs \
			--repetitions 3 --seed 7; \
	done
	$(PILOT).measured_report --runs pilot-out/measured-runs/runs \
		--out pilot-out/measured-report

pilot-clean:
	rm -rf pilot-out
