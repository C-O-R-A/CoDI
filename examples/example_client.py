import codi.runtime as rt
from codi.codi_enums import InterfaceType
from codi.exeptions import ProtocolSchemaError
from codi.messages import FeedbackObject
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "local_client.json"

# test send/receive with instance
rt.start_client(str(CONFIG))
client = rt.get_client()

time.sleep(2)
last_state = None

while True:
    try:
        client.send_command(
            pose_command=(0.1, 0.1, 0.1, 0.0, 0.0, 0.0),
            interface_type=InterfaceType.POSITION,
            rt=False,
            target='gripper',
            predef_pose='standby',
        )

        state: FeedbackObject = client.get_states()
        if state is not None and state.transforms:
            print(state.transforms[0].transform_matrix)

        time.sleep(0.3)

    except ProtocolSchemaError as e:
        print(f"Bad command: {e}")
        continue

    except KeyboardInterrupt:
        stop_client = input("Stop Client? Y/N ")
        match stop_client.strip().lower():
            case "y":
                client._end_interface()
                break
            case _:
                continue