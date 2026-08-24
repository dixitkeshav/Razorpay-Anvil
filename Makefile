.PHONY: install seed holdout run eval sweep reproduce test lint \
        test-phase-0 test-phase-1 test-phase-2 test-phase-3 test-phase-4 \
        test-phase-5 test-phase-6 test-phase-7 test-phase-8 test-phase-9 \
        test-phase-10 test-phase-11 test-phase-12 test-phase-13

VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff

$(VENV)/bin/activate:
	python3.11 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

install: $(VENV)/bin/activate

seed: install
	$(PY) -m src.generator.seed

holdout: install
	$(PY) -m src.generator.seed --holdout

run:
	docker compose up

eval: install
	$(PY) -m src.evaluation.run_eval

sweep: install
	$(PY) -m src.evaluation.run_sweep

reproduce: seed eval sweep

test: install
	$(PYTEST) -v

lint: install
	$(RUFF) check src tests

test-phase-0: install
	$(PYTEST) -v tests/test_phase0_razorpay_auth.py

test-phase-1: install
	$(PYTEST) -v tests/test_generator.py

test-phase-2: install
	$(PYTEST) -v tests/test_ingest.py

test-phase-3: install
	$(PYTEST) -v tests/test_detection.py tests/test_detector_ignores_ground_truth.py

test-phase-4: install
	$(PYTEST) -v tests/test_attribution.py

test-phase-5: install
	$(PYTEST) -v tests/test_impact.py tests/test_incident_state_machine.py

test-phase-6: install
	$(PYTEST) -v tests/test_policy_gates.py tests/test_stopping_rules.py tests/test_escalation_thresholds.py

test-phase-7: install
	$(PYTEST) -v tests/test_idempotency.py tests/test_ledger_append_only.py tests/test_execution.py

test-phase-8: install
	$(PYTEST) -v tests/test_evaluation.py
	$(MAKE) eval

test-phase-9: install
	$(PYTEST) -v tests/test_llm_cannot_reach_policy.py tests/test_injection_defense.py

test-phase-10: install
	$(PYTEST) -v tests/test_quality_monitor.py

test-phase-11: install
	$(PYTEST) -v tests/test_mcp_server.py

test-phase-12:
	@echo "Phase 12 gate is manual: docker compose up, then verify an incident renders end to end."

test-phase-13: install
	$(MAKE) holdout
	$(MAKE) eval
	$(MAKE) sweep
