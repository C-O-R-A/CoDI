import codi.api as cora
import codi.runtime as rt
import time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_client.json"
# test send/receive without (re)starting instance of object
# cora.send_joint_position(rt=False, space='TS', interface_type='position', target='gripper', gripper_command=1.0, command=[[1, 1, 1, 1], [2, 2, 2, 2]])

# test send/receive with instance
rt.start_client(str(CONFIG))
cora.send_joint_position(
    rt=False,
    space="TS",
    interface_type="position",
    target="gripper",
    gripper_command=1.0,
    command=np.array([[1, 1, 1, 1], [2, 2, 2, 2]]),
)
time.sleep(2)
print(cora.get_client().get_states())

stop_client = input("Stop Client? y/n")

match stop_client:
    case "n":
        pass
    case "y":
        cora.stop_client()
        pass
    case _:
        print('unknown')
        pass
