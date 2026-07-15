from codi import CoraServer
from codi.messages import CommandMessage
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "example_server.json"

cora_srv = CoraServer(str(CONFIG))
cora_srv.start()

last_command = None

try:
    while True:
        current_command: CommandMessage = cora_srv.get_command()

        if current_command is not None:

            if last_command is not current_command:
                last_command = current_command

                if isinstance(current_command, CommandMessage):
                    command = current_command
                    print(f"Received Command: {command.model_dump}")
                    
                    if command.joint_command is not None:
                        print(command.joint_command)
                    elif command.pose_command is not None:
                        print(command.pose_command)

                else:
                    print("Warning: unexpected command format:", current_command)

        time.sleep(0.01)

except KeyboardInterrupt:
    print("Keyboard interrupt detected. Shutting down server.")
