import codi.api as cora
import codi.runtime as rt
import time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_client.json"

# test send/receive with instance
rt.start_client(str(CONFIG))
client = cora.get_client()
cora.send_joint_position(
    rt=False,
    space="TS",
    interface_type="position",
    target="gripper",
    gripper_command=1.0,
    command=np.array([[1, 1, 1, 1], [2, 2, 2, 2]]),
)

time.sleep(2)
last_state = None

while True:
    try:
        state = client.get_states()
        if state != last_state:
            print(state)
            last_state = state

    except KeyboardInterrupt:
        stop_client = input("Stop Client? \n" + "Y/N")
        match stop_client:
            case "Y":
                client._end_interface()
                break
            case _:
                continue
