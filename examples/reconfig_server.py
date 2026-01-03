from codi import CoraServer
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_server.json"

cora_srv = CoraServer(str(CONFIG))
cora_srv._activate()
last_config = None

while True:
    config = cora_srv.receive_config()
    if config != last_config:
        try:
            print('Received Command:')
            print(config)
            last_config = config
            time.sleep(1)

        except KeyboardInterrupt as k:
            raise KeyboardInterrupt(f'keyboard interrupt, {k}')

    time.sleep(0.3)
