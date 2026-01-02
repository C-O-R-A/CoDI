import numpy as np
from numpy.typing import NDArray
import json as js
from typing import List, Tuple
import msgpack
import cv2

"""
TODO: we can use this module on the desktop as well as on the robot. 
add utility fucntions for encoding states and decoding commands as needed. 
also add options for reading/writing from files for offline testing.
"""


def image_to_bytes(
    image: NDArray,
    encoding: str = "jpeg",
    quality: int = 90,
) -> bytes:
    """
    Encode image to MessagePack bytes.

    :param image: numpy array (H x W x C or H x W)
    :param encoding: 'jpeg' or 'png'
    :param quality: JPEG quality (1–100)
    """
    if encoding == "jpeg":
        params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        ext = ".jpg"
    elif encoding == "png":
        params = []
        ext = ".png"
    else:
        raise ValueError("Unsupported image encoding")

    success, buffer = cv2.imencode(ext, image, params)
    if not success:
        raise RuntimeError("Image encoding failed")

    payload = {
        "encoding": encoding,
        "shape": image.shape,
        "dtype": str(image.dtype),
        "data": buffer.tobytes(),
    }

    return msgpack.packb(payload, use_bin_type=True)


def bytes_to_image(byte_data: bytes) -> NDArray:
    """
    Decode MessagePack image bytes into numpy array.
    """
    payload = msgpack.unpackb(byte_data, raw=False)
    buffer = np.frombuffer(payload["data"], dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED)

    if image is None:
        raise RuntimeError("Image decoding failed")

    return image


def encode_commands(
    rt: bool,
    space: str,
    interface_type: str,
    target: str,
    gripper_command: float,
    pose_command: NDArray,
) -> bytes:
    """
    Serialize  goal pose command and gripper command into string format.

    :param rt: True for real-time, False for non-real-time

    :param space: 'JS' for joint space or 'TS' for task (cartesian) space

    :param interface_type: command interface type; 'position', 'velocity', 'effort'

    :param target: command target frame, 'camera', 'gripper', 'end_effector'

    :param gripper_command: float of the gripper command
                            format: gripper_position <between 0.0 (open) and 1.0 (closed)>

    :param commands:  4x2 numpy array of the values wrt the selected space;
            format:
                    [[x, y, z, 1], [rx, ry, rz, w]] for position
                    or [[vx, vy, vz, 1], [wx, wy, wz, w]] for velocity
                    or [[Fx, Fy, Fz, 1],[Mx, My, Mz, w]] for effort



    returns: UTF-8 encoded json formatted commands;
            format: b'{'space': space, 'rt': rt, 'interface_type':interface_type, 'shape': [rows, columns],
                            'type': dtype, 'data_array': [[x, y, z, 1], [rx, ry, rz, w]]}'
    """
    command_data = {
        "rt": rt,
        "space": space,
        "interface_type": interface_type,
        "shape": list(pose_command.shape),
        "dtype": str(pose_command.dtype),
        "target": target,
        "gripper_data": gripper_command,
        "pose_data": pose_command.tolist(),
    }

    raw_json_commands = (js.dumps(command_data)).encode("utf-8")
    return raw_json_commands


def decode_commands(raw_json_commands: bytes) -> bool | str | float | NDArray:
    """
    Docstring for decode_commands

    :param raw_json_commands: Description
    :type raw_json_commands: bytes
    :return: Description
    :rtype: bool | str | float | NDArray
    """
    json_commands = js.loads(raw_json_commands.decode("utf-8"))
    gripper_command = json_commands["gripper_data"]
    pose_command = np.array(json_commands["pose_data"], float)
    target = json_commands["target"]
    interface_type = json_commands["interface_type"]
    space = json_commands["space"]
    rt = json_commands["rt"]
    return rt, space, interface_type, target, gripper_command, pose_command


def encode_pose_feedback(
    status: str,
    space: str,
    end_effector_states: NDArray,
    camera_frame_states: NDArray,
    gripper_frame_states: NDArray,
) -> bytes:
    """
    encode_pose_feedback

    :param status: Robot move status.
    :type status: str
    :param space: 'JS' for joint space or 'TS' for task (cartesian) space
    :type space: str
    :param end_effector_states: end effector states. [[x, y, z, 1], [rx, ry, rz, w]]
    :param camera_frame_states: camera frame states. [[x, y, z, 1], [rx, ry, rz, w]]
    :param gripper_frame_states: gripper frame states. [[x, y, z, 1], [rx, ry, rz, w]]
    """
    states_data = {
        "status": status,
        "space": space,
        "shape": end_effector_states.shape,
        "type": end_effector_states.dtype,
        "end_effector_data": end_effector_states.tolist(),
        "camera_frame_data": camera_frame_states.tolist(),
        "gripper_frame_data": gripper_frame_states.toList(),
    }
    raw_json_states = (js.dumps(states_data)).encode("utf-8")
    return raw_json_states


def decode_pose_feedback(raw_json_states: bytes) -> str | NDArray:
    """
    Load pose with json, convert from list to numpy array\n

    :param raw_json_states: states in json format as raw bytes\n
            format: b'{\n

            'status': status,\n
            'space': space,\n

            'shape': [rows, columns],\n
            'type': dtype, \n

            'end_effector_data': [[x, y, z, 1], [rx, ry, rz, w]]\n,
            'camera_frame_data': [[x, y, z, 1], [rx, ry, rz, w]]\n,
            'gripper_frame_data': [[x, y, z, 1], [rx, ry, rz, w]]\n
            }'\n

    returns status, space, states_array of type string, string, numpy_array;
            status: 'idle', 'at_target', 'moving', 'error'\n
            space: 'JS' for joint space or 'TS' for task (cartesian) space\n
            end_effector_states, camera_frame_states, gripper_frame_states: numpy array of the states values;
                    format:\n
                            [[x, y, z, 1], [rx, ry, rz, w]]\n
    """
    json_states = js.loads(raw_json_states.decode("utf-8"))
    status = json_states["status"]
    space = json_states["space"]
    end_effector_states = np.array(json_states["end_effector_data"], float)
    camera_frame_states = np.array(json_states["camera_frame_data"], float)
    gripper_frame_states = np.array(json_states["gripper_frame_data"], float)
    return status, space, end_effector_states, camera_frame_states, gripper_frame_states


def encode_configs(use_controller=False, use_video=False, use_vision=False) -> bytes:
    """
    Docstring for encode_configs

    :param use_controller: Description
    :param use_video: Description
    :param use_vision: Description
    """
    config_data = {
        "use_controller": use_controller,
        "use_video": use_video,
        "use_vision": use_vision,
    }

    raw_json_configs = (js.dumps(config_data)).encode("utf-8")
    return raw_json_configs


def decode_configs(raw_json_configs: bytes) -> bool:
    config_data = js.loads(raw_json_configs.decode("utf-8"))
    return (
        config_data["use_controller"],
        config_data["use_video"],
        config_data["use_vision"],
    )


def encode_aruco_poses(ids: List[str], poses: NDArray) -> bytes:
    """
    Encode ArUco marker poses into UTF-8 JSON bytes.

    :param ids: List of ArUco marker IDs
    :param poses: Nx2x4 array or equivalent iterable:
                    [[[x, y, z, 1], [rx, ry, rz, w]], ...]
    :return: UTF-8 encoded JSON bytes
    """
    pose_data = {id_: j.tolist() for id_, j in zip(ids, poses)}
    raw_json_poses = js.dumps(pose_data).encode("utf-8")
    return raw_json_poses


def decode_aruco_poses(raw_aruco_poses: bytes) -> list | NDArray:
    """
    Decode ArUco marker poses from UTF-8 JSON bytes

    :param raw_aruco_poses: UTF-8 encoded JSON bytes
    :type raw_aruco_poses: bytes
    :return: (ids, poses)
    :rtype: list | NDArray
    """
    aruco_poses = js.loads(raw_aruco_poses.decode("utf-8"))
    ids = list(aruco_poses.keys())
    poses = np.array(list(aruco_poses.values()), dtype=float)
    return ids, poses
