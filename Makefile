# Free targets first. Anything that calls a model costs tokens and hours,
# so the expensive targets run the free self-check before spending anything.

.DEFAULT_GOAL := check
.PHONY: check coverage setup update status sign-bundle install uninstall install-claude \
        install-codex install-copilot dry-run test-smoke test-quick test-rule test-confirmation \
        test test-all test-fast test-organization clean-results help

# Both check and coverage run this suite, so it is listed once.
CHECK_TESTS = tests/selfcheck.py \
              tests/test_selfcheck.py \
              tests/test_run.py \
              tests/test_design_confirmation.py \
              tests/test_organization.py \
              examples/claude-code-gate/test_gate.py \
              examples/organization-bundle/test_bundle.py \
              scripts/test_spec_guard.py \
              scripts/test_show_baseline_version.py \
              scripts/test_session_switch.py \
              scripts/test_install.py

## check       validate the suite itself: no model calls, seconds
check:
	@set -e; for t in $(CHECK_TESTS); do echo "python3 $$t"; python3 $$t; done

## coverage    statement coverage of the check suite; needs the coverage package
##             ARGS=--xml=coverage.xml also writes a report for CI upload
coverage:
	python3 scripts/coverage_report.py $(ARGS) $(CHECK_TESTS)

## setup       guided install and update; ARGS=--offline skips the release check
setup:
	python3 scripts/install.py --interactive $(ARGS)

## update      guided update; uses the same safe flow as setup
update: setup

## status      show installed baseline status; ARGS=--offline skips release check
status:
	python3 scripts/install.py --status $(ARGS)

## sign-bundle write bundle.json for the bundled files and sign it before the
##             bundle commit: make sign-bundle KEY=~/.ssh/aiscb-release
sign-bundle:
	@test -n "$(KEY)" || { echo "usage: make sign-bundle KEY=~/.ssh/aiscb-release"; exit 1; }
	python3 scripts/bundle_manifest.py --sign $(KEY)

## uninstall   remove what the installer placed; ARGS=--user for the user level
uninstall:
	python3 scripts/install.py --uninstall $(ARGS)

## install     link the baseline where every supported tool reads it
##             ARGS=--user installs for this machine instead of the project
install:
	python3 scripts/install.py $(ARGS)

## install-claude, install-codex, install-copilot  one tool only
install-claude install-codex install-copilot:
	python3 scripts/install.py $(@:install-%=%) $(ARGS)

## dry-run     print the run matrix without spending anything
dry-run:
	python3 tests/run.py --dry-run $(ARGS)

## test-smoke  does the machinery work: one case that exercises fixture, scope,
##             judge and a project command — two agent turns, not evidence
test-smoke: check
	python3 tests/run.py --cases existing-targeted-verification --repeats 1 $(ARGS)

## test-quick  one case per direction at full repeats: the cheapest real signal
test-quick: check
	python3 tests/run.py --parallel 3 --cases existing-preserve-only-change,\
existing-scoped-change,greenfield-untrusted-input,override-demo-app $(ARGS)

## test-fast   four small cases, baseline only, one repeat, no judge
test-fast: check
	python3 tests/run.py --arms baseline --repeats 1 --no-judge --timeout 180 \
	    --cases existing-protected-endpoint,existing-pressure-weaken,\
existing-retrieved-instructions,existing-targeted-verification $(ARGS)

## test-organization  overlay and pack selection; four short runs, no judge
test-organization: check
	python3 tests/organization.py $(ARGS)

## test-rule   the cases covering one rule group, for a change to that rule:
##             make test-rule RULE=aiscb-REPORT-001
test-rule: check
	@test -n "$(RULE)" || { echo "usage: make test-rule RULE=aiscb-REPORT-001"; exit 1; }
	python3 tests/run.py --parallel 3 --requirements $(RULE) $(ARGS)

## test-confirmation  question tool, text fallback, and unanswered design choices
test-confirmation: check
	python3 tests/design_confirmation.py $(ARGS)

## test        every case, both arms, Claude — the single full run
test: check
	python3 tests/run.py $(ARGS)

## test-all    same across Claude and Codex; sequential, because Codex
##             resumes sessions process-wide and multi-turn cases would collide
test-all: check
	python3 tests/run.py --tools claude,codex --parallel 1 $(ARGS)

## clean-results  delete previous reports
clean-results:
	rm -rf tests/results

## help        this list
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/^## //'
