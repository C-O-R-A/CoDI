"""Utility routines for encoding and decoding CoDI message payloads.

This module provides helpers for serializing image payloads to MessagePack,
converting raw JSON messages into Pydantic models, and decoding binary image
payloads for use with OpenCV.
"""

from pydantic import BaseModel
from typing import TypeVar, Type

from codi.messages import ImageMessage

T = TypeVar("T", bound=BaseModel)


def encode(message: Type[T]) -> bytes:
    """Encode a Pydantic model into UTF-8 JSON bytes. \n
    model -> json -> bytes

    Args:
        message: A Pydantic model instance.

    Returns:
        UTF-8 encoded JSON bytes.
    """
    message_data = message.model_dump_json()
    return message_data.encode("utf-8")


def decode(raw: bytes, model: Type[T]) -> T:
    """Decode UTF-8 JSON bytes into a Pydantic model instance. \n
    bytes -> json -> model

    Args:
        raw: JSON encoded as bytes.
        model: The Pydantic model type to validate against.

    Returns:
        Validated Pydantic model instance.
    """
    json = raw.decode("utf-8")
    return model.model_validate_json(json)
