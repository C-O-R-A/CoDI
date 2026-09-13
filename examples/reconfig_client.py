import codi.runtime as rt
from codi.codi_enums import GoalSpace, InterfaceType
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "local_client.json"

# test send/receive with instance
rt.start_client(str(CONFIG))
client = rt.get_client()
time.sleep(2)

print("reconfiguring cora client")
client.configure_robot(
    use_camera=True,
    rt=True,
    space=GoalSpace.TS,
    interface_type=InterfaceType.POSITION,
    target="end_effector",
)
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
