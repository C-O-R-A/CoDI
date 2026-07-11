from pydantic import BaseModel, Field, model_validator
from __future__ import annotations
from typing import Literal, Optional
from codi.codi_enums import GoalSpace, InterfaceType, MoveStatus
from dataclasses import dataclass


class Time(BaseModel):
    sec: int
    nanosec: int


class Header(BaseModel):
    stamp: Time
    frame_id: str


class Vector3(BaseModel):
    x: float
    y: float
    z: float


class Quaternion(BaseModel):
    x: float
    y: float
    z: float
    w: float


class Transform(BaseModel):
    translation: Vector3
    rotation: Quaternion


class TransformStamped(BaseModel):
    header: Header
    child_frame_id: str
    transform: Transform


class TFMessage(BaseModel):
    transforms: list[TransformStamped] = Field(default_factory=list)


class JointStates(BaseModel):
    header: Header

    name: list[str] = Field(default_factory=list)
    position: list[float] = Field(default_factory=list)
    velocity: list[float] = Field(default_factory=list)
    effort: list[float] = Field(default_factory=list)


class ImageMessage(BaseModel):
    """Model for representing image messages."""
    encoding: str = Field('png', description="Image encoding format (e.g., 'jpeg', 'png')")
    shape: tuple = Field(..., description="Shape of the image (height, width, channels)")
    dtype: str = Field(..., description="Data type of the image (e.g., 'uint8')")
    data: bytes = Field(..., description="Raw image data in bytes")
    quality: int = Field(95, description="Image quality (0-100)")


class CommandMessage(BaseModel):
    """Model for representing command messages."""

    pose_command: Optional[tuple] = None
    joint_command: Optional[tuple] = None

    interface_type: Optional[int] = InterfaceType.POSITION
    rt: Optional[bool] = False
    target: Optional[str] = None
    gripper_command: Optional[float] = None
    predef_pose: Optional[str] = None

    model_config = {
        "use_enum_values": True
    }

    @model_validator(mode="after")
    def validate_command_type(self):
        has_pose = self.pose_command is not None
        has_joint = self.joint_command is not None

        if has_pose == has_joint:
            raise ValueError(
                "Exactly one of 'pose_command' or 'joint_command' must be provided"
            )

        return self


class FeedbackMessage(BaseModel):
    """Model for representing feedback messages."""
    transforms: TFMessage
    joint_states: JointStates
    status: int


class ConfigMessage(BaseModel):
    """Model for representing configuration messages."""
    named_state: Optional[str] = None
    rt: Optional[bool] = None
    space: Optional[str] = None
    interface_type: Optional[str] = None
    target: Optional[str] = None
    enable_camera: Optional[bool] = None


@dataclass
class JointStateObject():
    position: float
    velocity: float
    effort: float

    
@dataclass
class TransformObject():
    parent: str
    child: str
    position: list[float]
    orientation: list[float]