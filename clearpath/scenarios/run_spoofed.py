"""Scenario 3: Spoofed telemetry and invalid preemption request rejection."""

from __future__ import annotations

import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("scenarios.run_spoofed")


def run() -> None:
    """Run spoofed emergency request rejection scenario."""
    logger.info("Executing Scenario 3: Spoofed Preemption Attack")


if __name__ == "__main__":
    run()

