"""
    DEPRECATED
"""

import codi.runtime as rt
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "local_client.json"

# test send/receive with instance
rt.start_client(str(CONFIG))
client = rt.get_client()
time.sleep(2)

print('reconfiguring cora client')
client.configure_robot(use_controller=True, use_camera=True, use_vision=True)
last_state = None

while True:
    try:
        time.sleep(0.5)
        continue

    except KeyboardInterrupt:
        stop_client = input("Stop Client? \n" + "Y/N")
        match stop_client:
            case "y":
                rt.stop_client()
                break
            case _:
                continue
