import numpy as np
from numpy.typing import NDArray
import json as js
from typing import List
import msgpack
import cv2
from cv2.typing import MatLike
from pydantic import BaseModel
from typing import TypeVar, Type

T = TypeVar("T", bound=BaseModel)


def image_to_bytes(
    image: ImageMessage
) -> bytes:
    """
    Encode image to MessagePack bytes.

    :param image: numpy array (H x W x C or H x W)
    :param encoding: 'jpeg' or 'png'
    :param quality: JPEG quality (1–100)
    """
    if image.encoding == "jpeg":
        params = [cv2.IMWRITE_JPEG_QUALITY, image.quality]
        ext = ".jpg"
    elif image.encoding == "png":
        params = []
        ext = ".png"
    else:
        raise ValueError("Unsupported image encoding")

    success, buffer = cv2.imencode(ext, image, params)
    if not success:
        raise RuntimeError("Image encoding failed")

    payload = {
        "encoding": image.encoding,
        "shape": image.shape,
        "dtype": str(image.dtype),
        "data": buffer.tobytes(),
    }

    return msgpack.packb(payload, use_bin_type=True)


def bytes_to_image(byte_data: bytes) -> MatLike:
    """
    Decode MessagePack image bytes into numpy array.
    """
    payload = msgpack.unpackb(byte_data, raw=False)
    buffer = np.frombuffer(payload["data"], dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED)

    if image is None:
        raise RuntimeError("Image decoding failed")

    return image


def encode(message) -> bytes:
    """
    Converts pydantic model messages to bytes.
    """
    message_data = message.model_dump_json()
    return message_data.encode("utf-8")


def decode(raw_json_message: bytes, model: Type[T]) -> T:
    """
    Converts raw json bytes into pydantic models.
    """
    json = raw_json_message.decode("utf-8")
    return model.model_validate_json(json)
