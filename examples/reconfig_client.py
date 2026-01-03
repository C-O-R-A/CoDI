import codi.api as cora
import codi.runtime as rt
import time

client = cora.get_client()
client.configure_robot(use_controller=True, use_camera=True, use_vision=True)
time.sleep(2)
last_state = None

while True:
    try:
        state = client.get_states()
        if state != last_state:
            print(state)
            last_state = state

    except KeyboardInterrupt:
        stop_client = input("Stop Client? \n" + "Y/N")
        match stop_client:
            case "Y":
                rt.stop_client()
                break
            case _:
                continue
