import codi.api as cora
import codi.runtime as rt
import time
from pathlib import Path
import numpy as np
from pynput import keyboard

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "local_client.json"

# test send/receive with instance
rt.start_client(str(CONFIG))
client = cora.get_client()

pressed_keys = set()


def on_press(key):
    try:
        pressed_keys.add(key.char)  # store pressed character
    except AttributeError:
        pass  # ignore special keys


def on_release(key):
    try:
        pressed_keys.discard(key.char)
    except AttributeError:
        pass


# Start the listener in the background
listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()
VELOCITY = 0.1

vectors = {
    "w": [VELOCITY, 0.0, 0.0],
    "a": [0.0, -VELOCITY, 0.0],
    "x": [-VELOCITY, 0.0, 0.0],
    "d": [0.0, VELOCITY, 0.0],
    "q": [-VELOCITY * np.sqrt(2), VELOCITY * np.sqrt(2), 0.0],
    "e": [VELOCITY * np.sqrt(2), VELOCITY * np.sqrt(2), 0.0],
    "c": [VELOCITY * np.sqrt(2), -VELOCITY * np.sqrt(2), 0.0],
    "z": [-VELOCITY * np.sqrt(2), -VELOCITY * np.sqrt(2), 0.0],
}


def command_speed(vector: list):
    vec = vector + [1.0]  # make a new list, original stays unchanged
    command = np.array([vec, [0, 0, 0, 0]])
    client.send_command(
        True, "TS", "velocity", "end_effector", 0.0, command, verbose=False
    )


while True:
    for key in vectors.keys():
        if key in pressed_keys:
            print(f"Pressed {key}, vector:{(vectors[key])}")
            command_speed(vectors[key])

    time.sleep(0.01)
