from codi import CoraServer
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_server.json"

cora_srv = CoraServer(str(CONFIG))
cora_srv.start()  # or cora_srv.start() if the API provides it

last_command = None

try:
    while True:
        current_command = cora_srv.get_command()  # could be None if no command

        if current_command is not None:

            if last_command is not current_command:
                last_command = current_command

                if len(current_command) == 6:
                    _, _, _, _, _, command = current_command
                    print("Received Command:")
                    print(command)

                else:
                    print("Warning: unexpected command format:", current_command)

        time.sleep(0.01)

except KeyboardInterrupt:
    print("Keyboard interrupt detected. Shutting down server.")
