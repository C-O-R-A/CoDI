import sys
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from codi import protocol as pt
from codi.codi_enums import GoalSpace, InterfaceType, MoveStatus
from codi.messages import CommandMessage, ConfigMessage, FeedbackMessage, ImageMessage


def test_protocol_round_trips_command_message():
    payload = CommandMessage(
        pose_command=(1.0, 2.0, 3.0),
        interface_type=InterfaceType.POSITION,
        rt=False,
    )

    raw = pt.encode(payload)
    decoded = pt.decode(raw, CommandMessage)

    assert isinstance(decoded, CommandMessage)
    assert decoded.pose_command == (1.0, 2.0, 3.0)
    assert decoded.interface_type == InterfaceType.POSITION.value
    assert decoded.rt is False


def test_command_message_requires_exactly_one_command_type():
    with pytest.raises(ValidationError):
        CommandMessage(
            pose_command=(1.0, 2.0, 3.0),
            joint_command=(0.1, 0.2, 0.3),
            interface_type=InterfaceType.POSITION,
        )

    with pytest.raises(ValidationError):
        CommandMessage(interface_type=InterfaceType.POSITION)


def test_protocol_round_trips_feedback_and_config_messages():
    feedback = FeedbackMessage(
        transforms={
            "transforms": [
                {
                    "header": {
                        "stamp": {"sec": 1, "nanosec": 0},
                        "frame_id": "base_link",
                    },
                    "child_frame_id": "tool0",
                    "transform": {
                        "translation": {"x": 1.0, "y": 2.0, "z": 3.0},
                        "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0},
                    },
                }
            ]
        },
        joint_states={
            "header": {"stamp": {"sec": 1, "nanosec": 0}, "frame_id": "base_link"},
            "name": ["joint_1"],
            "position": [0.1],
            "velocity": [0.2],
            "effort": [0.3],
        },
        status=MoveStatus.IDLE,
    )

    config = ConfigMessage(
        named_state="home",
        rt=True,
        space=GoalSpace.TS,
        interface_type=InterfaceType.POSITION,
        target="tool0",
        enable_camera=True,
    )

    feedback_raw = pt.encode(feedback)
    config_raw = pt.encode(config)

    decoded_feedback = pt.decode(feedback_raw, FeedbackMessage)
    decoded_config = pt.decode(config_raw, ConfigMessage)

    assert decoded_feedback.status.value == MoveStatus.IDLE.value
    assert decoded_feedback.transforms.transforms[0].child_frame_id == "tool0"
    assert decoded_config.space == GoalSpace.TS.value
    assert decoded_config.enable_camera is True


def test_protocol_round_trips_image_payloads():
    image = ImageMessage(
        encoding="png",
        shape=(2, 2, 3),
        dtype="uint8",
        data=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        quality=95,
    )

    raw = pt.encode(image)
    decoded = pt.decode(raw, ImageMessage)

    assert decoded.encoding == "png"
    assert decoded.shape == (2, 2, 3)
    assert decoded.data == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    assert np.array(decoded.data).reshape(decoded.shape).shape == (2, 2, 3)