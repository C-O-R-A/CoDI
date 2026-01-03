import codi.api as cora
import codi.runtime as rt
import time
from pathlib import Path
import cv2

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "local_client.json"

# test send/receive with instance
rt.start_client(str(CONFIG))
client = cora.get_client()
client.configure_robot(use_camera=True)
time.sleep(2)
fps = 30

while True:
    try:
        frame = client.get_frame()
        if frame is not None:
            print('frame received')
            cv2.imshow('Received frame', frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                client._end_interface()
                break

    except KeyboardInterrupt:
        stop_client = input("Stop Client? \n" + "Y/N")
        match stop_client:
            case "Y":
                client._end_interface()
                break
            case _:
                continue

    time.sleep(1/fps)
