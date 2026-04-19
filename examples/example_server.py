from codi import CoraServer
import time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_server.json"

cora_srv = CoraServer(str(CONFIG))
cora_srv.start()
last_command = None

while True:
    cora_srv.send_state('moving', 'joint',
                        end_effector_state=np.array([[1, 1, 1], [3, 3, 3]]),
                        camera_frame_state=np.array([[2, 2, 2], [4, 4, 4]]),
                        gripper_frame_state=np.array([[4, 4, 4], [5, 5, 5]]))

    if cora_srv.get_command() != last_command:
        try:
            print('Received Command:')
            last_command = cora_srv.get_command()
            print(last_command)
            time.sleep(1)

        except KeyboardInterrupt as k:
            raise KeyboardInterrupt(f'keyboard interrupt, {k}')

    time.sleep(0.3)
