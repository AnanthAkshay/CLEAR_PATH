"""Pytest configuration for ClearPath test suite."""

from __future__ import annotations

import os

# Set test HMAC secret to suppress the insecure development default warning
# during automated pytest executions while preserving it for normal runtime.
os.environ["CLEARPATH_SECRET"] = "clearpath-test-suite-secure-secret-key-12345"

