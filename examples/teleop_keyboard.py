"""
    DEPRECATED
"""

import codi.runtime as rt
import time
from pathlib import Path
import numpy as np
from pynput import keyboard

HERE = Path(__file__).resolve().parent
CONFIG = HERE.parent / "config" / "local_client.json"

# Start client
rt.start_client(str(CONFIG))
client = rt.get_client()
time.sleep(4)

pressed_keys = set()


def on_press(key):
    try:
        pressed_keys.add(key.char)
    except AttributeError:
        pass


def on_release(key):
    try:
        pressed_keys.discard(key.char)
    except AttributeError:
        pass


listener = keyboard.Listener(on_press=on_press, on_release=on_release)
listener.start()

VELOCITY_LIN = 0.1
VELOCITY_ANG = 2

# ---- MOTION KEYS ONLY (NO 's') ----
vectors = {
    "w": [VELOCITY_LIN, 0.0, 0.0],
    "a": [0.0, -VELOCITY_LIN, 0.0],
    "x": [-VELOCITY_LIN, 0.0, 0.0],
    "d": [0.0, VELOCITY_LIN, 0.0],
    "q": [-VELOCITY_LIN * np.sqrt(2), VELOCITY_LIN * np.sqrt(2), 0.0],
    "e": [VELOCITY_LIN * np.sqrt(2), VELOCITY_LIN * np.sqrt(2), 0.0],
    "z": [-VELOCITY_LIN * np.sqrt(2), -VELOCITY_LIN * np.sqrt(2), 0.0],
    "c": [VELOCITY_LIN * np.sqrt(2), -VELOCITY_LIN * np.sqrt(2), 0.0],
}


def command_joint(vector):
    client.send_command(
        True,
        "JS",
        "velocity",
        "gripper",
        0.0,
        np.array(vector),
        predef_pose=None,
        verbose=False,
    )


def command_speed(vector, space="TS"):
    vec = vector + [1.0]
    command = np.array([vec, [0, 0, 0, 0]])
    client.send_command(
        True,
        space,
        "velocity",
        "end_effector",
        0.0,
        command,
        predef_pose=None,
        verbose=False,
    )


def switch_space(space):
    return "JS" if space == "TS" else "TS"


client.send_command(
    rt=False,
    space="TS",
    interface_type="position",
    target="Gripper",
    gripper_command=0.01,
    command=np.array([[0.60, 0.0, 0.2, 1], [0.0, 0.0, -0.7070727, 0.7070727]]),
    predef_pose='standby',
    verbose=False,
)

time.sleep(10)

print(
    "Teleop started:\n"
    "  Motion: W A D X Q E Z C\n"
    "  Switch space: S\n"
    "  Ctrl+C to exit"
)

client.configure_robot(use_camera=True)

space = "TS"

while True:
    # ---- MODE SWITCH (S ONLY) ----
    if "s" in pressed_keys:
        space = switch_space(space)
        print(f"Switched control space → {space}")
        pressed_keys.remove("s")  # edge-triggered

    sent_command = False

    # ---- TASK SPACE ----
    if space == "TS":
        for key in pressed_keys:
            if key in vectors:
                command_speed(vectors[key], space=space)
                sent_command = True
        # ---- STOP WHEN NO INPUT ----
        if not sent_command:
            command_speed([0.0, 0.0, 0.0])

    # ---- JOINT SPACE ----
    elif space == "JS":
        velocity = VELOCITY_ANG
        for key in pressed_keys:
            if key == "-":
                velocity = -velocity
            else:
                velocity = velocity
            if key in ("1", "2", "3", "4", "5", "6"):
                idx = int(key) - 1
                vec = [0.0] * 6
                vec[idx] = velocity
                print(f"Commanding joint {key} with velocity {vec[idx]}")
                print('vector:', vec)
                command_joint(vec)
                sent_command = True

        # ---- STOP WHEN NO INPUT ----
        if not sent_command:
            command_joint([0.0] * 6)

    time.sleep(0.01)
