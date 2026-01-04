from codi import CoraServer
import time
from pathlib import Path
import cv2

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_server.json"
cap = cv2.VideoCapture(0)

cora_srv = CoraServer(str(CONFIG))
cora_srv.start()
fps = 30

while True:
    # Capture frame-by-frame
    ret, frame = cap.read()
    try:
        if ret:
            print('frame returned')
            cora_srv.send_frame(frame)
    except KeyboardInterrupt as k:
        raise KeyboardInterrupt(f'keyboard interrupt, {k}')
    time.sleep(1/fps)
