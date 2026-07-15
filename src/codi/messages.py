from __future__ import annotations
from pydantic import BaseModel, Field, model_validator
from typing import Optional
from codi.codi_enums import GoalSpace, InterfaceType, MoveStatus
from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray
from cv2.typing import MatLike

class Time(BaseModel):
    """Represents a ROS-style timestamp.

    Attributes:
        sec: Seconds component of the timestamp.
        nanosec: Nanoseconds component of the timestamp.
    """
    sec: int
    nanosec: int


class Header(BaseModel):
    """Metadata header containing time and frame information.

    Attributes:
        stamp: Timestamp of the header.
        frame_id: Coordinate frame identifier.
    """
    stamp: Time
    frame_id: str


class Vector3(BaseModel):
    """Cartesian coordinate vector in 3D space.

    Attributes:
        x: X coordinate.
        y: Y coordinate.
        z: Z coordinate.
    """
    x: float
    y: float
    z: float


class Quaternion(BaseModel):
    """Quaternion representation of orientation.

    Attributes:
        x: X component of the quaternion.
        y: Y component of the quaternion.
        z: Z component of the quaternion.
        w: W component of the quaternion.
    """
    x: float
    y: float
    z: float
    w: float


class Transform(BaseModel):
    """A rigid body transform with translation and rotation.

    Attributes:
        translation: Translation component as a Vector3.
        rotation: Rotation component as a Quaternion.
    """
    translation: Vector3
    rotation: Quaternion


class TransformStamped(BaseModel):
    """A transform with a timestamped header and child frame name.

    Attributes:
        header: Header containing the timestamp and frame id.
        child_frame_id: Name of the child frame.
        transform: Transform data for translation and rotation.
    """
    header: Header
    child_frame_id: str
    transform: Transform


class TFMessage(BaseModel):
    """A collection of stamped transforms representing a TF message.

    Attributes:
        transforms: List of stamped transforms.
    """
    transforms: list[TransformStamped] = Field(default_factory=list)


class JointStates(BaseModel):
    """Joint state message containing name, position, velocity, and effort arrays.

    Attributes:
        header: Message header.
        name: Joint names.
        position: Joint positions.
        velocity: Joint velocities.
        effort: Joint efforts.
    """
    header: Header

    name: list[str] = Field(default_factory=list)
    position: list[float] = Field(default_factory=list)
    velocity: list[float] = Field(default_factory=list)
    effort: list[float] = Field(default_factory=list)


class ImageMessage(BaseModel):
    """Model for representing encoded image messages.

    Attributes:
        encoding: Image encoding format (e.g. 'jpeg' or 'png').
        shape: Shape of the image (height, width, channels).
        dtype: Data type of the image array.
        data: Raw encoded image bytes.
        quality: JPEG quality level (0-100).
    """
    encoding: str = Field('png', description="Image encoding format (e.g., 'jpeg', 'png')")
    shape: tuple = Field(..., description="Shape of the image (height, width, channels)")
    dtype: str = Field(..., description="Data type of the image (e.g., 'uint8')")
    data: list[int] = Field(..., description="Image")
    quality: int = Field(95, description="Image quality (0-100)")


class CommandMessage(BaseModel):
    """Command payload for motion control.

    The message supports either a Cartesian pose command or a joint-space command,
    along with optional control settings such as the interface type and realtime flag.

    Attributes:
        pose_command: Cartesian pose command tuple.
        joint_command: Joint-space command tuple.
        interface_type: Motion interface type.
        rt: Real-time execution flag.
        target: Target frame or component identifier.
        gripper_command: Gripper command value.
        predef_pose: Name of a predefined pose.
    """

    pose_command: Optional[tuple] = None
    joint_command: Optional[tuple] = None

    interface_type: Optional[InterfaceType] = InterfaceType.POSITION
    rt: Optional[bool] = False
    target: Optional[str] = None
    gripper_command: Optional[float] = None
    predef_pose: Optional[str] = None

    model_config = {
        "use_enum_values": True
    }

    @model_validator(mode="after")
    def validate_command_type(self):
        """Validate that exactly one command type is provided.

        Raises:
            ValueError: If both or neither of pose_command and joint_command are provided.
        """
        has_pose = self.pose_command is not None
        has_joint = self.joint_command is not None

        if has_pose == has_joint:
            raise ValueError(
                "Exactly one of 'pose_command' or 'joint_command' must be provided"
            )
        return self


class FeedbackMessage(BaseModel):
    """Feedback payload containing transforms, joint states, and execution status.

    Attributes:
        transforms: A TFMessage containing transform data.
        joint_states: JointStates containing current joint status.
        status: Current motion status.
    """
    transforms: TFMessage
    joint_states: JointStates
    status: MoveStatus

    model_config = {
        "use_enum_values": True
    }


class ConfigMessage(BaseModel):
    """Configuration payload for motion and sensor settings.

    Attributes:
        named_state: Named robot state or preset.
        rt: Real-time mode flag.
        space: Goal space type.
        interface_type: Interface type string.
        target: Target frame or component identifier.
        enable_camera: Whether camera sensing is enabled.
    """
    named_state: Optional[str] = None
    rt: Optional[bool] = None
    space: Optional[GoalSpace] = GoalSpace.TS
    interface_type: Optional[InterfaceType] = InterfaceType.POSITION
    target: Optional[str] = None
    enable_camera: Optional[bool] = None
    
    model_config = {
        "use_enum_values": True
    }


@dataclass
class JointStateObject():
    """Lightweight representation of a single joint's state.

    Attributes:
        position: Joint position value.
        velocity: Joint velocity value.
        effort: Joint effort value.
    """
    position: float
    velocity: float
    effort: float


@dataclass
class TransformObject():
    """Lightweight representation of a transform with parent/child frame metadata.

    Attributes:
        parent: Parent frame name.
        child: Child frame name.
        position: Translation component as Vector3.
        orientation: Orientation as Quaternion.
        transform_matrix: 4x4 transform matrix.
    """
    parent: str
    child: str
    position: Vector3
    orientation: Quaternion
    transform_matrix: NDArray[np.float64] 


@dataclass
class FeedbackObject():
    """Lightweight feedback object combining joint states, transforms, and status.

    Attributes:
        joint_states: Mapping of joint names to JointStateObject instances.
        transforms: TransformObject containing frame metadata.
        status: Numeric status code.
    """
    joint_states: dict[str, JointStateObject]
    transforms: list[TransformObject]
    status: MoveStatus

    model_config = {
        "use_enum_values": True
    }

    def lookup_transform(self, parent_frame, child_frame):
        # child -> (parent, transform)
        graph = {
            tf.child: tf
            for tf in self.transforms
        }

        current = child_frame
        result = np.eye(4)

        while current != parent_frame:
            tf = graph.get(current)

            if tf is None:
                return None  # no path

            # accumulate child -> parent transforms
            result = tf.transform_matrix @ result
            current = tf.parent

        return result
    