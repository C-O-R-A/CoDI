from codi import CoraServer
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_server.json"

cora_srv = CoraServer(str(CONFIG))
cora_srv._activate()
last_command = None

while True:
    if cora_srv.command_msg != last_command:
        try:
            print('Received Command:')
            last_command = cora_srv.get_command()
            print(last_command)
            time.sleep(1)

        except KeyboardInterrupt as k:
            print(f'keyboard interrupt, {k}')
            break