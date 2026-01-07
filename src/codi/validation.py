from .exeptions import ProtocolSchemaError, ProtocolSemanticError
import numpy as np


def validate_command_schema(cmd: dict) -> None:
    required_keys = {
        "rt": bool,
        "space": str,
        "interface_type": str,
        "target": str,
        "gripper_data": (int, float),
        "pose_data": list,
    }

    for key, expected_type in required_keys.items():
        if key not in cmd:
            raise ProtocolSchemaError(f"Missing key: {key}")
        if not isinstance(cmd[key], expected_type):
            raise ProtocolSchemaError(
                f"Key '{key}' must be {expected_type}, got {type(cmd[key])}"
            )


def _raise_semantic_error(values: tuple, keystring: str, invalid_value: any):
    raise ProtocolSemanticError(
            f"Requested {keystring} {invalid_value} invalid. \
                can only accept {values}.")


def validate_command_semantic(cmd: dict) -> None:
    allowed_spaces = ('TS', 'JS')
    allowed_interfaces = ('position', 'velocity', 'acceleration', 'effort')
    allowed_targets = ('Camera', 'Gripper', 'endeffector')
    pose = np.array(cmd["pose_data"], dtype=float)

    # space can only be "TS" or "JS"
    if cmd["space"] not in allowed_spaces:
        _raise_semantic_error(allowed_spaces, 'space', cmd['space'])

    # interface type can only be "position", "velocity", "acceleration", "effort"
    if cmd["interface_type"] not in allowed_interfaces:
        _raise_semantic_error(allowed_interfaces,
                              'interface_type',
                              cmd['interface_type'])

    # target can only be "Camera", "Gripper", "endeffector"
    if cmd["target"] not in allowed_targets:
        _raise_semantic_error(allowed_targets, 'target', cmd['target'])

    # gripper data can only be between 0.00 and 1.00
    if not 0.0 <= cmd['gripper_data'] <= 1.0:
        raise ProtocolSemanticError(
            "Gripper command must be between 0.0 and 1.0"
        )

    # pose commands in JS must be of shape (0, 6) [J1, J2, J3, J4, J5, J6]
    if cmd["space"] == "JS" and pose.shape != (0, 6):
        raise ProtocolSemanticError(
            f'Expected shape (0, 6), but got {pose.shape}'
        )

    # pose commands in TS must be of shape (2, 4) [[x, y, z, 1][rx, ry, rz, w]]
    if cmd["space"] == "TS" and pose.shape != (2, 4):
        raise ProtocolSemanticError(
            f'Expected shape (2, 4), but got {pose.shape}'
            )

    # pose commands in preplanned TS cannot have interface type velocity, acceleration or effort yet...
    if cmd["space"] == "TS" and cmd["rt"] and cmd["interface_type"] != "position":
        raise ProtocolSemanticError(
            f'Only position interface supported for preplanned task space goals, \
                {cmd["interface_type"]} received'
        )
