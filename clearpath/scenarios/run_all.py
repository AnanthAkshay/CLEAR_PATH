"""Execute all benchmark scenarios sequentially."""

from __future__ import annotations

import logging

from clearpath.scenarios import run_emergency, run_normal, run_spoofed

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("scenarios.run_all")


def main() -> None:
    """Execute all scenarios in series."""
    logger.info("Starting benchmark suite...")
    run_normal.run()
    run_emergency.run()
    run_spoofed.run()
    logger.info("All scenarios completed successfully.")


if __name__ == "__main__":
    main()

