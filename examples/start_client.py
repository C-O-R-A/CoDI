"""Minimal example that keeps a CoDI client alive.

This script starts a local client using the default client configuration and blocks
until the connection is terminated. It is a lightweight example for keeping the
runtime process active in a headless environment.

Usage:
    python examples/start_client.py
"""

import codi.runtime as rt
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "local_client.json"

# test send/receive with instance
rt.start_client(str(CONFIG))

while rt.get_client():
    continue
