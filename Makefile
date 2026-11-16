.PHONY: help install test demo dashboard rl-train rl-eval

PYTHON ?= python

help:
	@echo "Available commands:"
	@echo "  make install    - Install required dependencies"
	@echo "  make test       - Run test suite via pytest"
	@echo "  make demo       - Execute all benchmark scenarios and print checklist"
	@echo "  make dashboard  - Launch live interactive Streamlit dashboard"
	@echo "  make rl-train   - Train RL junction policy with parameter sharing"
	@echo "  make rl-eval    - Run 3-way evaluation: Baseline vs Rules vs RL"

install:
	$(PYTHON) -m pip install -r requirements.txt

test:
	$(PYTHON) -m pytest -q

demo:
	$(PYTHON) -m clearpath.scenarios.run_all

dashboard:
	$(PYTHON) -m streamlit run clearpath/dashboard/app.py

rl-train:
	$(PYTHON) -m clearpath.rl.train --episodes 100 --seed 42

rl-eval:
	$(PYTHON) -m clearpath.rl.train --eval-only

