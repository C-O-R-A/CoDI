"""Example server that periodically fetches and prints the robot configuration.

This script connects to a CoDI server using the example configuration and polls the
runtime configuration. It is useful for verifying how robot settings are exposed and
updated over time.

Usage:
    python examples/reconfig_server.py
"""

from codi import CoraServer
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_server.json"

cora_srv = CoraServer(str(CONFIG))
cora_srv.start()
last_config = None

while True:
    try:
        if not cora_srv.connected:
            continue
        config = cora_srv.get_config()
        print('Received Config:')
        print(config)
        last_config = config
        time.sleep(1)

    except KeyboardInterrupt as k:
        cora_srv._end_interface()
        raise KeyboardInterrupt(f'keyboard interrupt, {k}')

    time.sleep(0.3)
