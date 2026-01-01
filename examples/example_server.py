from codi import CoraServer
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_server.json"

cora_srv = CoraServer(str(CONFIG))
cora_srv._activate()

while True:
    if cora_srv.command_msg:
        try:
            print('Received Command:')
            print(cora_srv.get_command())
            time.sleep(1)

        except KeyboardInterrupt as k:
            print(f'keyboard interrupt, {k}')
            break