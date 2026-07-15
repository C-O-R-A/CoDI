from codi import CoraServer
from codi.codi_enums import MoveStatus
import time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_server.json"

cora_srv = CoraServer(str(CONFIG))
cora_srv.start()
last_command = None

# Example joint names/state — swap these for real encoder feedback
joint_names = ["J1", "J2", "J3", "J4", "J5", "J6"]
joint_positions = np.zeros(len(joint_names)).tolist()
joint_velocities = np.zeros(len(joint_names)).tolist()
joint_efforts = np.zeros(len(joint_names)).tolist()

try:
    while True:
        transforms = {
            "transforms": [
                {
                    "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "base_link"},
                    "child_frame_id": "tool0",
                    "transform": {
                        "translation": {"x": 0.0, "y": 0.0, "z": 0.0},
                        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    },
                }
            ]
        }

        jointstates = {
            "header": {"stamp": {"sec": 0, "nanosec": 0}, "frame_id": "base_link"},
            "name": joint_names,
            "position": joint_positions,
            "velocity": joint_velocities,
            "effort": joint_efforts,
        }

        cora_srv.send_state(transforms, jointstates, MoveStatus.IDLE)

        command = cora_srv.get_command()
        if command is not None:
            last_command = command
            print("Received Command:")
            print(last_command.model_dump())

        time.sleep(0.3)

except KeyboardInterrupt:
    print("Keyboard interrupt, shutting down server...")
    cora_srv.cleanup()